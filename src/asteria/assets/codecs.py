"""Extensible typed asset codec registry; no central kind switch."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .package import AssetManifest, manifest_from_dict


@dataclass(frozen=True, slots=True)
class AssetDocument:
    manifest: AssetManifest
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AssetCodec:
    kind: str
    decode: Callable[[AssetDocument], Any]
    encode: Callable[[Any], Mapping[str, Any]]


class AssetCodecRegistry:
    def __init__(self):
        self._codecs = {}

    def register(self, codec: AssetCodec, replace=False):
        if not codec.kind:
            raise ValueError("kind")
        if codec.kind in self._codecs and not replace:
            raise KeyError(codec.kind)
        self._codecs[codec.kind] = codec
        return codec

    def unregister(self, kind):
        return self._codecs.pop(kind)

    def codec(self, kind):
        return self._codecs[kind]

    def decode_document(self, data: Mapping[str, Any]):
        manifest = manifest_from_dict(data)
        payload = data.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ValueError("payload must be mapping")
        return self.codec(manifest.kind).decode(AssetDocument(manifest, payload))

    def encode_asset(self, kind, obj):
        c = self.codec(kind)
        return dict(c.encode(obj))

    def kinds(self):
        return tuple(sorted(self._codecs))


def passthrough_codec(kind):
    def dec(doc):
        return {"manifest": doc.manifest, "payload": dict(doc.payload)}

    def enc(obj):
        return dict(obj)

    return AssetCodec(kind, dec, enc)


def install_common_passthrough_codecs(registry):
    for kind in (
        "character",
        "monster",
        "tileset",
        "prop",
        "icon",
        "portrait",
        "vfx",
        "audio",
        "font",
        "material",
    ):
        registry.register(passthrough_codec(kind))
    return registry
