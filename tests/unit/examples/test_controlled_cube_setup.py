from __future__ import annotations

from dataclasses import dataclass

import pytest

from examples._controlled_cube import ControlledCubeError
from examples._controlled_cube_setup import (
    BOUNDING_BOX_PATH,
    MATERIAL_POINT_PATH,
    SCENE_SETTINGS_PATH,
    validate_bounding_box,
    validate_material_point,
    validate_scene_settings,
    verify_generated_setup,
)

BOUNDING_BOX_YAML = """boundingBox:
  blockMeshDict:
    vertices:
      verticesList:
        - [-0.3, -0.3, 0.0]
        - [1.3, -0.3, 0.0]
        - [1.3, 1.3, 0.0]
        - [-0.3, 1.3, 0.0]
        - [-0.3, -0.3, 1.3]
        - [1.3, -0.3, 1.3]
        - [1.3, 1.3, 1.3]
        - [-0.3, 1.3, 1.3]
    blocks:
      - type: hex
        vertex_numbers: [0, 1, 2, 3, 4, 5, 6, 7]
        cells: [10, 10, 10]
  view:
    type: StandardBoundingBox
"""

TEMPLATE_DEFAULT_BOUNDING_BOX_YAML = """boundingBox:
  blockMeshDict:
    vertices:
      verticesList:
        - [-5, -4, 0]
        - [15, -4, 0]
        - [15, 4, 0]
        - [-5, 4, 0]
        - [-5, -4, 8]
        - [15, -4, 8]
        - [15, 4, 8]
        - [-5, 4, 8]
    blocks:
      - type: hex
        vertex_numbers: [0, 1, 2, 3, 4, 5, 6, 7]
        cells: [20, 8, 8]
  view:
    type: StandardBoundingBox
"""

MATERIAL_POINT_YAML = """materialPoint:
  locationInMesh: [-0.275, -0.275, 1.275]
  view:
    type: Point
"""

SCENE_SETTINGS_YAML = """sceneSettings:
  config:
    type: CONFIG
    camera:
      position:
        x: -3.0
        y: 2.0
        z: 4.0
      focal_point:
        x: 0.5
        y: 0.5
        z: 0.5
      view_up:
        x: 0.0
        y: 1.0
        z: 0.0
      roll: 1.5
      rotation_center:
        location:
          x: 0.5
          y: 0.5
          z: 0.5
"""


def test_generated_setup_pins_the_unit_cube_formula() -> None:
    minimum, maximum, cells = validate_bounding_box(BOUNDING_BOX_YAML)
    point = validate_material_point(MATERIAL_POINT_YAML, minimum, maximum)
    validate_scene_settings(SCENE_SETTINGS_YAML)

    assert minimum == (-0.3, -0.3, 0.0)
    assert maximum == (1.3, 1.3, 1.3)
    assert cells == (10, 10, 10)
    assert point == (-0.275, -0.275, 1.275)


def test_generated_setup_rejects_untouched_template_defaults() -> None:
    with pytest.raises(ControlledCubeError, match="unexpected cube"):
        validate_bounding_box(TEMPLATE_DEFAULT_BOUNDING_BOX_YAML)


@pytest.mark.parametrize(
    "content",
    [
        BOUNDING_BOX_YAML.replace("cells: [10, 10, 10]", "cells: [10, 0, 10]"),
        BOUNDING_BOX_YAML.replace("- [1.3, 1.3, 1.3]", "- [1.3, 1.3, 1.2]"),
        BOUNDING_BOX_YAML + "boundingBox:\n",
    ],
)
def test_generated_setup_rejects_invalid_background_mesh(content: str) -> None:
    with pytest.raises(ControlledCubeError, match="bounding-box"):
        validate_bounding_box(content)


@pytest.mark.parametrize(
    "content",
    [
        MATERIAL_POINT_YAML.replace("[-0.275, -0.275, 1.275]", "[0, 0, 0]"),
        MATERIAL_POINT_YAML.replace("type: Point", "type: Sphere"),
        MATERIAL_POINT_YAML + "  locationInMesh: [-0.275, -0.275, 1.275]\n",
    ],
)
def test_generated_setup_rejects_invalid_material_point(content: str) -> None:
    with pytest.raises(ControlledCubeError, match=r"material point|material-point"):
        validate_material_point(content, (-0.3, -0.3, 0.0), (1.3, 1.3, 1.3))


@pytest.mark.parametrize(
    "content",
    [
        SCENE_SETTINGS_YAML.replace("type: CONFIG", "type: RESULT"),
        SCENE_SETTINGS_YAML.replace("y: 1.0", "y: nan"),
        SCENE_SETTINGS_YAML.replace("y: 1.0", "y: 0.0"),
    ],
)
def test_generated_setup_rejects_invalid_camera(content: str) -> None:
    with pytest.raises(ControlledCubeError, match="scene-settings"):
        validate_scene_settings(content)


@dataclass
class _FakeConfigs:
    def __post_init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_text(self, *, config_id: str, path: str) -> str:
        assert config_id == "403"
        self.calls.append((config_id, path))
        return {
            BOUNDING_BOX_PATH: BOUNDING_BOX_YAML,
            MATERIAL_POINT_PATH: MATERIAL_POINT_YAML,
            SCENE_SETTINGS_PATH: SCENE_SETTINGS_YAML,
        }[path]


@dataclass
class _FakeClient:
    configs: _FakeConfigs


def test_workflow_reads_all_server_generated_setup_outputs() -> None:
    configs = _FakeConfigs()

    setup = verify_generated_setup(_FakeClient(configs), "403")  # type: ignore[arg-type]

    assert setup.cells == (10, 10, 10)
    assert setup.scene_settings == SCENE_SETTINGS_YAML
    assert configs.calls == [
        ("403", BOUNDING_BOX_PATH),
        ("403", MATERIAL_POINT_PATH),
        ("403", SCENE_SETTINGS_PATH),
    ]
