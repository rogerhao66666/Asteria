"""The game's own picture message window (V2): a window picture drawn at its own resolution
and scaled up by whole pixels, the text typed into its text area in a bitmap font, a "next"
arrow strip and a framed choice box - as handheld games draw their messages.

It used to be set only in the game folder's ``playable_test_manifest.json`` (``dialogue``);
now it is project data (``battle_presentation_library`` category ``dialogue_window``, record
``default``) edited on Presentation ▸ Menu Screens ▸ Layout ▸ Dialogue window ▸ Picture
window…. A project without the record still reads the manifest, and the editor turns a
manifest's settings into the record with one click (``from_manifest``).

The ordinary message window (a panel with the speaker, the line and the portrait) is laid out
like every other screen: the ``dialogue`` and ``dialogue_choice`` layouts.
"""

from __future__ import annotations

from dataclasses import dataclass

from .menu_layout import _color, _rect


def _pair(value, name):
    value = tuple(int(round(float(v))) for v in value)
    if len(value) != 2:
        raise ValueError(f"{name} must be two numbers")
    return value


@dataclass(frozen=True, slots=True)
class DialogueWindowStyle:
    """Every setting of the picture message window; the defaults are the engine's."""

    window: str = ""  # the window picture (its size is the window's resolution)
    enabled: bool = True  # off: the ordinary message window, the settings kept
    text_area: tuple = (16, 8, 216, 32)  # in window pixels
    line_height: int = 16
    font: str = ""  # a bitmap font id (Bitmap fonts…); "" = a small system face
    letter_color: tuple = (98, 98, 98)
    shadow_color: tuple = (213, 213, 205)
    speed: float = 40.0  # letters a second (0 = all at once)
    speeds: tuple = ()  # letters a second by the Text speed option (slow, mid, fast...)
    arrow: str = ""  # the "next" arrow: a strip of frames, one under the other
    arrow_size: tuple = (8, 16)
    arrow_at: tuple = (220, 24)
    arrow_frame_ms: int = 160
    choice_frame: str = ""  # a 3 x 3 grid of border pieces for the choice box
    choice_fill: tuple | None = None  # the box's inside (None: the frame's middle colour)
    choice_right: int | None = None  # the box's right edge in window pixels (None: w - 24)
    choice_bottom: int | None = None  # its bottom edge (None: just above the window)
    choice_line_height: int = 16
    cancel_picks_last: bool = False  # the cancel key picks a choice's last option
    confirm_sound: str = ""  # played when a line is closed

    def __post_init__(self):
        for name in ("window", "font", "arrow", "choice_frame", "confirm_sound"):
            object.__setattr__(self, name, str(getattr(self, name) or "").strip())
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "text_area", _rect(self.text_area, "text_area"))
        for name in ("arrow_size", "arrow_at"):
            object.__setattr__(self, name, _pair(getattr(self, name), name))
        for name in ("line_height", "arrow_frame_ms", "choice_line_height"):
            value = int(getattr(self, name))
            if value < 1:
                raise ValueError(f"{name} must be >= 1")
            object.__setattr__(self, name, value)
        for name in ("letter_color", "shadow_color", "choice_fill"):
            object.__setattr__(self, name, _color(getattr(self, name), name))
        if self.letter_color is None or self.shadow_color is None:
            raise ValueError("the letter and shadow colours are needed")
        speed = float(self.speed)
        speeds = tuple(float(v) for v in self.speeds)
        if speed < 0 or any(v < 0 for v in speeds):
            raise ValueError("speeds must be >= 0")
        object.__setattr__(self, "speed", speed)
        object.__setattr__(self, "speeds", speeds)
        for name in ("choice_right", "choice_bottom"):
            value = getattr(self, name)
            object.__setattr__(self, name, None if value is None else int(value))
        object.__setattr__(self, "cancel_picks_last", bool(self.cancel_picks_last))

    def settings(self):
        """The window as the drawing code reads it (the manifest's ``dialogue`` shape, the
        font named by id under ``font_id``); None when it is off or has no picture."""
        if not self.enabled or not self.window:
            return None
        out = {
            "window": self.window,
            "text_area": list(self.text_area),
            "line_height": self.line_height,
            "colours": [list(self.letter_color), list(self.shadow_color)],
            "speed": self.speed,
            "arrow_size": list(self.arrow_size),
            "arrow_at": list(self.arrow_at),
            "arrow_frame_ms": self.arrow_frame_ms,
            "choice_line_height": self.choice_line_height,
            "cancel_picks_last": self.cancel_picks_last,
        }
        optional = {
            "font_id": self.font,
            "speeds": list(self.speeds),
            "arrow": self.arrow,
            "choice_frame": self.choice_frame,
            "choice_fill": list(self.choice_fill) if self.choice_fill else None,
            "choice_right": self.choice_right,
            "choice_bottom": self.choice_bottom,
            "confirm_sound": self.confirm_sound,
        }
        out.update({k: v for k, v in optional.items() if v not in (None, "", [])})
        return out

    def to_data(self):
        data = {}
        empty = DialogueWindowStyle()
        for name in DialogueWindowStyle.__dataclass_fields__:
            value = getattr(self, name)
            if value == getattr(empty, name):
                continue
            data[name] = list(value) if isinstance(value, tuple) else value
        return data

    @classmethod
    def from_data(cls, data):
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError("unknown dialogue window fields: " + ", ".join(sorted(unknown)))
        return cls(**dict(data))

    @classmethod
    def from_manifest(cls, dialogue, font_id="", confirm_sound=""):
        """The record for a manifest's ``dialogue`` settings (its font already turned into
        the bitmap font ``font_id``)."""
        dialogue = dict(dialogue or {})
        letter, shadow = dialogue.get("colours", ((98, 98, 98), (213, 213, 205)))
        values = {
            "window": dialogue.get("window", ""),
            "text_area": dialogue.get("text_area", (16, 8, 216, 32)),
            "line_height": dialogue.get("line_height", 16),
            "font": font_id,
            "letter_color": letter,
            "shadow_color": shadow,
            "speed": dialogue.get("speed", 40),
            "speeds": tuple(dialogue.get("speeds", ())),
            "arrow": dialogue.get("arrow", ""),
            "arrow_size": dialogue.get("arrow_size", (8, 16)),
            "arrow_at": dialogue.get("arrow_at", (220, 24)),
            "choice_frame": dialogue.get("choice_frame", ""),
            "choice_fill": dialogue.get("choice_fill"),
            "choice_right": dialogue.get("choice_right"),
            "choice_bottom": dialogue.get("choice_bottom"),
            "choice_line_height": dialogue.get("choice_line_height", 16),
            "cancel_picks_last": dialogue.get("cancel_picks_last", False),
            "confirm_sound": confirm_sound or "",
        }
        return cls(**values)


__all__ = ["DialogueWindowStyle"]
