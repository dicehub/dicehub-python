from __future__ import annotations

import os
from pathlib import Path

import pytest

from examples.controlled_cube_workflow import main


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_controlled_cube_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to enable live requests.")
    if os.environ.get("DICEHUB_LIVE_CONTROLLED_CUBE_TEST") != "1":
        pytest.skip(
            "Set DICEHUB_LIVE_CONTROLLED_CUBE_TEST=1 to approve setup and the charged runs."
        )

    destination = tmp_path / "controlled-cube-results.zip"
    monkeypatch.setenv("DICEHUB_CONTROLLED_CUBE_RESULT_ZIP", str(destination))

    main()

    assert destination.is_file()
    assert destination.stat().st_size > 0
