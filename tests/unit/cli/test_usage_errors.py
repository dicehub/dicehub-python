from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, NoReturn

import httpx
import pytest
import typer
from typer._click.core import Context, Parameter
from typer._click.exceptions import (
    BadArgumentUsage,
    BadOptionUsage,
    BadParameter,
    NoSuchOption,
    UsageError,
)
from typer.core import TyperCommand, TyperGroup
from typer.testing import CliRunner, Result

from dicehub.cli._help import HelpGroup
from dicehub.cli._usage import UsageCommand
from dicehub.cli.app import app
from dicehub.client import Client

runner = CliRunner()
SENTINEL = "SENTINEL-not-a-secret-42"
CONTROL = "SENTINEL-\n\r\t\x1b[31m\x07"
OPTION = "--sentinel-opt-77"
FORMATS: tuple[list[str], ...] = ([], ["--output", "text"], ["--output", "json"], ["--output=json"])


@pytest.fixture(autouse=True)
def forbid_clients(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    attempts: list[bool] = []

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        attempts.append(True)
        raise AssertionError("Usage errors must not construct clients.")

    monkeypatch.setattr(Client, "__init__", forbidden)
    monkeypatch.setattr(httpx.Client, "__init__", forbidden)
    yield
    assert attempts == []


def _assert_error(result: Result, cause: str, path: str, *, json_output: bool) -> None:
    assert result.exit_code == 2, result.output
    help_line = f"Run '{path} --help' for help."
    if json_output:
        assert result.stderr == ""
        assert result.stdout.count("\n") == 1
        assert json.loads(result.stdout) == {
            "schema_version": "dicehub.cli/v1",
            "ok": False,
            "data": None,
            "error": {
                "code": "USAGE_ERROR",
                "message": f"{cause}\n{help_line}",
                "retryable": False,
            },
        }
    else:
        assert result.stdout == ""
        assert result.stderr == f"Error: {cause}\n{help_line}\n"
        assert len(result.stderr.splitlines()) == 2
    combined = result.stdout + result.stderr
    error = result.exception
    while error is not None:
        combined += repr(error)
        error = error.__cause__ or error.__context__
    assert "SENTINEL" not in combined
    assert OPTION not in combined
    assert "\x1b" not in combined


@pytest.mark.parametrize("output", FORMATS)
@pytest.mark.parametrize(
    ("arguments", "cause", "path"),
    [
        ([SENTINEL], "Unknown command.", "dicehub"),
        ([CONTROL], "Unknown command.", "dicehub"),
        (["projec"], "Unknown command. Did you mean 'project'?", "dicehub"),
        (["project", SENTINEL], "Unknown command.", "dicehub project"),
        (["project", "members", CONTROL], "Unknown command.", "dicehub project members"),
        ([OPTION, SENTINEL], "Unknown option.", "dicehub"),
        (["project", OPTION, SENTINEL], "Unknown option.", "dicehub project"),
        (["project", "list", OPTION, CONTROL], "Unknown option.", "dicehub project list"),
        (["project", "list", f"{OPTION}={SENTINEL}"], "Unknown option.", "dicehub project list"),
        (["project", "list", "--" + CONTROL], "Unknown option.", "dicehub project list"),
        (
            ["project", "list", "--limt", SENTINEL],
            "Unknown option. Did you mean '--limit'?",
            "dicehub project list",
        ),
        (["project", "list", "-" + SENTINEL], "Unknown option.", "dicehub project list"),
        (
            ["project", "list", "--limit", SENTINEL],
            "Invalid value for '--limit'. Expected an integer from 1 to 50.",
            "dicehub project list",
        ),
        (
            ["project", "list", "--limit", CONTROL],
            "Invalid value for '--limit'. Expected an integer from 1 to 50.",
            "dicehub project list",
        ),
        (
            ["project", "list", "--limit", "98172931"],
            "Invalid value for '--limit'. Expected an integer from 1 to 50.",
            "dicehub project list",
        ),
        (
            ["project", "list", "--offset", SENTINEL],
            "Invalid value for '--offset'. Expected an integer at least 0.",
            "dicehub project list",
        ),
        (
            ["project", "list", "--order", CONTROL],
            "Invalid value for '--order'. Expected one of asc|desc.",
            "dicehub project list",
        ),
        (
            ["run", "wait", SENTINEL, "--timeout", CONTROL],
            "Invalid value for '--timeout'. Expected a number.",
            "dicehub run wait",
        ),
        (
            ["group", "avatar", "set", SENTINEL, CONTROL],
            "Invalid value for argument 2. Expected an existing readable file.",
            "dicehub group avatar set",
        ),
        (["project", "get"], "Missing required argument 1.", "dicehub project get"),
        (["project", "move", SENTINEL], "Missing required argument 2.", "dicehub project move"),
        (
            ["project", "create", "--slug", SENTINEL],
            "Missing required option '--name'.",
            "dicehub project create",
        ),
        (["project", "list", CONTROL], "Unexpected argument.", "dicehub project list"),
        (["project", "get", SENTINEL, CONTROL], "Unexpected argument.", "dicehub project get"),
        (["help", SENTINEL], "Unknown command.", "dicehub"),
        (["help", "projec"], "Unknown command. Did you mean 'project'?", "dicehub"),
        (["help", "project", CONTROL], "Unknown command.", "dicehub project"),
        (["help", "project", "get", SENTINEL], "Unknown command.", "dicehub project get"),
        (["help", "config", "content", CONTROL], "Unknown command.", "dicehub config content"),
        (["help", OPTION], "Unknown command.", "dicehub"),
        (["project", "ls", OPTION], "Unknown option.", "dicehub project list"),
        (["help", "project", "ls", SENTINEL], "Unknown command.", "dicehub project list"),
        (
            ["run", "list", SENTINEL, "--type", CONTROL],
            "Invalid value for '--type'. Expected one of regular|extra|micro|prediction.",
            "dicehub run list",
        ),
        (
            ["project", "delete", SENTINEL, "--yes=" + CONTROL],
            "Option '--yes' does not take a value.",
            "dicehub project delete",
        ),
    ],
)
def test_usage_errors(arguments: list[str], cause: str, path: str, output: list[str]) -> None:
    result = runner.invoke(app, [*arguments, *output], prog_name=SENTINEL)
    _assert_error(result, cause, path, json_output=output in FORMATS[2:])


@pytest.mark.parametrize(
    ("group", "tail", "cause"),
    [
        ([], ["--", "--"], "Unknown command."),
        (["project"], ["--", "--"], "Unknown command."),
        (["project"], ["--"], "Missing command."),
    ],
)
def test_end_of_options_marker_as_command(group: list[str], tail: list[str], cause: str) -> None:
    # Groups have no --output option, and tokens after '--' are data, so only text applies.
    result = runner.invoke(app, [*group, *tail], prog_name=SENTINEL)
    _assert_error(result, cause, " ".join(("dicehub", *group)), json_output=False)


@pytest.mark.parametrize("output", FORMATS)
def test_missing_option_value(output: list[str]) -> None:
    result = runner.invoke(
        app,
        ["project", "list", "--search", CONTROL, *output, "--limit"],
        prog_name=SENTINEL,
    )
    _assert_error(
        result,
        "Missing value for '--limit'. Expected an integer from 1 to 50.",
        "dicehub project list",
        json_output=output in FORMATS[2:],
    )


@pytest.mark.parametrize("value", [SENTINEL, CONTROL])
def test_invalid_output_value(value: str) -> None:
    result = runner.invoke(app, ["project", "list", "--output", value])
    _assert_error(
        result,
        "Invalid value for '--output'. Expected one of json|text.",
        "dicehub project list",
        json_output=False,
    )


@pytest.mark.parametrize(
    ("arguments", "json_output"),
    [
        (["--output=json", SENTINEL], True),
        (["--output", "json", SENTINEL], True),
        ([SENTINEL, "--output", "JSON"], True),
        ([SENTINEL, "--output=json", "--output=text"], False),
        ([SENTINEL, "--", "--output=json"], False),
        ([SENTINEL, "--output=json" + CONTROL], False),
        ([SENTINEL, "--output-extra=json"], False),
        ([SENTINEL, "--output json"], False),
    ],
)
def test_output_detection_before_parsing(arguments: list[str], json_output: bool) -> None:
    cause = "Unknown option." if arguments[0].startswith("--output") else "Unknown command."
    _assert_error(runner.invoke(app, arguments), cause, "dicehub", json_output=json_output)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--search", "--output=json", OPTION],
        ["--search=--output=json", OPTION],
        ["--search", "--output", "json", OPTION],
        ["--", SENTINEL, "--output=json"],
    ],
)
def test_option_values_and_positional_tail_do_not_select_json(arguments: list[str]) -> None:
    cause = "Unexpected argument." if arguments[0] == "--" else "Unknown option."
    _assert_error(
        runner.invoke(app, ["project", "list", *arguments]),
        cause,
        "dicehub project list",
        json_output=False,
    )


