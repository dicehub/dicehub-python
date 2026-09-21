from __future__ import annotations

import base64
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import pytest

import dicehub as dh
from examples import controlled_cube_workflow
from examples._controlled_cube import CUBE_STL, ControlledCubeError
from examples._controlled_cube_geometry import (
    GEOMETRY_VTP_PATH,
    GEOMETRY_YAML_PATH,
    refine_imported_geometry,
    validate_imported_geometry_yaml,
    validate_refined_geometry_yaml,
    verify_imported_geometry,
)
from examples._controlled_cube_vtp import MAX_GEOMETRY_VTP_BYTES, validate_cube_vtp

GEOMETRY_YAML = """cube.stl:
  type: triSurfaceMesh
  name: cube
  bounds:
    xmin: 0.0
    xmax: 1.0
    ymin: 0.0
    ymax: 1.0
    zmin: 0.0
    zmax: 1.0
  regions:
    cube:
      name: cube
  view:
    type: VTPFileCollection
    paths:
      cube: cube.stl/cube.vtp
    geometry:
      cube:
        type: VTPFileCollectionItem
  features:
    refineFeatureEdgesOnly: false
    levels:
      - [0, 0]
    includedAngle: 150
    writeObj: false
    extractionMethod: extractFromSurface
    subsetFeatures:
      nonManifoldEdges: true
      openEdges: true
  level: [0, 0]
"""

VALID_CUBE_VTP = (
    Path(__file__).parents[2] / "fixtures" / "controlled_cube" / "cube.vtp"
).read_bytes()
CUBE_POINT_VALUES = tuple(
    float(value)
    for line in CUBE_STL.decode("ascii").splitlines()
    if (parts := line.split())[:1] == ["vertex"]
    for value in parts[1:]
)


def _replace_payload(content: bytes, name: str, payload: str) -> bytes:
    root = ElementTree.fromstring(content)
    arrays = [item for item in root.iter("DataArray") if item.attrib.get("Name") == name]
    if name in {"connectivity", "offsets"}:
        polys = root.find("./PolyData/Piece/Polys")
        assert polys is not None
        arrays = [item for item in arrays if item in polys]
    assert len(arrays) == 1
    arrays[0].text = payload
    return ElementTree.tostring(root)


def _compressed_payload(
    raw: bytes,
    *,
    endian: str = "<",
    header_code: str = "I",
    declared_size: int | None = None,
) -> str:
    compressed = zlib.compress(raw)
    size = len(raw) if declared_size is None else declared_size
    header = struct.pack(f"{endian}4{header_code}", 1, 32768, size, len(compressed))
    return base64.b64encode(header).decode() + base64.b64encode(compressed).decode()


def _compressed_blocks_payload(raw_blocks: tuple[bytes, ...]) -> str:
    assert raw_blocks and len({len(block) for block in raw_blocks}) == 1
    compressed = tuple(zlib.compress(block) for block in raw_blocks)
    header = struct.pack(
        f"<{3 + len(compressed)}I",
        len(compressed),
        len(raw_blocks[0]),
        0,
        *(len(block) for block in compressed),
    )
    return base64.b64encode(header).decode() + base64.b64encode(b"".join(compressed)).decode()


def test_imported_geometry_yaml_requires_renderable_collection_and_bounds() -> None:
    validate_imported_geometry_yaml(GEOMETRY_YAML)


def test_refinement_update_changes_only_the_two_reviewed_values() -> None:
    refined = refine_imported_geometry(GEOMETRY_YAML)

    expected = GEOMETRY_YAML.replace("      - [0, 0]\n", "      - [0, 1]\n").replace(
        "  level: [0, 0]\n",
        "  level: [1, 1]\n",
    )
    assert refined == expected
    validate_refined_geometry_yaml(refined)


@pytest.mark.parametrize(
    "content",
    [
        GEOMETRY_YAML.replace("  level: [0, 0]\n", "  level: [0, 1]\n"),
        GEOMETRY_YAML.replace("      - [0, 0]\n", "      - [0, 1]\n"),
        GEOMETRY_YAML + "  level: [0, 0]\n",
    ],
)
def test_refinement_update_rejects_unexpected_or_duplicate_source_values(content: str) -> None:
    with pytest.raises(ControlledCubeError, match="geometry YAML"):
        refine_imported_geometry(content)


