from __future__ import annotations
from dataclasses import dataclass

from asteria.rpg import (
    EnemyAIDefinition, EnemyBehaviorBinding, EnemyDefinition,
    EncounterDefinition, RewardDefinition,
)

class RpgEnemyEncounterAuthoringError(RuntimeError):
    pass

@dataclass(slots=True)
class _MapCommand:
    mapping: dict
    key: str
    new_value: object | None
    old_value: object | None
    description: str
    @property
    def label(self): return self.description
    def redo(self):
        if self.new_value is None: self.mapping.pop(self.key,None)
        else: self.mapping[self.key]=self.new_value
    def undo(self):
        if self.old_value is None: self.mapping.pop(self.key,None)
        else: self.mapping[self.key]=self.old_value

@dataclass(frozen=True, slots=True)
class EnemyEncounterSection:
    section_id: str
    label: str
    mode: str
    detail_groups: tuple[str,...]

@dataclass(frozen=True, slots=True)
class EnemyEncounterInformationArchitecture:
    sections: tuple[EnemyEncounterSection,...]=(
        EnemyEncounterSection("enemies","Enemies","list_detail",
                              ("Identity","Stats & Resources","Abilities","Tags","Behavior","Rewards")),
        EnemyEncounterSection("encounters","Encounters","composition_detail",
                              ("Identity","Members","Counts & Weights","Tags")),
        EnemyEncounterSection("ai","AI / Boss Phases","rule_phase_detail",
                              ("Decision Rules","Selected Rule","Phases","Selected Phase","Conditions","Targets & Actions")),
        EnemyEncounterSection("rewards","Rewards","embedded_detail",
                              ("Currencies","Progression","Loot")),
    )
    primary_navigation: str="category_sidebar"
    browser_pattern: str="search_filter_list"
    ai_pattern: str="rule_phase_browser_plus_contextual_detail"
    progressive_disclosure: bool=True
    show_all_boss_logic_simultaneously: bool=False
    show_all_details_simultaneously: bool=False
    def section(self,key):
        return next((x for x in self.sections if x.section_id==str(key)),None)

