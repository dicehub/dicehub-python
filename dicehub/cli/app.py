from __future__ import annotations

import typer

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
)
app.add_typer(auth_app, name="auth")
app.add_typer(api_key_app, name="api-key")
app.add_typer(app_app, name="app")
app.add_typer(config_app, name="config")
app.add_typer(group_app, name="group")
app.add_typer(project_app, name="project")
app.add_typer(resource_app, name="resource")
app.add_typer(run_app, name="run")
app.add_typer(template_app, name="template")


def main() -> None:
    app()
