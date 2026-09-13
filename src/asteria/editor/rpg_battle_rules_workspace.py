from __future__ import annotations
from dataclasses import dataclass
from .rpg_battle_rules_authoring import BattleRulesInformationArchitecture

@dataclass(frozen=True, slots=True)
class BattleRulesWorkspaceSnapshot:
    group_id: str
    kind_id: str
    query: str
    visible_ids: tuple[str,...]
    selected_id: str | None
    focused_child_id: str | None
    detail_groups: tuple[str,...]

class RpgBattleRulesWorkspaceModel:
    def __init__(self,controller):
        self.controller=controller
        self.architecture=BattleRulesInformationArchitecture()
        self.group_id="combat_model"
        self.kind_id="resources"
        self.query=""
        self.selected_id=None
        self.focused_child_id=None

    def set_group(self,group_id):
        group=self.architecture.group(group_id)
        if group is None: raise KeyError(group_id)
        self.group_id=group.group_id
        self.kind_id=group.kind_ids[0]
        self.selected_id=None; self.focused_child_id=None

    def set_kind(self,kind_id):
        group=self.architecture.group(self.group_id)
        if kind_id not in group.kind_ids: raise KeyError(kind_id)
        self.kind_id=str(kind_id); self.selected_id=None; self.focused_child_id=None

    def set_query(self,text): self.query=str(text or "").strip().lower()

    def visible_ids(self):
        kind=self.architecture.kind(self.kind_id)
        mapping=getattr(self.controller.database,kind.mapping_name)
        ids=tuple(sorted(mapping))
        if not self.query: return ids
        q=self.query
        return tuple(k for k in ids if q in k.lower() or q in str(mapping[k].to_data()).lower())

    def select(self,key):
        key=str(key)
        if key not in self.visible_ids(): raise KeyError(key)
        self.selected_id=key; self.focused_child_id=None

    def focus_child(self,child_id):
        if self.selected_id is None: raise RuntimeError("select a definition first")
        if self.kind_id not in {"sequences","gauges"}:
            raise RuntimeError("current battle rule does not use child focus")
        self.focused_child_id=str(child_id)

    def snapshot(self):
        kind=self.architecture.kind(self.kind_id)
        return BattleRulesWorkspaceSnapshot(
            self.group_id,self.kind_id,self.query,self.visible_ids(),
            self.selected_id,self.focused_child_id,kind.detail_groups,
        )
