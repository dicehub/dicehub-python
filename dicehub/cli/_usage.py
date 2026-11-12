"""Usage diagnostics built only from registered metadata and fixed text."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from difflib import get_close_matches
from functools import wraps
from typing import IO, Any, Concatenate, ParamSpec, TypeVar

import typer
from typer._click.core import Command, Context, Parameter
from typer._click.exceptions import (
    BadArgumentUsage,
    BadOptionUsage,
    BadParameter,
    MissingParameter,
    NoArgsIsHelpError,
    NoSuchOption,
    UsageError,
)
from typer._click.types import BoolParamType, FloatParamType, FloatRange, IntParamType, IntRange
from typer._types import TyperChoice
from typer.core import TyperArgument, TyperCommand, TyperGroup, TyperOption
from typer.models import TyperPath

from dicehub.cli.output import OutputFormat, write_error
from dicehub.errors import DiceHubError

_OUTPUT_KEY = "dicehub.usage_output"
_Command = TypeVar("_Command", bound=Command)
_Params = ParamSpec("_Params")
_Result = TypeVar("_Result")


class _UsageFailure(DiceHubError):
    code = "USAGE_ERROR"
    exit_code = 2


class SafeUsageError(UsageError):
    """Carry only a safe cause; leave Typer's exit handling intact."""

    def __init__(self, cause: str, ctx: Context) -> None:
        super().__init__(cause, ctx)
        self.help_line = f"Run '{_command_path(ctx)} --help' for help."
        self.output = ctx.meta.get(_OUTPUT_KEY, OutputFormat.TEXT)

    def show(self, file: IO[Any] | None = None) -> None:
        if self.output is OutputFormat.JSON:
            write_error(_UsageFailure(f"{self.message}\n{self.help_line}"), OutputFormat.JSON)
        else:
            typer.echo(f"Error: {self.message}\n{self.help_line}", file=file, err=True)


def _command_path(ctx: Context) -> str:
    # info_name and command_path may include caller-supplied program names or arguments.
    names: list[str] = []
    while ctx.parent is not None:
        parent = ctx.parent.command
        if not isinstance(parent, TyperGroup):
            break
        name = next(
            (name for name, command in parent.commands.items() if command is ctx.command), None
        )
        if name is None:
            break
        names.append(name)
        ctx = ctx.parent
    return " ".join(("dicehub", *reversed(names)))


def usage_output(command: Command, args: Sequence[str]) -> OutputFormat:
    """Find an explicit output flag even if parsing fails before it is reached."""
    output = OutputFormat.TEXT
    index = 0
    while index < len(args):
        word = args[index]
        index += 1
        if word == "--":
            break
        name, separator, value = word.partition("=")
        if name == "--output":
            if not separator and index < len(args):
                value = args[index]
                index += 1
            output = OutputFormat.JSON if value.casefold() == "json" else OutputFormat.TEXT
            continue
        # A flag-shaped option value is data, not a request for JSON.
        option = next(
            (
                param
                for param in command.params
                if isinstance(param, TyperOption) and name in (*param.opts, *param.secondary_opts)
            ),
            None,
        )
        if option is not None:
            if not option.is_flag and not option.count:
                index += max(0, option.nargs - bool(separator))
            continue
        if isinstance(command, TyperGroup):
            if word == "ls" and "list" in command.commands:
                word = "list"
            command = command.commands.get(word, command)
    return output


def _suggestion(word: str, names: Sequence[str]) -> str:
    matches = get_close_matches(word, names)
    if not matches:
        return ""
    return " Did you mean " + ", ".join(repr(name) for name in matches) + "?"


def unknown_command(ctx: Context, word: str) -> SafeUsageError:
    group = ctx.command
    names = list(group.commands) if isinstance(group, TyperGroup) and group.suggest_commands else []
    return SafeUsageError("Unknown command." + _suggestion(word, names), ctx)


def _parameter_label(param: Parameter, ctx: Context) -> str:
    if isinstance(param, TyperOption):
        return repr(param.opts[0])
    # Identify positional parameters by position, without printing identifier names.
    arguments = [item for item in ctx.command.params if isinstance(item, TyperArgument)]
    return f"argument {arguments.index(param) + 1}" if param in arguments else "argument"


