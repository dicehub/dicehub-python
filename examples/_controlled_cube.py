"""Deterministic inputs and offline validation for the controlled-cube example."""

from __future__ import annotations

import math
import re
import stat
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import dicehub as dh

MAX_RESULT_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_RESULT_MEMBERS = 20_000
SCENE_SETTINGS_PATH = "sceneSettings.yaml"
CONFIG_CAMERA_ROLL_DEGREES = 15.0
TERMINAL_RUN_STATES = frozenset(
    {
        dh.RunState.FINISHED,
        dh.RunState.STOPPED,
        dh.RunState.FAILED,
        dh.RunState.INTERRUPTED,
        dh.RunState.CANCELED,
    }
)

_CONFIG_CAMERA_ROLL_PATH = ("sceneSettings", "config", "camera", "roll")
_YAML_MAPPING_LINE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z_][A-Za-z0-9_.-]*):(?P<rest>.*)$")
_YAML_NUMBER = re.compile(
    r"^(?P<before>\s*)"
    r"(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?P<after>\s*(?:#.*)?)$"
)

CUBE_STL = b"""solid cube
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 0 1 0
      vertex 1 1 0
    endloop
  endfacet
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 1 1 0
      vertex 1 0 0
    endloop
  endfacet
  facet normal 0 0 1
    outer loop
      vertex 0 0 1
      vertex 1 0 1
      vertex 1 1 1
    endloop
  endfacet
  facet normal 0 0 1
    outer loop
      vertex 0 0 1
      vertex 1 1 1
      vertex 0 1 1
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 1 0 1
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 1 0 1
      vertex 0 0 1
    endloop
  endfacet
  facet normal 0 1 0
    outer loop
      vertex 0 1 0
      vertex 0 1 1
      vertex 1 1 1
    endloop
  endfacet
  facet normal 0 1 0
    outer loop
      vertex 0 1 0
      vertex 1 1 1
      vertex 1 1 0
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 0 0
      vertex 0 0 1
      vertex 0 1 1
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 0 0
      vertex 0 1 1
      vertex 0 1 0
    endloop
  endfacet
  facet normal 1 0 0
    outer loop
      vertex 1 0 0
      vertex 1 1 0
      vertex 1 1 1
    endloop
  endfacet
  facet normal 1 0 0
    outer loop
      vertex 1 0 0
      vertex 1 1 1
      vertex 1 0 1
    endloop
  endfacet
endsolid cube
"""


class ControlledCubeError(RuntimeError):
    """The example cannot safely finish or validate its exact target."""


@dataclass(frozen=True)
class ArchiveSummary:
    members: int
    uncompressed_bytes: int
    boundary_bytes: int
    project_foam_bytes: int


@dataclass(frozen=True)
class _CameraRollScalar:
    line_index: int
    start: int
    end: int
    value: float


def config_camera_roll(content: str) -> float:
    """Read the one finite CONFIG-camera roll from scene-settings YAML."""

    _lines, scalar = _config_camera_roll_scalar(content)
    return scalar.value


def rotate_config_camera(content: str) -> str:
    """Set the CONFIG-camera roll while preserving every other YAML byte."""

    lines, scalar = _config_camera_roll_scalar(content)
    line = lines[scalar.line_index]
    lines[scalar.line_index] = (
        line[: scalar.start] + f"{CONFIG_CAMERA_ROLL_DEGREES:.1f}" + line[scalar.end :]
    )
    return "".join(lines)


def _config_camera_roll_scalar(content: str) -> tuple[list[str], _CameraRollScalar]:
    if not isinstance(content, str) or not content or "\0" in content:
        raise ControlledCubeError(_camera_roll_contract_error())

    lines = content.splitlines(keepends=True)
    stack: list[tuple[int, str]] = []
    matches: list[_CameraRollScalar] = []
    scalar_indent: int | None = None
    for line_index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        stripped = body.strip()
        indent = len(body) - len(body.lstrip(" "))
        if scalar_indent is not None:
            if not stripped or indent > scalar_indent:
                continue
            scalar_indent = None
        if not stripped or body.lstrip().startswith("#"):
            continue
        if indent == 0 and (
            stripped == "---"
            or stripped == "..."
            or stripped.startswith("%YAML ")
            or stripped.startswith("%TAG ")
        ):
            stack.clear()
            continue
        mapping = _YAML_MAPPING_LINE.fullmatch(body)
        if mapping is None:
            continue

        indent = len(mapping.group("indent"))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key = mapping.group("key")
        path = (*[ancestor for _level, ancestor in stack], key)
        rest = mapping.group("rest")

        if path == _CONFIG_CAMERA_ROLL_PATH:
            scalar = _YAML_NUMBER.fullmatch(rest)
            if scalar is None:
                raise ControlledCubeError(_camera_roll_contract_error())
            value = float(scalar.group("number"))
            if not math.isfinite(value):
                raise ControlledCubeError(_camera_roll_contract_error())
            matches.append(
                _CameraRollScalar(
                    line_index=line_index,
                    start=mapping.start("rest") + scalar.start("number"),
                    end=mapping.start("rest") + scalar.end("number"),
                    value=value,
                )
            )

        if not rest.strip() or rest.lstrip().startswith("#"):
            stack.append((indent, key))
        else:
            # YAML permits block, quoted, and plain scalar values to continue on
            # later indented lines. None of those lines are child mappings.
            scalar_indent = indent

    if len(matches) != 1:
        raise ControlledCubeError(_camera_roll_contract_error())
    return lines, matches[0]


