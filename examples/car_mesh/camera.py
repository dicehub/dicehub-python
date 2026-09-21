"""Camera helpers for the car-mesh example."""

from __future__ import annotations

import io
import math

from ruamel.yaml import YAML  # type: ignore[import-not-found,import-untyped,unused-ignore]

Vector = tuple[float, float, float]


def _unit(vector: Vector) -> Vector:
    length = math.sqrt(sum(value * value for value in vector))
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _cross(left: Vector, right: Vector) -> Vector:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _vtk_roll(position: Vector, focal_point: Vector, view_up: Vector) -> float:
    """Return the VTK roll that keeps this position and view-up unchanged."""

    normal = _unit(
        (
            position[0] - focal_point[0],
            position[1] - focal_point[1],
            position[2] - focal_point[2],
        )
    )
    sideways = _unit(_cross(view_up, normal))
    orthogonal_up = _cross(normal, sideways)
    x2, y2, z2 = normal
    x3, y3, z3 = orthogonal_up
    horizontal = math.hypot(x2, z2)

    if horizontal < 0.001:
        cosine_theta = 1.0
        sine_theta = 0.0
        sine_phi = y2
        cosine_phi = z2
    else:
        cosine_theta = z2 / horizontal
        sine_theta = x2 / horizontal
        sine_phi = y2
        cosine_phi = horizontal

    x3_rotated = x3 * cosine_theta - z3 * sine_theta
    y3_rotated = -sine_phi * sine_theta * x3 + cosine_phi * y3 - sine_phi * cosine_theta * z3
    return math.degrees(math.atan2(x3_rotated, y3_rotated))


def rotate_config_camera_x(scene_settings: str, degrees: float = 90.0) -> str:
    """Rotate the CONFIG camera around its focal point on the global X axis."""

    yaml = YAML(typ="rt")
    data = yaml.load(scene_settings)
    camera = data["sceneSettings"]["config"]["camera"]

    angle = math.radians(degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)

    position = camera["position"]
    focal_point = camera["focal_point"]
    offset_y = position["y"] - focal_point["y"]
    offset_z = position["z"] - focal_point["z"]
    position["y"] = focal_point["y"] + cosine * offset_y - sine * offset_z
    position["z"] = focal_point["z"] + sine * offset_y + cosine * offset_z

    view_up = camera["view_up"]
    view_up_y = view_up["y"]
    view_up_z = view_up["z"]
    view_up["y"] = cosine * view_up_y - sine * view_up_z
    view_up["z"] = sine * view_up_y + cosine * view_up_z

    position_vector = (
        float(position["x"]),
        float(position["y"]),
        float(position["z"]),
    )
    focal_point_vector = (
        float(focal_point["x"]),
        float(focal_point["y"]),
        float(focal_point["z"]),
    )
    view_up_vector = (
        float(view_up["x"]),
        float(view_up["y"]),
        float(view_up["z"]),
    )
    camera["roll"] = _vtk_roll(position_vector, focal_point_vector, view_up_vector)

    result = io.StringIO()
    yaml.dump(data, result)
    return result.getvalue()
