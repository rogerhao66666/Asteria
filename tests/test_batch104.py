from asteria.presentation.actor_visual_layers import ActorVisualLayerTrack, FrameVisualLayer
from asteria.presentation.attachments import Socket, SocketRig, Transform2D


def rig():
    r = SocketRig()
    r.add(Socket("hand_r", default=Transform2D(x=24, y=20)))
    return r


def test_layers_can_be_clip_specific():
    track = ActorVisualLayerTrack(
        (
            FrameVisualLayer("slash.hand", clips=("slash",)),
            FrameVisualLayer("cast.hand", clips=("cast",)),
        )
    )
    assert [x.asset_id for x in track.resolve("slash", 0)] == ["slash.hand"]
    assert [x.asset_id for x in track.resolve("cast", 0)] == ["cast.hand"]


def test_layer_track_roundtrip():
    src = ActorVisualLayerTrack(
        (
            FrameVisualLayer(
                "hand",
                "fg",
                12.5,
                Transform2D(x=2, y=3, rotation_deg=9),
                frames=(1, 2),
                clips=("slash",),
            ),
        )
    )
    dst = ActorVisualLayerTrack.from_dict(src.to_dict())
    assert dst.layers == src.layers


def test_layer_track_is_generic_not_weapon_or_genre_specific():
    import inspect

    import asteria.presentation.actor_visual_layers as mod

    s = inspect.getsource(mod).lower()
    assert "if jrpg" not in s and "if arpg" not in s and "if sword" not in s