def _expected(param: Parameter) -> str:
    kind = param.type
    if isinstance(kind, TyperChoice):
        choices = [kind.normalize_choice(choice, ctx=None) for choice in kind.choices]
        return "one of " + "|".join(choices) if len(choices) <= 8 else "a choice listed in help"
    if isinstance(kind, (IntRange, FloatRange)):
        number = "an integer" if isinstance(kind, IntRange) else "a number"
        if (
            kind.min is not None
            and kind.max is not None
            and not kind.min_open
            and not kind.max_open
        ):
            return f"{number} from {kind.min} to {kind.max}"
        bounds = []
        if kind.min is not None:
            bounds.append(f"{'greater than' if kind.min_open else 'at least'} {kind.min}")
        if kind.max is not None:
            bounds.append(f"{'less than' if kind.max_open else 'at most'} {kind.max}")
        return " ".join((number, " and ".join(bounds))).rstrip()
    if isinstance(kind, IntParamType):
        return "an integer"
    if isinstance(kind, FloatParamType):
        return "a number"
    if isinstance(kind, BoolParamType):
        return "true or false"
    if isinstance(kind, TyperPath):
        parts = ["an existing" if kind.exists else "a"]
        if kind.readable:
            parts.append("readable")
        if kind.writable:
            parts.append("writable")
        parts.append("file" if not kind.dir_okay else "directory" if not kind.file_okay else "path")
        return " ".join(parts)
    return "a valid value"


def _cause(error: UsageError, ctx: Context) -> str:
    params = ctx.command.get_params(ctx)
    options = {
        name: param
        for param in params
        if isinstance(param, TyperOption)
        for name in (*param.opts, *param.secondary_opts)
    }
    if isinstance(error, NoSuchOption):
        return "Unknown option." + _suggestion(error.option_name, list(options))
    if isinstance(error, BadParameter):
        param = error.param
        # Never use param_hint, get_error_hint, or a parameter not registered on this command.
        if param is None or param not in params:
            return (
                "Missing required parameter."
                if isinstance(error, MissingParameter)
                else "Invalid value."
            )
        label = _parameter_label(param, ctx)
        if isinstance(error, MissingParameter):
            prefix = "option " if isinstance(param, TyperOption) else ""
            return f"Missing required {prefix}{label}."
        return f"Invalid value for {label}. Expected {_expected(param)}."
    if isinstance(error, BadOptionUsage):
        option = options.get(error.option_name)
        if option is None:
            return "Invalid option usage."
        label = _parameter_label(option, ctx)
        # Click has no structured reason here. Compare known templates; never render its message.
        if error.message in (
            f"Option {error.option_name!r} requires an argument.",
            f"Option {error.option_name!r} requires {option.nargs} arguments.",
        ):
            return f"Missing value for {label}. Expected {_expected(option)}."
        if error.message == f"Option {error.option_name!r} does not take a value.":
            return f"Option {label} does not take a value."
        return f"Invalid use of option {label}."
    if isinstance(error, BadArgumentUsage):
        return "Incorrect number of argument values."
    if error.message.startswith("Got unexpected extra argument(s) ("):
        return "Unexpected argument."
    if error.message == "Missing command.":
        return "Missing command."
    return "Invalid command usage."


def usage_errors(
    method: Callable[Concatenate[_Command, Context, _Params], _Result],
) -> Callable[Concatenate[_Command, Context, _Params], _Result]:
    @wraps(method)
    def guarded(
        self: _Command, ctx: Context, /, *args: _Params.args, **kwargs: _Params.kwargs
    ) -> _Result:
        try:
            return method(self, ctx, *args, **kwargs)
        except (NoArgsIsHelpError, SafeUsageError):
            raise
        except UsageError as error:
            context = error.ctx if error.ctx is not None else ctx
            safe_error = SafeUsageError(_cause(error, context), context)
        # Raise outside the handler so a secret-bearing Click error is not retained as context.
        raise safe_error

    return guarded


class UsageCommand(TyperCommand):
    @usage_errors
    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        return super().parse_args(ctx, args)

    @usage_errors
    def invoke(self, ctx: Context) -> Any:
        return super().invoke(ctx)
