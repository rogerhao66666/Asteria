from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite

from asteria.core.lifecycle import emit_hook


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _number(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _nonnegative_map(values, label):
    out = {}
    for key, value in dict(values or {}).items():
        key = _id(key, f"{label} id")
        value = _number(value, label)
        if value < 0:
            raise ValueError(f"{label} must be >= 0")
        out[key] = value
    return out


@dataclass(frozen=True, slots=True)
class ProgressionNodeRequirement:
    node_id: str
    minimum_rank: int = 1

    def __init__(self, node_id, minimum_rank=1):
        minimum_rank = int(minimum_rank)
        if minimum_rank < 1:
            raise ValueError("minimum_rank must be >= 1")
        object.__setattr__(self, "node_id", _id(node_id, "node_id"))
        object.__setattr__(self, "minimum_rank", minimum_rank)

    def to_data(self):
        return {"node_id": self.node_id, "minimum_rank": self.minimum_rank}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"node_id", "minimum_rank"}:
            raise ValueError("invalid progression node requirement")
        return cls(data["node_id"], data["minimum_rank"])


@dataclass(frozen=True, slots=True)
class ProgressionNodeReward:
    stat_bonuses: dict[str, float] = field(default_factory=dict)
    resource_bonuses: dict[str, float] = field(default_factory=dict)
    granted_tags: tuple[str, ...] = ()
    granted_abilities: tuple[str, ...] = ()
    unlocked_passives: tuple[str, ...] = ()
    granted_capabilities: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        stat_bonuses=None,
        resource_bonuses=None,
        granted_tags=(),
        granted_abilities=(),
        unlocked_passives=(),
        granted_capabilities=(),
    ):
        object.__setattr__(
            self,
            "stat_bonuses",
            {k: _number(v, "stat bonus") for k, v in dict(stat_bonuses or {}).items()},
        )
        object.__setattr__(
            self,
            "resource_bonuses",
            {k: _number(v, "resource bonus") for k, v in dict(resource_bonuses or {}).items()},
        )
        object.__setattr__(
            self,
            "granted_tags",
            tuple(sorted({_id(x, "tag").lower() for x in granted_tags})),
        )
        object.__setattr__(
            self,
            "granted_abilities",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in granted_abilities)),
        )
        object.__setattr__(
            self,
            "unlocked_passives",
            tuple(dict.fromkeys(_id(x, "passive_id") for x in unlocked_passives)),
        )
        object.__setattr__(
            self,
            "granted_capabilities",
            tuple(sorted({_id(x, "capability").lower() for x in granted_capabilities})),
        )

    def to_data(self):
        return {
            "stat_bonuses": dict(sorted(self.stat_bonuses.items())),
            "resource_bonuses": dict(sorted(self.resource_bonuses.items())),
            "granted_tags": list(self.granted_tags),
            "granted_abilities": list(self.granted_abilities),
            "unlocked_passives": list(self.unlocked_passives),
            "granted_capabilities": list(self.granted_capabilities),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "stat_bonuses",
            "resource_bonuses",
            "granted_tags",
            "granted_abilities",
            "unlocked_passives",
            "granted_capabilities",
        }
        if set(data) != expected:
            raise ValueError("invalid progression node reward")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ProgressionNodeDefinition:
    node_id: str
    display_name: str
    max_rank: int
    rank_costs: tuple[dict[str, float], ...]
    rewards: tuple[ProgressionNodeReward, ...]
    prerequisites: tuple[ProgressionNodeRequirement, ...] = ()
    any_prerequisites: tuple[ProgressionNodeRequirement, ...] = ()
    exclusive_group: str | None = None
    tags: tuple[str, ...] = ()

    def __init__(
        self,
        node_id,
        display_name=None,
        *,
        max_rank=1,
        rank_costs=None,
        rewards=None,
        prerequisites=(),
        any_prerequisites=(),
        exclusive_group=None,
        tags=(),
    ):
        node_id = _id(node_id, "node_id")
        max_rank = int(max_rank)
        if max_rank < 1:
            raise ValueError("max_rank must be >= 1")
        if rank_costs is None:
            rank_costs = [{} for _ in range(max_rank)]
        elif isinstance(rank_costs, dict):
            rank_costs = [rank_costs for _ in range(max_rank)]
        else:
            rank_costs = list(rank_costs)
        if len(rank_costs) != max_rank:
            raise ValueError("rank_costs must contain one entry per rank")
        costs = tuple(_nonnegative_map(x, "allocation cost") for x in rank_costs)

        if rewards is None:
            rewards = [ProgressionNodeReward() for _ in range(max_rank)]
        elif isinstance(rewards, ProgressionNodeReward):
            rewards = [rewards for _ in range(max_rank)]
        else:
            rewards = list(rewards)
        if len(rewards) != max_rank:
            raise ValueError("rewards must contain one entry per rank")
        rewards = tuple(
            x if isinstance(x, ProgressionNodeReward) else ProgressionNodeReward.from_data(x) for x in rewards
        )

        def reqs(values):
            return tuple(
                x if isinstance(x, ProgressionNodeRequirement) else ProgressionNodeRequirement.from_data(x)
                for x in values
            )

        group = None if exclusive_group is None else _id(exclusive_group, "exclusive_group")
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "display_name", str(display_name or node_id))
        object.__setattr__(self, "max_rank", max_rank)
        object.__setattr__(self, "rank_costs", costs)
        object.__setattr__(self, "rewards", rewards)
        object.__setattr__(self, "prerequisites", reqs(prerequisites))
        object.__setattr__(self, "any_prerequisites", reqs(any_prerequisites))
        object.__setattr__(self, "exclusive_group", group)
        object.__setattr__(self, "tags", tuple(sorted({_id(x, "tag").lower() for x in tags})))

    def cost_for_rank(self, rank):
        rank = int(rank)
        if rank < 1 or rank > self.max_rank:
            raise ValueError("rank outside node range")
        return dict(self.rank_costs[rank - 1])

    def reward_for_rank(self, rank):
        rank = int(rank)
        if rank < 1 or rank > self.max_rank:
            raise ValueError("rank outside node range")
        return self.rewards[rank - 1]

    def to_data(self):
        return {
            "schema": "asteria.rpg.progression_node",
            "version": 1,
            "node_id": self.node_id,
            "display_name": self.display_name,
            "max_rank": self.max_rank,
            "rank_costs": [dict(sorted(x.items())) for x in self.rank_costs],
            "rewards": [x.to_data() for x in self.rewards],
            "prerequisites": [x.to_data() for x in self.prerequisites],
            "any_prerequisites": [x.to_data() for x in self.any_prerequisites],
            "exclusive_group": self.exclusive_group,
            "tags": list(self.tags),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "schema",
            "version",
            "node_id",
            "display_name",
            "max_rank",
            "rank_costs",
            "rewards",
            "prerequisites",
            "any_prerequisites",
            "exclusive_group",
            "tags",
        }
        if set(data) != expected or data.get("schema") != "asteria.rpg.progression_node" or data.get("version") != 1:
            raise ValueError("unsupported progression node")
        return cls(
            data["node_id"],
            data["display_name"],
            max_rank=data["max_rank"],
            rank_costs=data["rank_costs"],
            rewards=[ProgressionNodeReward.from_data(x) for x in data["rewards"]],
            prerequisites=[ProgressionNodeRequirement.from_data(x) for x in data["prerequisites"]],
            any_prerequisites=[ProgressionNodeRequirement.from_data(x) for x in data["any_prerequisites"]],
            exclusive_group=data["exclusive_group"],
            tags=data["tags"],
        )


