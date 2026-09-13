from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class CostCommitMode(str, Enum):
    RESOLUTION = "resolution"
    START = "start"


class InterruptCostPolicy(str, Enum):
    KEEP = "keep"
    REFUND = "refund"


@dataclass(frozen=True, slots=True)
class ActionTransactionPolicy:
    ability_id: str
    cost_commit: CostCommitMode = CostCommitMode.RESOLUTION
    interrupt_cost: InterruptCostPolicy = InterruptCostPolicy.KEEP

    def __init__(self, ability_id, *, cost_commit=CostCommitMode.RESOLUTION, interrupt_cost=InterruptCostPolicy.KEEP):
        ability_id = str(ability_id).strip()
        if not ability_id:
            raise ValueError("ability_id is required")
        object.__setattr__(self, "ability_id", ability_id)
        object.__setattr__(self, "cost_commit", CostCommitMode(cost_commit))
        object.__setattr__(self, "interrupt_cost", InterruptCostPolicy(interrupt_cost))

    def to_data(self):
        return {
            "schema": "asteria.rpg.action_transaction_policy",
            "version": 1,
            "ability_id": self.ability_id,
            "cost_commit": self.cost_commit.value,
            "interrupt_cost": self.interrupt_cost.value,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.action_transaction_policy" or data.get("version") != 1:
            raise ValueError("unsupported action transaction policy")
        return cls(
            data["ability_id"], cost_commit=data.get("cost_commit", "resolution"),
            interrupt_cost=data.get("interrupt_cost", "keep"),
        )


@dataclass(slots=True)
class PendingCostReservation:
    token: str
    actor_id: str
    ability_id: str
    costs: tuple[tuple[str, float], ...]
    refund_on_interrupt: bool

    def to_data(self):
        return {"token": self.token, "actor_id": self.actor_id, "ability_id": self.ability_id,
                "costs": [[r, a] for r, a in self.costs], "refund_on_interrupt": self.refund_on_interrupt}

    @classmethod
    def from_data(cls, data):
        return cls(str(data["token"]), str(data["actor_id"]), str(data["ability_id"]),
                   tuple((str(r), float(a)) for r, a in data.get("costs", ())),
                   bool(data.get("refund_on_interrupt", False)))


class BattleTransactionRuntime:
    SCHEMA = "asteria.rpg.battle_transaction_runtime"
    VERSION = 1

    def __init__(self, policies=()):
        self.policies = {}
        for policy in policies:
            if not isinstance(policy, ActionTransactionPolicy):
                raise TypeError("policies must be ActionTransactionPolicy")
            if policy.ability_id in self.policies:
                raise ValueError(f"duplicate action transaction policy: {policy.ability_id}")
            self.policies[policy.ability_id] = policy
        self._reservations = {}

    def policy_for(self, ability_id):
        return self.policies.get(str(ability_id), ActionTransactionPolicy(str(ability_id)))

    @staticmethod
    def evaluate_costs(ability_runtime, ability_id, subject, target_subject=None):
        from asteria.gameplay.abilities import _formula_context
        definition = ability_runtime.registry.require(ability_id)
        context = _formula_context(subject, target_subject)
        result = []
        for cost in definition.costs:
            amount = float(cost.amount.evaluate(context))
            if not isfinite(amount) or amount < 0:
                raise ValueError(f"invalid cost: {cost.resource}")
            if not subject.resources.contains(cost.resource):
                raise ValueError(f"missing resource: {cost.resource}")
            if subject.resources.current(cost.resource) - subject.resources.get(cost.resource).minimum < amount:
                raise ValueError(f"insufficient resource: {cost.resource}")
            result.append((cost.resource, amount))
        return tuple(result)

    def commit_start(self, token, actor_id, ability_id, subject, target_subject, ability_runtime):
        policy = self.policy_for(ability_id)
        if policy.cost_commit != CostCommitMode.START:
            return ()
        costs = self.evaluate_costs(ability_runtime, ability_id, subject, target_subject)
        spent = []
        for resource, amount in costs:
            if not subject.resources.spend(resource, amount):
                for prior_resource, prior_amount in spent:
                    subject.resources.restore(prior_resource, prior_amount)
                raise ValueError(f"insufficient resource: {resource}")
            spent.append((resource, amount))
        self._reservations[str(token)] = PendingCostReservation(
            str(token), str(actor_id), str(ability_id), tuple(spent),
            policy.interrupt_cost == InterruptCostPolicy.REFUND,
        )
        return tuple(spent)

    def consume(self, token):
        return self._reservations.pop(str(token), None)

    def cancel(self, token, subject):
        reservation = self._reservations.pop(str(token), None)
        if reservation is not None and reservation.refund_on_interrupt:
            for resource, amount in reservation.costs:
                subject.resources.restore(resource, amount)
        return reservation

    def to_data(self):
        return {"schema": self.SCHEMA, "version": self.VERSION,
                "reservations": [self._reservations[k].to_data() for k in sorted(self._reservations)]}

    def restore_from_data(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported battle transaction runtime")
        self._reservations = {x["token"]: PendingCostReservation.from_data(x) for x in data.get("reservations", ())}
        return self
