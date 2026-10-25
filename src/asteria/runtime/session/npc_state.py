"""NPC state (WLD-02): positions, facing and animations remembered across visits."""

from __future__ import annotations

from asteria.core import Transform

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class NpcStateMixin:
    # -- NPC state (WLD-02) -----------------------------------------------------------------------
    def _record_npc(self, entity):
        from asteria.runtime.npc_state import NpcIdentity2DComponent

        identity = entity.try_get(NpcIdentity2DComponent)
        if identity is None or not identity.npc_id:
            return None
        state = self.world.npc(identity.npc_id)
        t = entity.get(Transform)
        state["scene_id"], state["position"] = self.scene.id, [t.x, t.y]
        if entity.id in self.entity_facing:
            state["facing"] = self.entity_facing[entity.id]
        return state

    def _rpg_value(self, name):
        """The ``rpg`` condition source: ``level:<actor>``, ``item:<id>``, ``gold`` (any
        currency: ``currency:<id>``), ``job:<actor>:<class>``, ``party:<actor>``,
        ``reputation:<faction>``, ``quest:<id>`` (its status), ``pets`` (the party's size) and
        ``shop`` (the shop open now, "" when none), ``name_input`` / ``picture_choice``
        ("open" while a name is entered / a pictured choice is made), ``light`` ("moving"
        while SET_LIGHT's circle changes), ``pressed:<action>`` / ``held:<action>`` (a control
        - confirm, cancel, menu... - pressed this frame / held now; ``a|b``: any of them) and
        ``saves`` (how many save slots hold a game, as the title screen found them)."""
        kind, _, rest = str(name).partition(":")
        state = self.save.rpg_state
        if kind == "level":
            return self.ensure_actor_progression(rest).level
        if kind == "item":
            return state.inventory.count(rest)
        if kind == "pets":  # how many creatures travel with the player
            return len(self.party_pets())
        if kind == "shop":  # the shop open now ("" when none): WAIT until it is ""
            return self.open_shop_id or ""
        if kind == "name_input":  # "open" while the name screen waits for a name, else ""
            return "open" if getattr(self, "name_input_request", None) else ""
        if kind in ("pressed", "held"):  # the host's controls this frame (a|b: any of them)
            found = getattr(self, "input_actions", {}).get(kind, ())
            return any(action in found for action in rest.split("|"))
        if kind == "saves":
            return int(getattr(self, "saves_used", 0))
        if kind == "light":  # "moving" while SET_LIGHT's circle grows or shrinks, else ""
            return "moving" if self.light_moving() else ""
        if kind == "picture_choice":  # "open" while a PICTURE_CHOICE waits, else ""
            return "open" if getattr(self, "picture_choice_request", None) else ""
        if kind == "gold":
            return state.currencies.get("gold", 0.0)
        if kind == "currency":
            return state.currencies.get(rest, 0.0)
        if kind == "job":
            actor, _, class_id = rest.partition(":")
            return class_id in self.ensure_actor_progression(actor).active_class_ids
        if kind == "party":
            return rest in state.party_actor_ids
        if kind == "reputation":
            return state.world.reputation.get(rest, 0.0)
        if kind == "quest":
            progress = state.quests.get(rest)
            return "inactive" if progress is None else progress.status
        raise ValueError(f"unknown rpg condition: {name}")

    def _audio_value(self, name):
        """The ``audio`` condition source: ``me`` (a fanfare plays, PLAY_ME) and ``se`` (the
        last sound effect, PLAY_SE, still sounds)."""
        if name not in self.audio_status:
            raise ValueError(f"unknown audio condition: {name}")
        return bool(self.audio_status[name])

    def _npc_value(self, name):
        npc_id, _, key = str(name).partition(".")
        return self.world.npc_value(npc_id, key)

    def set_npc(self, npc_id, key, value):
        """Change an NPC's saved state: visible, alive, mood, stage or flag.<name>; applied to the
        scene now."""
        from asteria.runtime.npc_state import NPC_KEYS, apply_npc_states, coerce_npc_value

        key = str(key)
        state = self.world.npc(npc_id)
        if key.startswith("flag."):
            state["flags"][key[5:]] = value
        elif key in NPC_KEYS:
            state[key] = coerce_npc_value(key, value)
        else:
            raise GameSessionError(f"unknown NPC field {key}")
        apply_npc_states(self.scene, self.world, self.entity_facing)
        self.refresh_quests()
        return state

    def move_npc(self, npc_id, scene_id, x, y):
        """Relocate an NPC (possibly to another scene); it appears there when that scene is
        entered."""
        from asteria.runtime.npc_state import apply_npc_states

        if self.project.scene(str(scene_id)) is None:
            raise GameSessionError(f"unknown scene: {scene_id}")
        state = self.world.npc(npc_id)
        state["scene_id"], state["position"] = str(scene_id), [float(x), float(y)]
        apply_npc_states(self.scene, self.world, self.entity_facing)
        return state

    def set_facing(self, key, facing):
        entity = self._sequence_entity(key)
        if entity is self.player:
            return self.set_player_facing(facing)
        self.entity_facing[entity.id] = str(facing)
        self._record_npc(entity)
        return self.entity_facing[entity.id]

    def play_animation(self, key, clip):
        from asteria.runtime.components2d import Animator2DComponent

        entity = self._sequence_entity(key)
        animator = entity.try_get(Animator2DComponent)
        if animator is not None:
            animator.default_clip = str(clip)
        self.entity_animation[entity.id] = str(clip)
        return str(clip)