@pytest.mark.parametrize(
    "content",
    [
        GEOMETRY_YAML.replace("VTPFileCollection\n", "VTPFile\n"),
        GEOMETRY_YAML.replace("cube: cube.stl/cube.vtp\n", "cube: wrong.vtp\n"),
        GEOMETRY_YAML.replace("regions:\n    cube:\n      name: cube\n", "regions: {}\n"),
        GEOMETRY_YAML.replace("xmin: 0.0", "xmin: -1.0"),
        GEOMETRY_YAML.replace("xmax: 1.0", "xmax: 0.0"),
        GEOMETRY_YAML.replace("zmax: 1.0", "zmax: nan"),
    ],
)
def test_imported_geometry_yaml_rejects_non_renderable_or_invalid_output(content: str) -> None:
    with pytest.raises(ControlledCubeError, match="geometry YAML"):
        validate_imported_geometry_yaml(content)


@pytest.mark.parametrize(
    "content",
    [
        "wrapper: |\n" + "".join(f"  {line}\n" for line in GEOMETRY_YAML.splitlines()),
        "wrapper: >-\n" + "".join(f"  {line}\n" for line in GEOMETRY_YAML.splitlines()),
        "wrapper: continued\n" + "".join(f"  {line}\n" for line in GEOMETRY_YAML.splitlines()),
        "---\n" + GEOMETRY_YAML,
        "--- # second document\n" + GEOMETRY_YAML,
        GEOMETRY_YAML + "---\n" + GEOMETRY_YAML,
        GEOMETRY_YAML.replace("xmax: 1.0", "xmax: 9.0\n    xmax: 1.0"),
        GEOMETRY_YAML + "  type: triSurfaceMesh\n",
        GEOMETRY_YAML + '"cube.stl": {type: attacker}\n',
        GEOMETRY_YAML + "cube.stl: {type: attacker}\n",
        GEOMETRY_YAML.replace("      - [0, 0]\n", "      - [0, 1]\n"),
        GEOMETRY_YAML.replace("      - [0, 0]\n", '      - [0, 0]\n"cube.stl": {}\n'),
    ],
)
def test_imported_geometry_yaml_rejects_scalar_document_and_duplicate_impostors(
    content: str,
) -> None:
    with pytest.raises(ControlledCubeError, match="geometry YAML"):
        validate_imported_geometry_yaml(content)


def test_cube_vtp_requires_exact_polydata_piece_and_inline_payloads() -> None:
    validate_cube_vtp(VALID_CUBE_VTP)


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"<not-xml",
        VALID_CUBE_VTP.replace(b'type="PolyData"', b'type="UnstructuredGrid"'),
        VALID_CUBE_VTP.replace(b'NumberOfPoints="36"', b'NumberOfPoints="8"'),
        VALID_CUBE_VTP.replace(b'NumberOfVerts="0"', b'NumberOfVerts="1"'),
        VALID_CUBE_VTP.replace(b'NumberOfLines="0"', b'NumberOfLines="1"'),
        VALID_CUBE_VTP.replace(b'NumberOfStrips="0"', b'NumberOfStrips="1"'),
        VALID_CUBE_VTP.replace(b'NumberOfPolys="12"', b'NumberOfPolys="11"'),
        _replace_payload(VALID_CUBE_VTP, "Points", ""),
        _replace_payload(VALID_CUBE_VTP, "Points", "not-base64!"),
        _replace_payload(VALID_CUBE_VTP, "Points", "AA=="),
        VALID_CUBE_VTP.replace(
            b'Name="Points" NumberOfComponents="3" format="binary"',
            b'Name="Points" NumberOfComponents="3" format="binary" offset="99999999999999999"',
        ),
        VALID_CUBE_VTP.replace(
            b'Name="connectivity" format="binary" RangeMin="0"',
            b'Name="connectivity" format="binary" offset="99999999999999999" RangeMin="0"',
        ),
        VALID_CUBE_VTP.replace(
            b'Name="offsets" format="binary" RangeMin="3"',
            b'Name="offsets" format="binary" offset="99999999999999999" RangeMin="3"',
        ),
        VALID_CUBE_VTP.replace(
            b"</PointData>",
            b'<DataArray type="Float32" Name="bad" format="binary">AA==</DataArray></PointData>',
        ),
        VALID_CUBE_VTP.replace(
            b"</CellData>",
            b'<DataArray type="Float32" Name="bad" format="binary">AA==</DataArray></CellData>',
        ),
        VALID_CUBE_VTP.replace(
            b"</Piece>",
            b'<AppendedData encoding="base64">_notbase64!</AppendedData></Piece>',
        ),
        VALID_CUBE_VTP.replace(
            b"</InformationKey>",
            b'</InformationKey><AppendedData encoding="base64">_notbase64!</AppendedData>',
            1,
        ),
        VALID_CUBE_VTP.replace(b"</VTKFile>", b"<!-- <AppendedData --></VTKFile>"),
        VALID_CUBE_VTP.replace(
            b"</InformationKey>",
            b"</InformationKey><![CDATA[<AppendedData]]>",
            1,
        ),
        VALID_CUBE_VTP.replace(
            b"</VTKFile>",
            b'<?x value="<AppendedData"?></VTKFile>',
        ),
        VALID_CUBE_VTP.replace(b"</Points>", b"<Bogus /></Points>"),
        VALID_CUBE_VTP.replace(b"</Points>", b"<Points /></Points>"),
        VALID_CUBE_VTP.replace(b"</Piece>", b"</Piece><Piece />"),
        b'<!DOCTYPE VTKFile [<!ENTITY x "payload">]>\n' + VALID_CUBE_VTP,
        b"x" * (MAX_GEOMETRY_VTP_BYTES + 1),
    ],
)
def test_cube_vtp_rejects_empty_malformed_or_wrong_geometry(content: bytes) -> None:
    with pytest.raises(ControlledCubeError, match=r"cube VTP|VTK PolyData"):
        validate_cube_vtp(content)


