"""Validate a public release tag without interpolating event data into a shell."""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    version = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("Public releases require a stable major.minor.patch version.")
    if os.environ["RELEASE_TAG"] != f"v{version}":
        raise SystemExit("Release tag must match VERSION exactly.")
    changelog = (ROOT / "CHANGELOG.md").read_text()
    if not re.search(
        rf"^## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.MULTILINE
    ):
        raise SystemExit("Add dated changelog notes for the release version.")
    print(f"Validated release tag v{version}.")


if __name__ == "__main__":
    main()