@dataclass(frozen=True, slots=True)
class ProgressionGraphDefinition:
    graph_id: str
    display_name: str
    nodes: tuple[ProgressionNodeDefinition, ...]
    tags: tuple[str, ...] = ()
    editor_view: str = "list"
    node_positions: dict[str, tuple[float, float]] = None

    def __init__(self, graph_id, display_name=None, *, nodes, tags=(), editor_view="list", node_positions=None):
        graph_id = _id(graph_id, "graph_id")
        nodes = tuple(nodes)
        if not nodes:
            raise ValueError("progression graph requires nodes")
        if any(not isinstance(x, ProgressionNodeDefinition) for x in nodes):
            raise TypeError("nodes must be ProgressionNodeDefinition values")
        ids = [x.node_id for x in nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("progression graph node ids must be unique")
        mapping = {x.node_id: x for x in nodes}
        for node in nodes:
            for req in node.prerequisites + node.any_prerequisites:
                if req.node_id not in mapping:
                    raise ValueError(f"node {node.node_id} references unknown prerequisite {req.node_id}")
                if req.minimum_rank > mapping[req.node_id].max_rank:
                    raise ValueError(f"node {node.node_id} prerequisite rank exceeds {req.node_id} max rank")
        # Reject direct/static prerequisite cycles. Any-prerequisite edges are
        # included conservatively because a closed cycle is never a useful
        # allocation start state.
        edges = {x.node_id: {r.node_id for r in x.prerequisites + x.any_prerequisites} for x in nodes}
        visiting, visited = set(), set()

        def visit(node_id):
            if node_id in visiting:
                raise ValueError("progression graph contains prerequisite cycle")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dep in edges[node_id]:
                visit(dep)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in ids:
            visit(node_id)

        object.__setattr__(self, "graph_id", graph_id)
        object.__setattr__(self, "display_name", str(display_name or graph_id))
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "tags", tuple(sorted({_id(x, "tag").lower() for x in tags})))
        view = str(editor_view).lower()
        if view not in {"list", "graph"}:
            raise ValueError("editor_view must be list or graph")
        positions = {}
        for key, value in dict(node_positions or {}).items():
            if key not in mapping:
                raise ValueError(f"node position references unknown node {key}")
            positions[str(key)] = (float(value[0]), float(value[1]))
        object.__setattr__(self, "editor_view", view)
        object.__setattr__(self, "node_positions", positions)

    def node(self, node_id):
        node_id = str(node_id)
        return next((x for x in self.nodes if x.node_id == node_id), None)

    def require_node(self, node_id):
        node = self.node(node_id)
        if node is None:
            raise KeyError(f"unknown progression node: {node_id}")
        return node

    def to_data(self):
        return {
            "schema": "asteria.rpg.progression_graph",
            "version": 2,
            "graph_id": self.graph_id,
            "display_name": self.display_name,
            "nodes": [x.to_data() for x in self.nodes],
            "tags": list(self.tags),
            "editor_view": self.editor_view,
            "node_positions": {k: list(v) for k, v in sorted(self.node_positions.items())},
        }

    @classmethod
    def from_data(cls, data):
        v = data.get("version")
        expected1 = {"schema", "version", "graph_id", "display_name", "nodes", "tags"}
        expected2 = expected1 | {"editor_view", "node_positions"}
        if (
            set(data) != (expected2 if v == 2 else expected1)
            or data.get("schema") != "asteria.rpg.progression_graph"
            or v not in {1, 2}
        ):
            raise ValueError("unsupported progression graph")
        return cls(
            data["graph_id"],
            data["display_name"],
            nodes=[ProgressionNodeDefinition.from_data(x) for x in data["nodes"]],
            tags=data["tags"],
            editor_view=data.get("editor_view", "list"),
            node_positions=data.get("node_positions", {}),
        )


