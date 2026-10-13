from asteria.assets import AssetRef
from asteria.core.ids import new_id
from asteria.graphics import (
    DirectionalClips,
    SpriteClip,
    SpriteFrame,
    SpriteKeyframe,
    SpriteSheet,
    TileLayer,
    TileMap,
)
from asteria.runtime import (
    AnimatorState,
    Camera2D,
    CameraFollow2D,
    CharacterAnimationController,
    CharacterController2D,
    InputSnapshot,
    PlayerRuntime,
    SpriteRendererState,
    TileMapQuery,
)


def test_character_animation_camera_runtime():
    tex = AssetRef(new_id(), "texture")
    sheet = SpriteSheet(tex, [SpriteFrame(0, 0, 16, 16) for _ in range(8)])
    dirs = ("down", "left", "right", "up")

    def c(name, i):
        return SpriteClip(name, [SpriteKeyframe(i, 0.1)], True)

    clips = DirectionalClips(
        {d: c("idle_" + d, i) for i, d in enumerate(dirs)},
        {d: c("walk_" + d, i + 4) for i, d in enumerate(dirs)},
    )
    tm = TileMap(
        AssetRef(new_id(), "tileset"),
        16,
        16,
        8,
        8,
        [TileLayer("col", collision_enabled=True)],
    )
    ctrl = CharacterController2D(32, 32, 32, 4, 4)
    a = AnimatorState(clips.idle["down"])
    ac = CharacterAnimationController(clips, a)
    spr = SpriteRendererState("hero", sheet.frames)
    cam = Camera2D(0, 0, 160, 90, 1)
    follow = CameraFollow2D(cam)
    p = PlayerRuntime(ctrl, TileMapQuery(tm), a, ac, spr, follow)
    p.update(InputSnapshot({"move_right": 1}), 0.1)
    assert ac.facing == "right" and spr.frame_index == 6
