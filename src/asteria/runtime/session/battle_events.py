"""Battle hooks: durability, refining, disassembly, job points, new game plus, weaknesses and
common events."""

from __future__ import annotations

import random

from asteria.core.lifecycle import LifecycleHookBus

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class BattleEventsMixin:
    # -- battle events (EVT-03) -------------------------------------------------------------------
    def _battle_hook_bus(self):
        """A fresh hook bus per battle; project lifecycle bindings on ``rpg.battle.*`` hooks run as
        battle events."""
        from asteria.events import LifecycleEventBridge

        bus = LifecycleHookBus()
        bus.subscribe(
            "rpg.battle.turn_skipped", self._turn_skipped
        )  # asleep, stunned, broken...: shown in battle
        bus.subscribe("rpg.battle.after_action", self._wear_equipment)  # durability
        for hook in ("state_ticked", "state_expired", "state_removed"):  # told in battle
            bus.subscribe(f"rpg.battle.{hook}", self._state_event)
        bindings = [
            b
            for b in self.project.lifecycle_event_bindings
            if b.hook_name.startswith("rpg.battle.")
        ]
        self.battle_events = LifecycleEventBridge(bus, self.events, bindings) if bindings else None
        self.save.event_context.providers["battle"] = self._battle_value
        return bus

    @property
    def durability_rules(self):
        """Project equipment durability rules: the first by id, or ``None``."""
        values = self.project.rpg_database.durability_rules
        return values[sorted(values)[0]] if values else None

    def wear_equipment(self, actor_id, event):
        """Wear ``actor_id``'s gear for ``event`` (``attack``, ``hit`` ...); returns what broke."""
        rules = self.durability_rules
        loadout = self.save.rpg_state.loadouts.get(str(actor_id))
        if rules is None or loadout is None:
            return ()
        in_battle = self.mode == "battle" and str(actor_id) in self.battle.members
        before = self.resolve_actor_build(actor_id) if in_battle else None
        broke = rules.apply_wear(loadout, str(event))
        for item in broke:
            name = item.nickname or self.name_of(item.equipment)
            self.notify(self.tr("notice.broke", "{name} broke!", name=name), kind="warning")
        if broke and in_battle:
            self._apply_break_to_battle(str(actor_id), before)
        return broke

    def _apply_break_to_battle(self, actor_id, before):
        """A weapon that breaks mid-battle stops helping at once: the stats and resource
        maxima it gave are taken off the fighter and the abilities it granted are blocked."""
        after = self.resolve_actor_build(actor_id)
        member = self.battle.member(actor_id)
        stats, resources = member.subject.stats, member.subject.resources
        for name in before.stats.names():
            delta = after.stats.get(name) - before.stats.get(name)
            if delta and stats.contains(name):
                stats.add(name, delta)
        for name in before.resources.names():
            if resources.contains(name) and after.resources.contains(name):
                top = resources.maximum(name) + (
                    after.resources.maximum(name) - before.resources.maximum(name)
                )
                resources.get(name).set_maximum(max(top, resources.get(name).minimum))
        lost = set(before.abilities) - set(after.abilities)
        if lost:
            self.battle.blocked_abilities.setdefault(actor_id, set()).update(lost)

    def _wear_equipment(self, event):
        if self.durability_rules is None:
            return
        data = event.data
        if not data["result"].execution_result.executed:
            return
        actor = data["actor"]
        if actor.side == "heroes":
            self.wear_equipment(actor.member_id, "attack")
        for target in data["targets"]:
            if target.side == "heroes" and target.side != actor.side:
                self.wear_equipment(target.member_id, "hit")

    def _equipped(self, actor_id, instance_id):
        """An equipped item by instance id, or ``slot:<slot id>`` for what the slot holds (an
        event that does not know the id: "refine the armour Mira wears")."""
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        text = str(instance_id)
        if text.startswith("slot:"):
            held = loadout.equipped(text[5:]) if text[5:] in loadout.slot_ids() else ()
            if not held:
                raise GameSessionError(f"{actor_id} wears nothing in {text[5:]}")
            return held[0]
        item = next((x for x in loadout.equipped() if x.instance_id == text), None)
        if item is None:
            raise GameSessionError(f"{instance_id} is not equipped by {actor_id}")
        return item

    def repair_equipment(self, actor_id, instance_id, amount=None):
        """Repair an equipped item, paying the rules' price in currency; returns points fixed."""
        rules = self.durability_rules
        if rules is None:
            raise GameSessionError("the project defines no durability rules")
        item = self._equipped(actor_id, instance_id)
        currency, cost = rules.repair_cost(item, amount)
        funds = self.save.rpg_state.currencies
        if cost and funds.get(currency, 0.0) < cost:
            raise GameSessionError(f"a repair costs {cost:g} {currency}")
        points = rules.repair(item, amount)
        if cost and points:
            funds[currency] = funds.get(currency, 0.0) - cost
        return points

    @property
    def refine_rules(self):
        """Project weapon refine rules: the first by id, or ``None``."""
        values = self.project.rpg_database.refine_rules
        return values[sorted(values)[0]] if values else None

    def refine_rules_for(self, item):
        """The first refine rules (by id) that take ``item`` (weapons, armour... by tag)."""
        values = self.project.rpg_database.refine_rules
        return next((values[k] for k in sorted(values) if values[k].eligible(item)), None)

    def refine_equipment(self, actor_id, instance_id, *, protect=False):
        """One refine attempt on an equipped item; the rules' price and materials are paid win
        or lose. ``protect`` uses up the rules' protection item: a failure then keeps the
        level."""
        if self.refine_rules is None:
            raise GameSessionError("the project defines no refine rules")
        item = self._equipped(actor_id, instance_id)
        rules = self.refine_rules_for(item)
        if rules is None:
            raise GameSessionError(f"{instance_id} cannot be refined")
        bag = self.save.rpg_state.inventory
        for item_id, count in rules.materials:
            if bag.count(item_id) < count:
                raise GameSessionError(f"a refine needs {count} {item_id}")
        protected = bool(protect and rules.protect_item)
        if protected and bag.count(rules.protect_item) < 1:
            raise GameSessionError(f"no {rules.protect_item} to protect the refine")
        if item.refine_level >= rules.max_level:
            raise GameSessionError(f"{instance_id} is at the maximum refine level")
        cost = rules.cost(item.refine_level)
        funds = self.save.rpg_state.currencies
        if cost and funds.get(rules.currency, 0.0) < cost:
            raise GameSessionError(f"a refine costs {cost:g} {rules.currency}")
        rng = getattr(self, "refine_rng", None)  # a test or replay may fix the rolls
        before = item.refine_level
        result = rules.attempt(item, rng or (self.battle.rng if self.mode == "battle" else None))
        if cost:
            funds[rules.currency] = funds.get(rules.currency, 0.0) - cost
        for item_id, count in rules.materials:
            bag.remove(item_id, count)
        if protected:
            bag.remove(rules.protect_item, 1)
            if result.outcome == "failure":  # the scroll holds the level
                rules.apply_level(item, before)
                result = type(result)("protected", before, before, result.cost, False)
        if result.destroyed:
            loadout = self.save.rpg_state.loadouts[str(actor_id)]
            for slot_id in loadout.slot_ids():
                held = loadout.equipped(slot_id)
                if item in held:
                    loadout.unequip(slot_id, held.index(item))
                    break
        return result

    def rename_equipment(self, actor_id, instance_id, name):
        """Give an equipped item a nickname of the player's choice."""
        return self._equipped(actor_id, instance_id).rename(name)

    def disassemble(self, item_id):
        """Break one ``item_id`` down by the project's disassembly recipe."""
        from asteria.rpg.disassembly import disassemble

        recipe = self.project.rpg_database.disassembly_recipes.get(str(item_id))
        if recipe is None:
            raise GameSessionError(f"{item_id} cannot be disassembled")
        state = self.save.rpg_state
        counter = self.world.add_counter("disassembly.count", 1)
        result = disassemble(
            recipe,
            state.inventory,
            state.currencies,
            random.Random(f"{item_id}:{int(counter)}:disassemble"),
        )
        if not result.done:
            raise GameSessionError(f"cannot disassemble {item_id}: {result.reason}")
        return result

    @property
    def job_point_rules(self):
        values = self.project.rpg_database.job_point_rules
        return values[sorted(values)[0]] if values else None

    def _award_job_points(self, defeated_count):
        rules = self.job_point_rules
        if rules is None:
            return {}
        state = self.save.rpg_state
        given = {}
        for actor_id in state.party_active_actor_ids:
            progress = state.actor_progression.get(actor_id)
            allocation = state.progression_allocations.get(actor_id)
            if progress is None or allocation is None:
                continue
            for balance, points in rules.award(progress.active_class_ids, defeated_count).items():
                allocation.grant(balance, points)
                given.setdefault(actor_id, {})[balance] = points
        return given

    def new_game_plus(self, rules_id=None):
        """A fresh save from the project's game start that keeps what the New Game Plus rules
        carry over from this game (the running game is left as it is)."""
        from asteria.rpg.new_game_plus import carry_over

        rules = self.project.rpg_database.new_game_plus_rules
        if not rules:
            raise GameSessionError("the project defines no New Game Plus rules")
        chosen = rules[str(rules_id) if rules_id else sorted(rules)[0]]
        self.sync_world_state()
        fresh = self.project.game_start.instantiate(self.project)
        return carry_over(chosen, self.save, fresh)

    def request_new_game_plus(self, rules_id=None):
        """Ask the game host to start over in New Game Plus (an event's ``NEW_GAME_PLUS``): the
        carried-over save waits in ``pending_new_game`` until the host adopts it."""
        self.pending_new_game = self.new_game_plus(rules_id)
        return self.pending_new_game

    @property
    def revealed_weaknesses(self):
        """``{(enemy kind, interaction rule id)}`` found by hitting a weakness (kept for the whole
        session)."""
        values = getattr(self, "_revealed_weaknesses", None)
        if values is None:
            values = self._revealed_weaknesses = set()
        return values

    def shield_resource(self):
        """The battle resource shown as shields: the rules' ``shield_resource_id``, else the first
        break gauge's."""
        if self.rules.shield_resource_id:
            return self.rules.shield_resource_id
        for composition_id in sorted(self.battle.gauge_compositions.definitions):
            for impact in self.battle.gauge_compositions.definitions[composition_id].impacts:
                return impact.resource_id
        return ""

    def weaknesses(self, member_id):
        """The member's weaknesses for the battle screen: ``[(label, revealed)]`` from the
        interaction rules whose
        outcome is the weakness tag and whose target tags the member carries (labels from their
        source tags)."""
        weak = self.rules.weakness_outcome_tag
        tags = self.battle.member(member_id).subject.tags
        kind = str(member_id).split(":", 1)[0]
        found = []
        for rule in self.battle.interactions.rules.values():
            if weak not in rule.outcome_tags:
                continue
            if rule.target_tags_all and not all(tags.contains(t) for t in rule.target_tags_all):
                continue
            if rule.target_tags_any and not any(tags.contains(t) for t in rule.target_tags_any):
                continue
            names = rule.source_tags_all or rule.source_tags_any or (rule.rule_id,)
            label = "/".join(n.split(".")[-1] for n in names)
            found.append((label, (kind, rule.rule_id) in self.revealed_weaknesses))
        return found

    def _state_event(self, event):
        """A state hurt its holder, ran out or was cured: logged as ``state_tick``,
        ``state_expired`` or ``state_removed`` (data: ``state``, ``changes``, ``trigger``)."""
        data = dict(event.data or {})
        kind = {
            "rpg.battle.state_ticked": "state_tick",
            "rpg.battle.state_expired": "state_expired",
            "rpg.battle.state_removed": "state_removed",
        }.get(event.name, "")
        if not kind:
            return
        self._log(
            kind,
            member_id=str(event.source),
            data={
                "state": data.get("state_id", ""),
                "changes": dict(data.get("changes", {})),
                "trigger": data.get("trigger", ""),
            },
        )

    def _turn_skipped(self, event):
        data = event.data or {}
        self._log(
            "turn_skipped",
            member_id=str(event.source),
            data={"states": tuple(data.get("blocking_states", ()))},
        )

    def _battle_value(self, name):
        """Values battle-event conditions can read: ``round``, ``hp_ratio:<member or enemy id>``,
        ``alive:<id>``."""
        battle = self.battle
        if battle is None:
            return None
        if name == "round":
            return battle.turn_queue.round_index
        kind, _, key = str(name).partition(":")
        members = [
            m
            for m in battle.members.values()
            if m.member_id == key or m.member_id.split(":", 1)[0] == key
        ]
        if kind == "alive":
            return any(battle.is_active(m) for m in members)
        if kind == "hp_ratio":
            resource = self.rules.knockout_resource_id
            for member in members:
                value = member.subject.resources.get(resource)
                return 0.0 if value.maximum == 0 else value.current / value.maximum
            return None
        raise KeyError(f"unknown battle value {name}")

    def _refresh_common_events(self):
        from asteria.events.scheduler import EventScheduleMode, ScheduledEventSpec

        desired = {}
        for common in self.project.common_events:
            if common.active(self.save.event_context):
                mode = (
                    EventScheduleMode.AUTORUN
                    if common.trigger == "autorun"
                    else EventScheduleMode.PARALLEL
                )
                spec = ScheduledEventSpec(f"common:{common.program_id}", common.program_id, mode)
                desired[spec.event_id] = spec
        for spec in self.common_events.specs():
            if spec.event_id not in desired:
                self.common_events.remove(spec.event_id)
        existing = {s.event_id for s in self.common_events.specs()}
        for event_id, spec in desired.items():
            if event_id not in existing:
                self.common_events.add(spec)

    @property
    def pending_dialogue(self):
        """The DialogueRequest or ChoiceRequest waiting for the player, if any."""
        runner = self._dialogue_runner()
        if runner is None:
            return None
        request = runner.dialogue.dialogue or runner.dialogue.choice
        line = getattr(request, "line", None)
        if line is not None and line is not self._last_logged_line:
            self._last_logged_line = line  # each line is logged once, when it first shows
            self.backlog.add(
                self.expand_message(self.speaker_of(line), plain=True),
                self.expand_message(self.line_text(line), plain=True),
            )
        return request
