from __future__ import annotations

from dataclasses import dataclass

import pytest

from examples import controlled_cube_workflow
from examples._controlled_cube import (
    CONFIG_CAMERA_ROLL_DEGREES,
    SCENE_SETTINGS_PATH,
    ControlledCubeError,
    config_camera_roll,
    rotate_config_camera,
)

SCENE_SETTINGS_YAML = """sceneSettings:
  config:
    type: CONFIG
    camera:
      position:
        x: -20.12018081
        y: 15.81435101
        z: 37.00620691
      focal_point:
        x: 5
        y: 0
        z: 3.999924165
      view_up:
        x: 0.2401149403
        y: 0.9339476242
        z: -0.2647388348
      roll: 1.76151579 # degrees
      rotation_center:
        location:
          x: 5
          y: 0
          z: 3.999924165
  result:
    type: RESULT
    camera:
      position:
        x: 0
        y: 0
        z: 10
      roll: 0
"""


def test_camera_rotation_changes_only_the_config_roll_scalar() -> None:
    rotated = rotate_config_camera(SCENE_SETTINGS_YAML)

    assert rotated == SCENE_SETTINGS_YAML.replace(
        "roll: 1.76151579 # degrees",
        "roll: 15.0 # degrees",
        1,
    )
    assert config_camera_roll(rotated) == CONFIG_CAMERA_ROLL_DEGREES
    assert "  result:\n" in rotated
    assert "      roll: 0\n" in rotated


def test_camera_rotation_preserves_crlf_and_comments() -> None:
    original = SCENE_SETTINGS_YAML.replace("\n", "\r\n")

    rotated = rotate_config_camera(original)

    assert "      roll: 15.0 # degrees\r\n" in rotated
    assert rotated.count("\r\n") == original.count("\r\n")


@pytest.mark.parametrize(
    "content",
    [
        SCENE_SETTINGS_YAML.replace("roll: 1.76151579", "yaw: 1.76151579"),
        SCENE_SETTINGS_YAML + SCENE_SETTINGS_YAML,
        SCENE_SETTINGS_YAML.replace("roll: 1.76151579", "roll: [1.76151579]"),
        SCENE_SETTINGS_YAML.replace("roll: 1.76151579", "roll: 1e999"),
        SCENE_SETTINGS_YAML.replace("    camera:\n", "    camera: {}\n", 1),
        """sceneSettings:
  config:
    camera:
      note: |
        roll: 2
""",
        """sceneSettings:
  config:
    camera:
      note: >-
        roll: 2
""",
        """sceneSettings:
  config:
    camera:
      note: camera details
        roll: 2
""",
        """sceneSettings:
  config:
    camera:
---
      roll: 2
""",
    ],
)
def test_camera_rotation_rejects_missing_duplicate_or_malformed_target(content: str) -> None:
    with pytest.raises(ControlledCubeError, match="exactly one finite numeric"):
        rotate_config_camera(content)


@dataclass
class _FakeConfigs:
    content: str
    persist: bool = True

    def __post_init__(self) -> None:
        self.calls: list[tuple[str, str, str, str | None]] = []

    def get_text(self, *, config_id: str, path: str) -> str:
        self.calls.append(("get", config_id, path, None))
        return self.content

    def set_text(self, *, config_id: str, path: str, content: str) -> None:
        self.calls.append(("set", config_id, path, content))
        if self.persist:
            self.content = content


class _FakeClient:
    def __init__(self, configs: _FakeConfigs) -> None:
        self.configs = configs


def test_workflow_reads_modifies_writes_once_and_verifies_exact_path() -> None:
    configs = _FakeConfigs(SCENE_SETTINGS_YAML)

    controlled_cube_workflow._rotate_camera(
        _FakeClient(configs),  # type: ignore[arg-type]
        "403",
    )

    assert [(method, config_id, path) for method, config_id, path, _content in configs.calls] == [
        ("get", "403", SCENE_SETTINGS_PATH),
        ("set", "403", SCENE_SETTINGS_PATH),
        ("get", "403", SCENE_SETTINGS_PATH),
    ]
    assert config_camera_roll(configs.content) == CONFIG_CAMERA_ROLL_DEGREES


def test_workflow_fails_when_camera_update_does_not_persist() -> None:
    configs = _FakeConfigs(SCENE_SETTINGS_YAML, persist=False)

    with pytest.raises(ControlledCubeError, match="did not persist exactly"):
        controlled_cube_workflow._rotate_camera(
            _FakeClient(configs),  # type: ignore[arg-type]
            "403",
        )

    assert [method for method, _config_id, _path, _content in configs.calls] == [
        "get",
        "set",
        "get",
    ]
