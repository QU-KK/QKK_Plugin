from __future__ import annotations

import struct
import zlib


MAGIC = b"FYRRPQ01"
VERSION = 2
COMPRESSED_MAGIC = b"MBCOMP01"


def fnv1a64(data: bytes | bytearray) -> int:
    value = 14695981039346656037
    for byte in data:
        value ^= byte
        value = (value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return value


def string_block(value) -> bytes:
    encoded = str(value).encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def serialize_request(
    *, generation: int, quality: int, baseline_manifest_path, preview_output_path,
    active_map_uuid: str, width: int, height: int, margin: int,
    anti_aliasing_scale: int, bit_depth: int, image_format: str, groups,
) -> bytes:
    raw = bytearray(MAGIC)
    raw += struct.pack("<IQI", VERSION, generation, quality)
    raw += string_block(baseline_manifest_path)
    raw += string_block(preview_output_path)
    raw += string_block(active_map_uuid)
    raw += struct.pack("<iiiii", width, height, margin, anti_aliasing_scale, bit_depth)
    raw += string_block(image_format)
    raw += struct.pack("<I", len(groups))
    for group_name, meshes in groups:
        raw += string_block(group_name)
        raw += struct.pack("<I", len(meshes))
        for object_name, surface_signature, uvs in meshes:
            raw += string_block(object_name) + string_block(surface_signature) + string_block("")
            raw += struct.pack("<I", len(uvs) // 2)
            if uvs:
                raw += struct.pack(f"<{len(uvs)}f", *uvs)
    raw += struct.pack("<Q", fnv1a64(raw))
    compressed = zlib.compress(bytes(raw))
    if len(compressed) < len(raw) * 0.95:
        return COMPRESSED_MAGIC + struct.pack("<IQ", 0, len(raw)) + compressed
    return bytes(raw)


def decompress_request(data: bytes) -> bytes:
    if not data.startswith(COMPRESSED_MAGIC):
        return data
    compression_type, size = struct.unpack_from("<IQ", data, 8)
    if compression_type != 0:
        raise ValueError("unsupported reprojection compression")
    raw = zlib.decompress(data[20:])
    if len(raw) != size:
        raise ValueError("reprojection request size mismatch")
    return raw
