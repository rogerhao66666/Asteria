from asteria.core import Component, Field, component_schema


@component_schema(
    type_name="asteria.SpriteRenderer2D",
    version=1,
    fields=(
        Field("sprite_sheet_asset_id", str, "", label="Sprite Sheet"),
        Field("frame_index", int, 0, minimum=0, label="Frame"),
        Field("layer", int, 0),
        Field("depth", float, 0.0),
        Field("elevation", float, 0.0),
        Field("opacity", float, 1.0, minimum=0.0, maximum=1.0),
        Field("flip_x", bool, False, label="Flip X"),
        Field("visible", bool, True),
    ),
)
class SpriteRenderer2D(Component):
    def __init__(self):
        super().__init__()
        self.sprite_sheet_asset_id = ""
        self.frame_index = 0
        self.layer = 0
        self.depth = 0.0
        self.elevation = 0.0
        self.opacity = 1.0
        self.flip_x = False
        self.visible = True


@component_schema(
    type_name="asteria.Camera2D",
    version=1,
    fields=(
        Field("width", int, 320, minimum=1),
        Field("height", int, 180, minimum=1),
        Field("zoom", float, 1.0, minimum=0.01),
        Field("active", bool, True),
        Field("follow_entity_id", str, "", label="Follow Entity"),
        Field("deadzone_x", float, 0.0, minimum=0.0),
        Field("deadzone_y", float, 0.0, minimum=0.0),
        Field("smoothing", float, 0.0, minimum=0.0),
    ),
)
class Camera2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.width = 320
        self.height = 180
        self.zoom = 1.0
        self.active = True
        self.follow_entity_id = ""
        self.deadzone_x = 0.0
        self.deadzone_y = 0.0
        self.smoothing = 0.0


@component_schema(
    type_name="asteria.Animator2D",
    version=1,
    fields=(
        Field("clip_set_id", str, "", label="Animation Set"),
        Field("default_clip", str, "idle_down", label="Default Clip"),
        Field("speed", float, 1.0, minimum=0.01),
        Field("playing", bool, True),
    ),
)
class Animator2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.clip_set_id = ""
        self.default_clip = "idle_down"
        self.speed = 1.0
        self.playing = True


@component_schema(
    type_name="asteria.TileMap2D",
    version=1,
    fields=(
        Field("tilemap_asset_id", str, "", label="Tile Map"),
        Field("origin_x", float, 0.0, label="Origin X"),
        Field("origin_y", float, 0.0, label="Origin Y"),
        Field("visible", bool, True),
    ),
)
class TileMap2DComponent(Component):
    """Persistent scene binding to a canonical TileMap asset."""

    def __init__(self):
        super().__init__()
        self.tilemap_asset_id = ""
        self.origin_x = 0.0
        self.origin_y = 0.0
        self.visible = True
