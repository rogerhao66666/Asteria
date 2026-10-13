from asteria.assets import (
    AssetCodecRegistry,
    AssetDocument,
    install_common_passthrough_codecs,
    install_complex_typed_codecs,
    install_simple_typed_codecs,
    manifest_from_dict,
    passthrough_codec,
)


def reg():
    return install_complex_typed_codecs(
        install_simple_typed_codecs(install_common_passthrough_codecs(AssetCodecRegistry()))
    )


def D(kind, payload):
    return {
        "schema_version": 3,
        "asset_id": f"{kind}/x",
        "kind": kind,
        "source": f"{kind}/x",
        "tags": ["hf"],
        "metadata": {"m": 1},
        "payload": payload,
    }


def clip(name="fx", size=(777, 333), n=5):
    return {
        "name": name,
        "frame_size": list(size),
        "frames": [f"{i}.png" for i in range(n)],
        "timings": [{"duration_ms": 8 + i * 3} for i in range(n)],
        "pivot": [100.25, 300.75],
        "layers": [
            {"name": "core", "z": 2, "blend_mode": "add", "opacity": 0.7, "material": "mat/glow"}
        ],
        "loop": True,
    }


def rt(kind, d):
    r = reg()
    a = r.decode_document(d)
    p = r.encode_asset(kind, a)
    m = manifest_from_dict({k: v for k, v in d.items() if k != "payload"})
    return a, r.codec(kind).decode(AssetDocument(m, p))


def test_tileset_roundtrip():
    p = {
        "image_size": [71, 71],
        "tile_size": [32, 32],
        "columns": 2,
        "rows": 2,
        "margin": 2,
        "spacing": 3,
        "tiles": [
            {
                "tile_id": 1,
                "terrain": "water",
                "collision": {"kind": "polygon", "points": [[0, 0], [1, 0], [1, 1]]},
                "properties": {"wet": True},
                "animation": [1, 2],
                "frame_ms": 120,
            }
        ],
    }
    a, b = rt("tileset", D("tileset", p))
    assert b.tile(1).terrain == "water" and b.spacing == 3


def test_monster_hf_roundtrip():
    p = {
        "animations": [{"name": "project.roar", "clip": clip(), "directions": ["burrow", "sky"]}],
        "default_animation": "project.roar",
        "collision_bounds": [-1, -2, 3, 4],
        "anchor": [0.5, 0.9],
    }
    a, b = rt("monster", D("monster", p))
    c = b.animation("project.roar").clip
    assert c.frame_size == (777, 333) and c.pivot == (100.25, 300.75)


def test_monster_timing_preserved():
    p = {"animations": [{"name": "x", "clip": clip()}], "default_animation": "x"}
    a, b = rt("monster", D("monster", p))
    assert [x.duration_ms for x in b.animation("x").clip.timings] == [8, 11, 14, 17, 20]


def test_monster_layers_preserved():
    p = {"animations": [{"name": "x", "clip": clip()}], "default_animation": "x"}
    a, b = rt("monster", D("monster", p))
    l = b.animation("x").clip.layers[0]
    assert (l.blend_mode, l.opacity, l.material) == ("add", 0.7, "mat/glow")


def test_vfx_roundtrip():
    p = {
        "variants": [
            {
                "name": "charged",
                "clip": clip("charged", (1536, 768), 12),
                "anchor": {"mode": "socket", "offset": [2.5, -1], "bone_or_socket": "weapon_tip"},
                "scale": [2, 0.5],
                "rotation_deg": 37,
                "properties": {"x": 1},
            }
        ],
        "default_variant": "charged",
        "presentation_tags": ["project.any"],
        "properties": {"quality": "high"},
    }
    a, b = rt("vfx", D("vfx", p))
    v = b.variant()
    assert (
        v.anchor.bone_or_socket == "weapon_tip"
        and v.rotation_deg == 37
        and len(v.clip.frames) == 12
    )


def test_manifest_preserved():
    p = {"animations": [{"name": "x", "clip": clip()}], "default_animation": "x"}
    a, b = rt("monster", D("monster", p))
    assert b.canonical.version == 3 and b.canonical.meta()["m"] == 1 and "hf" in b.canonical.tags


def test_registry_all_typed():
    r = reg()
    assert all(
        r.codec(k)
        for k in (
            "icon",
            "portrait",
            "audio",
            "font",
            "material",
            "prop",
            "tileset",
            "monster",
            "vfx",
        )
    )


def test_project_extension_survives():
    r = reg()
    r.register(passthrough_codec("project.future"))
    assert r.decode_document(D("project.future", {"x": 1}))["payload"]["x"] == 1


def test_large_monster_clip():
    p = {
        "animations": [{"name": "boss", "clip": clip("boss", (4096, 2048), 240)}],
        "default_animation": "boss",
    }
    a, b = rt("monster", D("monster", p))
    assert len(b.animation("boss").clip.frames) == 240


def test_100_vfx_variants():
    p = {
        "variants": [{"name": f"v{i}", "clip": clip(f"v{i}", n=3)} for i in range(100)],
        "default_variant": "v0",
    }
    a, b = rt("vfx", D("vfx", p))
    assert len(b.variants) == 100


def test_65536_tile_grid():
    p = {"image_size": [4096, 4096], "tile_size": [16, 16], "columns": 256, "rows": 256}
    a, b = rt("tileset", D("tileset", p))
    assert b.columns * b.rows == 65536


def test_1000_roundtrips():
    r = reg()
    manifest_from_dict({k: v for k, v in D("monster", {}).items() if k != "payload"})
    for i in range(1000):
        p = {"animations": [{"name": "x", "clip": clip(f"c{i}", n=3)}], "default_animation": "x"}
        d = D("monster", p)
        a = r.decode_document(d)
        out = r.encode_asset("monster", a)
        assert out["animations"][0]["clip"]["name"] == f"c{i}"
