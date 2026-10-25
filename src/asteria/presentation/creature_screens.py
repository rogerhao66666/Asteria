"""The creature game's own screens as project data (UI_PLAN_2 V5): the one-on-one battle
screen, the start menu, the shop, the name entry and the picture choices.

Each screen's settings (pictures, the ``layout`` points and ``colours`` of the battle, the bag
pockets, menu rows, trainer card, dex and option places...) were only written in the game
folder's ``playable_test_manifest.json``. They now live in the presentation library (category
``creature_screen``, one record per screen, the record id the manifest path it replaces) and
the editor edits them (Presentation ▸ Menu Screens ▸ Layout ▸ Creature screens…): a tree of
every setting with a picture picker, colour button, number box or table for each, and the
screen's points dragged on its picture. ``creature_settings(runtime, screen)`` gives what a
screen draws with: the project's record when it is on, else the manifest's (older games keep
working; the editor turns the manifest into records in one step).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

# record id (= the manifest path it replaces) -> the name shown in the editor
SCREENS = {
    "battle.creature_screen": "Creature battle",
    "field.creature_menu": "Start menu",
    "field.creature_shop": "Creature shop",
    "field.name_input": "Name entry",
    "field.picture_choices": "Picture choices",
}
RESOLUTION = (240, 160)  # the screens' own pixels (drawn scaled to the window)


@dataclass(frozen=True)
class CreatureScreenSettings:
    """One screen's settings: ``data`` in the manifest's own shape (nested dicts and lists of
    text, numbers, true / false); ``enabled`` False keeps the record but draws without it."""

    screen_id: str
    data: dict = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self):
        if self.screen_id not in SCREENS:
            raise ValueError(f"unknown creature screen: {self.screen_id}")
        if not isinstance(self.data, dict):
            raise ValueError("a creature screen's settings are a table of names")
        json.dumps(self.data)  # only what a project file can hold
        object.__setattr__(self, "data", copy.deepcopy(self.data))

    def __hash__(self):
        return hash((self.screen_id, json.dumps(self.data, sort_keys=True), self.enabled))

    def to_data(self):
        out = {"screen_id": self.screen_id, "data": copy.deepcopy(self.data)}
        if not self.enabled:
            out["enabled"] = False
        return out

    @classmethod
    def from_data(cls, data):
        unknown = set(data) - {"screen_id", "data", "enabled"}
        if unknown:
            raise ValueError(f"unknown creature screen fields: {sorted(unknown)}")
        return cls(
            str(data["screen_id"]), dict(data.get("data", {})), bool(data.get("enabled", True))
        )


def manifest_part(manifest, screen_id):
    """The manifest's settings of ``screen_id`` (``{}`` when it has none)."""
    value = manifest or {}
    for key in screen_id.split("."):
        value = value.get(key, {}) if isinstance(value, dict) else {}
    return value if isinstance(value, dict) else {}


def project_record(project, screen_id):
    """The project's record of ``screen_id``, or None."""
    library = getattr(project, "battle_presentation_library", None)
    records = getattr(library, "_records", {}).get("creature_screen", {})
    return records.get(screen_id)


def creature_settings(runtime, screen_id):
    """What ``screen_id`` draws with: the project's record when it is on, else the manifest's.
    A copy: a screen may change its own without touching the project."""
    record = project_record(getattr(runtime, "project", None), screen_id)
    if record is not None and record.enabled:
        return copy.deepcopy(record.data)
    return copy.deepcopy(manifest_part(getattr(runtime, "manifest", {}), screen_id))


def creature_battle_on(runtime):
    """The one-on-one creature battle screen is used: its record is on, or the manifest's
    ``battle.style`` is ``creature``."""
    record = project_record(getattr(runtime, "project", None), "battle.creature_screen")
    if record is not None and record.enabled:
        return True
    manifest = getattr(runtime, "manifest", {}) or {}
    return manifest.get("battle", {}).get("style") == "creature"


def from_manifest(manifest):
    """A record for every creature screen the manifest sets up (the editor's conversion)."""
    out = []
    for screen_id in SCREENS:
        part = manifest_part(manifest, screen_id)
        if screen_id == "battle.creature_screen":
            if manifest.get("battle", {}).get("style") == "creature" or part:
                out.append(CreatureScreenSettings(screen_id, part))
        elif part:
            out.append(CreatureScreenSettings(screen_id, part))
    return out


__all__ = [
    "RESOLUTION",
    "SCREENS",
    "CreatureScreenSettings",
    "creature_battle_on",
    "creature_settings",
    "from_manifest",
    "manifest_part",
    "project_record",
]
