from asteria.core import Component, Field, component_schema
from asteria.core.migration import component_migration


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
    version=2,
    fields=(
        Field("width", int, 320, minimum=1),
        Field("height", int, 180, minimum=1),
        Field("zoom", float, 1.0, minimum=0.01),
        Field("active", bool, True),
        Field("follow_entity_id", str, "", label="Follow Entity"),
        Field("deadzone_x", float, 0.0, minimum=0.0),
        Field("deadzone_y", float, 0.0, minimum=0.0),
        Field("smoothing", float, 0.0, minimum=0.0),
        Field("look_ahead_x", float, 0.0, minimum=0.0, label="Look Ahead X"),
        Field("look_ahead_y", float, 0.0, minimum=0.0, label="Look Ahead Y"),
        Field("bounds_enabled", bool, False, label="Limit to Bounds"),
        Field("bounds_min_x", float, 0.0, label="Bounds Left"),
        Field("bounds_min_y", float, 0.0, label="Bounds Top"),
        Field("bounds_max_x", float, 0.0, label="Bounds Right"),
        Field("bounds_max_y", float, 0.0, label="Bounds Bottom"),
        Field("group_entity_ids", str, "", label="Group Targets (ids, comma separated)"),
        Field("group_padding", float, 32.0, minimum=0.0, label="Group Padding"),
        Field("min_zoom", float, 0.5, minimum=0.01, label="Group Min Zoom"),
        Field("max_zoom", float, 2.0, minimum=0.01, label="Group Max Zoom"),
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
        self.look_ahead_x = 0.0
        self.look_ahead_y = 0.0
        self.bounds_enabled = False
        self.bounds_min_x = 0.0
        self.bounds_min_y = 0.0
        self.bounds_max_x = 0.0
        self.bounds_max_y = 0.0
        self.group_entity_ids = ""
        self.group_padding = 32.0
        self.min_zoom = 0.5
        self.max_zoom = 2.0

    @property
    def bounds(self):
        if not self.bounds_enabled:
            return None
        return (self.bounds_min_x, self.bounds_min_y, self.bounds_max_x, self.bounds_max_y)

    @property
    def group_ids(self):
        return tuple(x.strip() for x in self.group_entity_ids.split(",") if x.strip())


@component_migration("asteria.Camera2D", from_version=1)
def _camera2d_v1_to_v2(fields):
    # v2 only adds look-ahead, bounds and group fields; their defaults keep v1 behaviour
    return fields


@component_schema(
    type_name="asteria.Animator2D",
    version=2,
    fields=(
        Field("clip_set_id", str, "", label="Animation Set"),
        Field("default_clip", str, "idle_down", label="Default Clip"),
        Field("speed", float, 1.0, minimum=0.01),
        Field("playing", bool, True),
        Field(
            "stride",
            float,
            0.0,
            minimum=0.0,
            label="Walk Stride",
            tooltip=(
                "World units one whole walk clip carries the figure (two steps). Set, the walk "
                "plays as far as the figure moves, so its feet keep pace with the ground at "
                "any speed; 0 plays the walk by its frame times."
            ),
        ),
    ),
)
class Animator2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.clip_set_id = ""
        self.default_clip = "idle_down"
        self.speed = 1.0
        self.playing = True
        self.stride = 0.0


@component_migration("asteria.Animator2D", from_version=1)
def _animator2d_v1_to_v2(fields):
    return fields  # v2 adds stride (0 keeps v1's timed walk)


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


@component_migration("asteria.Interaction2D", from_version=1)
def _interaction2d_v1_to_v2(fields):
    fields.setdefault("trigger", "action")  # v1 interactions were all action-button
    return fields


@component_schema(
    type_name="asteria.Interaction2D",
    version=2,
    fields=(
        Field("event_binding_id", str, "", label="Event Binding"),
        Field("event_program_id", str, "", label="Event Program"),
        Field("range", float, 24.0, minimum=0.0, label="Interaction Range"),
        Field("require_facing", bool, True, label="Require Facing"),
        Field("local_scope_id", str, "", label="Local State Scope"),
        Field(
            "trigger",
            str,
            "action",
            choices=("action", "touch", "click"),
            label="Trigger",
            tooltip="action: the interact button while in range; touch: walking into range "
            "(doors, transfers); click: a mouse click on it (within Range).",
        ),
    ),
)
class Interaction2DComponent(Component):
    """Persistent authoring data for an interactable world entity."""

    def __init__(self):
        super().__init__()
        self.event_binding_id = ""
        self.event_program_id = ""
        self.range = 24.0
        self.require_facing = True
        self.local_scope_id = ""
        self.trigger = "action"


@component_schema(
    type_name="asteria.ParallaxBackground2D",
    version=1,
    fields=(
        Field("texture_asset_id", str, "", label="Texture"),
        Field("factor_x", float, 0.3, minimum=0.0, label="Scroll Factor X"),
        Field("factor_y", float, 0.0, minimum=0.0, label="Scroll Factor Y"),
        Field("scale", float, 1.0, minimum=0.01),
        Field("anchor", str, "bottom", choices=("top", "center", "bottom"), label="Anchor"),
        Field("offset_y", float, 0.0, label="Offset Y"),
        Field("repeat_x", bool, True, label="Repeat Horizontally"),
        Field("opacity", float, 1.0, minimum=0.0, maximum=1.0),
        Field("visible", bool, True),
    ),
)
class ParallaxBackground2DComponent(Component):
    """A scrolling backdrop behind the map: it moves at ``factor`` times the camera, so far
    layers (small factors) slide slowly and give depth. Drawn in entity order, below the tile
    layers."""

    def __init__(self):
        super().__init__()
        self.texture_asset_id = ""
        self.factor_x = 0.3
        self.factor_y = 0.0
        self.scale = 1.0
        self.anchor = "bottom"
        self.offset_y = 0.0
        self.repeat_x = True
        self.opacity = 1.0
        self.visible = True
