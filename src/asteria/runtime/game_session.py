from __future__ import annotations

import random
from dataclasses import dataclass, replace

from asteria.core import Transform
from asteria.core.lifecycle import LifecycleHookBus
from asteria.core.scene_transition import carry_persistent_entities
from asteria.events import EventRunner, SceneEventRuntime, WorldCommandRouter
from asteria.gameplay import AbilityRegistry, AbilityRuntime, GameplaySubject
from asteria.rpg import (
    ActorAbilityState, ActorProgressionState, BattleAction, BattleRuntime, BattleSessionRules, ClassAssignment, EquipmentGrowthRuntime, EquippedItem, Party, PartyMember, RewardRuntime, RpgActorSnapshot,
    RpgActorRuntime, roll_reward, resolve_actor_build,
)
from asteria.rpg.economy import ShopRuntime
from asteria.rpg.enemies import RewardDefinition
from asteria.rpg.quests import QuestLog
from asteria.rpg.targeting import TargetRelation
from asteria.runtime.input import InputSnapshot
from asteria.runtime.interaction import InteractionController
from asteria.runtime.world_command_handlers import move_entity_to_scene, register_standard_world_commands


class GameSessionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BattleLogEntry:
    """One canonical battle fact, in order, for presentation adapters to consume.

    kinds: ``battle_started``, ``turn``, ``action``, ``gauge``, ``capture``, ``battle_finished``.
    ``outcomes`` pairs each target with its non-mutating interaction outcome.
    """

    sequence: int
    kind: str
    member_id: str = ""
    ability_id: str = ""
    target_ids: tuple[str, ...] = ()
    outcomes: tuple = ()
    data: object = None


