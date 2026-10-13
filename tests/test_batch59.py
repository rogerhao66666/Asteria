from asteria.assets import (
    AssetSource,
    AtlasRegion,
    AudioAsset,
    CanonicalAsset,
    FontAsset,
    FrameTiming,
    HighFidelityClip,
    IconAsset,
    IconVariant,
    MaterialAsset,
    MonsterAnimation,
    MonsterAsset,
    PortraitAsset,
    PortraitVariant,
    VFXAnchor,
    VFXAsset,
    VFXVariant,
    VisualLayer,
    audio_request,
    clip_request,
    font_request,
    icon_request,
    material_request,
    monster_clip_request,
    portrait_request,
    vfx_request,
)


def C(a, k):
    return CanonicalAsset(a, k, AssetSource("src"))


def CL():
    return HighFidelityClip(
        "c",
        (4096, 2048),
        tuple(f"f{i}.png" for i in range(240)),
        tuple(FrameTiming(7 + i % 5) for i in range(240)),
        (123.25, 1999.75),
        (VisualLayer("body", 3, "screen", 0.75, "mat/glow"),),
        True,
    )


def test_audio():
    a = AudioAsset(
        C("a", "audio"), "a.flac", 1234.5, 2, 96000, (100.25, 900.75), (("stream", True),)
    )
    q = audio_request(a)
    assert q.sample_rate == 96000 and q.loop_region_ms == (100.25, 900.75)


def test_font():
    a = FontAsset(C("f", "font"), "f.otf", "Family", ("fa", "fb"), ())
    assert font_request(a).fallback_asset_ids == ("fa", "fb")


def test_material():
    a = MaterialAsset(
        C("m", "material"), "shader/custom", (("glow", 2.75),), (("albedo", "tex/a"),), ()
    )
    assert material_request(a).parameters[0][1] == 2.75


def test_icon():
    v = IconVariant("hi", image_uri="x.png", size=(512, 256), metadata=(("dpi", 4),))
    a = IconAsset(C("i", "icon"), (v,), "hi")
    assert icon_request(a).size == (512, 256)


def test_atlas():
    at = AtlasRegion("atlas.png", 3, 7, 128, 96)
    v = IconVariant("a", atlas=at, size=(128, 96))
    a = IconAsset(C("i", "icon"), (v,), "a")
    assert icon_request(a).region == (3, 7, 128, 96)


def test_portrait():
    v = PortraitVariant("happy", "p.png", (2048, 3072), (0.4, 0.3), None, (("e", "happy"),))
    a = PortraitAsset(C("p", "portrait"), (v,), "happy")
    assert portrait_request(a).size == (2048, 3072)


def test_clip():
    q = clip_request("x", "u", CL())
    assert q.frame_size == (4096, 2048) and q.frame_count == 240 and q.pivot == (123.25, 1999.75)


def test_timing():
    assert clip_request("x", "c", CL()).frame_durations_ms[:5] == (7, 8, 9, 10, 11)


def test_layer():
    l = clip_request("x", "c", CL()).layers[0]
    assert (l.z, l.opacity, l.blend_mode, l.material) == (3, 0.75, "screen", "mat/glow")


def test_monster():
    ma = MonsterAnimation("user_xyz", CL())
    a = MonsterAsset(C("boss", "monster"), (ma,), "user_xyz")
    assert monster_clip_request(a).clip_name == "user_xyz"


def test_vfx():
    v = VFXVariant(
        "cin",
        CL(),
        VFXAnchor("socket", (1.25, -2.5), "weapon_tip"),
        (2.0, 0.5),
        37.25,
        (("x", 9),),
    )
    a = VFXAsset(C("fx", "vfx"), (v,), "cin")
    q = vfx_request(a)
    assert q.socket == "weapon_tip" and q.rotation_deg == 37.25


def test_10000():
    a = AudioAsset(C("a", "audio"), "a.wav", None, 2, 48000, None, ())
    assert len([audio_request(a) for _ in range(10000)]) == 10000
