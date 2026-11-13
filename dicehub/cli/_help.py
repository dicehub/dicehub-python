"""Static help text and command-path aliases for the CLI."""

from __future__ import annotations

from contextlib import ExitStack

import typer
from typer._click.core import Command, Context
from typer.core import TyperGroup

from dicehub._core.defaults import DEFAULT_BASE_URL, DEFAULT_SESSION_BASE_URL
from dicehub.cli._examples import EXAMPLES

_ENVIRONMENT = (
    "\b\nEnvironment:\n"
    "  DICEHUB_API_KEY: API key for most commands. Do not set with DICEHUB_SESSION_COOKIE.\n"
    "  DICEHUB_SESSION_COOKIE: session cookie for session commands. "
    "Do not set with DICEHUB_API_KEY.\n"
    f"  DICEHUB_URL: server origin. Default: {DEFAULT_BASE_URL}; with a cookie, "
    f"{DEFAULT_SESSION_BASE_URL}."
)
_ROOT_HINT = "\b\nRun 'dicehub help <command>' for command help. 'ls' is an alias of 'list'."


class HelpGroup(TyperGroup):
    """Resolve aliases without adding commands to the visible command tree."""

    def resolve_command(
        self, ctx: Context, args: list[str]
    ) -> tuple[str | None, Command | None, list[str]]:
        if args and args[0] == "ls" and "list" in self.commands:
            args = ["list", *args[1:]]
        return super().resolve_command(ctx, args)

    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        if ctx.parent is None and args[:1] == ["help"] and not ctx.resilient_parsing:
            self._show_help_path(ctx, args[1:])
            ctx.exit()
        return super().parse_args(ctx, args)

    @staticmethod
    def _show_help_path(ctx: Context, path: list[str]) -> None:
        with ExitStack() as stack:
            for word in path:
                group = ctx.command
                if not isinstance(group, TyperGroup) or word.startswith("-"):
                    ctx.fail(f"No such command {word!r}.")
                name, command, _ = group.resolve_command(ctx, [word])
                assert command is not None
                # Build contexts without parsing required parameters or running callbacks.
                ctx = stack.enter_context(
                    command.context_class(command, info_name=name, parent=ctx)
                )
            typer.echo(ctx.get_help())


def configure_help(app: typer.Typer, path: tuple[str, ...] = ()) -> None:
    """Apply shared help once, after all command groups have been registered."""

    app.info.cls = HelpGroup
    if not path:
        app.info.epilog = f"{_ROOT_HINT}\n\n{_ENVIRONMENT}"
    for command in app.registered_commands:
        assert command.name is not None
        examples = EXAMPLES[(*path, command.name)]
        # Click's backspace marker preserves each row instead of wrapping the paragraph.
        rows = "\n".join(f"  {example}" for example in examples)
        command.epilog = f"{_ENVIRONMENT}\n\n\b\nExamples:\n{rows}"
    for group in app.registered_groups:
        assert group.typer_instance is not None and group.name is not None
        configure_help(group.typer_instance, (*path, group.name))
