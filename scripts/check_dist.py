"""Check the exact release archives, including source and typing metadata."""

from __future__ import annotations

import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = {
    ".gitignore",
    "dicehub",
    "docs",
    "examples",
    "requirements",
    "scripts",
    "tests",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "VERSION",
    "pyproject.toml",
    "PKG-INFO",
}


def main() -> None:
    version = (ROOT / "VERSION").read_text().strip()
    wheel_path = ROOT / "dist" / f"dicehub_python-{version}-py3-none-any.whl"
    source_path = ROOT / "dist" / f"dicehub_python-{version}.tar.gz"
    archives = set((ROOT / "dist").iterdir())
    assert archives == {wheel_path, source_path}, (
        "dist must contain only this release's two archives"
    )
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        info = f"dicehub_python-{version}.dist-info"
        assert "dicehub/py.typed" in names
        assert all(name.startswith(("dicehub/", f"{info}/")) for name in names)
        metadata = BytesParser().parsebytes(wheel.read(f"{info}/METADATA"))
        assert metadata["Name"] == "dicehub-python"
        assert metadata["Version"] == version
        assert metadata["Requires-Python"] == ">=3.10"
        wheel_has_license = f"{info}/licenses/LICENSE" in names
    with tarfile.open(source_path, "r:gz") as source:
        files = {member.name for member in source.getmembers() if member.isfile()}
        prefix = f"dicehub_python-{version}/"
        assert all(name.startswith(prefix) for name in files)
        relative = {name.removeprefix(prefix) for name in files}
        assert all(PurePosixPath(name).parts[0] in SOURCE_ROOTS for name in relative)
        assert {"README.md", "VERSION", "pyproject.toml", "dicehub/py.typed"} <= relative
        assert "tests/smoke/installed_package.py" in relative
        assert "docs/index.md" in relative
        assert "scripts/check_dist.py" in relative
        assert not any(
            part in {".env", ".netrc", ".pypirc", "__pycache__", ".git"} or part.startswith(".env.")
            for name in relative
            for part in PurePosixPath(name).parts
        )
    assert metadata["License-Expression"] and wheel_has_license and "LICENSE" in relative, (
        "Select a source license and include LICENSE in both archives before release"
    )
    print(f"Verified package contents and metadata for dicehub-python {version}.")


if __name__ == "__main__":
    main()
