"""``BattleRuntime``: the turn-based battle core. This module builds it (parties, rules and the
runtimes it coordinates); what it does lives in its mixins - ``runtime_roster`` (who is in the
battle), ``runtime_actions`` (actions and their results) and ``runtime_turns`` (turns, cooldowns,
the outcome). Its value types (``Party``, ``TurnQueue``, ``BattleAction``...) are in
``runtime_types``."""

from __future__ import annotations

import random
from collections.abc import Callable

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import AbilityRuntime
from asteria.rpg.battle.action_sequences import ActionSequenceRuntime
from asteria.rpg.battle.extensions import BattleExtensionRules, BattleExtensionRuntime
from asteria.rpg.battle.gauges import BattleGaugeCompositionRuntime
from asteria.rpg.battle.interactions import InteractionResolver
from asteria.rpg.battle.lifecycle import (
    BattleEscapeRule,
    BattleObjectiveRuntime,
    CombatantLifecycleRuntime,
)
from asteria.rpg.battle.reactions import ReactionRuntime
from asteria.rpg.battle.resources import BattleResourceRuntime
from asteria.rpg.battle.runtime_actions import BattleActionsMixin
from asteria.rpg.battle.runtime_roster import BattleRosterMixin
from asteria.rpg.battle.runtime_turns import BattleTurnsMixin
from asteria.rpg.battle.runtime_types import Party, PartyMember, TurnOrderPolicy, TurnQueue
from asteria.rpg.battle.scheduler import BattleScheduler, BattleSchedulerDefinition
from asteria.rpg.battle.states import BattleStateRuntime
from asteria.rpg.battle.targeting import BattleFormationRuntime, BattleTargetingRuntime
from asteria.rpg.battle.timing import BattleActionTimingRuntime
from asteria.rpg.battle.transactions import BattleTransactionRuntime
from asteria.rpg.enemies.ai import EnemyAIRuntime


