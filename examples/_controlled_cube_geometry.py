"""Validation for geometry created by the controlled-cube conversion microrun."""

from __future__ import annotations

import io
import math
import re

import dicehub as dh
from examples._controlled_cube import ControlledCubeError
from examples._controlled_cube_vtp import MAX_GEOMETRY_VTP_BYTES, validate_cube_vtp

GEOMETRY_FILENAME = "cube.stl"
GEOMETRY_YAML_PATH = f"geometry/{GEOMETRY_FILENAME}.yaml"
GEOMETRY_VTP_PATH = f"VTK/{GEOMETRY_FILENAME}/cube.vtp"
_BOUND_ABSOLUTE_TOLERANCE = 1e-9
_YAML_MAPPING_LINE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z_][A-Za-z0-9_.-]*):(?P<rest>.*)$")
_SURFACE_LEVEL_LINE = re.compile(
    r"^(?P<prefix> {2}level:[ \t]*)\[0,[ \t]*0\]"
    r"(?P<suffix>[ \t]*(?:#.*)?(?:\r?\n|$))",
    re.MULTILINE,
)
_FEATURE_LEVEL_LINE = re.compile(
    r"^(?P<prefix> {6}-[ \t]*)\[0,[ \t]*0\]"
    r"(?P<suffix>[ \t]*(?:#.*)?(?:\r?\n|$))",
    re.MULTILINE,
)


def verify_imported_geometry(client: dh.Client, config_id: str) -> str:
    """Validate generated YAML and the exact renderable VTP content entry."""

    geometry_yaml = client.configs.get_text(config_id=config_id, path=GEOMETRY_YAML_PATH)
    validate_imported_geometry_yaml(geometry_yaml)
    page = client.configs.list_content(
        config_id=config_id,
        area=dh.ConfigContentArea.FILES,
        path=f"VTK/{GEOMETRY_FILENAME}",
        recursive=True,
        limit=50,
    )
    expected = [
        entry
        for entry in page.entries
        if entry.path == GEOMETRY_VTP_PATH and entry.resource_type is dh.ConfigContentType.FILE
    ]
    if len(expected) != 1:
        raise ControlledCubeError(f"Geometry import did not create {GEOMETRY_VTP_PATH!r}.")
    destination = io.BytesIO()
    byte_count = client.configs.download_file(
        config_id=config_id,
        path=GEOMETRY_VTP_PATH,
        destination=destination,
        max_bytes=MAX_GEOMETRY_VTP_BYTES,
    )
    content = destination.getvalue()
    if byte_count != len(content):
        raise ControlledCubeError("Geometry VTP download returned an inconsistent byte count.")
    validate_cube_vtp(content)
    return geometry_yaml


def validate_imported_geometry_yaml(content: str) -> None:
    """Require the converter's renderable cube geometry contract."""

    _validate_geometry_shape_and_bounds(content)
    _validate_refinement_levels(content, surface="[0, 0]", feature_last=0)


def _validate_geometry_shape_and_bounds(content: str) -> None:
    scalars = _plain_yaml_scalars(content)
    root = (GEOMETRY_FILENAME,)
    expected = {
        (*root, "type"): "triSurfaceMesh",
        (*root, "regions", "cube", "name"): "cube",
        (*root, "view", "type"): "VTPFileCollection",
        (*root, "view", "paths", "cube"): f"{GEOMETRY_FILENAME}/cube.vtp",
        (*root, "view", "geometry", "cube", "type"): "VTPFileCollectionItem",
    }
    if any(scalars.get(path) != value for path, value in expected.items()):
        raise ControlledCubeError("Imported geometry YAML is not a renderable cube collection.")

    for name, expected_bound in (
        ("xmin", 0.0),
        ("xmax", 1.0),
        ("ymin", 0.0),
        ("ymax", 1.0),
        ("zmin", 0.0),
        ("zmax", 1.0),
    ):
        raw = scalars.get((*root, "bounds", name))
        try:
            value = float(raw) if raw is not None else math.nan
        except ValueError:
            value = math.nan
        if not math.isfinite(value) or not math.isclose(
            value,
            expected_bound,
            rel_tol=0.0,
            abs_tol=_BOUND_ABSOLUTE_TOLERANCE,
        ):
            raise ControlledCubeError("Imported geometry YAML has invalid cube bounds.")


def refine_imported_geometry(content: str) -> str:
    """Set the two reviewed refinement levels and preserve all other YAML bytes."""

    validate_imported_geometry_yaml(content)
    updated = _replace_one_level(
        content,
        _SURFACE_LEVEL_LINE,
        "[1, 1]",
        "surface refinement",
    )
    updated = _replace_one_level(
        updated,
        _FEATURE_LEVEL_LINE,
        "[0, 1]",
        "feature refinement",
    )
    validate_refined_geometry_yaml(updated)
    return updated


def validate_refined_geometry_yaml(content: str) -> None:
    """Require the configured surface and feature refinement values."""

    _validate_geometry_shape_and_bounds(content)
    _validate_refinement_levels(content, surface="[1, 1]", feature_last=1)


def _validate_refinement_levels(content: str, *, surface: str, feature_last: int) -> None:
    scalars = _plain_yaml_scalars(content)
    if scalars.get((GEOMETRY_FILENAME, "level")) != surface:
        raise ControlledCubeError("Imported geometry YAML has invalid surface refinement.")
    matches = re.findall(
        rf"^ {{6}}-[ \t]*\[0,[ \t]*{feature_last}\][ \t]*(?:#.*)?$",
        content,
        flags=re.MULTILINE,
    )
    if len(matches) != 1:
        raise ControlledCubeError("Imported geometry YAML has invalid feature refinement.")


def _replace_one_level(
    content: str,
    pattern: re.Pattern[str],
    replacement: str,
    label: str,
) -> str:
    matches = tuple(pattern.finditer(content))
    if len(matches) != 1:
        raise ControlledCubeError(f"Imported geometry YAML has invalid {label}.")
    match = matches[0]
    return (
        content[: match.start()]
        + match.group("prefix")
        + replacement
        + match.group("suffix")
        + content[match.end() :]
    )


def _plain_yaml_scalars(content: str) -> dict[tuple[str, ...], str]:
    if not isinstance(content, str) or not content or "\0" in content:
        return {}
    stack: list[tuple[int, str]] = []
    scalars: dict[tuple[str, ...], str] = {}
    seen: set[tuple[str, ...]] = set()
    scalar_indent: int | None = None
    for line in content.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if scalar_indent is not None:
            if not stripped or indent > scalar_indent:
                continue
            scalar_indent = None
        if not stripped or line.lstrip().startswith("#"):
            continue
        document_token = stripped.split(maxsplit=1)[0]
        if indent == 0 and (
            document_token in {"---", "..."}
            or stripped.startswith("%YAML ")
            or stripped.startswith("%TAG ")
        ):
            return {}
        mapping = _YAML_MAPPING_LINE.fullmatch(line)
        if mapping is None:
            path = tuple(ancestor for _level, ancestor in stack)
            if path == (GEOMETRY_FILENAME, "features", "levels") and stripped in {
                "- [0, 0]",
                "- [0, 1]",
            }:
                continue
            return {}
        indent = len(mapping.group("indent"))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key = mapping.group("key")
        path = (*[ancestor for _level, ancestor in stack], key)
        if path in seen:
            return {}
        seen.add(path)
        rest = mapping.group("rest")
        value = rest.strip()
        if value and not rest.lstrip().startswith("#"):
            value = value.split(" #", 1)[0].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            scalars[path] = value
            scalar_indent = indent
        else:
            stack.append((indent, key))
    return scalars