def test_root_option_reparse_preserves_end_of_options() -> None:
    _assert_error(
        runner.invoke(app, ["--", "--output=json", SENTINEL]),
        "Unknown option.",
        "dicehub",
        json_output=False,
    )


@pytest.mark.parametrize(
    "arguments", [[], ["project"], ["project", "members"], ["config", "content"]]
)
def test_no_args_is_help_is_unchanged(arguments: list[str]) -> None:
    help_result = runner.invoke(app, [*arguments, "--help"], prog_name="dicehub")
    result = runner.invoke(app, arguments, prog_name="dicehub")
    assert help_result.exit_code == 0
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == help_result.stdout


def _foreign_option(ctx: Context) -> Parameter:
    group = ctx.parent.command if ctx.parent is not None else None
    assert isinstance(group, TyperGroup)
    option = next(param for param in group.commands["create"].params if param.name == "name")
    assert option not in ctx.command.params
    return option


@pytest.mark.parametrize("output", FORMATS)
@pytest.mark.parametrize(
    ("error_factory", "cause"),
    [
        (
            lambda ctx: BadOptionUsage("--limit", "Repeated option: " + CONTROL),
            "Invalid use of option '--limit'.",
        ),
        (lambda ctx: BadOptionUsage(OPTION, CONTROL), "Invalid option usage."),
        (lambda ctx: BadArgumentUsage(CONTROL), "Incorrect number of argument values."),
        (lambda ctx: UsageError(CONTROL), "Invalid command usage."),
        (lambda ctx: BadParameter(CONTROL, param_hint=CONTROL), "Invalid value."),
        (
            # A parameter of another command is not registered on this one.
            lambda ctx: BadParameter(CONTROL, param=_foreign_option(ctx)),
            "Invalid value.",
        ),
        (
            lambda ctx: NoSuchOption("--limt", possibilities=[CONTROL, OPTION]),
            "Unknown option. Did you mean '--limit'?",
        ),
        (
            lambda ctx: BadParameter(
                CONTROL,
                param=next(param for param in ctx.command.params if param.name == "limit"),
                param_hint=CONTROL,
            ),
            "Invalid value for '--limit'. Expected an integer from 1 to 50.",
        ),
    ],
)
def test_unstructured_errors_never_supply_message_text(
    monkeypatch: pytest.MonkeyPatch,
    error_factory: Callable[[Context], UsageError],
    cause: str,
    output: list[str],
) -> None:
    # Exercise error forms that the current parser does not produce itself (including duplicates).
    def fail_parse(self: TyperCommand, ctx: Context, args: list[str]) -> NoReturn:
        raise error_factory(ctx)

    monkeypatch.setattr(TyperCommand, "parse_args", fail_parse)
    _assert_error(
        runner.invoke(app, ["project", "list", *output, SENTINEL]),
        cause,
        "dicehub project list",
        json_output=output in FORMATS[2:],
    )


