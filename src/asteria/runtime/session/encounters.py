"""Enemies and encounters: stealing, difficulty, members, auto battle, summons, starting a fight,
notices and the battle rules."""

from __future__ import annotations

import random

from asteria.gameplay import AbilityRegistry, AbilityRuntime
from asteria.rpg import (
    BattleRuntime,
    BattleSessionRules,
    Party,
    PartyMember,
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


class EncountersMixin:
    def steal(self, actor_id, target_id, *, chance_bonus=0.0):
        """Try to rob an enemy using the project's steal tables; loot goes into the bag."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        extensions = self.battle.extensions
        if extensions is None:
            raise GameSessionError("the project defines no steal tables")
        result = extensions.steal(
            self.battle,
            actor_id,
            target_id,
            self.save.rpg_state.inventory,
            random.Random(f"{self.encounter_id}:{actor_id}:{target_id}:steal"),
            chance_bonus=chance_bonus,
        )
        self._log(
            "steal",
            member_id=str(actor_id),
            target_ids=(str(target_id),),
            data={"stolen": result.stolen, "item_id": result.item_id, "reason": result.reason},
        )
        return result

    @property
    def enemy_level_rules(self):
        """Project enemy level rules (YEP EnemyLevels): the first by id, or ``None``."""
        values = self.project.rpg_database.enemy_level_rules
        return values[sorted(values)[0]] if values else None

    @property
    def difficulty(self):
        """Name of the difficulty slider setting in force (saved in the event variables)."""
        rules = self.enemy_level_rules
        chosen = self.save.event_context.get_variable(self.DIFFICULTY_VARIABLE, "")
        return str(chosen or (rules.default_difficulty if rules else ""))

    def set_difficulty(self, difficulty_id):
        rules = self.enemy_level_rules
        if rules is None or str(difficulty_id) not in {
            x.difficulty_id for x in rules.difficulties
        }:
            raise GameSessionError(f"unknown difficulty: {difficulty_id}")
        self.save.event_context.set_variable(self.DIFFICULTY_VARIABLE, str(difficulty_id))
        return str(difficulty_id)

    def _party_level(self):
        state = self.save.rpg_state
        levels = [
            int(state.actor_progression[x].level)
            for x in state.party_active_actor_ids
            if x in state.actor_progression
        ]
        return max(levels) if levels else 1

    def _scale_enemy(self, subject, member_id):
        rules = self.enemy_level_rules
        if rules is None:
            return 0
        level = rules.level_for(
            self.scene.id,
            random.Random(f"{self.scene.id}:{member_id}:level"),
            self._party_level(),
            self.difficulty or None,
        )
        rules.apply(subject, level, self.difficulty or None)
        return level

    def _actor_member(self, actor_id):
        build = self.resolve_actor_build(actor_id)
        subject = self._battle_subject(build.stats, build.resources, build.tags)
        speed = build.stats.get("speed")
        return PartyMember(
            str(actor_id),
            "heroes",
            subject,
            ability_ids=build.abilities,
            initiative=speed,
            initiative_stat="speed",
            initiative_expression=self.rules.initiative_expression,
        )

    def _enemy_member(self, enemy_id, index):
        definition = self.project.rpg_database.enemies[enemy_id]
        runtime = definition.instantiate()
        subject = self._battle_subject(runtime.stats, runtime.resources, runtime.tags)
        level = self._scale_enemy(subject, f"{enemy_id}:{index}")
        from asteria.rpg.derived_stats import apply_derived_stats

        derived = self.project.rpg_database.derived_stats.values()
        apply_derived_stats(subject.stats, derived, side="enemies")  # after its level
        speed = subject.stats.get("speed")
        if level:
            self.enemy_levels[f"{enemy_id}:{index}"] = level
        return PartyMember(
            f"{enemy_id}:{index}",
            "enemies",
            subject,
            ability_ids=definition.abilities,
            initiative=speed,
            initiative_stat="speed",
            initiative_expression=self.rules.initiative_expression,
        )

    def auto_battle_choice(self, actor_id, *, heal_tag="", heal_below=0.4):
        """What an auto-battling hero would do now: ``(ability_id, target_ids)`` or ``None``.

        With a ``heal_tag`` (a project's own tag), a usable ability carrying it is chosen when
        an ally's health is below ``heal_below`` of its maximum; otherwise the most costly
        usable ability (the strongest by convention), the first listed on ties. Nothing here is
        a game rule: projects that want other behaviour use their own code or AI trees.
        """
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        battle = self.battle
        member = battle.member(actor_id)
        resource = self.rules.knockout_resource_id
        weak_ally = False
        for ally in battle.parties[member.side].members:
            if not battle.is_active(ally) or not resource:
                continue
            pool = ally.subject.resources
            if resource in pool.to_data()["values"] and pool.maximum(resource) > 0:
                weak_ally = (
                    weak_ally or pool.current(resource) / pool.maximum(resource) < heal_below
                )
        usable = []
        for ability_id in member.ability_ids:
            definition = battle.ability_runtime.registry.get(ability_id)
            if definition is None or self.ability_unavailable(actor_id, ability_id):
                continue
            if getattr(definition, "concoct_station", ""):
                continue
            targets = self.default_targets(actor_id, ability_id)
            if not targets:
                continue
            cost = float(len(definition.costs))  # resource costs (formulas) count one each
            cost += sum(float(v) for v in definition.battle_costs.values())
            usable.append(
                (ability_id, targets, cost, bool(heal_tag) and heal_tag in definition.tags)
            )
        if not usable:
            return None
        if weak_ally:
            healing = [u for u in usable if u[3]]
            if healing:
                return healing[0][0], healing[0][1]
        best = max(usable, key=lambda u: u[2])  # max keeps the first of equal costs
        return best[0], best[1]

    def auto_battle_act(self, actor_id, **options):
        """Let ``actor_id`` take its turn by ``auto_battle_choice``; returns the result."""
        choice = self.auto_battle_choice(actor_id, **options)
        if choice is None:
            return None
        ability_id, targets = choice
        return self.use_ability(actor_id, ability_id, targets)

    def dispel(self, member_id, category, *, count=None):
        """Remove states of a category (``category.<name>`` contributed tag) from a battle
        member; returns the removed state ids."""
        if self.battle is None:
            raise GameSessionError("dispel needs a running battle")
        states = self.battle.member(member_id).subject.states
        removed = states.remove_category(category, count=count)
        for state_id in removed:
            self._log("state_dispelled", member_id=str(member_id), data={"state": state_id})
        return removed

    def _pet_member(self):
        """The first pet that fights as a hero-side unit (``battle_pets``), or ``None``."""
        pets = self.battle_pets()
        if not pets:
            return None
        self._pets_sent.add(pets[0].instance_id)
        return self._pet_unit(pets[0])

    def summon(
        self, *, enemy_id=None, actor_id=None, count=1, owner_id=None, join_current_round=True
    ):
        """Bring combatants into the running battle (RPG-08): ``enemy_id`` joins the enemies (a
        boss calling
        minions), ``actor_id`` joins the heroes (a companion from the roster, e.g. one in reserve).
        ``owner_id`` makes them the owner's summons. Returns the new member ids."""
        if self.battle is None:
            raise GameSessionError("summon needs a running battle")
        if (enemy_id is None) == (actor_id is None):
            raise GameSessionError("summon needs exactly one of enemy_id or actor_id")
        battle = self.battle
        added = []
        for _ in range(max(1, int(count))):
            if enemy_id is not None:
                if str(enemy_id) not in self.project.rpg_database.enemies:
                    raise GameSessionError(f"unknown enemy: {enemy_id}")
                index = 1 + sum(1 for m in battle.members if m.split(":", 1)[0] == str(enemy_id))
                while f"{enemy_id}:{index}" in battle.members:
                    index += 1
                member = self._enemy_member(str(enemy_id), index)
            else:
                if str(actor_id) not in self.project.rpg_database.actors:
                    raise GameSessionError(f"unknown actor: {actor_id}")
                if str(actor_id) in battle.members:
                    raise GameSessionError(f"{actor_id} is already in the battle")
                member = self._actor_member(str(actor_id))
            registry = battle.ability_runtime.registry
            for (
                ability_id
            ) in member.ability_ids:  # the newcomer's abilities join the battle's registry
                definition = self.project.gameplay_library.abilities.get(ability_id)
                if definition is not None and registry.get(ability_id) is None:
                    registry.register(definition)
            battle.summon(member, owner_id=owner_id, join_current_round=join_current_round)
            added.append(member.member_id)
            self._log("summoned", member_id=member.member_id, data={"owner_id": owner_id})
        return tuple(added)

    BATTLES_COUNTER = "battles.started"

    def _battle_seed(self, encounter_id):
        """The battle's dice: always 157, unless the rules vary it - then each battle of a
        save rolls its own (from how many battles the save has started)."""
        if not self.rules.vary_seed:
            return 157
        import zlib

        counters = self.world.counters
        count = int(counters.get(self.BATTLES_COUNTER, 0)) + 1
        counters[self.BATTLES_COUNTER] = count
        return zlib.crc32(f"{self.project.id}:{encounter_id}:{count}".encode())

    BATTLE_RUNNING_SWITCH = "battle.running"

    def start_encounter(self, encounter_id, *, opening=None):
        """Begin a turn-based fight; ``opening`` (preemptive / normal / surprise) replaces the
        rolled one (a field strike that hit the foe first)."""
        if self.mode != "field":
            raise GameSessionError("encounter already active")
        db = self.project.rpg_database
        encounter = db.encounters[str(encounter_id)]
        active = self.save.rpg_state.party_active_actor_ids
        pet_rules = self.pet_rules
        heroes = ()
        if pet_rules is None or pet_rules.actors_fight:
            heroes = tuple(self._actor_member(x) for x in active)
        self._pets_sent = set()
        self._species_foes = {}
        pet_members = tuple(self._pet_unit(p) for p in self.battle_pets())
        heroes += pet_members
        if not heroes:
            raise GameSessionError(
                self.tr("battle.no_one", "No one can fight: the party has no creature standing")
            )
        enemies = []
        enemy_definition_ids = []
        reserve = []
        serial = 0
        foe_rng = random.Random(f"{encounter_id}:{self.save.rpg_state.world.counters!r}:foes")
        for member in encounter.members:
            for _ in range(member.count):
                serial += 1
                if member.pet_species_id:
                    unit = self._species_foe_unit(member, serial, foe_rng)
                else:
                    unit = self._enemy_member(member.enemy_id, serial)
                enemies.append(unit)
                enemy_definition_ids.append(member.kind_id)
                if member.reserve:
                    reserve.append(unit.member_id)

        registry = (
            AbilityRegistry()
        )  # every project ability: items, summons and granted skills can act too
        library = self.project.gameplay_library.abilities
        for ability_id in library.ids():
            registry.register(library.get(ability_id))

        scheduler = next(iter(db.battle_schedulers.values()), None)
        for tag in encounter.tags:  # scheduler:<id> picks another turn scheduler
            if tag.startswith("scheduler:") and tag[len("scheduler:") :] in db.battle_schedulers:
                scheduler = db.battle_schedulers[tag[len("scheduler:") :]]
        self.battle = BattleRuntime(
            (Party("heroes", heroes), Party("enemies", tuple(enemies))),
            AbilityRuntime(registry),
            is_active=self._is_conscious,
            resource_definitions=db.battle_resources.values(),
            interaction_rules=db.interaction_rules.values(),
            outcome_checks=db.outcome_checks.values(),
            state_policies=db.battle_state_policies.values(),
            targeting_definitions=db.battle_targeting.values(),
            objective_definitions=self._encounter_objectives(encounter),
            escape_rules=db.escape_rules.values(),
            scheduler_definition=scheduler,
            action_timing_definitions=db.action_timings.values(),
            action_sequence_definitions=db.action_sequences.values(),
            gauge_composition_definitions=db.gauge_compositions.values(),
            reaction_definitions=db.reactions.values(),
            enemy_ai_definitions=db.enemy_ai.values(),
            transaction_policies=db.action_transactions.values(),
            rng_seed=self._battle_seed(encounter_id),
            hooks=self._battle_hook_bus(),
            extensions=self.extension_rules,
        )
        self.opening = "normal"
        self.battle.final_damage_expression = self.rules.final_damage_expression
        self.battle.knockout_resource_id = self.rules.knockout_resource_id
        self._sync_weather_tags()
        extensions = self.battle.extensions
        if extensions is not None:
            self._load_mastery(extensions)
            self.opening = extensions.roll_opening(random.Random(f"{encounter_id}:opening"))
        if opening:
            self.opening = str(opening)
        if extensions is not None:
            extensions.apply_opening(self.battle, self.opening, "heroes")
        else:
            from asteria.rpg.battle_extensions import apply_opening

            apply_opening(self.battle, self.opening, "heroes")
        if pet_rules is None or not pet_rules.pets_decide_outcome:
            for unit in pet_members:  # a fallen pet unit never decides the fight
                self.battle.outcome_exempt.add(unit.member_id)
        slots = pet_rules.battle_slots if pet_rules is not None else 0
        if slots:  # the other creatures of each side wait on the bench (creature party)
            for unit in pet_members[slots:]:
                self.battle.bench(unit.member_id)
            foes = [u for u in enemies if u.member_id in self._species_foes]
            for unit in foes[slots:]:
                self.battle.bench(unit.member_id)
        for member_id in reserve:
            self.battle.bench(member_id)
        if slots:
            self._refill_slots("enemies")  # reserve members never leave the stage empty
        for unit in pet_members:
            if unit.member_id not in self.battle.benched:
                self._pets_sent.add(self.pet_of_member(unit.member_id).instance_id)
        self.encounter_id = str(encounter_id)
        self.encounter_background = self._area_battle_background()
        self._enemy_ids = tuple(enemy_definition_ids)
        self._captured = set()
        for enemy_id in sorted(set(enemy_definition_ids)):
            self.world.note_enemy(enemy_id, "seen")
        self.mode = "battle"
        # on while the battle lasts: an event waits for "battle.running" off to go on after it
        self.save.event_context.set_switch(self.BATTLE_RUNNING_SWITCH, True)
        self.battle_log.clear()
        self._logged_turn = None
        self._log("battle_started", data={"encounter_id": self.encounter_id})
        return self.battle

    def notify(self, text, *, entity=None, duration_ms=1100.0, kind="info"):
        """Queue a short field message the host shows as animated text above ``entity`` (default
        the player)."""
        self.notices.append(
            {
                "text": str(text),
                "entity": entity,
                "duration_ms": float(duration_ms),
                "kind": str(kind),
            }
        )

    def drain_notices(self):
        values, self.notices = tuple(self.notices), []
        return values

    def _configure_inventory(self):
        """The project's inventory rules (RPG-01; the first by id) apply to every way items
        arrive."""
        db = self.project.rpg_database
        rules = getattr(db, "inventory_rules", {})
        chosen = rules[sorted(rules)[0]] if rules else None

        def lookup(item_id):
            return (
                db.items.get(item_id) or db.equipment.get(item_id) or db.attachments.get(item_id)
            )

        self.save.rpg_state.inventory.configure(chosen, lookup)

    @property
    def inventory_overflow(self):
        """``(item_id, amount)`` that did not fit in the bag, newest last (for "bag full"
        messages)."""
        return self.save.rpg_state.inventory.overflow

    @property
    def rules(self):
        """Project battle session rules: the ones a ``rules:<id>`` tag of the running
        encounter names, else the first by id, or inert defaults."""
        values = self.project.rpg_database.battle_session_rules
        if self.battle is not None and values:
            chosen = self._encounter_choice("rules", values)
            if chosen is not None:
                return chosen
        return values[sorted(values)[0]] if values else BattleSessionRules("default")