class BattleRuntime(BattleRosterMixin, BattleActionsMixin, BattleTurnsMixin):
    """Thin RPG coordinator over Phase 6 AbilityRuntime plus lifecycle hooks.

    Outcome semantics are injected through `is_active`; BattleRuntime never
    assumes HP, death tags, or any specific defeat rule.
    """

    def __init__(
        self,
        parties,
        ability_runtime,
        *,
        turn_policy=TurnOrderPolicy.FIXED_INITIATIVE,
        hooks=None,
        is_active: Callable[[PartyMember], bool] | None = None,
        resource_definitions=(),
        interaction_rules=(),
        outcome_checks=(),
        state_policies=(),
        targeting_definitions=(),
        formations=None,
        objective_definitions=(),
        escape_rules=(),
        scheduler_definition=None,
        action_timing_definitions=(),
        action_sequence_definitions=(),
        gauge_composition_definitions=(),
        reaction_definitions=(),
        enemy_ai_definitions=(),
        ai_condition_resolvers=None,
        ai_target_resolvers=None,
        ai_action_handlers=None,
        transaction_policies=(),
        rng_seed=0,
        extensions=None,
    ):
        parties = tuple(parties)
        if not parties:
            raise ValueError("battle requires at least one party")
        if any(not isinstance(x, Party) for x in parties):
            raise TypeError("parties must be Party values")
        if not isinstance(ability_runtime, AbilityRuntime):
            raise TypeError("ability_runtime must be AbilityRuntime")
        if is_active is not None and not callable(is_active):
            raise TypeError("is_active must be callable")
        self.hooks = hooks
        self.is_active = is_active or (lambda member: True)
        self.parties = {p.side: p for p in parties}
        if len(self.parties) != len(parties):
            raise ValueError("duplicate party side")
        members = []
        for p in parties:
            members.extend(p.members)
        if len({m.member_id for m in members}) != len(members):
            raise ValueError("duplicate battle member id")
        self.members = {m.member_id: m for m in members}
        self.outcome_exempt = set()  # members whose survival does not keep their side alive
        # members waiting off the stage (a creature party's bench): standing, but not acting,
        # not targetable, and still keeping their side in the fight
        self.benched = set()
        self._base_is_active = self.is_active
        self.combatants = CombatantLifecycleRuntime(
            members, hooks=hooks, initial_active=self._base_is_active
        )
        self.is_active = lambda member: (
            self.combatants.is_active(member)
            and self._base_is_active(member)
            and member.member_id not in self.benched
        )
        self.objectives = BattleObjectiveRuntime(objective_definitions, hooks=hooks)
        self.escape_rules = {}
        for rule in escape_rules:
            if not isinstance(rule, BattleEscapeRule):
                raise TypeError("escape_rules must be BattleEscapeRule values")
            if rule.rule_id in self.escape_rules:
                raise ValueError(f"duplicate escape rule: {rule.rule_id}")
            self.escape_rules[rule.rule_id] = rule
        self._escaped_sides = set()
        self._transform_stacks = {}
        self.ability_runtime = ability_runtime
        # member id -> {ability id: turns left} (AbilityDefinition.cooldown_turns)
        self.cooldowns = {}
        # member id -> abilities the member can no longer use (e.g. its weapon broke mid-battle)
        self.blocked_abilities = {}
        self._used_this_turn = set()
        self.battle_resources = BattleResourceRuntime(resource_definitions, members, hooks=hooks)
        self.interactions = InteractionResolver(interaction_rules, outcome_checks, hooks=hooks)
        self.battle_states = BattleStateRuntime(state_policies, hooks=hooks)
        self.battle_states.periodic_transform = self._periodic_interaction_transform
        self.periodic_interactions = []
        formation_runtimes = {}
        for side, value in dict(formations or {}).items():
            if isinstance(value, BattleFormationRuntime):
                runtime = value
            else:
                runtime = BattleFormationRuntime(value)
            formation_runtimes[str(side)] = runtime
        self.formations = formation_runtimes
        self.targeting = BattleTargetingRuntime(
            self.members,
            definitions=targeting_definitions,
            formations=self.formations,
            is_active=self.is_active,
            is_targetable=lambda member: self.combatants.is_targetable(member),
            candidate_filter=self._filter_candidates,
        )
        if scheduler_definition is None:
            self.scheduler = None
            self.turn_queue = TurnQueue(members, turn_policy)
        else:
            if not isinstance(scheduler_definition, BattleSchedulerDefinition):
                raise TypeError("scheduler_definition must be BattleSchedulerDefinition")
            self.scheduler = BattleScheduler(members, scheduler_definition)
            self.turn_queue = self.scheduler
        self.action_timing = BattleActionTimingRuntime(action_timing_definitions)
        self.action_sequences = ActionSequenceRuntime(action_sequence_definitions)
        self.gauge_compositions = BattleGaugeCompositionRuntime(
            gauge_composition_definitions, hooks=hooks
        )
        self.reactions = ReactionRuntime(reaction_definitions, hooks=hooks)
        self.enemy_ai = EnemyAIRuntime(
            enemy_ai_definitions,
            hooks=hooks,
            condition_resolvers=ai_condition_resolvers,
            target_resolvers=ai_target_resolvers,
            action_handlers=ai_action_handlers,
        )
        self.transactions = BattleTransactionRuntime(transaction_policies)
        self.rng = random.Random(rng_seed)
        if getattr(self.ability_runtime, "rng", "absent") is None:
            self.ability_runtime.rng = self.rng  # formula expressions roll the battle's dice
        self.escape_attempts = {}  # side -> how many times it tried to run (escape formulas)
        # set by the session from its battle rules: the expression every hit's damage goes
        # through after the interaction rules, and the resource that is health
        self.final_damage_expression = ""
        self.knockout_resource_id = ""
        self.battle_states.rng = self.rng  # prevent / cure chances and random durations
        if isinstance(extensions, BattleExtensionRules):
            extensions = BattleExtensionRuntime(extensions)
        # Optional rules layered on the core (taunt, life steal, use limits ...); see
        # battle_extensions.
        self.extensions = extensions
        if extensions is not None:
            extensions.sync_row_tags(self)
        self._resource_ready_entry = None
        self._resources_finished = False
        self.battle_resources.apply_trigger("rpg.battle.started")
        emit_hook(self.hooks, "rpg.battle.started", data={"battle": self})
        self.battle_resources.apply_trigger("rpg.battle.round_started")
        emit_hook(
            self.hooks,
            "rpg.battle.round_started",
            data={"round_index": self.turn_queue.round_index},
        )
