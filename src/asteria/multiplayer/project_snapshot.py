"""Bounded scene snapshot compression within the existing JSON-line wire format."""

from __future__ import annotations

import base64
import binascii
import json
import zlib
from collections.abc import Mapping

MAX_SCENE_BYTES = 1024 * 1024
ENCODING = "asteria.scene.zlib.v1"


def pack_scene_data(value: Mapping) -> dict:
    raw = json.dumps(dict(value), separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > MAX_SCENE_BYTES:
        raise ValueError("scene snapshot exceeds decoded size limit")
    return {"encoding": ENCODING, "data": base64.b64encode(zlib.compress(raw)).decode("ascii")}


def unpack_scene_data(value: Mapping) -> dict:
    if not isinstance(value, Mapping):
        raise ValueError("scene snapshot must be an object")
    if value.get("encoding") != ENCODING:
        if value.get("schema") != "asteria.scene":
            raise ValueError("unsupported scene snapshot encoding")
        return dict(value)
    try:
        encoded = value["data"]
        if not isinstance(encoded, str) or len(encoded) > MAX_SCENE_BYTES:
            raise ValueError("invalid packed scene")
        decoder = zlib.decompressobj()
        raw = decoder.decompress(base64.b64decode(encoded, validate=True), MAX_SCENE_BYTES + 1)
        if (
            len(raw) > MAX_SCENE_BYTES
            or decoder.unconsumed_tail
            or not decoder.eof
            or decoder.unused_data
        ):
            raise ValueError("invalid or oversized scene snapshot")
        result = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        if not isinstance(result, dict) or result.get("schema") != "asteria.scene":
            raise ValueError("decoded scene is invalid")
        return result
    except (KeyError, binascii.Error, zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid packed scene snapshot") from exc
