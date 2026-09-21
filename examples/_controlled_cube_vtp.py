"""Bounded validation for the controlled-cube converter's VTP output."""

from __future__ import annotations

import base64
import binascii
import math
import struct
import zlib
from collections import Counter
from dataclasses import dataclass
from xml.etree import ElementTree

from examples._controlled_cube import CUBE_STL, ControlledCubeError

MAX_GEOMETRY_VTP_BYTES = 1024 * 1024
_MAX_COMPRESSED_BLOCKS = 1024
_ZLIB_COMPRESSOR = "vtkZLibDataCompressor"

_Point = tuple[float, float, float]
_Facet = tuple[_Point, _Point, _Point]


@dataclass(frozen=True)
class _BinaryFormat:
    endian: str
    header_code: str
    header_width: int


def validate_cube_vtp(content: bytes) -> None:
    """Validate bounded inline-binary data for the exact twelve cube facets."""

    if not isinstance(content, bytes) or not content or len(content) > MAX_GEOMETRY_VTP_BYTES:
        raise _invalid_vtp("is empty or too large")
    declarations = content.upper()
    if b"<!DOCTYPE" in declarations or b"<!ENTITY" in declarations:
        raise _invalid_vtp("contains unsupported XML declarations")
    # vtkXMLDataParser scans raw bytes for this exact token, including inside
    # comments, CDATA, and processing instructions, then abandons inline data.
    if b"<AppendedData" in content:
        raise _invalid_vtp("contains unsupported appended data")
    try:
        root = ElementTree.fromstring(content)
    except (ElementTree.ParseError, ValueError) as error:
        raise _invalid_vtp("is not valid XML") from error

    if any(element.tag == "AppendedData" for element in root.iter()):
        raise _invalid_vtp("contains unsupported appended data")
    if root.tag != "VTKFile" or root.attrib.get("type") != "PolyData":
        raise _invalid_vtp("is not VTK PolyData")
    binary_format = _binary_format(root)
    poly_data = list(root)
    if len(poly_data) != 1 or poly_data[0].tag != "PolyData":
        raise _invalid_vtp("has an invalid PolyData structure")
    pieces = list(poly_data[0])
    if len(pieces) != 1 or pieces[0].tag != "Piece":
        raise _invalid_vtp("must contain exactly one Piece")
    piece = pieces[0]
    expected_counts = {
        "NumberOfPoints": "36",
        "NumberOfVerts": "0",
        "NumberOfLines": "0",
        "NumberOfStrips": "0",
        "NumberOfPolys": "12",
    }
    if any(piece.attrib.get(name) != value for name, value in expected_counts.items()):
        raise _invalid_vtp("has unexpected point or polygon counts")

    expected_piece_children = (
        "PointData",
        "CellData",
        "Points",
        "Verts",
        "Lines",
        "Strips",
        "Polys",
    )
    if tuple(child.tag for child in piece) != expected_piece_children:
        raise _invalid_vtp("has unexpected Piece data")

    point_data = piece.findall("PointData")
    cell_data = piece.findall("CellData")
    if len(point_data) != 1 or len(cell_data) != 1 or list(point_data[0]) or list(cell_data[0]):
        raise _invalid_vtp("has unexpected point or cell attributes")
    points_elements = piece.findall("Points")
    polys_elements = piece.findall("Polys")
    if len(points_elements) != 1 or len(polys_elements) != 1:
        raise _invalid_vtp("is missing point or polygon data")
    point_arrays = list(points_elements[0])
    poly_arrays = list(polys_elements[0])
    if (
        len(point_arrays) != 1
        or point_arrays[0].tag != "DataArray"
        or len(poly_arrays) != 2
        or any(array.tag != "DataArray" for array in poly_arrays)
    ):
        raise _invalid_vtp("has invalid data arrays")

    point_values = _float_array(
        point_arrays[0],
        binary_format=binary_format,
        name="Points",
        components=3,
        value_count=108,
    )
    arrays_by_name = {array.attrib.get("Name"): array for array in poly_arrays}
    if set(arrays_by_name) != {"connectivity", "offsets"}:
        raise _invalid_vtp("has invalid polygon array names")
    connectivity = _integer_array(
        arrays_by_name["connectivity"],
        binary_format=binary_format,
        name="connectivity",
        value_count=36,
    )
    offsets = _integer_array(
        arrays_by_name["offsets"],
        binary_format=binary_format,
        name="offsets",
        value_count=12,
    )

    if connectivity != tuple(range(36)) or offsets != tuple(range(3, 37, 3)):
        raise _invalid_vtp("has invalid cube polygon indexing")
    if not all(math.isfinite(value) for value in point_values):
        raise _invalid_vtp("has non-finite cube points")
    points = tuple(
        (point_values[index], point_values[index + 1], point_values[index + 2])
        for index in range(0, len(point_values), 3)
    )
    facets = Counter(
        (points[index], points[index + 1], points[index + 2]) for index in range(0, len(points), 3)
    )
    if facets != Counter(_cube_stl_facets()):
        raise _invalid_vtp("does not contain the uploaded cube facets")