@pytest.fixture
def parser_app() -> typer.Typer:
    local = typer.Typer(cls=HelpGroup, rich_markup_mode=None, pretty_exceptions_enable=False)

    @local.callback()
    def root() -> None:
        pass

    @local.command("check", cls=UsageCommand)
    def check(
        source: Annotated[
            Path | None, typer.Option("--source", exists=True, dir_okay=False, readable=True)
        ] = None,
        count: Annotated[int, typer.Option("--count")] = 1,
        pair: Annotated[tuple[int, int], typer.Option("--pair")] = (1, 2),
        output: str = "text",
    ) -> None:
        typer.echo(count)

    return local


@pytest.mark.parametrize("output", FORMATS)
def test_invalid_path_option(parser_app: typer.Typer, output: list[str]) -> None:
    _assert_error(
        runner.invoke(parser_app, ["check", "--source", CONTROL, *output]),
        "Invalid value for '--source'. Expected an existing readable file.",
        "dicehub check",
        json_output=output in FORMATS[2:],
    )


@pytest.mark.parametrize("output", FORMATS)
def test_missing_multiple_option_values(parser_app: typer.Typer, output: list[str]) -> None:
    _assert_error(
        runner.invoke(parser_app, ["check", *output, "--pair", SENTINEL]),
        "Missing value for '--pair'. Expected a valid value.",
        "dicehub check",
        json_output=output in FORMATS[2:],
    )


def test_repeated_single_value_options_keep_click_behavior(parser_app: typer.Typer) -> None:
    result = runner.invoke(parser_app, ["check", "--count", "3", "--count", "7"])
    assert result.exit_code == 0
    assert result.stdout == "7\n"
    assert result.stderr == ""
