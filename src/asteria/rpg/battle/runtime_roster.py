"""Who is in a battle: members on the stage and on the bench, sending in, fainting and reviving,
summons and transformations, escaping, and the states and targets a member can be given."""

from __future__ import annotations

from asteria.core.lifecycle import emit_hook
from asteria.rpg.battle.lifecycle import attempt_escape
from asteria.rpg.battle.runtime_types import PartyMember


class BattleRosterMixin:
    """``BattleRuntime``'s members: the stage, the bench, summons, transformations, escape."""

    def member(self, member_id):
        return self.members[str(member_id)]

    def _filter_candidates(self, actor_id, candidates):
        if self.extensions is None:
            return candidates
        return self.extensions.filter_candidates(self, actor_id, candidates)

    def can_act(self, member_id):
        member = self.member(member_id)
        return (
            self.combatants.can_act(member_id)
            and self._base_is_active(member)
            and member_id not in self.benched
        )

    def standing(self, member):
        """Conscious and present, on the stage or on the bench."""
        return self.combatants.is_active(member) and self._base_is_active(member)

    def bench(self, member_id):
        """Take a member off the stage: it keeps its state, but neither acts nor can be
        targeted until ``send_in``."""
        member_id = str(member_id)
        self.member(member_id)
        self.benched.add(member_id)
        self.turn_queue.remove_pending(member_id)
        emit_hook(self.hooks, "rpg.battle.benched", source=member_id, data={})

    def send_in(self, member_id):
        """Bring a benched member onto the stage; its next turn comes with the next round."""
        member_id = str(member_id)
        member = self.member(member_id)
        self.benched.discard(member_id)
        if self.scheduler is not None and member_id not in self.scheduler._members:
            self.scheduler.register_member(member)  # benching dropped it from the timeline
        emit_hook(self.hooks, "rpg.battle.sent_in", source=member_id, data={})

    def incapacitate(self, member_id, *, state_id="incapacitated", targetable=True, reason=""):
        state = self.combatants.incapacitate(
            member_id, state_id=state_id, targetable=targetable, reason=reason
        )
        self.turn_queue.remove_pending(member_id)
        return state

    def revive(self, member_id, *, state_id="active", targetable=True, reason=""):
        return self.combatants.revive(
            member_id, state_id=state_id, targetable=targetable, reason=reason
        )

    def set_member_abilities(self, member_id, ability_ids):
        """Replace what ``member_id`` can use now (after re-arming): its stats and states stay."""
        member = self.member(member_id)
        object.__setattr__(
            member, "ability_ids", tuple(dict.fromkeys(str(x) for x in ability_ids))
        )
        return member

    def remove_combatant(self, member_id, *, state_id="removed", reason=""):
        state = self.combatants.remove(member_id, state_id=state_id, reason=reason)
        self.turn_queue.remove_pending(member_id)
        formation = self.formations.get(self.member(member_id).side)
        if formation is not None and formation.slot_id_for(member_id) is not None:
            formation.remove(member_id)
        return state

    def summon(self, member, *, slot_id=None, owner_id=None, join_current_round=False):
        if not isinstance(member, PartyMember):
            raise TypeError("member must be PartyMember")
        if member.member_id in self.members:
            raise ValueError(f"duplicate battle member id: {member.member_id}")
        if member.side not in self.parties:
            raise ValueError(f"unknown battle side: {member.side}")
        if owner_id is not None and str(owner_id) not in self.members:
            raise ValueError(f"unknown summon owner: {owner_id}")
        formation = self.formations.get(member.side)
        if slot_id is not None:
            if formation is None:
                raise ValueError("summon slot requires a formation for the member side")
            formation.definition.slot(slot_id)
            if formation.member_at(slot_id) is not None:
                raise ValueError(f"formation slot occupied: {slot_id}")
        self.parties[member.side].add(member)
        self.members[member.member_id] = member
        generation = 1
        if owner_id is not None:
            owner_state = self.combatants.state(owner_id)
            generation = owner_state.summon_generation + 1
        self.combatants.register(
            member.member_id, summon_owner_id=owner_id, summon_generation=generation
        )
        self.battle_resources.register_member(member)
        self.targeting.members[member.member_id] = member
        self.turn_queue.register_member(member, join_current_round=join_current_round)
        if slot_id is not None:
            formation.place(member.member_id, slot_id)
        emit_hook(
            self.hooks,
            "rpg.battle.combatant_summoned",
            source=member.member_id,
            data={"member": member, "owner_id": owner_id, "slot_id": slot_id},
        )
        return member

    def transform(self, member_id, replacement, *, form_id, reason=""):
        member_id = str(member_id)
        current = self.member(member_id)
        if not isinstance(replacement, PartyMember):
            raise TypeError("replacement must be PartyMember")
        if replacement.member_id != current.member_id or replacement.side != current.side:
            raise ValueError("transformation replacement must preserve member_id and side")
        prior_form_id = self.combatants.state(member_id).form_id
        self._transform_stacks.setdefault(member_id, []).append((current, prior_form_id))
        self.members[member_id] = replacement
        party = self.parties[current.side]
        party.members = [replacement if x.member_id == member_id else x for x in party.members]
        self.targeting.members[member_id] = replacement
        self.turn_queue.replace_member(replacement)
        self.combatants.set_form(member_id, form_id, reason=reason)
        return replacement

    def revert_transform(self, member_id, *, reason=""):
        member_id = str(member_id)
        stack = self._transform_stacks.get(member_id) or []
        if not stack:
            raise ValueError(f"combatant has no previous form: {member_id}")
        previous, prior_form_id = stack.pop()
        current = self.member(member_id)
        self.members[member_id] = previous
        party = self.parties[current.side]
        party.members = [previous if x.member_id == member_id else x for x in party.members]
        self.targeting.members[member_id] = previous
        self.turn_queue.replace_member(previous)
        if prior_form_id is not None:
            self.combatants.set_form(member_id, prior_form_id, reason=reason)
        else:
            self.combatants.clear_form(member_id, reason=reason)
        return previous

    def set_objective_flag(self, flag_id, value=True):
        self.objectives.set_flag(flag_id, value)

    def attempt_escape(self, rule_id, *, rng=None):
        rule = self.escape_rules[str(rule_id)]
        result = attempt_escape(rule, self, rng=rng)
        self.escape_attempts[rule.side] = self.escape_attempts.get(rule.side, 0) + 1
        if result.succeeded:
            self._escaped_sides.add(rule.side)
            for member in tuple(self.parties[rule.side].members):
                if (
                    member.member_id in self.members
                    and self.combatants.state(member.member_id).present
                ):
                    self.remove_combatant(
                        member.member_id, state_id="escaped", reason=rule.rule_id
                    )
            self.set_objective_flag(f"escape.{rule.side}", True)
        return result

    def ability_availability(self, actor_id, ability_id):
        actor = self.member(actor_id)
        definition = self.ability_runtime.registry.require(ability_id)
        return self.battle_states.ability_availability(actor.subject, definition.tags)

    def apply_state(self, state_id, source_id, target_id, *, rng=None):
        source = self.member(source_id)
        target = self.member(target_id)
        rng = self.rng if rng is None else rng  # the battle's own seeded dice
        return self.battle_states.apply(
            state_id, source.member_id, source.subject, target.member_id, target.subject, rng=rng
        )

    def resolve_targets(self, actor_id, ability_id, requested_ids=(), *, rng=None):
        rng = self.rng if rng is None else rng
        return self.targeting.resolve(actor_id, ability_id, requested_ids, rng=rng)
