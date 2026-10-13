from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _nonnegative(value, label):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and >= 0")
    return value


def _positive(value, label):
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and > 0")
    return value


@dataclass(frozen=True, slots=True)
class BattleUiPolishProfile:
    """Project-owned visual hierarchy/spacing policy for the default Battle UI."""

    interaction_width: float = 156.0
    interaction_padding: float = 7.0
    interaction_row_height: float = 12.0
    interaction_header_height: float = 11.0
    interaction_footer_height: float = 11.0
    interaction_bottom_gap: float = 8.0
    focus_member_emphasis: bool = True
    selected_prefix: str = "▶ "
    selected_option_prefix: str = "✓ "
    idle_prefix: str = "  "
    empty_label: str = "—"
    page_separator: str = " / "

    SCHEMA = "asteria.battle_ui_polish_profile"
    VERSION = 1

    def __post_init__(self):
        for name in (
            "interaction_width",
            "interaction_padding",
            "interaction_row_height",
            "interaction_header_height",
            "interaction_footer_height",
        ):
            _positive(getattr(self, name), name)
        _nonnegative(self.interaction_bottom_gap, "interaction_bottom_gap")
        for name in (
            "selected_prefix",
            "selected_option_prefix",
            "idle_prefix",
            "empty_label",
            "page_separator",
        ):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} must be str")

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "interaction_width": self.interaction_width,
            "interaction_padding": self.interaction_padding,
            "interaction_row_height": self.interaction_row_height,
            "interaction_header_height": self.interaction_header_height,
            "interaction_footer_height": self.interaction_footer_height,
            "interaction_bottom_gap": self.interaction_bottom_gap,
            "focus_member_emphasis": self.focus_member_emphasis,
            "selected_prefix": self.selected_prefix,
            "selected_option_prefix": self.selected_option_prefix,
            "idle_prefix": self.idle_prefix,
            "empty_label": self.empty_label,
            "page_separator": self.page_separator,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle UI polish profile")
        return cls(**{k: v for k, v in data.items() if k not in {"schema", "version"}})