@dataclass(frozen=True, slots=True)
class ProgressionAllocationContribution:
    stat_bonuses: dict[str, float]
    resource_bonuses: dict[str, float]
    granted_tags: tuple[str, ...]
    granted_abilities: tuple[str, ...]
    unlocked_passives: tuple[str, ...]
    granted_capabilities: tuple[str, ...]
    ability_grants: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ProgressionAllocationPreview:
    graph_id: str
    node_id: str
    old_rank: int
    new_rank: int
    allowed: bool
    costs: dict[str, float]
    reasons: tuple[str, ...]


class ProgressionAllocationRuntime:
    """Saveable point-allocation state over project-defined progression graphs."""

    SCHEMA = "asteria.rpg.progression_allocation_runtime"
    VERSION = 1

    def __init__(self, definitions=(), *, balances=None, allocations=None, hooks=None):
        self.hooks = hooks
        self.definitions = {}
        for definition in definitions:
            if not isinstance(definition, ProgressionGraphDefinition):
                raise TypeError("definitions must be ProgressionGraphDefinition values")
            if definition.graph_id in self.definitions:
                raise ValueError(f"duplicate progression graph: {definition.graph_id}")
            self.definitions[definition.graph_id] = definition
        self.balances = _nonnegative_map(balances or {}, "allocation balance")
        self.allocations = {graph_id: {} for graph_id in self.definitions}
        for graph_id, raw_nodes in dict(allocations or {}).items():
            if graph_id not in self.definitions:
                raise KeyError(f"unknown progression graph: {graph_id}")
            graph = self.definitions[graph_id]
            for node_id, raw_rank in dict(raw_nodes).items():
                node = graph.require_node(node_id)
                rank = int(raw_rank)
                if rank < 0 or rank > node.max_rank:
                    raise ValueError(f"invalid allocation rank for {graph_id}:{node_id}")
                if rank:
                    self.allocations[graph_id][node_id] = rank
        self._validate_allocations()

    def balance(self, currency_id):
        return self.balances.get(str(currency_id), 0.0)

    def grant(self, currency_id, amount):
        currency_id = _id(currency_id, "currency_id")
        amount = _number(amount, "allocation grant")
        if amount < 0:
            raise ValueError("allocation grant must be >= 0")
        self.balances[currency_id] = self.balance(currency_id) + amount
        emit_hook(
            self.hooks, "rpg.progression_allocation.currency_granted", source=currency_id, data={"amount": amount}
        )
        return self.balances[currency_id]

    def rank(self, graph_id, node_id):
        graph_id = str(graph_id)
        if graph_id not in self.definitions:
            raise KeyError(f"unknown progression graph: {graph_id}")
        self.definitions[graph_id].require_node(node_id)
        return self.allocations[graph_id].get(str(node_id), 0)

    def _requirements_met(self, graph_id, node, allocations=None):
        allocations = self.allocations if allocations is None else allocations
        ranks = allocations[graph_id]
        missing = []
        for req in node.prerequisites:
            if ranks.get(req.node_id, 0) < req.minimum_rank:
                missing.append(f"requires {req.node_id} rank {req.minimum_rank}")
        if node.any_prerequisites and not any(
            ranks.get(req.node_id, 0) >= req.minimum_rank for req in node.any_prerequisites
        ):
            choices = " or ".join(f"{x.node_id} rank {x.minimum_rank}" for x in node.any_prerequisites)
            missing.append(f"requires one of: {choices}")
        if node.exclusive_group is not None and ranks.get(node.node_id, 0) == 0:
            graph = self.definitions[graph_id]
            for other in graph.nodes:
                if (
                    other.node_id != node.node_id
                    and other.exclusive_group == node.exclusive_group
                    and ranks.get(other.node_id, 0) > 0
                ):
                    missing.append(f"exclusive with {other.node_id}")
        return tuple(missing)

    def preview_allocate(self, graph_id, node_id, count=1):
        graph_id = _id(graph_id, "graph_id")
        count = int(count)
        if count < 1:
            raise ValueError("count must be >= 1")
        graph = self.definitions[graph_id]
        node = graph.require_node(node_id)
        old_rank = self.rank(graph_id, node.node_id)
        target_rank = old_rank + count
        reasons = list(self._requirements_met(graph_id, node))
        if target_rank > node.max_rank:
            reasons.append(f"maximum rank is {node.max_rank}")
        costs = {}
        if not reasons:
            for rank in range(old_rank + 1, target_rank + 1):
                for currency_id, amount in node.cost_for_rank(rank).items():
                    costs[currency_id] = costs.get(currency_id, 0.0) + amount
            for currency_id, amount in costs.items():
                if self.balance(currency_id) < amount:
                    reasons.append(
                        f"insufficient {currency_id}: requires {amount:g}, current {self.balance(currency_id):g}"
                    )
        return ProgressionAllocationPreview(
            graph_id,
            node.node_id,
            old_rank,
            min(target_rank, node.max_rank),
            not reasons,
            costs,
            tuple(reasons),
        )

    def allocate(self, graph_id, node_id, count=1):
        preview = self.preview_allocate(graph_id, node_id, count)
        emit_hook(
            self.hooks, "rpg.progression_allocation.before_allocate", source=preview.node_id, data={"preview": preview}
        )
        if not preview.allowed:
            raise ValueError("allocation rejected: " + "; ".join(preview.reasons))
        for currency_id, amount in preview.costs.items():
            self.balances[currency_id] = self.balance(currency_id) - amount
        self.allocations[preview.graph_id][preview.node_id] = preview.new_rank
        emit_hook(
            self.hooks, "rpg.progression_allocation.after_allocate", source=preview.node_id, data={"preview": preview}
        )
        return preview

    def _validate_allocations(self, allocations=None):
        allocations = self.allocations if allocations is None else allocations
        for graph_id, graph in self.definitions.items():
            ranks = allocations.get(graph_id, {})
            for node in graph.nodes:
                if ranks.get(node.node_id, 0) <= 0:
                    continue
                reasons = self._requirements_met(graph_id, node, allocations=allocations)
                if reasons:
                    raise ValueError(f"invalid allocated node {graph_id}:{node.node_id}: " + "; ".join(reasons))
        return True

    def refund(self, graph_id, node_id, count=1, *, refund_ratio=1.0):
        graph_id = _id(graph_id, "graph_id")
        count = int(count)
        ratio = _number(refund_ratio, "refund_ratio")
        if count < 1:
            raise ValueError("count must be >= 1")
        if ratio < 0 or ratio > 1:
            raise ValueError("refund_ratio must be between 0 and 1")
        graph = self.definitions[graph_id]
        node = graph.require_node(node_id)
        old_rank = self.rank(graph_id, node.node_id)
        if old_rank < count:
            raise ValueError("cannot refund more ranks than allocated")
        new_rank = old_rank - count
        simulated = {gid: dict(values) for gid, values in self.allocations.items()}
        if new_rank:
            simulated[graph_id][node.node_id] = new_rank
        else:
            simulated[graph_id].pop(node.node_id, None)
        try:
            self._validate_allocations(simulated)
        except ValueError as exc:
            raise ValueError(f"refund rejected: {exc}") from exc
        refund = {}
        for rank in range(new_rank + 1, old_rank + 1):
            for currency_id, amount in node.cost_for_rank(rank).items():
                refund[currency_id] = refund.get(currency_id, 0.0) + amount * ratio
        emit_hook(
            self.hooks,
            "rpg.progression_allocation.before_refund",
            source=node.node_id,
            data={"old_rank": old_rank, "new_rank": new_rank, "refund": dict(refund)},
        )
        self.allocations = simulated
        for currency_id, amount in refund.items():
            self.balances[currency_id] = self.balance(currency_id) + amount
        emit_hook(
            self.hooks,
            "rpg.progression_allocation.after_refund",
            source=node.node_id,
            data={"old_rank": old_rank, "new_rank": new_rank, "refund": dict(refund)},
        )
        return dict(refund)

    def contribution(self, graph_ids=None):
        selected = set(self.definitions) if graph_ids is None else {str(x) for x in graph_ids}
        unknown = selected - set(self.definitions)
        if unknown:
            raise KeyError("unknown progression graph(s): " + ", ".join(sorted(unknown)))
        stats, resources, tags, abilities, passives, capabilities = {}, {}, set(), [], [], set()
        ability_grants = []
        for graph_id in sorted(selected):
            graph = self.definitions[graph_id]
            ranks = self.allocations[graph_id]
            for node in graph.nodes:
                active_rank = ranks.get(node.node_id, 0)
                for rank in range(1, active_rank + 1):
                    reward = node.reward_for_rank(rank)
                    for key, value in reward.stat_bonuses.items():
                        stats[key] = stats.get(key, 0.0) + value
                    for key, value in reward.resource_bonuses.items():
                        resources[key] = resources.get(key, 0.0) + value
                    tags.update(reward.granted_tags)
                    capabilities.update(reward.granted_capabilities)
                    for ability_id in reward.granted_abilities:
                        if ability_id not in abilities:
                            abilities.append(ability_id)
                        ability_grants.append((ability_id, f"{graph_id}:{node.node_id}:rank{rank}"))
                    for passive_id in reward.unlocked_passives:
                        if passive_id not in passives:
                            passives.append(passive_id)
        return ProgressionAllocationContribution(
            stats,
            resources,
            tuple(sorted(tags)),
            tuple(abilities),
            tuple(passives),
            tuple(sorted(capabilities)),
            tuple(ability_grants),
        )

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "balances": {k: self.balances[k] for k in sorted(self.balances)},
            "allocations": {
                graph_id: {k: self.allocations[graph_id][k] for k in sorted(self.allocations[graph_id])}
                for graph_id in sorted(self.allocations)
            },
        }

    @classmethod
    def from_data(cls, data, definitions, *, hooks=None):
        expected = {"schema", "version", "balances", "allocations"}
        if set(data) != expected or data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported progression allocation runtime")
        return cls(definitions, balances=data["balances"], allocations=data["allocations"], hooks=hooks)

    def validate(self):
        self._validate_allocations()
        return True

    def replace_from(self, other):
        if not isinstance(other, ProgressionAllocationRuntime):
            raise TypeError("other must be ProgressionAllocationRuntime")
        if set(self.definitions) != set(other.definitions):
            raise ValueError("progression graph definitions do not match")
        self.balances = dict(other.balances)
        self.allocations = {k: dict(v) for k, v in other.allocations.items()}
        return self
