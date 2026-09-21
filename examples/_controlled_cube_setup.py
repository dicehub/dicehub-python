"""Validation for the server-generated controlled-cube domain setup."""

from __future__ import annotations

import ast
import itertools
import math
import re
from dataclasses import dataclass

import dicehub as dh
from examples._controlled_cube import ControlledCubeError
from examples._controlled_cube_geometry import _plain_yaml_scalars

BOUNDING_BOX_PATH = "geometry/boundingBox.yaml"
MATERIAL_POINT_PATH = "geometry/materialPoint.yaml"
SCENE_SETTINGS_PATH = "sceneSettings.yaml"

Point3 = tuple[float, float, float]
Cells3 = tuple[int, int, int]
_EXPECTED_MIN: Point3 = (-0.3, -0.3, 0.0)
_EXPECTED_MAX: Point3 = (1.3, 1.3, 1.3)
_EXPECTED_CELLS: Cells3 = (10, 10, 10)
_EXPECTED_MATERIAL_POINT: Point3 = (-0.275, -0.275, 1.275)
_SETUP_ABSOLUTE_TOLERANCE = 1e-8

_VERTEX_LINE = re.compile(
    r"^ {8}- (?P<vector>\[[^\]\r\n]{1,256}\])(?:\s+#.*)?$",
    re.MULTILINE,
)
_CELLS_LINE = re.compile(
    r"^ {8}cells:\s*(?P<vector>\[[^\]\r\n]{1,128}\])(?:\s+#.*)?$",
    re.MULTILINE,
)
_VERTEX_NUMBERS_LINE = re.compile(
    r"^ {8}vertex_numbers:\s*(?P<vector>\[[^\]\r\n]{1,128}\])(?:\s+#.*)?$",
    re.MULTILINE,
)
_MATERIAL_POINT_LINE = re.compile(
    r"^ {2}locationInMesh:\s*(?P<vector>\[[^\]\r\n]{1,256}\])(?:\s+#.*)?$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class GeneratedSetup:
    bounds_min: Point3
    bounds_max: Point3
    cells: Cells3
    material_point: Point3
    scene_settings: str


def verify_generated_setup(client: dh.Client, config_id: str) -> GeneratedSetup:
    """Read and validate the three outputs of the setup-bounding-box run."""

    bounding_box = client.configs.get_text(config_id=config_id, path=BOUNDING_BOX_PATH)
    material_point = client.configs.get_text(config_id=config_id, path=MATERIAL_POINT_PATH)
    scene_settings = client.configs.get_text(config_id=config_id, path=SCENE_SETTINGS_PATH)
    bounds_min, bounds_max, cells = validate_bounding_box(bounding_box)
    point = validate_material_point(material_point, bounds_min, bounds_max)
    validate_scene_settings(scene_settings)
    return GeneratedSetup(
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        cells=cells,
        material_point=point,
        scene_settings=scene_settings,
    )


def validate_bounding_box(content: str) -> tuple[Point3, Point3, Cells3]:
    """Require one rectangular generated domain that encloses the unit cube."""

    _require_text(content, "Generated bounding-box YAML")
    for pattern in (
        r"^boundingBox:\s*(?:#.*)?$",
        r"^ {2}blockMeshDict:\s*(?:#.*)?$",
        r"^ {4}vertices:\s*(?:#.*)?$",
        r"^ {6}verticesList:\s*(?:#.*)?$",
        r"^ {4}blocks:\s*(?:#.*)?$",
        r"^ {2}view:\s*(?:#.*)?$",
        r"^ {4}type:\s*['\"]?StandardBoundingBox['\"]?\s*(?:#.*)?$",
    ):
        _require_one_line(content, pattern, "Generated bounding-box YAML has an invalid shape.")

    vertex_matches = _VERTEX_LINE.findall(content)
    if len(vertex_matches) != 8:
        raise ControlledCubeError("Generated bounding-box YAML must contain eight vertices.")
    vertices = tuple(_numeric_vector(raw, count=3) for raw in vertex_matches)
    minimum: Point3 = (
        min(vertex[0] for vertex in vertices),
        min(vertex[1] for vertex in vertices),
        min(vertex[2] for vertex in vertices),
    )
    maximum: Point3 = (
        max(vertex[0] for vertex in vertices),
        max(vertex[1] for vertex in vertices),
        max(vertex[2] for vertex in vertices),
    )
    if any(
        low >= high or low > 0.0 or high < 1.0 for low, high in zip(minimum, maximum, strict=True)
    ):
        raise ControlledCubeError("Generated bounding-box YAML does not enclose the unit cube.")
    corners = set(
        itertools.product(*((low, high) for low, high in zip(minimum, maximum, strict=True)))
    )
    if len(set(vertices)) != 8 or set(vertices) != corners:
        raise ControlledCubeError("Generated bounding-box YAML is not one rectangular domain.")
    if not _points_close(minimum, _EXPECTED_MIN) or not _points_close(maximum, _EXPECTED_MAX):
        raise ControlledCubeError("Generated bounding-box YAML has unexpected cube bounds.")

    vertex_numbers = _one_vector(content, _VERTEX_NUMBERS_LINE, "vertex numbers", integers=True)
    if vertex_numbers != tuple(range(8)):
        raise ControlledCubeError("Generated bounding-box YAML has invalid vertex numbers.")
    cells_raw = _one_vector(content, _CELLS_LINE, "cell counts", integers=True)
    if len(cells_raw) != 3 or any(value <= 0 or value > 10_000_000 for value in cells_raw):
        raise ControlledCubeError("Generated bounding-box YAML has invalid cell counts.")
    cells = (cells_raw[0], cells_raw[1], cells_raw[2])
    if cells != _EXPECTED_CELLS:
        raise ControlledCubeError("Generated bounding-box YAML has unexpected cube cell counts.")
    return minimum, maximum, cells


def validate_material_point(content: str, minimum: Point3, maximum: Point3) -> Point3:
    """Require the generated material point inside the domain and outside the cube."""

    _require_text(content, "Generated material-point YAML")
    for pattern in (
        r"^materialPoint:\s*(?:#.*)?$",
        r"^ {2}view:\s*(?:#.*)?$",
        r"^ {4}type:\s*['\"]?Point['\"]?\s*(?:#.*)?$",
    ):
        _require_one_line(content, pattern, "Generated material-point YAML has an invalid shape.")
    matches = _MATERIAL_POINT_LINE.findall(content)
    if len(matches) != 1:
        raise ControlledCubeError("Generated material-point YAML has an invalid location.")
    values = _numeric_vector(matches[0], count=3)
    point: Point3 = (values[0], values[1], values[2])
    if any(
        value < low or value > high
        for value, low, high in zip(point, minimum, maximum, strict=True)
    ):
        raise ControlledCubeError("Generated material point is outside the background mesh.")
    if all(0.0 < value < 1.0 for value in point):
        raise ControlledCubeError("Generated material point is inside the solid cube.")
    if not _points_close(point, _EXPECTED_MATERIAL_POINT):
        raise ControlledCubeError("Generated material point has an unexpected cube location.")
    return point


def validate_scene_settings(content: str) -> None:
    """Require finite generated CONFIG-camera coordinates."""

    scalars = _plain_yaml_scalars(content)
    root = ("sceneSettings", "config")
    if scalars.get((*root, "type")) != "CONFIG":
        raise ControlledCubeError("Generated scene-settings YAML has no CONFIG camera.")
    camera = (*root, "camera")
    paths = tuple(
        (*camera, group, axis)
        for group in ("position", "focal_point", "view_up")
        for axis in ("x", "y", "z")
    ) + tuple((*camera, "rotation_center", "location", axis) for axis in ("x", "y", "z"))
    values: dict[tuple[str, ...], float] = {}
    for path in (*paths, (*camera, "roll")):
        raw = scalars.get(path)
        try:
            value = float(raw) if raw is not None else math.nan
        except ValueError:
            value = math.nan
        if not math.isfinite(value):
            raise ControlledCubeError("Generated scene-settings YAML has invalid camera values.")
        values[path] = value
    view_up = tuple(values[(*camera, "view_up", axis)] for axis in ("x", "y", "z"))
    if math.sqrt(sum(value * value for value in view_up)) == 0.0:
        raise ControlledCubeError("Generated scene-settings YAML has an invalid view-up vector.")


def _require_text(content: str, label: str) -> None:
    if not isinstance(content, str) or not content or "\0" in content:
        raise ControlledCubeError(f"{label} is empty or invalid.")


def _points_close(actual: Point3, expected: Point3) -> bool:
    return all(
        math.isclose(value, target, rel_tol=0.0, abs_tol=_SETUP_ABSOLUTE_TOLERANCE)
        for value, target in zip(actual, expected, strict=True)
    )


def _require_one_line(content: str, pattern: str, message: str) -> None:
    if len(re.findall(pattern, content, flags=re.MULTILINE)) != 1:
        raise ControlledCubeError(message)


def _one_vector(
    content: str,
    pattern: re.Pattern[str],
    label: str,
    *,
    integers: bool,
) -> tuple[int, ...]:
    matches = pattern.findall(content)
    if len(matches) != 1:
        raise ControlledCubeError(f"Generated bounding-box YAML has invalid {label}.")
    values = _numeric_vector(matches[0], count=None, integers=integers)
    return tuple(int(value) for value in values)


def _numeric_vector(
    raw: str,
    *,
    count: int | None,
    integers: bool = False,
) -> tuple[float, ...]:
    try:
        values = ast.literal_eval(raw)
    except (SyntaxError, ValueError) as error:
        raise ControlledCubeError("Generated setup YAML has an invalid numeric vector.") from error
    if not isinstance(values, list) or (count is not None and len(values) != count):
        raise ControlledCubeError("Generated setup YAML has an invalid numeric vector.")
    if integers:
        if any(type(value) is not int for value in values):
            raise ControlledCubeError("Generated setup YAML has an invalid integer vector.")
    elif any(type(value) not in {int, float} for value in values):
        raise ControlledCubeError("Generated setup YAML has an invalid numeric vector.")
    numbers = tuple(float(value) for value in values)
    if not numbers or any(not math.isfinite(value) for value in numbers):
        raise ControlledCubeError("Generated setup YAML has an invalid numeric vector.")
    return numbers
