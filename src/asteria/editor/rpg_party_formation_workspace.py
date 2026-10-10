from __future__ import annotations

from dataclasses import dataclass

from .rpg_party_formation_authoring import PartyFormationInformationArchitecture


@dataclass(frozen=True, slots=True)
class PartyFormationWorkspaceSnapshot:
    section_id: str
    visible_ids: tuple[str, ...]
    selected_id: str | None
    focused_actor_id: str | None
    focused_slot_id: str | None
    detail_groups: tuple[str, ...]
    mode: str


class RpgPartyFormationWorkspaceModel:
    def __init__(self, controller):
        self.controller = controller
        self.architecture = PartyFormationInformationArchitecture()
        self.section_id = "parties"
        self.selected_id = None
        self.focused_actor_id = None
        self.focused_slot_id = None

    def set_section(self, key):
        if self.architecture.section(key) is None:
            raise KeyError(key)
        self.section_id = str(key)
        self.selected_id = None
        self.focused_actor_id = None
        self.focused_slot_id = None

    def visible_ids(self):
        db = self.controller.database
        if self.section_id == "parties":
            return tuple(sorted(db.party_setups))
        if self.section_id == "formations":
            return tuple(sorted(db.formations))
        return tuple(sorted(db.party_presentation_policies))

    def select(self, key):
        key = str(key)
        if key not in self.visible_ids():
            raise KeyError(key)
        self.selected_id = key
        self.focused_actor_id = None
        self.focused_slot_id = None

    def focus_actor(self, actor_id):
        if self.section_id != "parties" or self.selected_id is None:
            raise RuntimeError("select a party first")
        party = self.controller.database.party_setups[self.selected_id]
        if actor_id not in party.roster_actor_ids:
            raise KeyError(actor_id)
        self.focused_actor_id = str(actor_id)

    def focus_slot(self, slot_id):
        if self.section_id != "formations" or self.selected_id is None:
            raise RuntimeError("select a formation first")
        self.controller.database.formations[self.selected_id].slot(slot_id)
        self.focused_slot_id = str(slot_id)

    def snapshot(self):
        section = self.architecture.section(self.section_id)
        return PartyFormationWorkspaceSnapshot(
            self.section_id,
            self.visible_ids(),
            self.selected_id,
            self.focused_actor_id,
            self.focused_slot_id,
            section.detail_groups,
            section.mode,
        )
