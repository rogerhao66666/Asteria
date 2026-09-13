from __future__ import annotations

import random

from asteria.core import Transform
from asteria.gameplay import AbilityRegistry, AbilityRuntime, GameplaySubject
from asteria.rpg import (
    ActorAbilityState, ActorProgressionState, BattleAction, BattleRuntime, ClassAssignment, EquipmentGrowthRuntime, EquippedItem, Party, PartyMember, RewardRuntime, RpgActorSnapshot,
    RpgActorRuntime, roll_reward, resolve_actor_build,
)
from asteria.runtime.input import InputSnapshot
from asteria.runtime.interaction import InteractionController


class GameSessionError(RuntimeError):
    pass


class GameSessionRuntime:
    """Generic Project + GameRuntimeSave integration runtime.

    This is the engine-level seam used by reference/full-play validation. It does
    not know project-specific actor, boss, job, resource, weakness or party-size
    names. Project definitions provide those rules; GameRuntimeSave provides the
    mutable player state.
    """

    def __init__(self, project, runtime_save):
        runtime_save.validate(project)
        self.project=project
        self.save=runtime_save
        self.scene=project.scene(runtime_save.scene_id)
        self.player=self.scene.get_entity(runtime_save.player_entity_id)
        if self.player is None:
            raise GameSessionError("saved player entity does not exist")
        self.facing=runtime_save.player_facing
        if runtime_save.player_position is not None:
            transform=self.player.get(Transform)
            transform.x,transform.y=runtime_save.player_position
        self.interaction=InteractionController(action="interact")
        self.mode="field"
        self.battle=None
        self.encounter_id=None
        self._enemy_ids=()

    def set_player_position(self,x,y):
        t=self.player.get(Transform); t.x=float(x); t.y=float(y)
        self.save.player_position=(t.x,t.y)
        return self.save.player_position

    def set_player_facing(self,facing):
        self.facing=str(facing); self.save.player_facing=self.facing
        return self.facing

    def field_step(self,actions=None):
        if self.mode!="field":
            raise GameSessionError("field input unavailable outside field mode")
        trigger=self.interaction.step(InputSnapshot(dict(actions or {})),self.scene,self.player,self.facing)
        if trigger is None:
            return None
        program=self.project.event_programs.require(trigger.event_program_id)
        for instruction in program.instructions:
            if instruction.opcode=="WORLD" and instruction.args.get("command")=="START_ENCOUNTER":
                self.start_encounter(instruction.args["encounter_id"])
                break
        return trigger

    def set_active_classes(self,actor_id,class_ids):
        actor_id=str(actor_id); state=self.save.rpg_state.actor_progression[actor_id]
        values=tuple(dict.fromkeys(str(x) for x in class_ids))
        missing=set(values)-set(state.unlocked_class_ids)
        if missing: raise GameSessionError("cannot activate locked classes: "+", ".join(sorted(missing)))
        self.save.rpg_state.actor_progression[actor_id]=ActorProgressionState(
            state.level,state.experience,points=state.points,
            unlocked_class_ids=state.unlocked_class_ids,active_class_ids=values,
        )
        return values

    def set_active_party(self,actor_ids,placements=None):
        actor_ids=tuple(dict.fromkeys(str(x) for x in actor_ids))
        roster=set(self.save.rpg_state.party_actor_ids)
        if not set(actor_ids).issubset(roster):
            raise GameSessionError("active party must be selected from roster")
        self.save.rpg_state.party_active_actor_ids=actor_ids
        if placements is not None:
            values={str(k):str(v) for k,v in dict(placements).items()}
            if not set(values).issubset(set(actor_ids)):
                raise GameSessionError("placements must reference active party actors")
            self.save.rpg_state.party_placements=values
        return actor_ids

    def _ability_state(self,actor_id):
        snapshot=self.save.rpg_state.actor_snapshots[str(actor_id)]
        return ActorAbilityState() if snapshot.ability_state is None else ActorAbilityState.from_data(snapshot.ability_state)

    def _store_ability_state(self,actor_id,state):
        actor_id=str(actor_id); old=self.save.rpg_state.actor_snapshots[actor_id]
        self.save.rpg_state.actor_snapshots[actor_id]=RpgActorSnapshot(
            old.actor_id,old.stats,old.resources,old.tags,state.to_data()
        )
        return state

    def learn_ability(self,actor_id,ability_id):
        ability_id=str(ability_id)
        if self.project.gameplay_library.abilities.get(ability_id) is None: raise KeyError(ability_id)
        state=self._ability_state(actor_id); state.learn(ability_id)
        self._store_ability_state(actor_id,state); return ability_id

    def equip_passive(self,actor_id,passive_id,*,capacity=None):
        passive_id=str(passive_id)
        if passive_id not in self.project.rpg_database.passives: raise KeyError(passive_id)
        state=self._ability_state(actor_id)
        if passive_id not in state.active_passives:
            cap=max(len(state.active_passives)+1,1) if capacity is None else int(capacity)
            state.equip_passive(passive_id,capacity=cap)
        self._store_ability_state(actor_id,state); return passive_id

    def allocate_progression(self,actor_id,graph_id,node_id,count=1):
        allocation=self.save.rpg_state.progression_allocations[str(actor_id)]
        return allocation.allocate(str(graph_id),str(node_id),int(count))

    def grant_actor_points(self, actor_id, **point_amounts):
        actor_id=str(actor_id); state=self.save.rpg_state.actor_progression[actor_id]
        points=dict(state.points)
        for key, amount in point_amounts.items():
            key=str(key).strip(); amount=float(amount)
            if not key or amount < 0:
                raise ValueError("actor point grants require non-negative named amounts")
            points[key]=points.get(key,0.0)+amount
        self.save.rpg_state.actor_progression[actor_id]=ActorProgressionState(
            state.level,state.experience,points=points,
            unlocked_class_ids=state.unlocked_class_ids,active_class_ids=state.active_class_ids,
        )
        allocation=self.save.rpg_state.progression_allocations.get(actor_id)
        if allocation is not None and "ap" in point_amounts:
            allocation.grant("ap", point_amounts["ap"])
        return dict(points)

    def grant_actor_experience(self, actor_id, amount, *, level_threshold=1000.0, ap_per_level=2.0, ability_points_per_level=1.0):
        """Generic acceptance/runtime helper for actor-level progression.

        Projects choose the threshold and point vocabulary; the engine does not
        attach semantics to AP/ability_points beyond persisting named balances.
        """
        actor_id=str(actor_id); amount=float(amount); threshold=float(level_threshold)
        if amount < 0 or threshold <= 0:
            raise ValueError("experience amount must be >= 0 and threshold > 0")
        state=self.save.rpg_state.actor_progression[actor_id]
        total=state.experience+amount
        old_level=state.level
        new_level=max(old_level, int(total//threshold)+1)
        gained=max(0,new_level-old_level)
        points=dict(state.points)
        if gained:
            points["ap"]=points.get("ap",0.0)+gained*float(ap_per_level)
            points["ability_points"]=points.get("ability_points",0.0)+gained*float(ability_points_per_level)
            allocation=self.save.rpg_state.progression_allocations.get(actor_id)
            if allocation is not None and ap_per_level:
                allocation.grant("ap",gained*float(ap_per_level))
        self.save.rpg_state.actor_progression[actor_id]=ActorProgressionState(
            new_level,total,points=points,unlocked_class_ids=state.unlocked_class_ids,
            active_class_ids=state.active_class_ids,
        )
        return {"old_level":old_level,"new_level":new_level,"levels_gained":gained,"experience":total,"points":dict(points)}

    def set_secondary_class(self, actor_id, class_id):
        actor_id=str(actor_id); class_id=str(class_id)
        state=self.save.rpg_state.actor_progression[actor_id]
        if class_id not in state.unlocked_class_ids:
            raise GameSessionError(f"class is locked: {class_id}")
        primary=(state.active_class_ids or state.unlocked_class_ids)[:1]
        values=tuple(dict.fromkeys((*primary,class_id)))
        return self.set_active_classes(actor_id,values[:2])

    def set_passives(self, actor_id, passive_ids, *, capacity=4):
        actor_id=str(actor_id); values=tuple(dict.fromkeys(str(x) for x in passive_ids))
        if len(values)>int(capacity):
            raise GameSessionError("passive loadout exceeds capacity")
        for passive_id in values:
            if passive_id not in self.project.rpg_database.passives:
                raise KeyError(passive_id)
        state=self._ability_state(actor_id); state.active_passives=values
        self._store_ability_state(actor_id,state); return values

    def equip_definition(self, actor_id, equipment_id, *, slot_id=None, replace=True):
        actor_id=str(actor_id); equipment_id=str(equipment_id)
        definition=self.project.rpg_database.equipment[equipment_id]
        slot_id=str(slot_id or definition.slot)
        loadout=self.save.rpg_state.loadouts[actor_id]
        if replace and loadout.equipped(slot_id):
            loadout.unequip(slot_id,0)
        prefix=f"{equipment_id}:runtime:{actor_id}:"
        used={item.instance_id for item in loadout.equipped()}
        sequence=1
        while f"{prefix}{sequence}" in used:
            sequence+=1
        instance=EquippedItem(
            definition, instance_id=f"{prefix}{sequence}",
            growth=(EquipmentGrowthRuntime(self.project.rpg_database.equipment_growth[definition.growth_id]) if definition.growth_id else None),
        )
        loadout.equip(slot_id,instance,validate_requirements=False)
        return instance

    def upgrade_equipment(self, actor_id, instance_id, node_id):
        loadout=self.save.rpg_state.loadouts[str(actor_id)]
        item=next((x for x in loadout.equipped() if x.instance_id==str(instance_id)),None)
        if item is None: raise KeyError(instance_id)
        growth=item.ensure_growth(self.project.rpg_database.equipment_growth)
        return growth.unlock(str(node_id))

    def attach_equipment(self,actor_id,instance_id,socket_id,attachment_id):
        loadout=self.save.rpg_state.loadouts[str(actor_id)]
        item=next((x for x in loadout.equipped() if x.instance_id==str(instance_id)),None)
        if item is None: raise KeyError(instance_id)
        attachment=self.project.rpg_database.attachments[str(attachment_id)]
        if str(socket_id) in item.attachments: item.detach(str(socket_id))
        item.attach(str(socket_id),attachment)
        return attachment

    def resolve_actor_build(self,actor_id):
        actor_id=str(actor_id)
        db=self.project.rpg_database
        base=db.actors[actor_id]
        progress=self.save.rpg_state.actor_progression.get(actor_id)
        definition=base
        if progress is not None and progress.active_class_ids:
            authored={x.class_id:x for x in base.class_assignments}
            assignments=[]
            for index,class_id in enumerate(progress.active_class_ids):
                source=authored.get(class_id)
                assignments.append(ClassAssignment(
                    class_id,
                    assignment_id=(source.assignment_id if source else f"save:{actor_id}:{class_id}"),
                    role=(source.role if source else ("primary" if index==0 else "secondary")),
                    enabled=True,priority=(source.priority if source else 10-index),
                    progression_track_ids=(source.progression_track_ids if source else ()),
                    tags=(source.tags if source else ()),
                ))
            definition=type(base)(
                base.actor_id,base.display_name,class_assignments=tuple(assignments),
                base_stats=base.base_stats,base_resources=base.base_resources,
                tags=base.tags,abilities=base.abilities,
            )
        actor=RpgActorRuntime(definition,class_definitions=db.classes)
        snapshot=self.save.rpg_state.actor_snapshots.get(actor_id)
        if snapshot is not None: actor.restore(snapshot)
        return resolve_actor_build(
            actor,progression=self.save.rpg_state.progression,
            allocations=self.save.rpg_state.progression_allocations.get(actor_id),
            loadout=self.save.rpg_state.loadouts.get(actor_id),
            passives=db.passives,evolution_rules=db.ability_evolutions.values(),
        )

    def _actor_member(self,actor_id):
        build=self.resolve_actor_build(actor_id)
        subject=GameplaySubject(build.stats,build.resources,build.tags)
        speed=build.stats.get("speed")
        return PartyMember(str(actor_id),"heroes",subject,ability_ids=build.abilities,initiative=speed)

    def _enemy_member(self,enemy_id,index):
        definition=self.project.rpg_database.enemies[enemy_id]
        runtime=definition.instantiate()
        subject=GameplaySubject(runtime.stats,runtime.resources,runtime.tags)
        speed=runtime.stats.get("speed")
        return PartyMember(
            f"{enemy_id}:{index}","enemies",subject,
            ability_ids=definition.abilities,initiative=speed,
        )

    def start_encounter(self,encounter_id):
        if self.mode!="field": raise GameSessionError("encounter already active")
        db=self.project.rpg_database
        encounter=db.encounters[str(encounter_id)]
        active=self.save.rpg_state.party_active_actor_ids
        heroes=tuple(self._actor_member(x) for x in active)
        enemies=[]; enemy_definition_ids=[]
        serial=0
        for member in encounter.members:
            for _ in range(member.count):
                serial+=1
                enemies.append(self._enemy_member(member.enemy_id,serial))
                enemy_definition_ids.append(member.enemy_id)

        registry=AbilityRegistry()
        used={a for member in (*heroes,*enemies) for a in member.ability_ids}
        for ability_id in sorted(used):
            definition=self.project.gameplay_library.abilities.get(ability_id)
            if definition is not None: registry.register(definition)

        scheduler=next(iter(db.battle_schedulers.values()),None)
        self.battle=BattleRuntime(
            (Party("heroes",heroes),Party("enemies",tuple(enemies))),
            AbilityRuntime(registry),
            is_active=lambda m: (
                "vitality" not in m.subject.resources.to_data()["values"]
                or m.subject.resources.current("vitality")>0
            ),
            resource_definitions=db.battle_resources.values(),
            interaction_rules=db.interaction_rules.values(),
            outcome_checks=db.outcome_checks.values(),
            state_policies=db.battle_state_policies.values(),
            targeting_definitions=db.battle_targeting.values(),
            objective_definitions=db.battle_objectives.values(),
            escape_rules=db.escape_rules.values(),
            scheduler_definition=scheduler,
            action_timing_definitions=db.action_timings.values(),
            action_sequence_definitions=db.action_sequences.values(),
            gauge_composition_definitions=db.gauge_compositions.values(),
            reaction_definitions=db.reactions.values(),
            enemy_ai_definitions=db.enemy_ai.values(),
            transaction_policies=db.action_transactions.values(),
            rng_seed=157,
        )
        self.encounter_id=str(encounter_id)
        self._enemy_ids=tuple(enemy_definition_ids)
        self.mode="battle"
        return self.battle

    def execute(self,actor_id,ability_id,target_ids):
        if self.mode!="battle": raise GameSessionError("no active battle")
        return self.battle.execute(BattleAction(actor_id,ability_id,target_ids))

    def enemy_turn(self,member_id,ai_id):
        if self.mode!="battle": raise GameSessionError("no active battle")
        decision=self.battle.enemy_ai.decide(self.battle,ai_id,member_id,rng=self.battle.rng)
        if decision is None:return None
        return self.battle.enemy_ai.execute_decision(self.battle,decision,rng=self.battle.rng)

    def active_enemy_ids(self):
        if self.battle is None:return ()
        return tuple(
            m.member_id for m in self.battle.parties["enemies"].members
            if self.battle.is_active(m)
        )

    def active_hero_ids(self):
        if self.battle is None:return ()
        return tuple(
            m.member_id for m in self.battle.parties["heroes"].members
            if self.battle.is_active(m)
        )

    def _write_battle_heroes_to_save(self):
        for member in self.battle.parties["heroes"].members:
            old=self.save.rpg_state.actor_snapshots.get(member.member_id)
            ability_state=None if old is None else old.ability_state
            self.save.rpg_state.actor_snapshots[member.member_id]=RpgActorSnapshot(
                member.member_id,
                member.subject.stats.to_data(),
                member.subject.resources.to_data(),
                member.subject.tags.to_data(),
                ability_state,
            )

    def finish_victory(self):
        if self.mode!="battle": raise GameSessionError("no active battle")
        if self.active_enemy_ids():
            raise GameSessionError("encounter is not defeated")
        self._write_battle_heroes_to_save()
        db=self.project.rpg_database
        reward_runtime=RewardRuntime(
            inventory=self.save.rpg_state.inventory,
            progression=self.save.rpg_state.progression,
            currencies=self.save.rpg_state.currencies,
        )
        applied=[]
        rng=random.Random(157)
        for enemy_id in self._enemy_ids:
            reward=roll_reward(db.enemies[enemy_id].reward,rng)
            applied.append(reward_runtime.apply(reward))
        self.save.event_context.set_switch(f"encounter.{self.encounter_id}.defeated",True)
        self.mode="field"; self.battle=None; self.encounter_id=None; self._enemy_ids=()
        self.interaction.reset()
        return tuple(applied)

    def sync_world_state(self):
        t=self.player.get(Transform)
        self.save.scene_id=self.scene.id
        self.save.player_entity_id=self.player.id
        self.save.player_facing=self.facing
        self.save.player_position=(t.x,t.y)
        return self.save