@pytest.mark.parametrize(
    "content",
    [
        # The compression header promises four bytes but expands far beyond them.
        _replace_payload(
            VALID_CUBE_VTP,
            "Points",
            _compressed_payload(b"x" * 4096, declared_size=4),
        ),
        # The declared uncompressed size breaches the explicit one-MiB bound.
        _replace_payload(
            VALID_CUBE_VTP,
            "Points",
            _compressed_payload(b"x", declared_size=MAX_GEOMETRY_VTP_BYTES + 1),
        ),
        # A huge block count is rejected before its missing size table is read.
        _replace_payload(
            VALID_CUBE_VTP,
            "Points",
            base64.b64encode(struct.pack("<3I", 1025, 32768, 1)).decode() + "AA==",
        ),
        _replace_payload(
            VALID_CUBE_VTP,
            "Points",
            _compressed_payload(b"\x00" * (108 * 4)),
        ),
        _replace_payload(
            VALID_CUBE_VTP,
            "connectivity",
            _compressed_payload(struct.pack("<36q", *([0] * 36))),
        ),
        _replace_payload(
            VALID_CUBE_VTP,
            "offsets",
            _compressed_payload(struct.pack("<12q", *([3] * 12))),
        ),
    ],
)
def test_cube_vtp_rejects_header_bombs_and_wrong_decoded_arrays(content: bytes) -> None:
    with pytest.raises(ControlledCubeError, match="cube VTP"):
        validate_cube_vtp(content)


def test_cube_vtp_honors_default_uint32_header_type() -> None:
    validate_cube_vtp(VALID_CUBE_VTP.replace(b' header_type="UInt32"', b""))


def test_cube_vtp_decodes_multiple_full_compression_blocks() -> None:
    raw = struct.pack("<108f", *CUBE_POINT_VALUES)
    content = _replace_payload(
        VALID_CUBE_VTP,
        "Points",
        _compressed_blocks_payload((raw[:216], raw[216:])),
    )
    validate_cube_vtp(content)


def test_cube_vtp_accepts_float64_points_and_int32_indexes() -> None:
    root = ElementTree.fromstring(VALID_CUBE_VTP)
    polys = root.find("./PolyData/Piece/Polys")
    assert polys is not None
    formats = {
        "Points": ("Float64", "d", CUBE_POINT_VALUES),
        "connectivity": ("Int32", "i", tuple(range(36))),
        "offsets": ("Int32", "i", tuple(range(3, 37, 3))),
    }
    for array in root.iter("DataArray"):
        name = array.attrib.get("Name")
        if name not in formats or (name != "Points" and array not in polys):
            continue
        data_type, code, values = formats[name]
        array.set("type", data_type)
        array.text = _compressed_payload(struct.pack(f"<{len(values)}{code}", *values))
    validate_cube_vtp(ElementTree.tostring(root))


