"""Background-mesh helpers for the car-mesh example."""

from __future__ import annotations

import io
import math

from ruamel.yaml import YAML  # type: ignore[import-not-found,import-untyped,unused-ignore]
from ruamel.yaml.comments import (  # type: ignore[import-not-found,import-untyped,unused-ignore]
    CommentedSeq,
)

Vector = tuple[float, float, float]


def _flow(values: tuple[float, float, float]) -> CommentedSeq:
    sequence = CommentedSeq(values)
    sequence.fa.set_flow_style()
    return sequence


def configure_background_mesh(
    bounding_box_yaml: str,
    material_point_yaml: str,
    minimum: Vector,
    maximum: Vector,
    cell_size: float,
    material_point: Vector,
) -> tuple[str, str]:
    """Set the wind-tunnel box, cell target, and material point."""

    yaml = YAML(typ="rt")
    bounding_box = yaml.load(bounding_box_yaml)
    block_mesh = bounding_box["boundingBox"]["blockMeshDict"]
    vertices = block_mesh["vertices"]["verticesList"]

    for index in (0, 3, 4, 7):
        vertices[index][0] = minimum[0]
    for index in (1, 2, 5, 6):
        vertices[index][0] = maximum[0]
    for index in (0, 1, 4, 5):
        vertices[index][1] = minimum[1]
    for index in (2, 3, 6, 7):
        vertices[index][1] = maximum[1]
    for index in (0, 1, 2, 3):
        vertices[index][2] = minimum[2]
    for index in (4, 5, 6, 7):
        vertices[index][2] = maximum[2]

    cells = block_mesh["blocks"][0]["cells"]
    for axis in range(3):
        cells[axis] = math.floor((maximum[axis] - minimum[axis]) / cell_size)

    bounding_box_result = io.StringIO()
    yaml.dump(bounding_box, bounding_box_result)

    yaml = YAML(typ="rt")
    material = yaml.load(material_point_yaml)
    material["materialPoint"]["locationInMesh"] = _flow(material_point)
    material_point_result = io.StringIO()
    yaml.dump(material, material_point_result)

    return bounding_box_result.getvalue(), material_point_result.getvalue()
