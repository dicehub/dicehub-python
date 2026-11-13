from __future__ import annotations

import importlib
import json
import os
import re
import shlex
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn, cast

import httpx
import pytest
from typer._click.core import Command
from typer.core import TyperGroup, TyperOption
from typer.main import get_command
from typer.testing import CliRunner

import dicehub
from dicehub.cli._examples import EXAMPLES
from dicehub.cli.app import app
from dicehub.client import Client

runner = CliRunner()


def _walk(
    command: Command, path: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], Command]]:
    yield path, command
    if isinstance(command, TyperGroup):
        for name, child in command.commands.items():
            yield from _walk(child, (*path, name))


_TREE = tuple(_walk(get_command(app)))
_PATHS = tuple(path for path, _ in _TREE)
_LEAVES = tuple(path for path, command in _TREE if not isinstance(command, TyperGroup))
_GROUPS = tuple((path, command) for path, command in _TREE if isinstance(command, TyperGroup))
_LIST_GROUPS = tuple(path for path, group in _GROUPS if "list" in group.commands)
_ENVIRONMENT_NAMES = ("DICEHUB_API_KEY", "DICEHUB_SESSION_COOKIE", "DICEHUB_URL")


@pytest.fixture(autouse=True)
def forbid_client_and_environment_reads(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    attempts: list[str] = []
    original_getitem = type(os.environ).__getitem__

    def guarded_getitem(environment: os._Environ[str], name: str) -> str:
        if name in _ENVIRONMENT_NAMES:
            attempts.append(name)
            raise AssertionError("Static CLI pages must not read credentials or the origin.")
        return original_getitem(environment, name)

    def forbidden_client(*args: object, **kwargs: object) -> NoReturn:
        attempts.append("client")
        raise AssertionError("Static CLI pages must not construct a client.")

    monkeypatch.setattr(type(os.environ), "__getitem__", guarded_getitem)
    monkeypatch.setattr(Client, "__init__", forbidden_client)
    monkeypatch.setattr(httpx.Client, "__init__", forbidden_client)
    yield
    assert attempts == []


def _help(path: tuple[str, ...], *, width: int = 80) -> str:
    result = runner.invoke(app, [*path, "--help"], prog_name="dicehub", terminal_width=width)
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert "\x1b" not in result.stdout
    return result.stdout


def _assert_environment(page: str) -> None:
    assert page.count("Environment:") == 1
    block = page.split("Environment:\n", 1)[1].split("\n\n", 1)[0]
    rows = [line.strip() for line in block.splitlines()]
    assert len(rows) == 3
    assert all(
        row.startswith(name + ":") for name, row in zip(_ENVIRONMENT_NAMES, rows, strict=True)
    )
    assert "Do not set with DICEHUB_SESSION_COOKIE" in rows[0]
    assert "Do not set with DICEHUB_API_KEY" in rows[1]
    # The session default origin differs from the API-key default.
    assert "https://dicehub.com" in rows[2] and "http://127.0.0.1:8080" in rows[2]
    assert all(len(line) <= 100 for line in block.splitlines())


def test_group_descriptions_and_root_help() -> None:
    assert set(EXAMPLES) == set(_LEAVES)
    assert app.pretty_exceptions_enable is False
    for path, group in _GROUPS:
        assert group.rich_markup_mode is None
        assert group.help and len(group.help.splitlines()) == 1, path
        page = _help(path)
        command_rows = page.split("Commands:\n", 1)[1].split("\n\n", 1)[0].splitlines()
        names = {line.split()[0] for line in command_rows}
        assert "help" not in names and "ls" not in names
        for name, child in group.commands.items():
            if isinstance(child, TyperGroup):
                row = next(line for line in command_rows if line.split()[0] == name)
                assert row.strip().split(maxsplit=1)[1] == child.help
    root_page = _help(())
    _assert_environment(root_page)
    assert "Run 'dicehub help <command>' for command help. 'ls' is an alias of 'list'." in root_page


def _parse_example(line: str) -> dict[str, object]:
    words = shlex.split(line)
    assert words.pop(0) == "dicehub"
    command = get_command(app)
    parent = None
    name = "dicehub"
    with ExitStack() as stack:
        while True:
            context = stack.enter_context(
                command.make_context(name, words.copy(), parent=parent, resilient_parsing=False)
            )
            if not isinstance(command, TyperGroup):
                assert context.args == []
                return context.params
            next_name, child, words = command.resolve_command(context, words)
            assert next_name is not None and child is not None
            command, name, parent = child, next_name, context


@pytest.mark.parametrize("path", _LEAVES, ids=lambda path: " ".join(path))
def test_leaf_examples_and_environment(
    path: tuple[str, ...], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The avatar source has exists=True. Supply that local prerequisite without running a command.
    (tmp_path / "avatar.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.chdir(tmp_path)
    page = _help(path)
    _assert_environment(page)
    assert page.count("Examples:") == 1
    rows = [line.strip() for line in page.split("Examples:\n", 1)[1].splitlines()]
    assert tuple(rows) == EXAMPLES[path]
    assert 1 <= len(rows) <= 3
    prefix = "dicehub " + " ".join(path)
    assert rows[0] == prefix or rows[0].startswith(prefix + " ")
    for row in rows:
        assert row.startswith("dicehub ") and len(row) <= 100
        _parse_example(row)


def test_examples_contain_no_credentials_or_other_origins() -> None:
    credential = re.compile(r"key|cookie|token|password|secret|\bsk-|\beyJ", re.IGNORECASE)
    for path, rows in EXAMPLES.items():
        for row in rows:
            # The command name api-key and the descriptor option are not secret values.
            arguments = shlex.split(row)[len(path) + 1 :]
            for argument in arguments:
                if argument != "--secret-fd":
                    assert not credential.search(argument), row
            urls = re.findall(r"https?://\S+", row)
            assert all(url == "https://dicehub.com" for url in urls)


@pytest.mark.parametrize("width", [40, 120])
def test_example_rows_do_not_wrap(width: int) -> None:
    for path in (("group", "members", "add"), ("run", "watch"), ("project", "list")):
        page = _help(path, width=width)
        _assert_environment(page)
        rows = tuple(line.strip() for line in page.split("Examples:\n", 1)[1].splitlines())
        assert rows == EXAMPLES[path]


@pytest.mark.parametrize("path", _PATHS, ids=lambda path: " ".join(path) or "root")
def test_help_command_matches_flag(path: tuple[str, ...]) -> None:
    expected = _help(path)
    result = runner.invoke(app, ["help", *path], prog_name="dicehub")
    assert result.exit_code == 0
    assert result.stdout == expected
    assert result.stderr == ""


@pytest.mark.parametrize("path", _LIST_GROUPS, ids=lambda path: " ".join(path))
def test_ls_help_matches_list(path: tuple[str, ...]) -> None:
    expected = _help((*path, "list"))
    for arguments in ([*path, "ls", "--help"], ["help", *path, "ls"]):
        result = runner.invoke(app, arguments, prog_name="dicehub")
        assert result.exit_code == 0
        assert result.stdout == expected
        assert result.stderr == ""


@pytest.mark.parametrize("path", _LIST_GROUPS, ids=lambda path: " ".join(path))
def test_ls_execution_matches_list(path: tuple[str, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def list_records(**kwargs: object) -> object:
        calls.append(kwargs)
        if path[0] == "api-key":
            return ()
        return SimpleNamespace(
            apps=(),
            configs=(),
            entries=(),
            groups=(),
            projects=(),
            resources=(),
            runs=(),
            templates=(),
            offset=0,
            count=0,
            cursor=None,
        )

    service = SimpleNamespace(list=list_records, list_content=list_records)
    domain = "api_keys" if path[0] == "api-key" else path[0] + "s"
    client = cast(Client, SimpleNamespace(**{domain: service}))

    def run_fake(action: Callable[[Client], object], output: object, **kwargs: object) -> object:
        return action(client)

    module = importlib.import_module("dicehub.cli.commands." + path[0].replace("-", "_"))
    monkeypatch.setattr(module, "_run", run_fake)
    arguments = shlex.split(EXAMPLES[(*path, "list")][0])[len(path) + 2 :]
    listed = runner.invoke(app, [*path, "list", *arguments], prog_name="dicehub")
    aliased = runner.invoke(app, [*path, "ls", *arguments], prog_name="dicehub")
    assert listed.exit_code == aliased.exit_code == 0
    assert listed.stdout == aliased.stdout
    assert listed.stderr == aliased.stderr == ""
    assert len(calls) == 2 and calls[0] == calls[1]
    assert json.loads(aliased.stdout)["schema_version"] == "dicehub.cli/v1"

    listed_error = runner.invoke(app, [*path, "list", "--invalid"], prog_name="dicehub")
    aliased_error = runner.invoke(app, [*path, "ls", "--invalid"], prog_name="dicehub")
    assert listed_error.exit_code == aliased_error.exit_code == 2
    assert listed_error.stdout == aliased_error.stdout == ""
    assert listed_error.stderr == aliased_error.stderr


@pytest.mark.parametrize("word", ["help", "ls"])
def test_alias_words_remain_argument_and_option_values(word: str) -> None:
    assert _parse_example(f"dicehub project get {word}")["project_id"] == word
    assert _parse_example(f"dicehub project list --search {word}")["search_filter"] == word


@pytest.mark.parametrize(
    "path", tuple(path for path, group in _GROUPS if "list" not in group.commands)
)
def test_ls_without_list_is_a_usage_error(path: tuple[str, ...]) -> None:
    result = runner.invoke(app, [*path, "ls"], prog_name="dicehub")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "No such command 'ls'." in result.stderr


@pytest.mark.parametrize("path", tuple(path for path, _ in _GROUPS if path))
def test_help_is_not_a_nested_command(path: tuple[str, ...]) -> None:
    result = runner.invoke(app, [*path, "help"], prog_name="dicehub")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "No such command 'help'." in result.stderr


@pytest.mark.parametrize(
    "path",
    [
        ("missing",),
        ("project", "missing"),
        ("project", "members", "missing"),
        ("project", "list", "missing"),
        ("project", "get", "42"),
        ("project", "members", "ls"),
        ("help",),
        ("--version",),
    ],
)
def test_unknown_help_path_is_a_usage_error(path: tuple[str, ...]) -> None:
    result = runner.invoke(app, ["help", *path], prog_name="dicehub")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr.startswith("Usage: dicehub")
    assert f"No such command {path[-1]!r}." in result.stderr


def test_version_is_the_package_version_and_has_only_a_long_flag() -> None:
    result = runner.invoke(app, ["--version"], prog_name="dicehub")
    assert result.exit_code == 0
    assert result.stdout == dicehub.__version__ + "\n"
    assert result.stderr == ""
    root = get_command(app)
    version = next(parameter for parameter in root.params if parameter.name == "version")
    assert isinstance(version, TyperOption)
    assert version.opts == ["--version"]
    assert version.secondary_opts == []
    for arguments in (["-v"], ["-V"], ["project", "--version"]):
        assert runner.invoke(app, arguments).exit_code == 2


def test_version_exits_before_command_execution() -> None:
    result = runner.invoke(app, ["--version", "project", "delete", "42", "--yes"])
    assert result.exit_code == 0
    assert result.stdout == dicehub.__version__ + "\n"
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("arguments", "usage", "message"),
    [
        (["project", "help"], "project [OPTIONS] COMMAND [ARGS]...", "No such command 'help'."),
        (
            ["project", "get"],
            "project get [OPTIONS] {project_id}",
            "Missing argument 'project_id'.",
        ),
        (["project", "list", "--invalid"], "project list [OPTIONS]", "No such option: --invalid"),
    ],
)
def test_existing_usage_error_text_is_unchanged(
    arguments: list[str], usage: str, message: str
) -> None:
    result = runner.invoke(app, arguments, prog_name="dicehub")
    command_path = usage.split(" [OPTIONS]", 1)[0]
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"Usage: dicehub {usage}\n"
        f"Try 'dicehub {command_path} --help' for help.\n\n"
        f"Error: {message}\n"
    )
