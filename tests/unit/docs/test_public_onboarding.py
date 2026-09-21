from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[3]
HOSTED_ORIGIN = "https://dicehub.com"
ONBOARDING_FILES = (
    ROOT / "README.md",
    ROOT / "docs" / "getting-started.md",
    ROOT / "docs" / "authentication.md",
    ROOT / "docs" / "api-keys.md",
    ROOT / "docs" / "cli.md",
    ROOT / "docs" / "decisions" / "0001-public-onboarding.md",
)
HOSTED_COMMAND_FILES = (
    ROOT / "docs" / "authentication.md",
    ROOT / "docs" / "api-keys.md",
    ROOT / "docs" / "cli.md",
    ROOT / "docs" / "runs.md",
    ROOT / "docs" / "guides" / "controlled-cube-workflow.md",
    ROOT / "examples" / "car_mesh" / "README.md",
)


def test_hosted_onboarding_contract_has_one_complete_first_use_path() -> None:
    getting_started = (ROOT / "docs" / "getting-started.md").read_text(encoding="utf-8")

    required_contract = (
        f"{HOSTED_ORIGIN}/signup",
        f"{HOSTED_ORIGIN}/signin",
        f"{HOSTED_ORIGIN}/settings/tokens/create",
        f"{HOSTED_ORIGIN}/settings/tokens",
        f"{HOSTED_ORIGIN}/contact-us",
        "DICEHUB_API_KEY",
        "client.auth.context()",
        "dicehub auth status --output json",
        "VIEW_PROJECT_INFO",
        "CREATE_USER_PROJECT",
        '"schema_version":"dicehub.cli/v1"',
    )

    for value in required_contract:
        assert value in getting_started


def test_public_documentation_has_no_placeholder_origin() -> None:
    public_files = (
        ROOT / "README.md",
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "examples").rglob("*.md")),
        *sorted((ROOT / "examples").rglob("*.py")),
    )

    for path in public_files:
        content = path.read_text(encoding="utf-8")
        assert "dicehub.example" not in content, path.relative_to(ROOT)
        assert "example.com" not in content, path.relative_to(ROOT)


def test_onboarding_files_use_the_canonical_hosted_origin() -> None:
    for path in ONBOARDING_FILES:
        assert HOSTED_ORIGIN in path.read_text(encoding="utf-8"), path.relative_to(ROOT)


def test_explicit_hosted_origins_are_canonical() -> None:
    for path in HOSTED_COMMAND_FILES:
        content = path.read_text(encoding="utf-8")
        assignments = re.findall(r"^export DICEHUB_URL=(.+)$", content, flags=re.MULTILINE)
        assert set(assignments) <= {HOSTED_ORIGIN}, path.relative_to(ROOT)


def test_authentication_example_requires_environment_credentials() -> None:
    example = (ROOT / "examples" / "auth_status.py").read_text(encoding="utf-8")

    assert 'os.environ["DICEHUB_URL"]' not in example
    assert 'os.environ["DICEHUB_API_KEY"]' in example
    assert "client.auth.context()" in example
    assert "http://" not in example
    assert "https://" not in example


def test_examples_do_not_require_a_url_for_hosted_dicehub() -> None:
    example_files = sorted((ROOT / "examples").rglob("*.py"))

    for path in example_files:
        assert 'os.environ["DICEHUB_URL"]' not in path.read_text(encoding="utf-8"), (
            path.relative_to(ROOT)
        )

    for path in (
        ROOT / "examples" / "manage_api_keys.py",
        ROOT / "examples" / "car_mesh" / "workflow.py",
        ROOT / "examples" / "controlled_cube_workflow.py",
    ):
        assert 'os.environ.get("DICEHUB_URL", "https://dicehub.com")' in path.read_text(
            encoding="utf-8"
        )


def test_project_lifecycle_uses_an_environment_api_key() -> None:
    example = (ROOT / "examples" / "manage_projects.py").read_text(encoding="utf-8")

    assert 'api_key=os.environ["DICEHUB_API_KEY"]' in example
    assert "session_cookie" not in example
