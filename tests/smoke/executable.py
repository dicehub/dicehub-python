"""Check a frozen executable without credentials or a running server."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

COMMANDS = (
    (),
    ("auth", "status"),
    ("api-key", "create"),
    ("app", "members"),
    ("config", "content"),
    ("group", "members"),
    ("group", "avatar"),
    ("project", "members"),
    ("resource",),
    ("template", "get-by-route"),
    ("run", "machine-types"),
    ("run", "wait"),
    ("run", "watch"),
    ("run", "start"),
    ("run", "stop"),
    ("run", "download-results"),
)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: executable.py EXECUTABLE")
    executable = Path(sys.argv[1]).resolve(strict=True)
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("DICEHUB_")
    }
    for command in COMMANDS:
        result = subprocess.run(
            [str(executable), *command, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=environment,
        )
        assert result.returncode == 0, (command, result.stderr)
        assert "Usage" in result.stdout, command
    print(f"Verified {len(COMMANDS)} executable help commands.")


if __name__ == "__main__":
    main()
