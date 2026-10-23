"""Real-time play with RPG actors (ASTERIA_SPEC sections 20 and 21; D22 A7)."""

from __future__ import annotations

from asteria.core import Transform
from asteria.runtime.character_control import CharacterController2DComponent
from asteria.runtime.input import InputSnapshot

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class ActionPlayMixin:
    # -- real-time play with RPG actors (ASTERIA_SPEC §20, §21; D22 A7) ---------------------------
    def _actor_of(self, entity):
        from asteria.runtime.actor_link import ActorLinkComponent

        link = entity.try_get(ActorLinkComponent)
        if link is None or link.actor_id not in self.project.rpg_database.actors:
            return None
        return link.actor_id

    def _actor_combat_state(self, entity, combatant):
        """Combat stats, resources and tags of an ActorLink entity: its actor's resolved build
        (classes, level,
        skill tree, equipment and rolled affixes)."""
        from asteria.gameplay import ResourcePool, StatBlock, TagSet
        from asteria.runtime.combat import CombatantState

        actor_id = self._actor_of(entity)
        if actor_id is None:
            return None
        build = self.resolve_actor_build(actor_id)
        return CombatantState(
            StatBlock.from_data(build.stats.to_data()),
            ResourcePool.from_data(build.resources.to_data()),
            TagSet(build.tags.values()),
        )

    def _known_abilities(self, entity):
        actor_id = self._actor_of(entity)
        return None if actor_id is None else set(self.resolve_actor_build(actor_id).abilities)

    def _equipped_abilities(self, entity):
        """The skill slots of an entity's actor (``slot:N``), or ``None`` without rules."""
        actor_id = self._actor_of(entity)
        if actor_id is None or self.ability_loadout_rules is None:
            return None
        return tuple(self.ability_slots(actor_id)[0])

    def refresh_combatant(self, entity):
        """Rebuild an entity's combat stats (after a level-up, a new class, a skill point, an
        equipment change);
        current resource values (hp...) and running states are kept."""
        from asteria.runtime.combat import CombatantComponent

        combatant = entity.try_get(CombatantComponent)
        if combatant is None or combatant.state is None:
            return None
        old = combatant.state
        combatant.reset_state()
        new = self.combat.state(entity)
        for name in old.resources.names():
            if new.resources.contains(name):
                new.resources.set_current(
                    name, min(old.resources.current(name), new.resources.maximum(name))
                )
        new.poise, new.dead = old.poise, old.dead
        if old.states is not None:
            old.states.stats, old.states.resources, old.states.tags = (
                new.stats,
                new.resources,
                new.tags,
            )
            new.states = old.states
        return new

    def refresh_actor_combatants(self, actor_id):
        from asteria.runtime.actor_link import ActorLinkComponent

        for entity, link in self.scene.query(ActorLinkComponent):
            if link.actor_id == str(actor_id):
                self.refresh_combatant(entity)

    @property
    def combat_scene(self):
        """The current scene's ``CombatScene`` settings (``None``: a classic encounter scene)."""
        from asteria.runtime.action_play import combat_scene

        return combat_scene(self.scene)

    @property
    def action_scene(self):
        settings = self.combat_scene
        return settings is not None and settings.combat_mode == "action"

    def prepare_action_player(self):
        """In an action scene, give the player what real-time play needs and does not have yet: a
        controller (in
        the scene's view), player input, hit / hurt boxes, a combatant, ability use, a looter and
        a link to the first
        party actor (so it fights with that actor's build). Authored components are left as they
        are."""
        settings = self.combat_scene
        if settings is None or settings.combat_mode != "action":
            return
        from asteria.runtime.action_combat import ActionCombatComponent
        from asteria.runtime.actor_link import ActorLinkComponent
        from asteria.runtime.character_control import (
            Hitbox2DComponent,
            Hurtbox2DComponent,
            PlayerInput2DComponent,
        )
        from asteria.runtime.combat import CombatantComponent
        from asteria.runtime.loot import LooterComponent

        player = self.player
        controller = player.try_get(CharacterController2DComponent)
        if controller is None:
            controller = player.add_component(CharacterController2DComponent())
            controller.speed, controller.half_width, controller.half_height = 70.0, 6.0, 8.0
            controller.coyote_time, controller.jump_buffer, controller.jump_cut = 0.1, 0.12, 0.45
        controller.mode = settings.view
        if not player.has(PlayerInput2DComponent):
            player.add_component(PlayerInput2DComponent())
        if not player.has(ActorLinkComponent) and self.save.rpg_state.party_actor_ids:
            player.add_component(
                ActorLinkComponent()
            ).actor_id = self.save.rpg_state.party_actor_ids[0]
        if not player.has(CombatantComponent):
            player.add_component(CombatantComponent()).team = "hero"
        if settings.player_life_resource:
            player.get(CombatantComponent).life_resource = settings.player_life_resource
        team = player.get(CombatantComponent).team or "hero"
        if not player.has(Hurtbox2DComponent):
            hurt = player.add_component(Hurtbox2DComponent())
            hurt.team, hurt.width, hurt.height = team, 12.0, 16.0
        if not player.has(Hitbox2DComponent):
            hit = player.add_component(Hitbox2DComponent())
            hit.team, hit.width, hit.height, hit.offset_x, hit.follow_facing = (
                team,
                24.0,
                16.0,
                14.0,
                True,
            )
        if not player.has(ActionCombatComponent):
            player.add_component(ActionCombatComponent())
        if not player.has(LooterComponent):
            player.add_component(LooterComponent())

    def _player_fell(self, event):
        if event.kind != "death" or event.target_id != self.player.id or not self.action_scene:
            return
        settings = self.combat_scene
        if settings.on_player_death == "game_over":
            self.player_defeated = True
            return
        self.player_down = max(settings.respawn_delay, 1e-6)

        controller = self.player.try_get(CharacterController2DComponent)
        if controller is not None:
            controller.lock_control(self.player_down)

    def _respawn_player(self):
        from asteria.runtime.combat import CombatantComponent

        x, y = self._action_spawn.get(
            self.scene.id, (self.player.get(Transform).x, self.player.get(Transform).y)
        )
        self.set_player_position(x, y)
        combatant = self.player.try_get(CombatantComponent)
        if combatant is not None and combatant.state is not None:
            state = combatant.state
            state.dead = False
            state.down_phase, state.down_left = "", 0.0
            if self.combat_scene.respawn_heal:
                for name in state.resources.names():
                    state.resources.set_current(name, state.resources.maximum(name))
            self.hits.grant_invincibility(self.player.id, 1.5)

    def _remember_defeat(self, event):
        """A defeated combatant with a ``defeat_switch`` is remembered in the save."""
        name = event.data.get("defeat_switch") if event.kind == "death" else ""
        if name:
            self.save.event_context.set_switch(str(name), True)

    def _remove_defeated(self, scene):
        """Entities whose ``defeat_switch`` is on stay gone (they were beaten in an earlier
        visit or session)."""
        from asteria.runtime.combat import CombatantComponent

        for entity, combatant in list(scene.query(CombatantComponent)):
            name = combatant.defeat_switch
            if name and self.save.event_context.get_switch(str(name)):
                scene.remove_entity(entity)

    def _award_experience(self, event):
        if event.kind != "death" or not event.data.get("experience") or not event.attacker_id:
            return
        attacker = self.scene.get_entity(event.attacker_id)
        actor_id = None if attacker is None else self._actor_of(attacker)
        if actor_id is None:
            return
        result = self.grant_actor_experience(
            actor_id, event.data["experience"], **self.action_progression
        )
        self.progression_events.append({"actor_id": actor_id, **result})
        if result["levels_gained"]:
            self.refresh_actor_combatants(actor_id)

    def equip_from_bag(self, actor_id, index, slot_id=None):
        """Equip a rolled item from the equipment bag (its requirements checked against the actor's
        capabilities); whatever was in the slot goes back to the bag."""
        actor_id = str(actor_id)
        bag = self.save.rpg_state.equipment_bag
        item = bag[int(index)]
        slot_id = str(slot_id or item.equipment.slot)
        loadout = self.save.rpg_state.loadouts[actor_id]
        capabilities = self.resolve_actor_build(actor_id).capabilities
        displaced = list(loadout.equipped(slot_id))
        for _ in displaced:
            loadout.unequip(slot_id, 0)
        try:
            loadout.equip(slot_id, item, capabilities=capabilities)
        except Exception:
            for previous in displaced:
                loadout.equip(slot_id, previous, validate_requirements=False)
            raise
        bag.pop(int(index))
        bag.extend(displaced)
        self.refresh_actor_combatants(actor_id)
        return item

    def set_field_input(self, actions=None):
        """This frame's input actions for real-time control (``ActionCombat`` bindings, lock-on);
        ``None`` = none."""

        self.field_input = None if actions is None else InputSnapshot(dict(actions))

    @property
    def action_combat(self):
        """Real-time ability use (ASTERIA_SPEC §20) for the current scene: ``use``, cooldowns,
        lock-on."""
        return self._field_systems()["action_combat"]

    @property
    def combat(self):
        """Real-time combat resolution (ASTERIA_SPEC §20) for the current scene; ``combat.events``
        per update."""
        return self._field_systems()["combat"]

    @property
    def projectiles(self):
        """Projectiles in flight (ASTERIA_SPEC §20) for the current scene; ``fire`` / ``views()`` /
        ``events``."""
        return self._field_systems()["projectiles"]

    @property
    def hits(self):
        """Hitbox / hurtbox detection (ENG-17) for the current scene; ``hits.events`` per
        update."""
        return self._field_systems()["hits"]
