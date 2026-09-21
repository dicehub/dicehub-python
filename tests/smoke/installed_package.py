from __future__ import annotations

import subprocess
import sys
from importlib import import_module
from importlib.metadata import version
from pathlib import Path

import dicehub

# Source tests own public API assertions; this script checks installation and command registration.
DOMAINS = (
    "api_keys",
    "apps",
    "auth",
    "configs",
    "groups",
    "projects",
    "resources",
    "runs",
    "storage",
    "teams",
    "templates",
    "users",
)
COMMANDS = {
    (): ("auth", "api-key", "app", "config", "group", "project", "run", "template"),
    ("api-key",): ("list", "get", "permissions", "create", "update", "revoke"),
    ("app",): ("create", "update", "delete", "get-by-route", "roles", "members"),
    ("app", "members"): ("list-users", "list-teams", "add", "update", "remove"),
    ("config",): ("create", "delete", "list", "get"),
    ("group",): (
        "list",
        "get",
        "get-by-route",
        "update",
        "create",
        "delete",
        "move",
        "roles",
        "avatar",
        "members",
    ),
    ("group", "avatar"): ("set", "clear"),
    ("group", "members"): ("list-users", "list-teams", "add", "update", "remove"),
    ("project",): ("delete", "roles", "members"),
    ("project", "members"): ("list-users", "list-teams", "add", "update", "remove"),
    ("run",): ("list", "get", "status", "wait", "watch", "start", "stop", "download-results"),
    ("template",): ("list", "get", "get-by-route"),
    ("api-key", "create"): (),
    ("auth", "status"): (),
    ("config", "content"): (),
    ("group", "get-by-route"): (),
    ("group", "update"): (),
    ("template", "get-by-route"): (),
    ("run", "start"): (),
    ("run", "stop"): (),
}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: installed_package.py VERSION_FILE")
    environment_path = Path(sys.prefix).resolve()
    package_path = Path(dicehub.__file__).resolve()
    assert package_path.is_relative_to(environment_path), (package_path, environment_path)
    assert package_path.with_name("py.typed").is_file()
    expected_version = Path(sys.argv[1]).read_text().strip()
    assert version("dicehub-python") == expected_version
    assert dicehub.__version__ == expected_version
    for domain in DOMAINS:
        module = import_module(f"dicehub.{domain}")
        assert module.__file__ is not None, domain
        assert Path(module.__file__).resolve().is_relative_to(environment_path), domain

    executable = Path(sys.executable).with_name("dicehub")
    for command, expected in COMMANDS.items():
        result = subprocess.run(
            [str(executable), *command, "--help"],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (command, result.stderr)
        assert "Usage" in result.stdout, command
        for name in expected:
            assert name in result.stdout, (command, name)


if __name__ == "__main__":
    main()
