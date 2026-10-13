"""Typed codecs for simple canonical asset families."""

from .codecs import AssetCodec
from .icon import AtlasRegion, IconAsset, IconVariant
from .portrait import NormalizedRect, PortraitAsset, PortraitVariant
from .prop import CollisionShape, InteractionPoint, PropAsset, PropVisual
from .resources import AudioAsset, FontAsset, MaterialAsset


def _canon(doc):
    return doc.manifest.canonical()


def _pairs(d):
    return tuple(sorted((d or {}).items()))


def icon_codec():
    def dec(d):
        vs = []
        for v in d.payload["variants"]:
            a = v.get("atlas")
            ar = AtlasRegion(**a) if a else None
            vs.append(
                IconVariant(
                    v["name"],
                    v.get("image_uri"),
                    ar,
                    tuple(v["size"]) if v.get("size") else None,
                    _pairs(v.get("metadata")),
                )
            )
        return IconAsset(
            _canon(d),
            tuple(vs),
            d.payload["default_variant"],
            frozenset(d.payload.get("usages", ())),
            _pairs(d.payload.get("properties")),
        )

    def enc(a):
        return {
            "variants": [
                {
                    "name": v.name,
                    "image_uri": v.image_uri,
                    "atlas": (
                        {
                            "image_uri": v.atlas.image_uri,
                            "x": v.atlas.x,
                            "y": v.atlas.y,
                            "width": v.atlas.width,
                            "height": v.atlas.height,
                        }
                        if v.atlas
                        else None
                    ),
                    "size": list(v.size) if v.size else None,
                    "metadata": dict(v.metadata),
                }
                for v in a.variants
            ],
            "default_variant": a.default_variant,
            "usages": sorted(a.usages),
            "properties": dict(a.properties),
        }

    return AssetCodec("icon", dec, enc)


def portrait_codec():
    def dec(d):
        vs = []
        for v in d.payload["variants"]:
            c = v.get("safe_crop")
            crop = NormalizedRect(**c) if c else None
            vs.append(
                PortraitVariant(
                    v["name"],
                    v["image_uri"],
                    tuple(v["size"]),
                    tuple(v.get("focal_point", (0.5, 0.5))),
                    crop,
                    _pairs(v.get("metadata")),
                )
            )
        return PortraitAsset(
            _canon(d),
            tuple(vs),
            d.payload["default_variant"],
            d.payload.get("subject_ref"),
            _pairs(d.payload.get("properties")),
        )

    def enc(a):
        return {
            "variants": [
                {
                    "name": v.name,
                    "image_uri": v.image_uri,
                    "size": list(v.size),
                    "focal_point": list(v.focal_point),
                    "safe_crop": (
                        {
                            "x": v.safe_crop.x,
                            "y": v.safe_crop.y,
                            "width": v.safe_crop.width,
                            "height": v.safe_crop.height,
                        }
                        if v.safe_crop
                        else None
                    ),
                    "metadata": dict(v.metadata),
                }
                for v in a.variants
            ],
            "default_variant": a.default_variant,
            "subject_ref": a.subject_ref,
            "properties": dict(a.properties),
        }

    return AssetCodec("portrait", dec, enc)


def audio_codec():
    def dec(d):
        p = d.payload
        return AudioAsset(
            _canon(d),
            p["uri"],
            p.get("duration_ms"),
            p.get("channels"),
            p.get("sample_rate"),
            tuple(p["loop_region_ms"]) if p.get("loop_region_ms") else None,
            _pairs(p.get("properties")),
        )

    def enc(a):
        return {
            "uri": a.uri,
            "duration_ms": a.duration_ms,
            "channels": a.channels,
            "sample_rate": a.sample_rate,
            "loop_region_ms": list(a.loop_region_ms) if a.loop_region_ms else None,
            "properties": dict(a.properties),
        }

    return AssetCodec("audio", dec, enc)


def font_codec():
    def dec(d):
        p = d.payload
        return FontAsset(
            _canon(d),
            p["uri"],
            p.get("family_hint"),
            tuple(p.get("fallback_refs", ())),
            _pairs(p.get("properties")),
        )

    def enc(a):
        return {
            "uri": a.uri,
            "family_hint": a.family_hint,
            "fallback_refs": list(a.fallback_refs),
            "properties": dict(a.properties),
        }

    return AssetCodec("font", dec, enc)


def material_codec():
    def dec(d):
        p = d.payload
        return MaterialAsset(
            _canon(d),
            p["shader_ref"],
            _pairs(p.get("parameters")),
            _pairs(p.get("texture_refs")),
            _pairs(p.get("properties")),
        )

    def enc(a):
        return {
            "shader_ref": a.shader_ref,
            "parameters": dict(a.parameters),
            "texture_refs": dict(a.texture_refs),
            "properties": dict(a.properties),
        }

    return AssetCodec("material", dec, enc)


def prop_codec():
    def dec(d):
        p = d.payload
        vs = tuple(
            PropVisual(
                v["image_uri"],
                tuple(v["size"]),
                tuple(v["pivot"]),
                v.get("z_offset", 0),
                v.get("opacity", 1),
                v.get("material"),
            )
            for v in p.get("visuals", ())
        )
        cs = tuple(
            CollisionShape(
                c["kind"],
                tuple(tuple(x) for x in c.get("points", ())),
                tuple(c["size"]) if c.get("size") else None,
                tuple(c.get("offset", (0, 0))),
            )
            for c in p.get("collisions", ())
        )
        ins = tuple(
            InteractionPoint(
                x["name"],
                tuple(x["position"]),
                frozenset(x.get("tags", ())),
                _pairs(x.get("metadata")),
            )
            for x in p.get("interactions", ())
        )
        return PropAsset(
            _canon(d),
            vs,
            cs,
            ins,
            _pairs(p.get("properties")),
            p.get("animation_ref"),
            p.get("presentation_ref"),
        )

    def enc(a):
        return {
            "visuals": [
                {
                    "image_uri": v.image_uri,
                    "size": list(v.size),
                    "pivot": list(v.pivot),
                    "z_offset": v.z_offset,
                    "opacity": v.opacity,
                    "material": v.material,
                }
                for v in a.visuals
            ],
            "collisions": [
                {
                    "kind": c.kind,
                    "points": [list(x) for x in c.points],
                    "size": list(c.size) if c.size else None,
                    "offset": list(c.offset),
                }
                for c in a.collisions
            ],
            "interactions": [
                {
                    "name": x.name,
                    "position": list(x.position),
                    "tags": sorted(x.tags),
                    "metadata": dict(x.metadata),
                }
                for x in a.interactions
            ],
            "properties": dict(a.properties),
            "animation_ref": a.animation_ref,
            "presentation_ref": a.presentation_ref,
        }

    return AssetCodec("prop", dec, enc)


def install_simple_typed_codecs(r):
    for c in (
        icon_codec(),
        portrait_codec(),
        audio_codec(),
        font_codec(),
        material_codec(),
        prop_codec(),
    ):
        r.register(c, replace=True)
    return r
