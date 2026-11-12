from __future__ import annotations

from typing import Annotated

import typer

from dicehub._version import __version__
from dicehub.cli._help import configure_help
from dicehub.cli.commands.api_key import api_key_app
from dicehub.cli.commands.app import app_app
from dicehub.cli.commands.auth import auth_app
from dicehub.cli.commands.config import config_app
from dicehub.cli.commands.group import group_app
from dicehub.cli.commands.project import project_app
from dicehub.cli.commands.resource import resource_app
from dicehub.cli.commands.run import run_app
from dicehub.cli.commands.template import template_app

app = typer.Typer(
    name="dicehub",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
    help="Manage dicehub projects, apps, and simulations.",
)
app.add_typer(auth_app, name="auth", help="Check authentication and identity.")
app.add_typer(api_key_app, name="api-key", help="Manage API keys and permissions.")
app.add_typer(app_app, name="app", help="Manage apps and their members.")
app.add_typer(config_app, name="config", help="Manage configurations and their content.")
app.add_typer(group_app, name="group", help="Manage groups and their members.")
app.add_typer(project_app, name="project", help="Manage projects and their members.")
app.add_typer(resource_app, name="resource", help="Manage resources and transfer files.")
app.add_typer(run_app, name="run", help="Start, inspect, and stop runs.")
app.add_typer(template_app, name="template", help="Find templates for new apps.")


def _show_version(ctx: typer.Context, value: bool) -> None:
    if value and not ctx.resilient_parsing:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Show the package version and exit.",
        ),
    ] = False,
) -> None:
    pass


configure_help(app)


def main() -> None:
    app()
