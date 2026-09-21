"""Mesh-refinement helpers for the car-mesh example."""

from __future__ import annotations

import io

from ruamel.yaml import YAML  # type: ignore[import-not-found,import-untyped,unused-ignore]
from ruamel.yaml.comments import (  # type: ignore[import-not-found,import-untyped,unused-ignore]
    CommentedSeq,
)


def configure_edge_refinement(
    geometry_yaml: str,
    geometry_name: str,
    distance: float,
    level: int,
) -> str:
    """Set one edge-refinement distance and level on an imported geometry."""

    yaml = YAML(typ="rt")
    geometry = yaml.load(geometry_yaml)
    edge_level = geometry[geometry_name]["features"]["levels"][0]
    edge_level[0] = distance
    edge_level[1] = level

    result = io.StringIO()
    yaml.dump(geometry, result)
    return result.getvalue()


def configure_surface_refinement(
    geometry_yaml: str,
    geometry_name: str,
    minimum_level: int,
    maximum_level: int,
) -> str:
    """Set the surface-refinement levels on an imported geometry."""

    yaml = YAML(typ="rt")
    geometry = yaml.load(geometry_yaml)
    surface_level = geometry[geometry_name]["level"]
    surface_level[0] = minimum_level
    surface_level[1] = maximum_level

    result = io.StringIO()
    yaml.dump(geometry, result)
    return result.getvalue()


def create_refinement_box(
    name: str,
    minimum: tuple[float, float, float],
    maximum: tuple[float, float, float],
    level: int,
) -> str:
    """Create one box-shaped volume-refinement configuration."""

    minimum_values = CommentedSeq(minimum)
    minimum_values.fa.set_flow_style()
    maximum_values = CommentedSeq(maximum)
    maximum_values.fa.set_flow_style()
    refinement_level = CommentedSeq([0, level])
    refinement_level.fa.set_flow_style()

    geometry = {
        name: {
            "name": name,
            "type": "searchableBox",
            "min": minimum_values,
            "max": maximum_values,
            "view": {
                "type": "BoxWidget",
                "opacity": 0.3,
                "selection_opacity": 0.5,
            },
            "refinementRegions": {
                "mode": "inside",
                "levels": [refinement_level],
            },
        }
    }

    yaml = YAML(typ="rt")
    result = io.StringIO()
    yaml.dump(geometry, result)
    return result.getvalue()


def configure_boundary_layers(
    geometry_yaml: str,
    geometry_name: str,
    region_name: str,
    layer_count: int,
    expansion_ratio: float,
    final_thickness: float,
    minimum_thickness: float,
) -> str:
    """Add boundary layers to one imported geometry region."""

    yaml = YAML(typ="rt")
    geometry = yaml.load(geometry_yaml)
    geometry[geometry_name]["regions"][region_name]["layers"] = {
        "nSurfaceLayers": layer_count,
        "expansionRatio": expansion_ratio,
        "finalLayerThickness": final_thickness,
        "minThickness": minimum_thickness,
    }

    result = io.StringIO()
    yaml.dump(geometry, result)
    return result.getvalue()
