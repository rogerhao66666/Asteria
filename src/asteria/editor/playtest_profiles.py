from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from asteria.runtime.game_save import GameRuntimeSave


class PlaytestProfileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PlaytestProfile:
    profile_id: str
    display_name: str
    runtime_state: dict
    description: str = ""
    default: bool = False

    SCHEMA = "asteria.playtest_profile"
    VERSION = 1

    def __post_init__(self):
        if not str(self.profile_id).strip():
            raise PlaytestProfileError("profile id required")
        if not str(self.display_name).strip():
            raise PlaytestProfileError("display name required")
        if not isinstance(self.runtime_state, dict):
            raise PlaytestProfileError("runtime_state must be data")

    def instantiate(self, project):
        data = dict(self.runtime_state)
        data["project_id"] = project.id
        value = GameRuntimeSave.from_data(data, project)
        # A playtest profile is a template: every Run gets a fresh state.
        return GameRuntimeSave.from_data(value.to_data(), project)

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "description": self.description,
            "default": self.default,
            "runtime_state": self.runtime_state,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != 1:
            raise PlaytestProfileError("unsupported playtest profile")
        return cls(
            str(data["profile_id"]),
            str(data["display_name"]),
            dict(data["runtime_state"]),
            str(data.get("description", "")),
            bool(data.get("default", False)),
        )

    @classmethod
    def load_json(cls, path):
        return cls.from_data(json.loads(Path(path).read_text(encoding="utf-8")))


class PlaytestProfileLibrary:
    """Developer-only launch profiles stored beside a Project, never Player Saves."""

    def __init__(self, resource_root):
        self.resource_root = Path(resource_root)
        self.directory = self.resource_root / "playtest_profiles"

    def profiles(self):
        if not self.directory.exists():
            return ()
        values = []
        for path in sorted(self.directory.glob("*.asteria-playtest.json")):
            values.append(PlaytestProfile.load_json(path))
        return tuple(values)

    def get(self, profile_id):
        profile_id = str(profile_id)
        for value in self.profiles():
            if value.profile_id == profile_id:
                return value
        raise PlaytestProfileError(f"unknown playtest profile: {profile_id}")

    def default(self):
        values = self.profiles()
        for value in values:
            if value.default:
                return value
        return values[0] if values else None

    def instantiate(self, profile_id, project):
        return self.get(profile_id).instantiate(project)
