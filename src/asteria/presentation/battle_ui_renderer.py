from __future__ import annotations

from dataclasses import dataclass

from .battle_ui import BattleUiFrame
from .ui_skin import NinePatch, skin_for

Color = tuple[int, int, int, int]


def _color(value, label):
    value = tuple(int(x) for x in value)
    if len(value) not in (3, 4):
        raise ValueError(f"{label} must have 3 or 4 channels")
    if any(x < 0 or x > 255 for x in value):
        raise ValueError(f"{label} channels must be 0..255")
    if len(value) == 3:
        value = (*value, 255)
    return value


def _hex(text):
    """``"#rrggbb"`` / ``"#rrggbbaa"`` as an RGBA tuple."""
    digits = str(text).lstrip("#")
    channels = [int(digits[i : i + 2], 16) for i in range(0, len(digits), 2)]
    return _color(channels, "color")


@dataclass(frozen=True, slots=True)
class BattleUiTheme:
    panel_fill: Color = (18, 23, 34, 224)
    panel_border: Color = (110, 132, 168, 255)
    result_fill: Color = (12, 16, 25, 242)
    result_border: Color = (218, 181, 86, 255)
    text_primary: Color = (242, 245, 250, 255)
    text_secondary: Color = (180, 190, 207, 255)
    text_emphasis: Color = (255, 215, 112, 255)
    damage_text: Color = (255, 118, 105, 255)
    heal_text: Color = (113, 224, 147, 255)
    gauge_track: Color = (49, 57, 73, 255)
    gauge_fill: Color = (94, 190, 130, 255)
    gauge_full: Color = (233, 193, 85, 255)
    target: Color = (206, 216, 233, 255)
    target_primary: Color = (255, 208, 83, 255)
    panel_focus_fill: Color = (24, 31, 47, 236)
    panel_focus_border: Color = (255, 206, 96, 255)
    interaction_fill: Color = (15, 20, 31, 240)
    interaction_border: Color = (126, 149, 190, 255)
    text_muted: Color = (136, 148, 168, 255)
    text_disabled: Color = (106, 116, 134, 255)
    text_selected: Color = (255, 224, 137, 255)
    panel_radius: int = 4
    border_width: int = 1
    font_size: int = 10
    headline_font_size: int = 18
    # skin (all optional): pictures for panels and buttons by role pattern, first match wins
    # (``hud:*``, ``button:selected``, ``*``), and a font file; without them the colours above
    # are used
    panel_skins: tuple = ()
    font_asset_id: str = ""
    font_scale: float = 1.0

    def __post_init__(self):
        skins = []
        for pattern, patch in tuple(self.panel_skins):
            if not isinstance(patch, NinePatch):
                patch = NinePatch.from_data(patch)
            if not str(pattern).strip():
                raise ValueError("a panel skin needs a role pattern")
            skins.append((str(pattern).strip(), patch))
        object.__setattr__(self, "panel_skins", tuple(skins))
        object.__setattr__(self, "font_asset_id", str(self.font_asset_id or "").strip())
        if not float(self.font_scale) > 0:
            raise ValueError("font_scale must be > 0")
        object.__setattr__(self, "font_scale", float(self.font_scale))
        for field_name in (
            "panel_fill",
            "panel_border",
            "result_fill",
            "result_border",
            "text_primary",
            "text_secondary",
            "text_emphasis",
            "damage_text",
            "heal_text",
            "gauge_track",
            "gauge_fill",
            "gauge_full",
            "target",
            "target_primary",
            "panel_focus_fill",
            "panel_focus_border",
            "interaction_fill",
            "interaction_border",
            "text_muted",
            "text_disabled",
            "text_selected",
        ):
            object.__setattr__(self, field_name, _color(getattr(self, field_name), field_name))
        if self.panel_radius < 0 or self.border_width < 0:
            raise ValueError("panel radius/border must be >= 0")
        if self.font_size <= 0 or self.headline_font_size <= 0:
            raise ValueError("font sizes must be > 0")

    def panel_skin(self, role):
        """The nine-patch skin of a panel role, or ``None`` (plain colours)."""
        return skin_for(self.panel_skins, role)

    def panel_style(self, role):
        role = str(role)
        if role.startswith("button"):  # a row of a menu: only the selected one is lit by default
            if role == "button:selected":
                return (70, 62, 30, 150), (255, 206, 96, 220)
            return (0, 0, 0, 0), (0, 0, 0, 0)
        if role == "result":
            return self.result_fill, self.result_border
        if role == "interaction:float":  # see-through list beside the acting member
            return (10, 14, 26, 200), (150, 160, 190, 230)
        if role == "hud:side":
            return (12, 16, 28, 120), (96, 108, 140, 160)
        if role == "hud:side:focus":
            return (28, 30, 44, 140), (255, 210, 96, 230)
        if role.startswith("interaction:"):
            return self.interaction_fill, self.interaction_border
        if role.startswith("timeline_tile:"):  # one tile per turn, tinted by side
            return {
                "ally": ((28, 48, 88, 235), (112, 160, 230, 255)),
                "enemy": ((82, 28, 32, 235), (222, 112, 100, 255)),
            }.get(role.split(":", 1)[1], ((72, 60, 22, 245), (255, 210, 96, 255)))
        if role.endswith(":focus"):
            return self.panel_focus_fill, self.panel_focus_border
        return self.panel_fill, self.panel_border

    def text_color(self, role):
        role = str(role)
        if role == "result_headline":
            return self.text_emphasis
        if (
            role == "timeline_current"
            or role == "feedback_label"
            or role == "action_selected"
            or role == "workflow_option_selected"
            or role == "workflow_complete"
            or role.endswith(":focus")
        ):
            return self.text_selected
        if role.startswith("value:heal"):
            return self.heal_text
        if role.startswith("value:damage"):
            return self.damage_text
        if role in {
            "action_disabled",
            "action_cost_disabled",
            "action_disabled_reason",
            "workflow_option_disabled",
        }:
            return self.text_disabled
        if role == "status_chip":
            return (255, 200, 120, 255)
        if role in {
            "gauge_label",
            "gauge_value",
            "timeline_time",
            "action_categories",
            "action_filter",
            "action_page",
            "action_detail",
            "workflow_step",
        }:
            return self.text_muted
        return self.text_primary

    def text_size(self, role):
        role = str(role)
        if role == "result_headline":
            return self.headline_font_size
        if role in {"workflow_title", "action_selected"} or role.endswith(":focus"):
            return self.font_size + 1
        return self.font_size

    def to_data(self):
        return {
            "schema": "asteria.battle_ui_theme",
            "version": 1,
            **{
                name: list(getattr(self, name))
                for name in (
                    "panel_fill",
                    "panel_border",
                    "result_fill",
                    "result_border",
                    "text_primary",
                    "text_secondary",
                    "text_emphasis",
                    "damage_text",
                    "heal_text",
                    "gauge_track",
                    "gauge_fill",
                    "gauge_full",
                    "target",
                    "target_primary",
                    "panel_focus_fill",
                    "panel_focus_border",
                    "interaction_fill",
                    "interaction_border",
                    "text_muted",
                    "text_disabled",
                    "text_selected",
                )
            },
            "panel_radius": self.panel_radius,
            "border_width": self.border_width,
            "font_size": self.font_size,
            "headline_font_size": self.headline_font_size,
            **(
                {"panel_skins": [[p, n.to_data()] for p, n in self.panel_skins]}
                if self.panel_skins
                else {}
            ),
            **({"font_asset_id": self.font_asset_id} if self.font_asset_id else {}),
            **({"font_scale": self.font_scale} if self.font_scale != 1.0 else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.battle_ui_theme" or data.get("version") != 1:
            raise ValueError("unsupported battle UI theme")
        kwargs = dict(data)
        kwargs.pop("schema", None)
        kwargs.pop("version", None)
        kwargs["panel_skins"] = tuple(
            (p, NinePatch.from_data(n)) for p, n in kwargs.get("panel_skins", ())
        )
        return cls(**kwargs)


class BattleUiRenderer:
    """Executes adapter-ready BattleUiFrame commands against a UI backend.

    The backend owns pixels/fonts/assets. The renderer preserves deterministic
    command order and has no access to Battle Core.
    """

    def __init__(self, backend, theme=None):
        self.backend = backend
        self.theme = theme or BattleUiTheme()
        if not isinstance(self.theme, BattleUiTheme):
            raise TypeError("theme must be BattleUiTheme")

    def render(self, frame):
        if not isinstance(frame, BattleUiFrame):
            raise TypeError("frame must be BattleUiFrame")
        b = self.backend
        t = self.theme
        b.begin_battle_ui(frame.scene_id)

        def on_top(role):  # the command menu and its rows are drawn last, over any HUD
            role = str(role)
            return role.startswith(("interaction:", "button", "action", "workflow_"))

        def panel(item):
            fill, border = t.panel_style(item.role)
            style = {
                "fill": fill,
                "border": border,
                "radius": t.panel_radius,
                "border_width": t.border_width,
            }
            skin = t.panel_skin(item.role)
            if skin is not None:  # backends without skins never see the argument
                style["skin"] = skin
            b.draw_panel(item, **style)

        for layer in (False, True):
            for item in frame.panels:
                if on_top(item.role) == layer:
                    panel(item)
            if not layer:
                for gauge in frame.gauges:
                    fill = t.gauge_full if gauge.normalized >= 1.0 else t.gauge_fill
                    own = getattr(gauge, "color", "")
                    if own:  # the resource's own colour (HUD style), full or not
                        fill = _hex(own)
                    b.draw_gauge(gauge, track=t.gauge_track, fill=fill)
            for icon in frame.icons:
                if on_top(icon.role) == layer:
                    b.draw_icon(icon)
            if not layer:
                for marker in frame.markers:
                    b.draw_marker(marker, color=t.target_primary if marker.primary else t.target)
            for text in frame.texts:
                if on_top(text.role) == layer:
                    b.draw_text(text, color=t.text_color(text.role), size=t.text_size(text.role))

        for effect in frame.vfx:
            b.draw_vfx(effect)
        for effect in frame.screen_fx:
            b.draw_screen_fx(effect)

        b.end_battle_ui()
        return frame


class HeadlessBattleUiBackend:
    """Deterministic renderer test double; records UI operations only."""

    def __init__(self):
        self.ops = []

    def begin_battle_ui(self, scene_id):
        self.ops.append(("begin", str(scene_id)))

    def draw_panel(self, panel, **style):
        self.ops.append(("panel", panel.panel_id, panel.role, dict(style)))

    def draw_gauge(self, gauge, **style):
        self.ops.append(
            ("gauge", gauge.member_id, gauge.resource_id, gauge.normalized, dict(style))
        )

    def draw_icon(self, icon):
        self.ops.append(("icon", icon.asset_id, icon.member_id, icon.role))

    def draw_marker(self, marker, **style):
        self.ops.append(("marker", marker.member_id, marker.primary, dict(style)))

    def draw_text(self, text, **style):
        self.ops.append(("text", text.text, text.role, text.align, dict(style)))

    def draw_vfx(self, effect):
        self.ops.append(("vfx", getattr(effect, "cue_id", "")))

    def draw_screen_fx(self, effect):
        self.ops.append(("screen_fx", getattr(effect, "effect", "")))

    def end_battle_ui(self):
        self.ops.append(("end",))
