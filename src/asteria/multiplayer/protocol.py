"""Versioned JSON-line wire format for Asteria multiplayer sessions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 64 * 1024
MAX_DISPLAY_NAME = 40
MAX_COMMAND_NAME = 80


class ProtocolError(ValueError):
    """A message is malformed or incompatible with this protocol version."""


def message(kind: str, **fields: Any) -> dict[str, Any]:
    kind = str(kind).strip()
    if not kind:
        raise ProtocolError("message type is required")
    return {"protocol": PROTOCOL_VERSION, "type": kind, **fields}


def encode_frame(value: Mapping[str, Any]) -> bytes:
    if not isinstance(value, Mapping):
        raise ProtocolError("message must be an object")
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError(
            f"message is not JSON serializable or contains non-finite numbers: {exc}"
        ) from exc
    if len(encoded) > MAX_FRAME_BYTES:
        raise ProtocolError(f"message exceeds {MAX_FRAME_BYTES} bytes")
    return encoded + b"\n"


def decode_frame(frame: bytes | str) -> dict[str, Any]:
    if isinstance(frame, bytes):
        if len(frame) > MAX_FRAME_BYTES:
            raise ProtocolError(f"message exceeds {MAX_FRAME_BYTES} bytes")
        try:
            text = frame.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ProtocolError("message must be UTF-8") from exc
    elif isinstance(frame, str):
        text = frame.strip()
        if len(text.encode("utf-8")) > MAX_FRAME_BYTES:
            raise ProtocolError(f"message exceeds {MAX_FRAME_BYTES} bytes")
    else:
        raise ProtocolError("message frame must be bytes or text")
    try:
        value = json.loads(text, parse_constant=_reject_json_constant)
    except ProtocolError:
        raise
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ProtocolError("message must be a JSON object")
    if value.get("protocol") != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version: {value.get('protocol')!r}")
    if not isinstance(value.get("type"), str) or not value["type"].strip():
        raise ProtocolError("message type is required")
    return value


def _reject_json_constant(value: str):
    raise ProtocolError(f"non-finite number is not allowed: {value}")


def clean_display_name(value: object) -> str:
    name = "".join(char for char in str(value) if char.isprintable()).strip()
    name = name[:MAX_DISPLAY_NAME]
    return name or "Player"


def clean_guest_id(value: object) -> str:
    """Validate the optional persistent guest key; it does not authenticate a user."""
    if not isinstance(value, str):
        raise ValueError("guest_id must be text")
    guest_id = value.strip()
    if not 1 <= len(guest_id) <= 64 or any(
        not (char.isascii() and (char.isalnum() or char in "-_")) for char in guest_id
    ):
        raise ValueError("guest_id must be 1-64 ASCII letters, digits, '-' or '_'")
    return guest_id