def _binary_format(root: ElementTree.Element) -> _BinaryFormat:
    byte_order = root.attrib.get("byte_order")
    if byte_order == "LittleEndian":
        endian = "<"
    elif byte_order == "BigEndian":
        endian = ">"
    else:
        raise _invalid_vtp("has an unsupported byte order")

    header_type = root.attrib.get("header_type", "UInt32")
    if header_type == "UInt32":
        header_code, header_width = "I", 4
    elif header_type == "UInt64":
        header_code, header_width = "Q", 8
    else:
        raise _invalid_vtp("has an unsupported binary header type")
    if root.attrib.get("compressor") != _ZLIB_COMPRESSOR:
        raise _invalid_vtp("has an unsupported compressor")
    return _BinaryFormat(endian=endian, header_code=header_code, header_width=header_width)


def _float_array(
    data_array: ElementTree.Element,
    *,
    binary_format: _BinaryFormat,
    name: str,
    components: int,
    value_count: int,
) -> tuple[float, ...]:
    data_type = data_array.attrib.get("type")
    codes = {"Float32": ("f", 4), "Float64": ("d", 8)}
    if (
        data_array.attrib.get("Name") != name
        or data_array.attrib.get("NumberOfComponents") != str(components)
        or data_type not in codes
    ):
        raise _invalid_vtp("has invalid point metadata")
    code, width = codes[data_type]
    raw = _array_bytes(data_array, binary_format)
    if len(raw) != value_count * width:
        raise _invalid_vtp("has an invalid point payload length")
    try:
        return tuple(
            float(value)
            for value in struct.unpack(f"{binary_format.endian}{value_count}{code}", raw)
        )
    except struct.error as error:
        raise _invalid_vtp("has an invalid point payload") from error


def _integer_array(
    data_array: ElementTree.Element,
    *,
    binary_format: _BinaryFormat,
    name: str,
    value_count: int,
) -> tuple[int, ...]:
    data_type = data_array.attrib.get("type")
    codes = {"Int32": ("i", 4), "Int64": ("q", 8)}
    if (
        data_array.attrib.get("Name") != name
        or data_array.attrib.get("NumberOfComponents", "1") != "1"
        or data_type not in codes
    ):
        raise _invalid_vtp("has invalid polygon metadata")
    code, width = codes[data_type]
    raw = _array_bytes(data_array, binary_format)
    if len(raw) != value_count * width:
        raise _invalid_vtp("has an invalid polygon payload length")
    try:
        return tuple(
            int(value) for value in struct.unpack(f"{binary_format.endian}{value_count}{code}", raw)
        )
    except struct.error as error:
        raise _invalid_vtp("has an invalid polygon payload") from error


def _array_bytes(data_array: ElementTree.Element, binary_format: _BinaryFormat) -> bytes:
    if (
        data_array.attrib.get("format") != "binary"
        or "offset" in data_array.attrib
        or data_array.text is None
    ):
        raise _invalid_vtp("has a missing inline-binary payload")
    return _decode_vtk_inline_binary(data_array.text, binary_format=binary_format)


