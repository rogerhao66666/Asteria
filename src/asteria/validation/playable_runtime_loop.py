from __future__ import annotations

from dataclasses import dataclass

from asteria.core import Entity, Scene, Transform
from asteria.runtime import InputSnapshot, Interaction2DComponent, InteractionController

from .rpg_validation_project import AsteriaRpgValidationProject


@dataclass(frozen=True, slots=True)
class PlayableRuntimeState:
    mode: str
    player_position: tuple[float, float]
    player_facing: str
    nearby_monster_id: str | None
    active_encounter_id: str | None
    level: int
    jobs: tuple[tuple[str, str], ...]
    equipped_instance_ids: tuple[str, ...]
    abilities: tuple[str, ...]
    inventory: tuple[tuple[str, int], ...]
    battle_player_vitality: float | None
    battle_enemy_vitality: float | None


class PlayableRpgRuntimeLoop:
    """Minimal playable RPG validation loop.

    This is deliberately simple:
      character configuration -> field -> face monster + Interact -> battle
      -> finish battle -> field.

    World interaction uses Asteria's canonical Scene/Entity/Transform and
    Interaction2DComponent/InteractionController. Character configuration uses
    the existing canonical RPG validation project. Battle creation is rebuilt
    from the *current* resolved actor state at encounter start.
    """

    def __init__(self):
        self.project = AsteriaRpgValidationProject()
        self.scene = Scene("Validation Field")
        self.player = Entity("Player")
        self.player.add_component(Transform(0.0, 0.0))
        self.scene.add_entity(self.player)

        self.monster = Entity("Training Monster")
        self.monster.add_component(Transform(20.0, 0.0))
        interaction = self.monster.add_component(Interaction2DComponent())
        interaction.range = 24.0
        interaction.require_facing = True
        interaction.event_program_id = "encounter:training_monster"
        interaction.local_scope_id = "training_monster"
        self.scene.add_entity(self.monster)

        self.interaction = InteractionController(action="interact")
        self.player_facing = "right"
        self.mode = "field"
        self.active_encounter_id = None
        self.battle = None
        self.scene.enter()

    # ---- character / progression -------------------------------------------------

    def award_experience(self, amount):
        return self.project.character.award_experience(amount)

    def unlock_job(self, class_id):
        return self.project.character.unlock_job(class_id)

    def set_job(self, slot_id, class_id):
        return self.project.character.set_job(slot_id, class_id)

    def clear_job(self, slot_id):
        return self.project.character.clear_job(slot_id)

    def allocate_skill(self, graph_id, node_id, count=1):
        return self.project.character.allocate_node(graph_id, node_id, count)

    def refund_skill(self, graph_id, node_id, count=1):
        return self.project.character.refund_node(graph_id, node_id, count)

    def equip_passive(self, passive_id, *, capacity=2):
        return self.project.character.equip_passive(passive_id, capacity=capacity)

    def unequip_passive(self, passive_id):
        return self.project.character.unequip_passive(passive_id)

    # ---- equipment / accessory / attachment / growth ----------------------------

    def equip(self, slot_id, instance_id):
        return self.project.equipment.equip(slot_id, instance_id)

    def unequip(self, slot_id, index=0):
        return self.project.equipment.unequip(slot_id, index)

    def attach(self, instance_id, socket_id, attachment_id):
        return self.project.equipment.attach(instance_id, socket_id, attachment_id)

    def detach(self, instance_id, socket_id):
        return self.project.equipment.detach(instance_id, socket_id)

    def add_equipment_growth(self, instance_id, counter_id, amount):
        return self.project.equipment.add_growth_progress(instance_id, counter_id, amount)

    # ---- inventory / composition -------------------------------------------------

    @property
    def inventory(self):
        return self.project.shared_scenario.inventory

    def craft_healing_tonic(self):
        lab = self.project.inventory
        lab.begin()
        lab.select("red_herb")
        lab.advance()
        lab.select("glass_vial")
        lab.advance()
        lab.advance()
        return lab.craft()

    # ---- party / formation --------------------------------------------------------

    def swap_party(self, outgoing_id, incoming_id):
        return self.project.party.swap_active_with_reserve(outgoing_id, incoming_id)

    def move_formation(self, member_id, slot_id):
        return self.project.party.move(member_id, slot_id)

    # ---- field -------------------------------------------------------------------

    def set_player_position(self, x, y):
        t = self.player.get(Transform)
        t.x = float(x)
        t.y = float(y)
        return (t.x, t.y)

    def set_player_facing(self, facing):
        self.player_facing = str(facing)
        return self.player_facing

    def field_step(self, actions=None):
        if self.mode != "field":
            raise RuntimeError("field input is unavailable outside field mode")
        snapshot = InputSnapshot(dict(actions or {}))
        trigger = self.interaction.step(snapshot, self.scene, self.player, self.player_facing)
        if trigger is None:
            return None
        if trigger.event_program_id.startswith("encounter:"):
            encounter_id = trigger.event_program_id.split(":", 1)[1]
            self.start_encounter(encounter_id)
        return trigger

    def start_encounter(self, encounter_id):
        if self.mode != "field":
            raise RuntimeError("encounter can only start from field mode")
        encounter_id = str(encounter_id)
        if encounter_id != "training_monster":
            raise KeyError(encounter_id)
        # Critical integration boundary: arena is built from the *current*
        # shared actor scenario, after job/skill/equipment edits.
        self.battle = self.project.build_battle_arena()
        self.active_encounter_id = encounter_id
        self.mode = "battle"
        return self.battle

    # ---- battle ------------------------------------------------------------------

    def player_action(self, ability_id):
        if self.mode != "battle" or self.battle is None:
            raise RuntimeError("no active battle")
        return self.battle.player_action(str(ability_id))

    def enemy_action(self):
        if self.mode != "battle" or self.battle is None:
            raise RuntimeError("no active battle")
        return self.battle.enemy_action()

    def battle_vitality(self):
        if self.battle is None:
            return None, None
        scenario = self.battle.scenario
        p = scenario.battle.member(scenario.player_member_id)
        e = scenario.battle.member(scenario.enemy_member_id)
        return (
            p.subject.resources.current("vitality"),
            e.subject.resources.current("vitality"),
        )

    def finish_encounter(self):
        if self.mode != "battle":
            raise RuntimeError("no active encounter")
        self.battle = None
        self.active_encounter_id = None
        self.mode = "field"
        # Require a new button edge after returning to field.
        self.interaction.reset()
        return self.state()

    # ---- snapshot ----------------------------------------------------------------

    def state(self):
        build = self.project.resolve_build()
        char = self.project.character.snapshot()
        equip = self.project.equipment.snapshot()
        pt = self.player.get(Transform)
        nearby = self.interaction.query.nearest(self.scene, self.player, self.player_facing)
        pv, ev = self.battle_vitality()
        jobs = tuple((role, class_id) for _, role, class_id in char.class_assignments)
        return PlayableRuntimeState(
            self.mode,
            (pt.x, pt.y),
            self.player_facing,
            None if nearby is None else nearby.component.local_scope_id,
            self.active_encounter_id,
            char.level_rank,
            jobs,
            tuple(x for _, ids in equip.equipped for x in ids),
            tuple(build.abilities),
            tuple(sorted(self.inventory.to_data()["counts"].items())),
            pv,
            ev,
        )
