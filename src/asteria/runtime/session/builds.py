"""An actor's resolved build: the runtime actor, ability loadout, mastery and shared gauges."""

from __future__ import annotations

from asteria.gameplay import GameplaySubject
from asteria.rpg import (
    ActorAbilityState,
    ClassAssignment,
    RpgActorRuntime,
    resolve_actor_build,
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


class BuildsMixin:
    def resolve_actor_build(self, actor_id, *, apply_slots=True):
        actor_id = str(actor_id)
        db = self.project.rpg_database
        actor = self._actor_runtime(actor_id)
        progress = self.save.rpg_state.actor_progression.get(actor_id)
        build = resolve_actor_build(
            actor,
            level=1 if progress is None else int(progress.level),
            progression=self.save.rpg_state.progression,
            allocations=self.save.rpg_state.progression_allocations.get(actor_id),
            loadout=self.save.rpg_state.loadouts.get(actor_id),
            passives=db.passives,
            evolution_rules=db.ability_evolutions.values(),
            derived_stats=db.derived_stats.values(),
        )
        rules = self.ability_loadout_rules
        if rules is not None and apply_slots:  # only equipped slot-limited abilities stay usable
            from dataclasses import replace

            equipped = set(self._ability_state_of(actor_id).equipped_abilities)
            usable = rules.filter(build.abilities, build.ability_grants, equipped)
            build = replace(build, abilities=usable)
        return build

    def _actor_runtime(self, actor_id):
        """The actor before any build layer: its definition, its active jobs' base bonuses and
        what its snapshot keeps (resources spent, learned abilities). Level growth, trees, gear,
        passives and stat formulas come on top in ``resolve_actor_build``."""
        actor_id = str(actor_id)
        db = self.project.rpg_database
        base = db.actors[actor_id]
        progress = self.save.rpg_state.actor_progression.get(actor_id)
        definition = base
        if progress is not None and progress.active_class_ids:
            authored = {x.class_id: x for x in base.class_assignments}
            assignments = []
            for index, class_id in enumerate(progress.active_class_ids):
                source = authored.get(class_id)
                assignments.append(
                    ClassAssignment(
                        class_id,
                        assignment_id=(
                            source.assignment_id if source else f"save:{actor_id}:{class_id}"
                        ),
                        role=(
                            source.role if source else ("primary" if index == 0 else "secondary")
                        ),
                        enabled=True,
                        priority=(source.priority if source else 10 - index),
                        progression_track_ids=(source.progression_track_ids if source else ()),
                        tags=(source.tags if source else ()),
                    )
                )
            definition = type(base)(
                base.actor_id,
                base.display_name,
                class_assignments=tuple(assignments),
                base_stats=base.base_stats,
                base_resources=base.base_resources,
                tags=base.tags,
                abilities=base.abilities,
            )
        actor = RpgActorRuntime(definition, class_definitions=db.classes)
        snapshot = self.save.rpg_state.actor_snapshots.get(actor_id)
        if snapshot is not None:
            actor.restore(snapshot)
        return actor

    @property
    def ability_loadout_rules(self):
        """Project ability slot rules: the first by id, or ``None`` (no slot limit)."""
        values = self.project.rpg_database.ability_loadout_rules
        return values[sorted(values)[0]] if values else None

    def _ability_state_of(self, actor_id):
        snapshot = self.save.rpg_state.actor_snapshots.get(str(actor_id))
        if snapshot is None or snapshot.ability_state is None:
            return ActorAbilityState()
        return ActorAbilityState.from_data(snapshot.ability_state)

    def ability_slots(self, actor_id):
        """``(equipped ability ids, capacity)`` of an actor under the slot rules."""
        rules = self.ability_loadout_rules
        level = 1
        progress = self.save.rpg_state.actor_progression.get(str(actor_id))
        if progress is not None:
            level = int(progress.level)
        capacity = rules.capacity_at(level) if rules is not None else 0
        return self._ability_state_of(actor_id).equipped_abilities, capacity

    def slot_candidates(self, actor_id):
        """The abilities an actor may put in a skill slot: those granted by the rules' limited
        sources (learned skills, skill-tree nodes...), in grant order."""
        rules = self.ability_loadout_rules
        if rules is None:
            return ()
        build = self.resolve_actor_build(actor_id, apply_slots=False)
        limited = set(rules.limited_sources)
        always = set(rules.always_usable)
        found = []
        for grant in build.ability_grants:
            if grant.source_kind in limited and grant.ability_id not in always:
                if grant.ability_id not in found:
                    found.append(grant.ability_id)
        return tuple(found)

    def equip_ability(self, actor_id, ability_id):
        """Put an ability of ``slot_candidates`` in a slot (needs free capacity)."""
        rules = self.ability_loadout_rules
        if rules is None:
            raise GameSessionError("the project has no ability slot rules")
        ability_id = str(ability_id)
        state = self._ability_state(actor_id)
        if ability_id not in self.slot_candidates(actor_id):
            raise GameSessionError(f"{ability_id} is not learned")
        _equipped, capacity = self.ability_slots(actor_id)
        try:
            state.equip_ability(ability_id, capacity=capacity)
        except ValueError as exc:
            raise GameSessionError(str(exc)) from exc
        self._store_ability_state(actor_id, state)
        return ability_id

    def unequip_ability(self, actor_id, ability_id):
        state = self._ability_state(actor_id)
        state.unequip_ability(ability_id)
        self._store_ability_state(actor_id, state)
        return str(ability_id)

    def _battle_subject(self, stats, resources, tags):
        """A combatant subject that can hold battle states (break, buffs...) from the project's
        state registry."""
        from asteria.gameplay import StateRuntime

        for name, (low, high, start) in (self.rules.battle_counters or {}).items():
            if not resources.contains(name):  # the rules' per-battle counters (stat stages...)
                resources.define(name, high, current=start, minimum=low)
        states = StateRuntime(self.project.gameplay_library.states, stats, resources, tags)
        return GameplaySubject(stats, resources, tags, states)

    @property
    def extension_rules(self):
        """Project battle extension rules (taunt, life steal...): the first by id, or ``None``."""
        values = self.project.rpg_database.battle_extension_rules
        return values[sorted(values)[0]] if values else None

    MASTERY_PREFIX = "mastery."

    def _load_mastery(self, extensions):
        """Lifetime ability uses live in the saved world counters; mastery tags follow them."""
        for key, value in self.world.counters.items():
            if key.startswith(self.MASTERY_PREFIX):
                member_id, _, ability_id = key[len(self.MASTERY_PREFIX) :].partition("|")
                extensions.mastery_uses[(member_id, ability_id)] = int(value)
        for member_id in self.battle.members:
            extensions.sync_mastery_tags(self.battle, member_id)
        for gauge_id, _maximum in extensions.rules.shared_gauges:
            key = f"{self.GAUGE_PREFIX}{gauge_id}"
            extensions.shared[gauge_id] = float(self.world.counters.get(key, 0.0))
        extensions.on_shared_change = self._store_shared_gauge

    GAUGE_PREFIX = "gauge."

    def _store_shared_gauge(self, gauge_id, value):
        self.world.counters[f"{self.GAUGE_PREFIX}{gauge_id}"] = float(value)

    def party_gauge(self, gauge_id):
        """A party-wide gauge's value (saved with the world; works in and out of battle)."""
        return float(self.world.counters.get(f"{self.GAUGE_PREFIX}{gauge_id}", 0.0))

    def change_party_gauge(self, gauge_id, amount):
        """Add / spend on a party-wide gauge, clamped to ``0..maximum``; returns the change."""
        rules = self.extension_rules
        maximum = dict(rules.shared_gauges).get(str(gauge_id)) if rules else None
        if maximum is None:
            raise GameSessionError(f"unknown party gauge {gauge_id}")
        before = self.party_gauge(gauge_id)
        after = max(0.0, min(maximum, before + float(amount)))
        self._store_shared_gauge(str(gauge_id), after)
        if self.battle is not None and self.battle.extensions is not None:
            self.battle.extensions.shared[str(gauge_id)] = after
        return after - before

    def _store_mastery(self):
        extensions = None if self.battle is None else self.battle.extensions
        if extensions is None:
            return
        for (member_id, ability_id), uses in extensions.mastery_uses.items():
            if member_id in self.save.rpg_state.actor_progression:
                self.world.counters[f"{self.MASTERY_PREFIX}{member_id}|{ability_id}"] = float(uses)