def _decode_vtk_inline_binary(payload: str, *, binary_format: _BinaryFormat) -> bytes:
    """Decode one VTK zlib block stream without trusting its declared sizes."""

    try:
        encoded = "".join(payload.split()).encode("ascii")
    except UnicodeEncodeError as error:
        raise _invalid_vtp("has a non-ASCII binary payload") from error
    if not encoded or len(encoded) > 2 * MAX_GEOMETRY_VTP_BYTES:
        raise _invalid_vtp("has an invalid binary payload size")

    prefix_bytes = 3 * binary_format.header_width
    prefix_chars = _base64_length(prefix_bytes)
    prefix = _decode_base64(encoded[:prefix_chars], expected_bytes=prefix_bytes)
    try:
        initial = struct.unpack(f"{binary_format.endian}3{binary_format.header_code}", prefix)
    except struct.error as error:
        raise _invalid_vtp("has an invalid compression header") from error
    block_count = int(initial[0])
    if not 1 <= block_count <= _MAX_COMPRESSED_BLOCKS:
        raise _invalid_vtp("has an invalid compression block count")

    header_bytes = (3 + block_count) * binary_format.header_width
    header_chars = _base64_length(header_bytes)
    if header_chars >= len(encoded):
        raise _invalid_vtp("has a truncated compression header")
    header = _decode_base64(encoded[:header_chars], expected_bytes=header_bytes)
    try:
        values = struct.unpack(
            f"{binary_format.endian}{3 + block_count}{binary_format.header_code}", header
        )
    except struct.error as error:
        raise _invalid_vtp("has an invalid compression header") from error

    block_size = int(values[1])
    last_block_size = int(values[2])
    compressed_sizes = tuple(int(value) for value in values[3:])
    if (
        not 1 <= block_size <= MAX_GEOMETRY_VTP_BYTES
        or not 0 <= last_block_size <= block_size
        or any(not 1 <= size <= MAX_GEOMETRY_VTP_BYTES for size in compressed_sizes)
    ):
        raise _invalid_vtp("has invalid compression sizes")
    output_size = (block_count - 1) * block_size + (last_block_size or block_size)
    compressed_size = sum(compressed_sizes)
    if output_size > MAX_GEOMETRY_VTP_BYTES or compressed_size > MAX_GEOMETRY_VTP_BYTES:
        raise _invalid_vtp("exceeds bounded compression sizes")
    compressed = _decode_base64(encoded[header_chars:], expected_bytes=compressed_size)

    output = bytearray()
    start = 0
    for index, size in enumerate(compressed_sizes):
        expected = (
            block_size if index < block_count - 1 or last_block_size == 0 else last_block_size
        )
        output.extend(_decompress_block(compressed[start : start + size], expected=expected))
        start += size
    if len(output) != output_size:
        raise _invalid_vtp("has an inconsistent uncompressed size")
    return bytes(output)


def _decode_base64(encoded: bytes, *, expected_bytes: int) -> bytes:
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise _invalid_vtp("has malformed base64 data") from error
    if len(decoded) != expected_bytes:
        raise _invalid_vtp("has an inconsistent encoded size")
    return decoded


def _decompress_block(compressed: bytes, *, expected: int) -> bytes:
    decoder = zlib.decompressobj()
    try:
        output = decoder.decompress(compressed, expected + 1)
        if len(output) > expected or decoder.unconsumed_tail:
            raise _invalid_vtp("has an oversized compressed block")
        output += decoder.flush(expected + 1 - len(output))
    except zlib.error as error:
        raise _invalid_vtp("has invalid zlib data") from error
    if len(output) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise _invalid_vtp("has an inconsistent compressed block")
    return output


def _base64_length(byte_count: int) -> int:
    return 4 * ((byte_count + 2) // 3)


def _cube_stl_facets() -> tuple[_Facet, ...]:
    points: list[_Point] = []
    for line in CUBE_STL.decode("ascii").splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "vertex":
            points.append((float(parts[1]), float(parts[2]), float(parts[3])))
    if len(points) != 36:
        raise RuntimeError("The controlled cube STL fixture is invalid.")
    return tuple(
        (points[index], points[index + 1], points[index + 2]) for index in range(0, len(points), 3)
    )


def _invalid_vtp(detail: str) -> ControlledCubeError:
    return ControlledCubeError(f"Imported cube VTP {detail}.")
