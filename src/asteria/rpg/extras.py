"""Optional front-end content: a music room track list and credits pages."""

from __future__ import annotations

from dataclasses import dataclass


def _text(value):
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class MusicTrack:
    """A track in the music room. ``unlock_switch`` ("" = always available) names the event switch
    that opens it; playing a track in the game turns on ``music.heard.<track_id>``."""

    track_id: str
    name: str
    asset_id: str
    unlock_switch: str = ""
    note: str = ""

    def __init__(self, track_id, name, asset_id, *, unlock_switch="", note=""):
        track_id, asset_id = _text(track_id), _text(asset_id)
        if not track_id or not asset_id:
            raise ValueError("a track needs an id and an audio asset")
        object.__setattr__(self, "track_id", track_id)
        object.__setattr__(self, "name", _text(name) or track_id)
        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "unlock_switch", _text(unlock_switch))
        object.__setattr__(self, "note", _text(note))

    def to_data(self):
        data = {"track_id": self.track_id, "name": self.name, "asset_id": self.asset_id}
        if self.unlock_switch:
            data["unlock_switch"] = self.unlock_switch
        if self.note:
            data["note"] = self.note
        return data

    @classmethod
    def from_data(cls, data):
        data = dict(data)
        return cls(data.pop("track_id"), data.pop("name"), data.pop("asset_id"), **data)


@dataclass(frozen=True, slots=True)
class CreditsPage:
    page_id: str
    title: str
    lines: tuple[str, ...] = ()
    order: int = 0

    def __init__(self, page_id, title="", lines=(), *, order=0):
        page_id = _text(page_id)
        if not page_id:
            raise ValueError("page_id is required")
        object.__setattr__(self, "page_id", page_id)
        object.__setattr__(self, "title", _text(title))
        object.__setattr__(self, "lines", tuple(str(x) for x in lines))
        object.__setattr__(self, "order", int(order))

    def to_data(self):
        return {
            "page_id": self.page_id,
            "title": self.title,
            "lines": list(self.lines),
            "order": self.order,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["page_id"],
            data.get("title", ""),
            data.get("lines", ()),
            order=data.get("order", 0),
        )


@dataclass(frozen=True, slots=True)
class MenuEntry:
    """A project-defined entry of the pause menu that runs an event program (a bestiary
    shortcut, a common-event menu, a debug tool...). It shows while ``visible_switch`` is on
    ("" = always) and can be chosen while ``enabled_switch`` is on ("" = always)."""

    entry_id: str
    label: str
    event_program_id: str
    visible_switch: str = ""
    enabled_switch: str = ""
    order: int = 0

    def __init__(
        self,
        entry_id,
        label="",
        event_program_id="",
        *,
        visible_switch="",
        enabled_switch="",
        order=0,
    ):
        entry_id = _text(entry_id)
        if not entry_id:
            raise ValueError("entry_id is required")
        program = _text(event_program_id)
        if not program:
            raise ValueError("event_program_id is required")
        s = object.__setattr__
        s(self, "entry_id", entry_id)
        s(self, "label", _text(label) or entry_id)
        s(self, "event_program_id", program)
        s(self, "visible_switch", _text(visible_switch))
        s(self, "enabled_switch", _text(enabled_switch))
        s(self, "order", int(order))

    def to_data(self):
        return {
            "entry_id": self.entry_id,
            "label": self.label,
            "event_program_id": self.event_program_id,
            **({"visible_switch": self.visible_switch} if self.visible_switch else {}),
            **({"enabled_switch": self.enabled_switch} if self.enabled_switch else {}),
            **({"order": self.order} if self.order else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["entry_id"],
            data.get("label", ""),
            data["event_program_id"],
            visible_switch=data.get("visible_switch", ""),
            enabled_switch=data.get("enabled_switch", ""),
            order=data.get("order", 0),
        )
