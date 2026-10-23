"""After a fight: loot luck, hero state, the aftermath, rewards, gear drops and the world state."""

from __future__ import annotations

import random

from asteria.core import Transform
from asteria.rpg import (
    RewardRuntime,
    roll_reward,
)

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class RewardsMixin:
    LOOT_LUCK_VARIABLE = "loot.luck"
    DIFFICULTY_VARIABLE = "difficulty.setting"
    MAX_IDLE_ROUNDS = 20  # rounds in a row in which nobody can act before giving up

    @property
    def loot_luck(self):
        """Luck applied to loot rolls; events set it through the ``loot.luck`` variable."""
        try:
            return float(self.save.event_context.get_variable(self.LOOT_LUCK_VARIABLE, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def capture_hero_state(self):
        """Level, stats and abilities of the active heroes (before / after a reward step)."""
        state = self.save.rpg_state
        result = {}
        for actor_id in state.party_active_actor_ids:
            build = self.resolve_actor_build(actor_id)
            progress = state.actor_progression.get(actor_id)
            result[actor_id] = {
                "level": int(progress.level) if progress is not None else 1,
                "stats": {name: build.stats.get(name) for name in build.stats.names()},
                "abilities": tuple(build.abilities),
            }
        return result

    def build_aftermath(self, applied, before, experience=None):
        """The victory results (rewards, level changes) for the battle just won."""
        from asteria.rpg.victory import build_aftermath

        db = self.project.rpg_database
        names = {x: db.actors[x].display_name for x in before if x in db.actors}
        notes = []
        extensions = None if self.battle is None else self.battle.extensions
        if extensions is not None:
            for member_id in sorted(extensions.overkill):
                scale = extensions.overkill_scale(self.battle, member_id)
                if scale > 1.0:
                    notes.append(
                        self.tr("victory.overkill", "Overkill x{scale}", scale=f"{scale:.2g}")
                    )
        return build_aftermath(
            applied,
            before,
            self.capture_hero_state(),
            defeated=tuple(self._last_defeated),
            names=names,
            experience=experience,
            bonus_notes=tuple(dict.fromkeys(notes)),
        )

    def _scaled_reward(self, reward, member_id):
        """Currency and experience grow with the enemy's level and with overkill damage."""
        scale = 1.0
        rules = self.enemy_level_rules
        level = self.enemy_levels.get(member_id)
        if rules is not None and level:
            scale *= rules.reward_multiplier(level, self.difficulty or None)
        extensions = None if self.battle is None else self.battle.extensions
        if extensions is not None and member_id in self.battle.members:
            scale *= extensions.overkill_scale(self.battle, member_id)
        if scale == 1.0:
            return reward
        return type(reward)(
            {k: v * scale for k, v in reward.currencies.items()},
            {k: v * scale for k, v in reward.experience.items()},
            reward.items,
        )

    def _roll_gear_drop(self, equipment_id, amount, member_id, rng):
        """Drops that name equipment become rolled instances in the equipment bag."""
        from asteria.rpg.loot import roll_equipment

        db = self.project.rpg_database
        bag = self.save.rpg_state.equipment_bag
        level = self.enemy_levels.get(member_id) or 1
        for _ in range(int(amount)):
            serial = sum(1 for g in bag if g.equipment.equipment_id == equipment_id) + 1
            bag.append(
                roll_equipment(
                    db.equipment[equipment_id],
                    rng,
                    item_level=level,
                    rarities=db.rarities or None,
                    affixes=db.affixes,
                    luck=self.loot_luck,
                    instance_id=f"{equipment_id}:drop{serial}",
                )
            )
            self.offer_equipment(bag[-1])

    def finish_victory(self):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        if self.active_enemy_ids():
            raise GameSessionError("encounter is not defeated")
        self._write_battle_heroes_to_save()
        db = self.project.rpg_database
        reward_runtime = RewardRuntime(
            inventory=self.save.rpg_state.inventory,
            progression=self.save.rpg_state.progression,
            currencies=self.save.rpg_state.currencies,
        )
        applied = []
        rng = random.Random(157)
        # Captured enemies joined the party: they give no reward and do not count as defeated.
        defeated = tuple(
            enemy_id
            for serial, enemy_id in enumerate(self._enemy_ids, 1)
            if f"{enemy_id}:{serial}" not in self._captured
        )
        member_ids = tuple(
            f"{enemy_id}:{serial}"
            for serial, enemy_id in enumerate(self._enemy_ids, 1)
            if f"{enemy_id}:{serial}" not in self._captured
        )
        for enemy_id, member_id in zip(defeated, member_ids, strict=True):
            definition = db.enemies[enemy_id].reward
            reward = roll_reward(
                definition, rng, luck=self.loot_luck, switches=self.save.event_context.get_switch
            )
            if definition.drop_table_id:
                from asteria.rpg.drop_tables import roll_drop_table

                extra = roll_drop_table(
                    db.drop_tables[definition.drop_table_id],
                    rng,
                    counters=self.world.counters,  # pity counters are saved with the world state
                    luck=self.loot_luck,
                    switches=self.save.event_context.get_switch,
                )
                items = dict(reward.items)
                for item_id, amount in extra.items():
                    if item_id in db.equipment:  # gear is rolled (rarity, affixes), not counted
                        self._roll_gear_drop(item_id, amount, member_id, rng)
                        self.world.note_enemy(enemy_id, f"drop:{item_id}", amount)
                        continue
                    items[item_id] = items.get(item_id, 0) + amount
                reward = type(reward)(reward.currencies, reward.experience, items)
            for item_id, amount in reward.items.items():  # the bestiary lists what really fell
                self.world.note_enemy(enemy_id, f"drop:{item_id}", amount)
            reward = self._scaled_reward(reward, member_id)
            applied.append(reward_runtime.apply(reward))
        self._store_mastery()
        self._award_job_points(len(defeated))
        self._last_defeated = defeated
        self._log(
            "battle_finished", data={"winning_sides": ("heroes",), "defeated_sides": ("enemies",)}
        )
        self.save.event_context.set_switch(f"encounter.{self.encounter_id}.defeated", True)
        log = self.quest_log
        for enemy_id in defeated:
            log.record_defeat(enemy_id)
            self.world.note_enemy(enemy_id, "defeated")
        self._quest_switches()
        self.refresh_achievements()
        self._pets_gain_experience()
        self.mode = "field"
        self.battle = None
        self.encounter_id = None
        self._enemy_ids = ()
        self.interaction.reset()
        return tuple(applied)

    def sync_world_state(self):
        t = self.player.get(Transform)
        self.save.scene_id = self.scene.id
        self.save.player_entity_id = self.player.id
        self.save.player_facing = self.facing
        self.save.player_position = (t.x, t.y)
        self.save.active_event = self.events.snapshot()
        from asteria.runtime.npc_state import npc_entities

        for npc_id, entity in npc_entities(self.scene).items():
            if entity.enabled and npc_id in self.world.npcs:
                self._record_npc(entity)  # keep where moved NPCs stand
        return self.save
