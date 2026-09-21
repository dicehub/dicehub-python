"""Run-setting helpers for the car-mesh example."""

from __future__ import annotations

import io

from ruamel.yaml import YAML  # type: ignore[import-not-found,import-untyped,unused-ignore]


def configure_local_run(
    settings_yaml: str,
    decomposition_yaml: str,
    node_count: int,
    cpu_count: int,
) -> tuple[str, str]:
    """Select local execution and configure its OpenFOAM subdomains."""

    yaml = YAML(typ="rt")
    settings = yaml.load(settings_yaml)
    settings["run"]["provider"] = "LOCAL"
    settings["run"]["machine_type_id"] = "local"
    settings["run"]["node_count"] = node_count
    settings["run"]["cpu_count"] = cpu_count
    settings["run"]["flow"] = (
        "multi-core-flow-nfs-docker" if node_count * cpu_count > 1 else "single-core-flow-docker"
    )

    decomposition = yaml.load(decomposition_yaml)
    decomposition["decomposeParDict"]["numberOfSubdomains"] = node_count * cpu_count

    settings_result = io.StringIO()
    yaml.dump(settings, settings_result)
    decomposition_result = io.StringIO()
    yaml.dump(decomposition, decomposition_result)
    return settings_result.getvalue(), decomposition_result.getvalue()