def _camera_roll_contract_error() -> str:
    return (
        f"{SCENE_SETTINGS_PATH} must contain exactly one finite numeric "
        "sceneSettings.config.camera.roll value."
    )


def wait_for_finished(
    get_status: Callable[[], dh.RunStatus],
    *,
    timeout_seconds: float,
    poll_seconds: float,
    on_status: Callable[[dh.RunStatus], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dh.RunStatus:
    """Poll one known run to FINISHED, with a strict monotonic deadline."""

    if not 0 < poll_seconds <= timeout_seconds:
        raise ValueError("poll_seconds must be positive and no greater than timeout_seconds")
    deadline = monotonic() + timeout_seconds
    status = get_status()
    while True:
        observed_at = monotonic()
        if observed_at > deadline:
            raise ControlledCubeError(
                f"Run {status.run_id} did not finish within {timeout_seconds:g} seconds."
            )
        if on_status is not None:
            on_status(status)
        if status.state is dh.RunState.FINISHED:
            return status
        if status.state in TERMINAL_RUN_STATES:
            raise ControlledCubeError(
                f"Run {status.run_id} ended in {status.state.value} before successful completion."
            )
        remaining = deadline - observed_at
        if remaining <= 0:
            raise ControlledCubeError(
                f"Run {status.run_id} did not finish within {timeout_seconds:g} seconds."
            )
        sleep(min(poll_seconds, remaining))
        if monotonic() >= deadline:
            raise ControlledCubeError(
                f"Run {status.run_id} did not finish within {timeout_seconds:g} seconds."
            )
        status = get_status()


def wait_for_terminal(
    get_status: Callable[[], dh.RunStatus],
    *,
    timeout_seconds: float,
    poll_seconds: float,
    on_status: Callable[[dh.RunStatus], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dh.RunStatus:
    """Poll one known run to any terminal state for bounded cleanup."""

    if not 0 < poll_seconds <= timeout_seconds:
        raise ValueError("poll_seconds must be positive and no greater than timeout_seconds")
    deadline = monotonic() + timeout_seconds
    status = get_status()
    while True:
        observed_at = monotonic()
        if observed_at > deadline:
            raise ControlledCubeError(
                f"Run {status.run_id} did not stop within {timeout_seconds:g} seconds."
            )
        if on_status is not None:
            on_status(status)
        if status.state in TERMINAL_RUN_STATES:
            return status
        remaining = deadline - observed_at
        if remaining <= 0:
            raise ControlledCubeError(
                f"Run {status.run_id} did not stop within {timeout_seconds:g} seconds."
            )
        sleep(min(poll_seconds, remaining))
        if monotonic() >= deadline:
            raise ControlledCubeError(
                f"Run {status.run_id} did not stop within {timeout_seconds:g} seconds."
            )
        status = get_status()


def validate_result_archive(path: Path) -> ArchiveSummary:
    """Validate result members and CRCs without extracting server-controlled paths."""

    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_RESULT_MEMBERS:
                raise ControlledCubeError("Result ZIP has an invalid member count.")

            by_name: dict[str, zipfile.ZipInfo] = {}
            total = 0
            for info in infos:
                name = _safe_archive_name(info)
                if name in by_name:
                    raise ControlledCubeError(f"Result ZIP repeats member {name!r}.")
                by_name[name] = info
                total += info.file_size
                if total > MAX_RESULT_ARCHIVE_BYTES:
                    raise ControlledCubeError("Result ZIP expands beyond the example safety limit.")
                if any(part.casefold() == "vtk" for part in name.rstrip("/").split("/")):
                    raise ControlledCubeError("Result ZIP unexpectedly contains VTK output.")

            boundary = by_name.get("case/constant/polyMesh/boundary")
            project_foam = by_name.get("case/project.foam")
            if boundary is None or boundary.file_size == 0:
                raise ControlledCubeError(
                    "Result ZIP has no non-empty case/constant/polyMesh/boundary file."
                )
            if project_foam is None or project_foam.is_dir():
                raise ControlledCubeError("Result ZIP has no case/project.foam marker.")

            corrupt_name = archive.testzip()
            if corrupt_name is not None:
                raise ControlledCubeError(f"Result ZIP failed CRC validation at {corrupt_name!r}.")
            return ArchiveSummary(
                members=len(infos),
                uncompressed_bytes=total,
                boundary_bytes=boundary.file_size,
                project_foam_bytes=project_foam.file_size,
            )
    except zipfile.BadZipFile as error:
        raise ControlledCubeError("dicehub returned an invalid result ZIP.") from error


def _safe_archive_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not name or "\x00" in name or "\\" in name or name.startswith("/"):
        raise ControlledCubeError(f"Result ZIP contains unsafe member {name!r}.")
    parts = name.split("/")
    if info.is_dir():
        parts = parts[:-1]
    if not parts or any(not part or part in {".", ".."} or ":" in part for part in parts):
        raise ControlledCubeError(f"Result ZIP contains unsafe member {name!r}.")
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) == stat.S_IFLNK or info.flag_bits & 0x1:
        raise ControlledCubeError(f"Result ZIP contains unsupported member {name!r}.")
    return name
