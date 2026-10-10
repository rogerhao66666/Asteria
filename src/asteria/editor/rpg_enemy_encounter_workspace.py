from __future__ import annotations

from dataclasses import dataclass

from .rpg_enemy_encounter_authoring import EnemyEncounterInformationArchitecture


@dataclass(frozen=True, slots=True)
class EnemyEncounterWorkspaceSnapshot:
    section_id: str
    visible_ids: tuple[str, ...]
    selected_id: str | None
    selected_rule_id: str | None
    selected_phase_id: str | None
    detail_groups: tuple[str, ...]
    mode: str


class RpgEnemyEncounterWorkspaceModel:
    def __init__(self, controller):
        self.controller = controller
        self.architecture = EnemyEncounterInformationArchitecture()
        self.section_id = "enemies"
        self.selected_id = None
        self.selected_rule_id = None
        self.selected_phase_id = None

    def set_section(self, key):
        if self.architecture.section(key) is None:
            raise KeyError(key)
        self.section_id = str(key)
        self.selected_id = None
        self.selected_rule_id = None
        self.selected_phase_id = None

    def visible_ids(self):
        db = self.controller.database
        if self.section_id == "enemies":
            return tuple(sorted(db.enemies))
        if self.section_id == "encounters":
            return tuple(sorted(db.encounters))
        if self.section_id == "ai":
            return tuple(sorted(db.enemy_ai))
        return tuple(sorted(db.enemies))

    def select(self, key):
        key = str(key)
        if key not in self.visible_ids():
            raise KeyError(key)
        self.selected_id = key
        self.selected_rule_id = None
        self.selected_phase_id = None

    def select_rule(self, rule_id):
        if self.section_id != "ai" or self.selected_id is None:
            raise RuntimeError("select AI first")
        ai = self.controller.database.enemy_ai[self.selected_id]
        if rule_id not in {x.rule_id for x in ai.rules}:
            raise KeyError(rule_id)
        self.selected_rule_id = str(rule_id)
        self.selected_phase_id = None

    def select_phase(self, phase_id):
        if self.section_id != "ai" or self.selected_id is None:
            raise RuntimeError("select AI first")
        ai = self.controller.database.enemy_ai[self.selected_id]
        if phase_id not in {x.phase_id for x in ai.phases}:
            raise KeyError(phase_id)
        self.selected_phase_id = str(phase_id)
        self.selected_rule_id = None

    def snapshot(self):
        s = self.architecture.section(self.section_id)
        return EnemyEncounterWorkspaceSnapshot(
            self.section_id,
            self.visible_ids(),
            self.selected_id,
            self.selected_rule_id,
            self.selected_phase_id,
            s.detail_groups,
            s.mode,
        )