def test_cube_vtp_honors_big_endian_uint64_encoding() -> None:
    root = ElementTree.fromstring(VALID_CUBE_VTP)
    root.set("byte_order", "BigEndian")
    root.set("header_type", "UInt64")
    formats = {
        "Points": ("f", CUBE_POINT_VALUES),
        "connectivity": ("q", tuple(range(36))),
        "offsets": ("q", tuple(range(3, 37, 3))),
    }
    polys = root.find("./PolyData/Piece/Polys")
    assert polys is not None
    for array in root.iter("DataArray"):
        name = array.attrib.get("Name")
        if name not in formats or (name != "Points" and array not in polys):
            continue
        code, values = formats[name]
        raw = struct.pack(f">{len(values)}{code}", *values)
        array.text = _compressed_payload(raw, endian=">", header_code="Q")
    validate_cube_vtp(ElementTree.tostring(root))


@dataclass(frozen=True)
class _Page:
    entries: tuple[dh.ConfigContentEntry, ...]


class _FakeConfigs:
    def __init__(
        self,
        *,
        vtp_path: str = GEOMETRY_VTP_PATH,
        vtp_content: bytes = VALID_CUBE_VTP,
    ) -> None:
        self.vtp_path = vtp_path
        self.vtp_content = vtp_content
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_text(self, **kwargs: object) -> str:
        self.calls.append(("get_text", kwargs))
        return GEOMETRY_YAML

    def list_content(self, **kwargs: object) -> _Page:
        self.calls.append(("list_content", kwargs))
        return _Page(
            entries=(
                dh.ConfigContentEntry(
                    path=self.vtp_path,
                    resource_type=dh.ConfigContentType.FILE,
                ),
            )
        )

    def download_file(
        self,
        *,
        config_id: str,
        path: str,
        destination: object,
        max_bytes: int,
    ) -> int:
        self.calls.append(
            (
                "download_file",
                {
                    "config_id": config_id,
                    "path": path,
                    "max_bytes": max_bytes,
                },
            )
        )
        return destination.write(self.vtp_content)  # type: ignore[attr-defined,no-any-return]


class _FakeClient:
    def __init__(self, configs: _FakeConfigs) -> None:
        self.configs = configs


def test_workflow_verifies_generated_yaml_and_exact_vtp_content_path() -> None:
    configs = _FakeConfigs()

    geometry_yaml = verify_imported_geometry(
        _FakeClient(configs),  # type: ignore[arg-type]
        "403",
    )

    assert geometry_yaml == GEOMETRY_YAML
    assert configs.calls == [
        ("get_text", {"config_id": "403", "path": GEOMETRY_YAML_PATH}),
        (
            "list_content",
            {
                "config_id": "403",
                "area": dh.ConfigContentArea.FILES,
                "path": "VTK/cube.stl",
                "recursive": True,
                "limit": 50,
            },
        ),
        (
            "download_file",
            {
                "config_id": "403",
                "path": GEOMETRY_VTP_PATH,
                "max_bytes": MAX_GEOMETRY_VTP_BYTES,
            },
        ),
    ]


def test_workflow_rejects_missing_expected_vtp() -> None:
    configs = _FakeConfigs(vtp_path="VTK/cube.stl/other.vtp")

    with pytest.raises(ControlledCubeError, match="did not create"):
        verify_imported_geometry(
            _FakeClient(configs),  # type: ignore[arg-type]
            "403",
        )


def test_workflow_rejects_malformed_downloaded_vtp() -> None:
    configs = _FakeConfigs(vtp_content=b"<VTKFile />")

    with pytest.raises(ControlledCubeError, match="VTK PolyData"):
        verify_imported_geometry(
            _FakeClient(configs),  # type: ignore[arg-type]
            "403",
        )


class _RefinementConfigs:
    def __init__(self) -> None:
        self.content = GEOMETRY_YAML
        self.calls: list[tuple[str, str]] = []

    def set_text(self, *, config_id: str, path: str, content: str) -> None:
        assert config_id == "403"
        assert path == GEOMETRY_YAML_PATH
        self.calls.append(("set", path))
        self.content = content

    def get_text(self, *, config_id: str, path: str) -> str:
        assert config_id == "403"
        self.calls.append(("get", path))
        return self.content


def test_workflow_persists_and_verifies_refinement_update() -> None:
    configs = _RefinementConfigs()

    controlled_cube_workflow._configure_geometry_refinement(
        _FakeClient(configs),  # type: ignore[arg-type]
        "403",
        GEOMETRY_YAML,
    )

    assert configs.calls == [("set", GEOMETRY_YAML_PATH), ("get", GEOMETRY_YAML_PATH)]
    validate_refined_geometry_yaml(configs.content)
