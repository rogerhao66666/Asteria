"""Save slots (ENG-21): numbered player saves plus the autosave, with a summary per slot.

``SaveSlots`` reads and writes ``GameRuntimeSave`` files in the game's save
folder: ``slot1..slotN.asteria-save.json`` and the existing
``playtest_autosave.asteria-save.json`` (quick save, F5). ``info`` summarises a
slot without starting it (scene, party leader and level, time saved).
``SlotMenu`` is the logic of the in-game Save / Load screen: overwriting and
deleting ask for a second confirmation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .game_save import GameRuntimeSave

SLOT_COUNT = 3
AUTOSAVE = "autosave"


@dataclass(frozen=True, slots=True)
class SlotInfo:
    slot: str
    exists: bool
    scene: str = ""
    leader: str = ""
    level: int = 0
    saved_at: str = ""
    error: str = ""

    @property
    def summary(self):
        if self.error:
            return f"damaged save ({self.error})"
        if not self.exists:
            return "— empty —"
        return f"{self.scene} · {self.leader} Lv {self.level} · {self.saved_at}"


class SaveSlots:
    def __init__(self, folder, project, *, count=SLOT_COUNT):
        self.folder = Path(folder)
        self.project = project
        self.count = int(count)

    def slots(self):
        return (AUTOSAVE, *(str(i) for i in range(1, self.count + 1)))

    def path(self, slot):
        slot = str(slot)
        if slot == AUTOSAVE:
            return self.folder / "playtest_autosave.asteria-save.json"
        if slot not in self.slots():
            raise ValueError(f"unknown save slot {slot}")
        return self.folder / f"slot{slot}.asteria-save.json"

    def info(self, slot):
        path = self.path(slot)
        if not path.exists():
            return SlotInfo(str(slot), False)
        try:
            save = GameRuntimeSave.load_json(path, self.project)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            return SlotInfo(str(slot), True, error=str(exc)[:60])
        scene = self.project.scene(save.scene_id)
        state = save.rpg_state
        leader_id = (state.party_active_actor_ids or state.party_actor_ids or ("",))[0]
        leader = self.project.rpg_database.actors.get(leader_id)
        progression = state.actor_progression.get(leader_id)
        return SlotInfo(
            str(slot),
            True,
            scene=scene.name if scene is not None else save.scene_id,
            leader=leader.display_name if leader is not None else leader_id,
            level=progression.level if progression is not None else 0,
            saved_at=time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime)),
        )

    def save(self, slot, game):
        game.sync_world_state()
        path = self.path(slot)
        path.parent.mkdir(parents=True, exist_ok=True)
        game.save.save_json(path)
        return path

    def load(self, slot):
        path = self.path(slot)
        if not path.exists():
            raise FileNotFoundError(f"slot {slot} is empty")
        return GameRuntimeSave.load_json(path, self.project)

    def delete(self, slot):
        path = self.path(slot)
        if path.exists():
            path.unlink()
            return True
        return False


class SlotMenu:
    """Save or load screen logic: choose a slot; overwrite / delete need a second press."""

    def __init__(self, slots, mode):
        if mode not in ("save", "load"):
            raise ValueError("mode must be save or load")
        self.slots = slots
        self.mode = mode
        self.row = 0 if mode == "load" else 1  # saving starts on slot 1, not the autosave
        self.pending = None  # ("overwrite" | "delete", slot) awaiting confirmation
        self.message = ""

    def rows(self):
        return [self.slots.info(s) for s in self.slots.slots()]

    def move(self, step):
        self.row = (self.row + step) % len(self.slots.slots())
        self.pending = None

    @property
    def slot(self):
        return self.slots.slots()[self.row]

    def activate(self, game=None):
        """Enter: ``("saved", path)``, ``("loaded", save)``, ``("confirm", slot)`` or ``("refused",
        reason)``."""
        info = self.slots.info(self.slot)
        if self.mode == "load":
            if not info.exists or info.error:
                self.message = "That slot is empty" if not info.exists else "That save is damaged"
                return ("refused", self.message)
            return ("loaded", self.slots.load(self.slot))
        if info.exists and self.pending != ("overwrite", self.slot):
            self.pending = ("overwrite", self.slot)
            self.message = f"Overwrite slot {self.slot}? Press Enter again"
            return ("confirm", self.slot)
        self.pending = None
        path = self.slots.save(self.slot, game)
        self.message = f"Saved to slot {self.slot}"
        return ("saved", path)

    def delete(self):
        if not self.slots.info(self.slot).exists:
            return False
        if self.pending != ("delete", self.slot):
            self.pending = ("delete", self.slot)
            self.message = f"Delete slot {self.slot}? Press Delete again"
            return False
        self.pending = None
        self.slots.delete(self.slot)
        self.message = f"Deleted slot {self.slot}"
        return True