class RpgEnemyEncounterAuthoringController:
    information_architecture=EnemyEncounterInformationArchitecture()

    def __init__(self,document): self.document=document
    @property
    def project(self):
        if self.document.project is None: raise RpgEnemyEncounterAuthoringError("project required")
        return self.document.project
    @property
    def database(self): return self.project.rpg_database
    def _execute(self,c): self.document.execute(c); return c

    def _coerce(self,value,cls):
        if isinstance(value,cls): return value
        if isinstance(value,dict): return cls.from_data(value)
        raise TypeError(f"value must be {cls.__name__} or data")

    def _validate_reward(self,reward):
        missing_items=sorted({x.item_id for x in reward.loot}-set(self.database.items))
        if missing_items: raise RpgEnemyEncounterAuthoringError("unknown reward items: "+", ".join(missing_items))
        missing_tracks=sorted(set(reward.experience)-set(self.database.progression_tracks))
        if missing_tracks: raise RpgEnemyEncounterAuthoringError("unknown progression tracks: "+", ".join(missing_tracks))

    def _validate_enemy(self,value):
        missing=sorted(set(value.abilities)-set(self.project.gameplay_library.abilities.ids()))
        if missing: raise RpgEnemyEncounterAuthoringError("unknown enemy abilities: "+", ".join(missing))
        self._validate_reward(value.reward)

    def create_enemy(self,value):
        value=self._coerce(value,EnemyDefinition); key=value.enemy_id
        if key in self.database.enemies: raise RpgEnemyEncounterAuthoringError(f"duplicate enemy: {key}")
        self._validate_enemy(value)
        self._execute(_MapCommand(self.database.enemies,key,value,None,f"Add Enemy {key}"))
        return value

    def edit_enemy(self,enemy_id,value):
        key=str(enemy_id); old=self.database.enemies.get(key)
        if old is None: raise RpgEnemyEncounterAuthoringError(f"unknown enemy: {key}")
        value=self._coerce(value,EnemyDefinition)
        if value.enemy_id!=key: raise RpgEnemyEncounterAuthoringError("enemy id cannot change during edit")
        self._validate_enemy(value)
        self._execute(_MapCommand(self.database.enemies,key,value,old,f"Edit Enemy {key}"))
        return value

    def delete_enemy(self,enemy_id):
        key=str(enemy_id); old=self.database.enemies.get(key)
        if old is None: raise RpgEnemyEncounterAuthoringError(f"unknown enemy: {key}")
        refs=[x.encounter_id for x in self.database.encounters.values() if any(m.enemy_id==key for m in x.members)]
        if key in self.database.enemy_behavior_bindings: refs.append("behavior_binding")
        if refs: raise RpgEnemyEncounterAuthoringError(f"enemy {key} is referenced by "+", ".join(sorted(refs)))
        self._execute(_MapCommand(self.database.enemies,key,None,old,f"Delete Enemy {key}"))

    def create_encounter(self,value):
        value=self._coerce(value,EncounterDefinition); key=value.encounter_id
        if key in self.database.encounters: raise RpgEnemyEncounterAuthoringError(f"duplicate encounter: {key}")
        missing=sorted({m.enemy_id for m in value.members}-set(self.database.enemies))
        if missing: raise RpgEnemyEncounterAuthoringError("unknown encounter enemies: "+", ".join(missing))
        self._execute(_MapCommand(self.database.encounters,key,value,None,f"Add Encounter {key}"))
        return value

    def edit_encounter(self,encounter_id,value):
        key=str(encounter_id); old=self.database.encounters.get(key)
        if old is None: raise RpgEnemyEncounterAuthoringError(f"unknown encounter: {key}")
        value=self._coerce(value,EncounterDefinition)
        if value.encounter_id!=key: raise RpgEnemyEncounterAuthoringError("encounter id cannot change during edit")
        missing=sorted({m.enemy_id for m in value.members}-set(self.database.enemies))
        if missing: raise RpgEnemyEncounterAuthoringError("unknown encounter enemies: "+", ".join(missing))
        self._execute(_MapCommand(self.database.encounters,key,value,old,f"Edit Encounter {key}"))
        return value

    def delete_encounter(self,encounter_id):
        key=str(encounter_id); old=self.database.encounters.get(key)
        if old is None: raise RpgEnemyEncounterAuthoringError(f"unknown encounter: {key}")
        self._execute(_MapCommand(self.database.encounters,key,None,old,f"Delete Encounter {key}"))

    def create_ai(self,value):
        value=self._coerce(value,EnemyAIDefinition); key=value.ai_id
        if key in self.database.enemy_ai: raise RpgEnemyEncounterAuthoringError(f"duplicate enemy AI: {key}")
        self._validate_ai(value)
        self._execute(_MapCommand(self.database.enemy_ai,key,value,None,f"Add Enemy AI {key}"))
        return value

    def edit_ai(self,ai_id,value):
        key=str(ai_id); old=self.database.enemy_ai.get(key)
        if old is None: raise RpgEnemyEncounterAuthoringError(f"unknown enemy AI: {key}")
        value=self._coerce(value,EnemyAIDefinition)
        if value.ai_id!=key: raise RpgEnemyEncounterAuthoringError("AI id cannot change during edit")
        self._validate_ai(value)
        self._execute(_MapCommand(self.database.enemy_ai,key,value,old,f"Edit Enemy AI {key}"))
        return value

    def _validate_ai(self,value):
        known=set(self.project.gameplay_library.abilities.ids())
        refs=[]
        for rule in value.rules:
            if rule.action_kind in {"ability","use_ability"}:
                aid=rule.payload.get("ability_id")
                if aid is not None: refs.append(str(aid))
        missing=sorted(set(refs)-known)
        if missing: raise RpgEnemyEncounterAuthoringError("unknown AI abilities: "+", ".join(missing))

    def delete_ai(self,ai_id):
        key=str(ai_id); old=self.database.enemy_ai.get(key)
        if old is None: raise RpgEnemyEncounterAuthoringError(f"unknown enemy AI: {key}")
        refs=[x.enemy_id for x in self.database.enemy_behavior_bindings.values() if x.ai_id==key]
        if refs: raise RpgEnemyEncounterAuthoringError(f"AI {key} is bound to enemies: "+", ".join(sorted(refs)))
        self._execute(_MapCommand(self.database.enemy_ai,key,None,old,f"Delete Enemy AI {key}"))

    def bind_enemy_ai(self,enemy_id,ai_id,*,tags=()):
        enemy_id=str(enemy_id); ai_id=str(ai_id)
        if enemy_id not in self.database.enemies: raise RpgEnemyEncounterAuthoringError(f"unknown enemy: {enemy_id}")
        if ai_id not in self.database.enemy_ai: raise RpgEnemyEncounterAuthoringError(f"unknown enemy AI: {ai_id}")
        value=EnemyBehaviorBinding(enemy_id,ai_id,tags=tags)
        old=self.database.enemy_behavior_bindings.get(enemy_id)
        self._execute(_MapCommand(self.database.enemy_behavior_bindings,enemy_id,value,old,f"Bind Enemy AI {enemy_id}"))
        return value

    def unbind_enemy_ai(self,enemy_id):
        key=str(enemy_id); old=self.database.enemy_behavior_bindings.get(key)
        if old is None: raise RpgEnemyEncounterAuthoringError(f"enemy has no AI binding: {key}")
        self._execute(_MapCommand(self.database.enemy_behavior_bindings,key,None,old,f"Unbind Enemy AI {key}"))

    def validate(self):
        try: self.project.validate()
        except Exception as exc: return (str(exc),)
        return ()
