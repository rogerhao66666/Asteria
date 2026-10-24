"""Each strike of an action: repeats, hit checks, kills, reactions, and whose turn it is."""

from __future__ import annotations

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class StrikesMixin:
    def _repeat_action(self, actor_id, ability_id, targets, offensive, repeats, power=1.0):
        definition = self.battle.ability_runtime.registry.get(ability_id)
        self._send_out_pet(actor_id, definition)
        hits = tuple(getattr(definition, "hits", ()) or ()) or ({"tags": [], "power": 1.0},)
        results = []
        actor_tags = self.battle.member(actor_id).subject.tags
        self.last_outcome_tags = set()  # what this action's hit checks came out as (a miss...)
        counts = getattr(definition, "hit_counts", None) or {}
        if counts:  # a move that strikes several times: one count rolled per use
            repeats *= self._roll_count(counts)
        first_rolled = None  # the first strike's first_checks, kept for the later strikes
        strikes = 0
        for _ in range(repeats):
            for (
                hit
            ) in hits:  # each hit lands on its own: its damage types meet weaknesses and shields
                hit_tags = list(hit["tags"])
                follow = getattr(definition, "follow_tags", None) or {}
                hit_tags += [to for have, to in follow.items() if actor_tags.contains(have)]
                if offensive and hit.get("first_checks") and targets:
                    if first_rolled is None:
                        first_rolled = self._roll_hit_checks(
                            actor_id,
                            hit["first_checks"],
                            targets[0],
                            action_tags=(*definition.tags, *hit_tags),
                        )
                        if first_rolled:
                            self._log(
                                "hit_check",
                                member_id=str(actor_id),
                                target_ids=(str(targets[0]),),
                                data={"tags": tuple(first_rolled)},
                            )
                    hit_tags += first_rolled
                    self.last_outcome_tags.update(first_rolled)
                if offensive and hit.get("checks") and targets:
                    rolled = self._roll_hit_checks(
                        actor_id,
                        hit["checks"],
                        targets[0],
                        action_tags=(*definition.tags, *hit_tags),
                    )
                    hit_tags += rolled
                    self.last_outcome_tags.update(rolled)
                    if rolled:  # a crit / evade the player should see and the log can count
                        self._log(
                            "hit_check",
                            member_id=str(actor_id),
                            target_ids=(str(targets[0]),),
                            data={"tags": tuple(rolled)},
                        )
                added = [t for t in dict.fromkeys(hit_tags) if not actor_tags.contains(t)]
                for tag in added:
                    actor_tags.add(tag)
                self.battle.action_scale = hit["power"] * power
                try:
                    targets = self._one_hit(
                        actor_id,
                        ability_id,
                        targets,
                        offensive,
                        results,
                        waive_costs=bool(results),
                    )
                finally:
                    self.battle.action_scale = 1.0
                    for tag in added:
                        actor_tags.remove(tag)
                strikes += 1
                if offensive and hit.get("kill"):
                    self._apply_hit_kill(actor_id, hit["kill"], targets)
                if not targets:
                    break
                if first_rolled and counts and self._missed(first_rolled):
                    break  # the whole use missed: no more strikes
            else:
                continue
            break
        if counts and strikes and not self._missed(first_rolled or ()):
            self._log("strikes", member_id=str(actor_id), data={"count": strikes})
        return tuple(results)

    def _roll_count(self, counts):
        """One count of ``{count: weight}`` by its weight (the battle's dice)."""
        roll = self.battle.rng.random() * sum(counts.values())
        for count, weight in counts.items():
            roll -= weight
            if roll < 0:
                return count
        return max(counts)

    def _missed(self, tags):
        """Whether outcome ``tags`` hold a check's failure (a miss): its failure tags."""
        checks = self.battle.interactions.checks
        failures = {t for check in checks.values() for t in check.failure_tags}
        return bool(failures & set(tags))

    def _roll_hit_checks(self, actor_id, check_ids, target_id, *, action_tags=()):
        """Outcome tags of a hit's checks, rolled once per hit against its first target (the
        tags then meet the interaction rules like any other source tag). The skill's and the
        hit's tags count as the source's, so a check can ask for (or refuse) ``magic``."""
        battle = self.battle
        source = battle.member(actor_id).subject
        target = battle.member(target_id).subject
        tags = []
        for check_id in check_ids:
            if check_id in battle.interactions.checks:
                check = battle.interactions.check(
                    check_id, source, target, action_tags=action_tags, rng=battle.rng
                )
                tags.extend(check.outcome_tags)
        return tags

    def _drain_and_recoil(self, actor_id, ability_id, targets, before):
        """An ability with ``drain`` heals its user by that share of the damage it just dealt
        (at least 1); with ``recoil`` the user takes that share itself (at least 1)."""
        definition = self.battle.ability_runtime.registry.get(ability_id)
        drain = getattr(definition, "drain", 0.0)
        recoil = getattr(definition, "recoil", 0.0)
        resource = self.rules.knockout_resource_id
        if not (drain or recoil) or not resource:
            return
        after = self._knockout_values(targets)
        dealt = sum(max(0.0, before.get(t, 0.0) - after.get(t, 0.0)) for t in targets)
        if dealt <= 0:
            return
        pool = self.battle.member(actor_id).subject.resources
        if not pool.contains(resource):
            return
        if drain:
            gain = max(1.0, float(int(dealt * drain)))
            pool.set_current(resource, min(pool.maximum(resource), pool.current(resource) + gain))
            self._log(
                "drain", member_id=str(actor_id), target_ids=tuple(targets), data={"amount": gain}
            )
        if recoil:
            loss = max(1.0, float(int(dealt * recoil)))
            pool.set_current(resource, max(0.0, pool.current(resource) - loss))
            self._log("recoil", member_id=str(actor_id), data={"amount": loss})

    def _apply_hit_kill(self, actor_id, kill, target_ids):
        """Instant KO of a hit: ``chance`` to empty ``resource``; targets tagged immune take
        ``immune_fraction`` of the resource maximum instead (default nothing)."""
        resource = kill["resource"]
        for target_id in target_ids:
            member = self.battle.member(target_id)
            if not self.battle.is_active(member):
                continue
            if self.battle.rng.random() >= kill["chance"]:
                continue
            pool = member.subject.resources
            immune = any(member.subject.tags.contains(t) for t in kill.get("immune_tags", ()))
            if immune:
                loss = kill.get("immune_fraction", 0.0) * pool.maximum(resource)
                pool.set_current(resource, max(0.0, pool.current(resource) - loss))
            else:
                pool.set_current(resource, 0.0)
            self._log(
                "kill",
                member_id=str(actor_id),
                target_ids=(str(target_id),),
                data={"immune": immune, "resource": resource},
            )

    def _run_reactions(self, actor_id, ability_id, target_ids):
        """Reactions of the project (counters, covers...) after an action; each one that ran is
        logged like an action of its own, so the battle screen plays it."""
        db = self.project.rpg_database
        if not db.reactions or self.mode != "battle":
            return ()
        definition = self.battle.ability_runtime.registry.get(ability_id)
        tags = tuple(definition.tags) if definition is not None else ()
        chain = self.battle.resolve_reactions(
            "rpg.battle.after_action", actor_id, tuple(target_ids), tags=tags
        )
        for request, result in zip(chain.requests, chain.action_results):
            if request.ability_id is None:
                continue
            before = {t: 0.0 for t in request.target_ids}
            self._log(
                "action",
                member_id=request.reactor_id,
                ability_id=request.ability_id,
                target_ids=tuple(request.target_ids),
                outcomes=self._action_outcomes(
                    request.reactor_id, request.ability_id, request.target_ids, None
                ),
            )
            _ = before, result
        return chain

    def _one_hit(self, actor_id, ability_id, targets, offensive, results, *, waive_costs=False):
        rules = self.rules
        if offensive:
            targets = tuple(t for t in targets if self.battle.is_active(self.battle.member(t)))
            if not targets:
                return ()
        before = self._knockout_values(targets)
        result = self.execute(actor_id, ability_id, targets, waive_costs=waive_costs)
        results.append(result)
        self._drain_and_recoil(actor_id, ability_id, targets, before)
        outcomes = (
            self._action_outcomes(actor_id, ability_id, targets, before) if offensive else ()
        )
        self._log(
            "action",
            member_id=str(actor_id),
            ability_id=str(ability_id),
            target_ids=tuple(targets),
            outcomes=outcomes,
        )
        weak = self.rules.weakness_outcome_tag
        for target_id, outcome in outcomes:
            if (
                weak and weak in outcome.outcome_tags
            ):  # a weakness hit reveals its rule for that enemy kind
                kind = str(target_id).split(":", 1)[0]
                self.revealed_weaknesses.update((kind, r) for r in outcome.value.matched_rules)
            for composition_id in sorted(self.battle.gauge_compositions.definitions):
                gauge = self.battle.apply_gauge_impact(
                    composition_id,
                    actor_id,
                    target_id,
                    trigger=rules.hit_trigger,
                    outcome=outcome,
                )
                if getattr(gauge, "thresholds", ()):
                    self._log("gauge", member_id=str(target_id), data=gauge)
        if offensive:
            self._run_reactions(actor_id, ability_id, targets)
        return targets

    def current_turn_actor(self):
        """Member whose turn it is under the battle's scheduler; starts new rounds as needed."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        if not self.active_enemy_ids() or not self.active_hero_ids():
            return None
        self.resolve_casts()
        if not self.active_enemy_ids() or not self.active_hero_ids():
            return None
        actor = (
            self.battle.next_actor()
        )  # members who cannot act (asleep, broken...) are skipped there
        # a round where everyone left is stunned, asleep or broken passes (their states tick
        # down as they are skipped); try further rounds instead of stalling the battle
        for _ in range(self.MAX_IDLE_ROUNDS):
            if actor is not None:
                break
            self.battle.start_next_round()
            actor = self.battle.next_actor()
        if actor is None:
            return None
        key = (self.battle.turn_queue.round_index, actor.member_id)
        if key != self._logged_turn:
            self._logged_turn = key
            self._log("turn", member_id=actor.member_id)
        return actor.member_id

    def turn_prevented(self, member_id):
        """States of ``member_id`` whose battle policy prevents acting (``prevent_action``); empty
        when free."""
        subject = self.battle.member(member_id).subject
        if subject.states is None:
            return ()
        policies = self.battle.battle_states.policies
        return tuple(
            sorted(
                a.state_id
                for a in subject.states.active_states()
                if getattr(policies.get(a.state_id), "prevent_action", False)
            )
        )

    def _encounter_objectives(self, encounter):
        """The objectives of a fight: every objective no encounter names, plus the ones this
        encounter names with an ``objective:<id>`` tag (named objectives belong to the
        encounters that name them, e.g. "survive four rounds")."""
        db = self.project.rpg_database
        scoped = {
            tag[len("objective:") :]
            for other in db.encounters.values()
            for tag in other.tags
            if tag.startswith("objective:")
        }
        own = {tag[len("objective:") :] for tag in encounter.tags if tag.startswith("objective:")}
        return tuple(
            o
            for o in db.battle_objectives.values()
            if o.objective_id not in scoped or o.objective_id in own
        )

    def encounter_choice(self, prefix, options):
        """The record an ``<prefix>:<id>`` tag of the running encounter names, else None."""
        encounter = self.project.rpg_database.encounters.get(self.encounter_id or "")
        for tag in () if encounter is None else encounter.tags:
            if tag.startswith(f"{prefix}:") and tag[len(prefix) + 1 :] in options:
                return options[tag[len(prefix) + 1 :]]
        return None

    _encounter_choice = encounter_choice
