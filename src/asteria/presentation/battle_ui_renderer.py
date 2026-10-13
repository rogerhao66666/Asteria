from __future__ import annotations

from dataclasses import dataclass

from .battle_ui import BattleUiFrame

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

    def __post_init__(self):
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

    def panel_style(self, role):
        role = str(role)
        if role == "result":
            return self.result_fill, self.result_border
        if role.startswith("interaction:"):
            return self.interaction_fill, self.interaction_border
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
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.battle_ui_theme" or data.get("version") != 1:
            raise ValueError("unsupported battle UI theme")
        kwargs = dict(data)
        kwargs.pop("schema", None)
        kwargs.pop("version", None)
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

        for panel in frame.panels:
            fill, border = t.panel_style(panel.role)
            b.draw_panel(
                panel, fill=fill, border=border, radius=t.panel_radius, border_width=t.border_width
            )

        for gauge in frame.gauges:
            fill = t.gauge_full if gauge.normalized >= 1.0 else t.gauge_fill
            b.draw_gauge(gauge, track=t.gauge_track, fill=fill)

        for icon in frame.icons:
            b.draw_icon(icon)

        for marker in frame.markers:
            b.draw_marker(marker, color=t.target_primary if marker.primary else t.target)

        for text in frame.texts:
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