class GameSessionRuntime:
    """Generic Project + GameRuntimeSave integration runtime.

    This is the engine-level seam used by reference/full-play validation. It does
    not know project-specific actor, boss, job, resource, weakness or party-size
    names. Project definitions provide those rules; GameRuntimeSave provides the
    mutable player state.
    """

    def __init__(self, project, runtime_save):
        runtime_save.validate(project)
        runtime_save.rpg_state.bind_database(project.rpg_database)
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
        self._captured=set()
        self.battle_log=[]
        self._log_sequence=0
        self._logged_turn=None
        # Event programs run here: one foreground runner for interactions plus
        # the current scene's autorun/parallel scheduler.
        self.presentation_requests=[]
        self.event_errors=[]
        self.world_commands=register_standard_world_commands(WorldCommandRouter(),self)
        self.events=EventRunner(project.event_programs,context=runtime_save.event_context,world_commands=self.world_commands)
        if runtime_save.active_event is not None:
            self.events.restore(runtime_save.active_event)
        self.scene_events=None
        self.open_shop_id=None
        self._field_simulation={}
        self._build_scene_events()

    def set_player_position(self,x,y):
        t=self.player.get(Transform); t.x=float(x); t.y=float(y)
        self.save.player_position=(t.x,t.y)
        return self.save.player_position

    def set_player_facing(self,facing):
        self.facing=str(facing); self.save.player_facing=self.facing
        return self.facing

    def field_step(self,actions=None):
        """Feed field input; an interaction starts its event program in the foreground runner."""
        if self.mode!="field":
            raise GameSessionError("field input unavailable outside field mode")
        if self.event_busy:
            return None
        trigger=self.interaction.step(InputSnapshot(dict(actions or {})),self.scene,self.player,self.facing)
        if trigger is None:
            return None
        self.events.start_trigger(trigger,replace=True)
        self.update_events(0.0)
        return trigger

    def _field_systems(self):
        """Field AI and spawn systems for the current scene (created on first use)."""
        systems=self._field_simulation.get(self.scene.id)
        if systems is None:
            from asteria.runtime.collision import CollisionWorld
            from asteria.runtime.field_ai import FieldAISystem, SpawnSystem
            from asteria.runtime.preview import build_preview_registry
            scene=self.scene
            def blocking(entity):
                # Enemies are blocked by solid colliders, not by the player they chase.
                return CollisionWorld.from_scene(scene).blocking_query(exclude={entity.id,self.player.id})
            systems=(
                SpawnSystem(self.project.prefabs,build_preview_registry(),switches=self.save.event_context.get_switch,
                            rng=random.Random(f"{scene.id}:spawn")),
                FieldAISystem(blocking,rng=random.Random(f"{scene.id}:ai"),default_target_id=self.player.id),
            )
            self._field_simulation[scene.id]=systems
        return systems

    def field_update(self,dt):
        """Advance field enemies and spawn zones, then start any touched visible encounter."""
        if self.mode!="field" or self.event_busy:
            return None
        for system in self._field_systems():
            system.update(self.scene,float(dt))
        return self.check_visible_encounter()

    def check_visible_encounter(self):
        """Start the encounter of a field enemy (VisibleEncounterComponent) the player touches."""
        from asteria.runtime.field_ai import VisibleEncounterComponent, touched_encounter
        if self.mode!="field" or self.event_busy:
            return None
        entity=touched_encounter(self.scene,self.player)
        if entity is None:
            return None
        spec=entity.get(VisibleEncounterComponent)
        encounter_id=spec.encounter_id
        if spec.remove_on_start:
            self.scene.remove_entity(entity)
        self.start_encounter(encounter_id)
        return encounter_id

    def _build_scene_events(self):
        bindings=self.project.scene_event_bindings.get(self.scene.id)
        self.scene_events=None if bindings is None else SceneEventRuntime.build(
            bindings,self.project.event_programs,context=self.save.event_context,world_commands=self.world_commands,
        )

    @property
    def event_busy(self):
        """True while a foreground or autorun event blocks player control."""
        return self.events.busy or (self.scene_events is not None and self.scene_events.scheduler.autorun_busy)

    def _dialogue_runner(self):
        if self.events.dialogue.blocked:
            return self.events
        if self.scene_events is not None:
            for spec in self.scene_events.scheduler.specs():
                instance=self.scene_events.scheduler.instance(spec.event_id)
                if instance is not None and instance.runner.dialogue.blocked:
                    return instance.runner
        return None

    @property
    def pending_dialogue(self):
        """The DialogueRequest or ChoiceRequest waiting for the player, if any."""
        runner=self._dialogue_runner()
        if runner is None: return None
        return runner.dialogue.dialogue or runner.dialogue.choice

    def acknowledge_dialogue(self):
        runner=self._dialogue_runner()
        if runner is None: raise GameSessionError("no dialogue is waiting")
        runner.acknowledge_dialogue()
        return self.update_events(0.0)

    def choose(self,index):
        runner=self._dialogue_runner()
        if runner is None: raise GameSessionError("no choice is waiting")
        selected=runner.choose(index)
        self.update_events(0.0)
        return selected

    def update_events(self,dt=0.0):
        """Advance running event programs. Failures stop that event and are kept in event_errors."""
        output=()
        try:
            output=self.events.update(dt)
        except Exception as exc:
            self.event_errors.append(exc)
            self.events.stop()
        if not self.events.busy:
            self.events.clear_completed()
        if self.scene_events is not None and self.mode=="field" and not self.events.busy:
            try:
                self.scene_events.update(dt)
            except Exception as exc:
                self.event_errors.append(exc)
                self.scene_events.scheduler.stop_all()
        return output

    def transfer_player(self,scene_id,x=None,y=None,*,facing=None):
        """Move the player entity to another scene (or position) and switch event bindings."""
        destination=self.project.scene(str(scene_id))
        if destination is None: raise GameSessionError(f"unknown scene: {scene_id}")
        changed=destination is not self.scene
        previous=self.scene
        transform=move_entity_to_scene(self.player,self.scene,destination,x,y)
        if changed: carry_persistent_entities(previous,destination)
        self.scene=destination
        self.save.scene_id=destination.id
        self.save.player_position=(transform.x,transform.y)
        if facing: self.set_player_facing(facing)
        if changed:
            self.interaction.reset()
            self._build_scene_events()
        return destination

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
        instance=EquippedItem(
            definition, instance_id=f"{equipment_id}:runtime:{actor_id}:{len(loadout.equipped())+1}",
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
            is_active=self._is_conscious,
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
            hooks=LifecycleHookBus(),
        )
        self.encounter_id=str(encounter_id)
        self._enemy_ids=tuple(enemy_definition_ids)
        self._captured=set()
        for enemy_id in sorted(set(enemy_definition_ids)):
            self.world.note_enemy(enemy_id,"seen")
        self.mode="battle"
        self.battle_log.clear(); self._logged_turn=None
        self._log("battle_started",data={"encounter_id":self.encounter_id})
        return self.battle

    @property
    def rules(self):
        """Project battle session rules; the first by id, or inert defaults."""
        values=self.project.rpg_database.battle_session_rules
        return values[sorted(values)[0]] if values else BattleSessionRules("default")

    def _is_conscious(self,member):
        resource=self.rules.knockout_resource_id
        if not resource or resource not in member.subject.resources.to_data()["values"]:
            return True
        return member.subject.resources.current(resource)>0

    def ability_relation(self,ability_id):
        if self.mode!="battle": raise GameSessionError("no active battle")
        definition=self.battle.targeting.definition_for(ability_id)
        return TargetRelation.OPPONENT if definition is None else definition.relation

    def default_targets(self,actor_id,ability_id):
        """Targets a manual selection would default to, from the ability's targeting data."""
        if self.mode!="battle": raise GameSessionError("no active battle")
        definition=self.battle.targeting.definition_for(ability_id)
        if definition is not None and definition.relation==TargetRelation.SELF:
            return (str(actor_id),)
        candidates=self.battle.targeting.candidates(actor_id,ability_id)
        maximum=1 if definition is None else max(1,definition.maximum_targets)
        return tuple(candidates[:maximum])

    def max_boost_level(self,actor_id):
        if self.mode!="battle": raise GameSessionError("no active battle")
        rules=self.rules
        if not rules.boost_enabled: return 0
        available=self.battle.battle_resources.current(actor_id,rules.boost_resource_id)
        return min(rules.boost_max_level,int(available//rules.boost_cost_per_level))

    def use_ability(self,actor_id,ability_id,target_ids=None,*,boost_level=0):
        """Run one player action through project rules: targeting, boost and hit gauges.

        Each boost level spends ``boost_cost_per_level`` of the boost resource
        and repeats the action once more. Every action against opponents emits
        ``hit_trigger`` into all project gauge compositions.
        """
        if self.mode!="battle": raise GameSessionError("no active battle")
        rules=self.rules
        boost_level=int(boost_level)
        if boost_level<0 or boost_level>self.max_boost_level(actor_id):
            raise GameSessionError(f"boost level {boost_level} is not available")
        targets=tuple(target_ids) if target_ids is not None else self.default_targets(actor_id,ability_id)
        if not targets: raise GameSessionError(f"{ability_id} has no valid targets")
        offensive=self.ability_relation(ability_id)==TargetRelation.OPPONENT
        if boost_level:
            self.battle.battle_resources.spend(
                actor_id,rules.boost_resource_id,boost_level*rules.boost_cost_per_level,trigger="rpg.session.boost",
            )
        results=[]
        for _ in range(boost_level+1):
            if offensive:
                targets=tuple(t for t in targets if self.battle.is_active(self.battle.member(t)))
                if not targets: break
            before=self._knockout_values(targets)
            result=self.execute(actor_id,ability_id,targets)
            results.append(result)
            outcomes=self._action_outcomes(actor_id,ability_id,targets,before) if offensive else ()
            self._log("action",member_id=str(actor_id),ability_id=str(ability_id),target_ids=tuple(targets),outcomes=outcomes)
            for target_id,outcome in outcomes:
                for composition_id in sorted(self.battle.gauge_compositions.definitions):
                    gauge=self.battle.apply_gauge_impact(
                        composition_id,actor_id,target_id,trigger=rules.hit_trigger,outcome=outcome,
                    )
                    if getattr(gauge,"thresholds",()):
                        self._log("gauge",member_id=str(target_id),data=gauge)
        return tuple(results)

    def current_turn_actor(self):
        """Member whose turn it is under the battle's scheduler; starts new rounds as needed."""
        if self.mode!="battle": raise GameSessionError("no active battle")
        if not self.active_enemy_ids() or not self.active_hero_ids(): return None
        actor=self.battle.next_actor()
        if actor is None:
            self.battle.start_next_round()
            actor=self.battle.next_actor()
        if actor is None: return None
        key=(self.battle.turn_queue.round_index,actor.member_id)
        if key!=self._logged_turn:
            self._logged_turn=key
            self._log("turn",member_id=actor.member_id)
        return actor.member_id

    def end_turn(self):
        if self.mode!="battle": raise GameSessionError("no active battle")
        self._logged_turn=None
        return self.battle.advance_turn()

    def enemy_act(self,member_id):
        """One enemy action: its bound AI, else its first ability on default targets."""
        if self.mode!="battle": raise GameSessionError("no active battle")
        enemy_id=str(member_id).split(":",1)[0]
        binding=self.project.rpg_database.enemy_behavior_bindings.get(enemy_id)
        if binding is not None:
            return self.enemy_turn(member_id,binding.ai_id)
        definition=self.project.rpg_database.enemies.get(enemy_id)
        if definition is None or not definition.abilities: return None
        ability_id=definition.abilities[0]
        targets=self.default_targets(member_id,ability_id)
        if not targets: return None
        before=self._knockout_values(targets)
        result=self.execute(member_id,ability_id,targets)
        self._log("action",member_id=str(member_id),ability_id=ability_id,target_ids=targets,
                  outcomes=self._action_outcomes(member_id,ability_id,targets,before))
        return result

    def run_enemy_turns(self,*,limit=1000):
        """Advance through enemy turns until a hero must act or the battle is decided.

        Returns ``(hero_id_or_None, ((enemy_member_id, result_or_error), ...))``.
        """
        log=[]
        for _ in range(int(limit)):
            actor_id=self.current_turn_actor()
            if actor_id is None or self.battle.member(actor_id).side!="enemies":
                if not self.active_hero_ids():
                    self._log("battle_finished",data={"winning_sides":("enemies",),"defeated_sides":("heroes",)})
                return actor_id,tuple(log)
            try:
                outcome=self.enemy_act(actor_id)
            except Exception as exc:
                outcome=exc
            log.append((actor_id,outcome))
            self.end_turn()
        raise GameSessionError("enemy turns did not yield to a hero")

    def _log(self,kind,**values):
        self._log_sequence+=1
        entry=BattleLogEntry(self._log_sequence,kind,**values)
        self.battle_log.append(entry)
        return entry

    def drain_battle_log(self):
        """Return and clear battle facts recorded since the last drain."""
        values=tuple(self.battle_log); self.battle_log.clear()
        return values

    def _knockout_values(self,target_ids):
        resource=self.rules.knockout_resource_id
        values={}
        for target_id in target_ids:
            pool=self.battle.member(target_id).subject.resources
            if resource and resource in pool.to_data()["values"]:
                values[target_id]=pool.current(resource)
        return values

    def _action_outcomes(self,actor_id,ability_id,target_ids,before=None):
        """Interaction outcomes for opponent targets, valued by the observed knockout-resource change.

        Outcome tags/disposition come from the non-mutating interaction resolver;
        ``value.resolved_value`` is replaced by how much the knockout resource
        actually dropped (when ``before`` was measured), so presentation shows
        what happened rather than a multiplier.
        """
        if self.ability_relation(ability_id)!=TargetRelation.OPPONENT: return ()
        action=BattleAction(actor_id,ability_id,tuple(target_ids))
        after=self._knockout_values(target_ids)
        outcomes=[]
        for target_id in target_ids:
            outcome=self.battle.resolve_interaction(action,target_id,1.0)
            if before is not None and target_id in before and target_id in after:
                observed=max(0.0,before[target_id]-after[target_id])
                outcome=replace(outcome,value=replace(outcome.value,resolved_value=observed))
            outcomes.append((target_id,outcome))
        return tuple(outcomes)

    def preview(self,actor_id,ability_id,target_ids):
        """Predicted resource changes of an action (same pipeline as execute; nothing mutates)."""
        if self.mode!="battle": raise GameSessionError("no active battle")
        return self.battle.preview_action(BattleAction(actor_id,ability_id,tuple(target_ids)))

    def execute(self,actor_id,ability_id,target_ids):
        if self.mode!="battle": raise GameSessionError("no active battle")
        return self.battle.execute(BattleAction(actor_id,ability_id,target_ids))

    def enemy_turn(self,member_id,ai_id):
        if self.mode!="battle": raise GameSessionError("no active battle")
        decision=self.battle.enemy_ai.decide(self.battle,ai_id,member_id,rng=self.battle.rng)
        if decision is None:return None
        before=self._knockout_values(decision.target_ids)
        result=self.battle.enemy_ai.execute_decision(self.battle,decision,rng=self.battle.rng)
        ability_id=decision.payload.get("ability_id") if decision.action_kind=="ability" else None
        if ability_id:
            self._log("action",member_id=str(member_id),ability_id=str(ability_id),target_ids=tuple(decision.target_ids),
                      outcomes=self._action_outcomes(member_id,ability_id,decision.target_ids,before))
        return result

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

    # --- economy and quests -------------------------------------------------

    def _reward_runtime(self):
        return RewardRuntime(
            inventory=self.save.rpg_state.inventory,
            progression=self.save.rpg_state.progression,
            currencies=self.save.rpg_state.currencies,
        )

    @property
    def shops(self):
        state=self.save.rpg_state
        return ShopRuntime(self.project.rpg_database.shops,inventory=state.inventory,currencies=state.currencies,stock=state.shop_stock)

    @property
    def quest_log(self):
        def grant(reward:RewardDefinition):
            self._reward_runtime().apply(roll_reward(reward,random.Random(0)))
        return QuestLog(
            self.project.rpg_database.quests,self.save.rpg_state.quests,
            inventory=self.save.rpg_state.inventory,
            switches=self.save.event_context.get_switch,
            grant_reward=grant,
        )

    def craft(self,payload,*,station="",quality_bonus=0.0,rng=None):
        """Craft with the project's recipes against the saved inventory and progression."""
        from asteria.rpg import CompositionRuntime
        runtime=CompositionRuntime(self.project.rpg_database.composition_recipes.values())
        state=self.save.rpg_state
        result=runtime.craft(state.inventory,payload,station=station,rng=rng,quality_bonus=quality_bonus,progression=state.progression)
        self.refresh_quests()
        return result

    def open_shop(self,shop_id):
        shop_id=str(shop_id)
        if shop_id not in self.project.rpg_database.shops:
            raise GameSessionError(f"unknown shop: {shop_id}")
        self.open_shop_id=shop_id
        return shop_id

    def close_shop(self):
        self.open_shop_id=None

    def buy(self,item_id,quantity=1,*,shop_id=None):
        result=self.shops.buy(shop_id or self.open_shop_id,item_id,quantity)
        self.refresh_quests()
        return result

    def sell(self,item_id,quantity=1,*,shop_id=None):
        result=self.shops.sell(shop_id or self.open_shop_id,item_id,quantity)
        self.refresh_quests()
        return result

    def _quest_switches(self):
        for quest_id,progress in self.save.rpg_state.quests.items():
            for status in ("active","completed","failed"):
                self.save.event_context.set_switch(f"quest.{quest_id}.{status}",progress.status==status)

    def _quest_call(self,method,*args):
        log=self.quest_log
        result=getattr(log,method)(*args)
        self._quest_switches()
        self.refresh_achievements()
        return result

    # --- world record: reputation, relationships, counters, achievements, bestiary

    @property
    def world(self):
        return self.save.rpg_state.world

    def refresh_achievements(self):
        db=self.project.rpg_database
        log=QuestLog(db.quests,self.save.rpg_state.quests)
        unlocked=self.world.unlock_ready(db.achievements,factions=db.factions,
                                         switches=self.save.event_context.get_switch,quest_status=log.status)
        for achievement_id in unlocked:
            self.save.event_context.set_switch(f"achievement.{achievement_id}.unlocked",True)
        return unlocked

    def change_reputation(self,faction_id,amount):
        faction=self.project.rpg_database.factions.get(str(faction_id))
        if faction is None: raise GameSessionError(f"unknown faction: {faction_id}")
        value=self.world.change_reputation(faction,amount)
        self.save.event_context.set_variable(f"reputation.{faction.faction_id}",value)
        self.refresh_achievements()
        return value

    def change_relationship(self,subject_id,amount):
        value=self.world.change_relationship(subject_id,amount)
        self.save.event_context.set_variable(f"relationship.{subject_id}",value)
        return value

    def add_counter(self,counter_id,amount=1):
        value=self.world.add_counter(counter_id,amount)
        self.refresh_achievements()
        return value

    def capture_chance(self,target_id):
        """Chance (0–1) that capturing ``target_id`` succeeds now, or None if it cannot be captured."""
        if self.mode!="battle" or str(target_id) not in self.active_enemy_ids():
            return None
        rule=self.project.rpg_database.capture_rules.get(str(target_id).rsplit(":",1)[0])
        if rule is None:
            return None
        resources=self.battle.member(str(target_id)).subject.resources
        resource=self.rules.knockout_resource_id
        ratio=1.0
        if resource and resource in resources.to_data()["values"] and resources.maximum(resource)>0:
            ratio=resources.current(resource)/resources.maximum(resource)
        return rule.chance(ratio)

    def capture_targets(self):
        """``(member_id, chance, item_id)`` for every enemy that can be captured right now."""
        result=[]
        for member_id in self.active_enemy_ids():
            chance=self.capture_chance(member_id)
            if chance is not None:
                rule=self.project.rpg_database.capture_rules[member_id.rsplit(":",1)[0]]
                result.append((member_id,chance,rule.item_id))
        return tuple(result)

    def attempt_capture(self,actor_id,target_id,*,rng=None):
        """Try to capture enemy ``target_id``; on success it leaves battle and its actor joins the roster."""
        if self.mode!="battle": raise GameSessionError("no active battle")
        target_id=str(target_id)
        if target_id not in self.active_enemy_ids(): raise GameSessionError(f"{target_id} cannot be captured now")
        enemy_id=target_id.rsplit(":",1)[0]
        rule=self.project.rpg_database.capture_rules.get(enemy_id)
        if rule is None: raise GameSessionError(f"{enemy_id} cannot be captured")
        state=self.save.rpg_state
        if rule.item_id and not state.inventory.remove(rule.item_id,1):
            raise GameSessionError(f"capturing needs {rule.item_id}")
        roll=(rng or self.battle.rng).random()
        success=roll<self.capture_chance(target_id)
        self._log("capture",member_id=str(actor_id),target_ids=(target_id,),data={"success":success,"actor_id":rule.actor_id})
        if not success:
            return False
        self.battle.remove_combatant(target_id,state_id="captured",reason="captured")
        self._captured.add(target_id)
        self.world.note_enemy(enemy_id,"captured")
        if rule.actor_id not in state.party_actor_ids:
            state.party_actor_ids=state.party_actor_ids+(rule.actor_id,)
        self.refresh_achievements()
        return True

    def start_quest(self,quest_id): return self._quest_call("start",quest_id)
    def advance_quest(self,quest_id,objective_id,amount=1): return self._quest_call("advance",quest_id,objective_id,amount)
    def complete_quest(self,quest_id): return self._quest_call("complete",quest_id)
    def fail_quest(self,quest_id): return self._quest_call("fail",quest_id)
    def refresh_quests(self): return self._quest_call("refresh")

    LOOT_LUCK_VARIABLE="loot.luck"

    @property
    def loot_luck(self):
        """Luck applied to loot rolls; events set it through the ``loot.luck`` variable."""
        try:
            return float(self.save.event_context.get_variable(self.LOOT_LUCK_VARIABLE,0.0) or 0.0)
        except (TypeError,ValueError):
            return 0.0

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
        # Captured enemies joined the party: they give no reward and do not count as defeated.
        defeated=tuple(enemy_id for serial,enemy_id in enumerate(self._enemy_ids,1)
                       if f"{enemy_id}:{serial}" not in self._captured)
        for enemy_id in defeated:
            reward=roll_reward(db.enemies[enemy_id].reward,rng,luck=self.loot_luck,switches=self.save.event_context.get_switch)
            applied.append(reward_runtime.apply(reward))
        self._log("battle_finished",data={"winning_sides":("heroes",),"defeated_sides":("enemies",)})
        self.save.event_context.set_switch(f"encounter.{self.encounter_id}.defeated",True)
        log=self.quest_log
        for enemy_id in defeated:
            log.record_defeat(enemy_id)
            self.world.note_enemy(enemy_id,"defeated")
        self._quest_switches()
        self.refresh_achievements()
        self.mode="field"; self.battle=None; self.encounter_id=None; self._enemy_ids=()
        self.interaction.reset()
        return tuple(applied)

    def sync_world_state(self):
        t=self.player.get(Transform)
        self.save.scene_id=self.scene.id
        self.save.player_entity_id=self.player.id
        self.save.player_facing=self.facing
        self.save.player_position=(t.x,t.y)
        self.save.active_event=self.events.snapshot()
        return self.save
