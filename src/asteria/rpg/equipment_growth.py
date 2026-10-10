from __future__ import annotations

from dataclasses import dataclass

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import GameplayTrigger, StatModifier


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _tags(values):
    return tuple(sorted({_id(x, "tag").lower() for x in values}))


def _nonnegative_map(values, label):
    result = {}
    for key, value in dict(values or {}).items():
        key = _id(key, label)
        value = float(value)
        if value < 0:
            raise ValueError(f"{label} values must be >= 0")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class EquipmentGrowthReward:
    modifiers: tuple[StatModifier, ...] = ()
    granted_abilities: tuple[str, ...] = ()
    granted_tags: tuple[str, ...] = ()
    granted_capabilities: tuple[str, ...] = ()
    granted_triggers: tuple[GameplayTrigger, ...] = ()
    unlocked_sockets: tuple[str, ...] = ()
    evolution_equipment_id: str | None = None

    def __init__(
        self,
        *,
        modifiers=(),
        granted_abilities=(),
        granted_tags=(),
        granted_capabilities=(),
        granted_triggers=(),
        unlocked_sockets=(),
        evolution_equipment_id=None,
    ):
        modifiers = tuple(modifiers)
        triggers = tuple(granted_triggers)
        if any(not isinstance(x, StatModifier) for x in modifiers):
            raise TypeError("modifiers must be StatModifier values")
        if any(not isinstance(x, GameplayTrigger) for x in triggers):
            raise TypeError("granted_triggers must be GameplayTrigger values")
        object.__setattr__(self, "modifiers", modifiers)
        object.__setattr__(
            self,
            "granted_abilities",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in granted_abilities)),
        )
        object.__setattr__(self, "granted_tags", _tags(granted_tags))
        object.__setattr__(self, "granted_capabilities", _tags(granted_capabilities))
        object.__setattr__(self, "granted_triggers", triggers)
        object.__setattr__(
            self,
            "unlocked_sockets",
            tuple(dict.fromkeys(_id(x, "socket_id") for x in unlocked_sockets)),
        )
        object.__setattr__(
            self,
            "evolution_equipment_id",
            None if evolution_equipment_id is None else _id(evolution_equipment_id, "evolution_equipment_id"),
        )

    def to_data(self):
        return {
            "modifiers": [x.to_data() for x in self.modifiers],
            "granted_abilities": list(self.granted_abilities),
            "granted_tags": list(self.granted_tags),
            "granted_capabilities": list(self.granted_capabilities),
            "granted_triggers": [x.to_data() for x in self.granted_triggers],
            "unlocked_sockets": list(self.unlocked_sockets),
            "evolution_equipment_id": self.evolution_equipment_id,
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "modifiers",
            "granted_abilities",
            "granted_tags",
            "granted_capabilities",
            "granted_triggers",
            "unlocked_sockets",
            "evolution_equipment_id",
        }
        if set(data) != expected:
            raise ValueError("invalid equipment growth reward")
        return cls(
            modifiers=[StatModifier.from_data(x) for x in data["modifiers"]],
            granted_abilities=data["granted_abilities"],
            granted_tags=data["granted_tags"],
            granted_capabilities=data["granted_capabilities"],
            granted_triggers=[GameplayTrigger.from_data(x) for x in data["granted_triggers"]],
            unlocked_sockets=data["unlocked_sockets"],
            evolution_equipment_id=data["evolution_equipment_id"],
        )


@dataclass(frozen=True, slots=True)
class EquipmentGrowthNodeDefinition:
    node_id: str
    display_name: str
    max_rank: int
    rank_requirements: tuple[dict[str, float], ...]
    rewards: tuple[EquipmentGrowthReward, ...]
    prerequisites: tuple[tuple[str, int], ...] = ()
    exclusive_group: str | None = None
    auto_unlock: bool = True
    tags: tuple[str, ...] = ()

    def __init__(
        self,
        node_id,
        display_name=None,
        *,
        max_rank=1,
        rank_requirements=None,
        rewards=None,
        prerequisites=(),
        exclusive_group=None,
        auto_unlock=True,
        tags=(),
    ):
        node_id = _id(node_id, "node_id")
        max_rank = int(max_rank)
        if max_rank < 1:
            raise ValueError("max_rank must be >= 1")
        if rank_requirements is None:
            rank_requirements = [{} for _ in range(max_rank)]
        elif isinstance(rank_requirements, dict):
            rank_requirements = [rank_requirements for _ in range(max_rank)]
        else:
            rank_requirements = list(rank_requirements)
        if len(rank_requirements) != max_rank:
            raise ValueError("rank_requirements must contain one entry per rank")
        requirements = tuple(_nonnegative_map(x, "growth counter") for x in rank_requirements)
        if rewards is None:
            rewards = [EquipmentGrowthReward() for _ in range(max_rank)]
        elif isinstance(rewards, EquipmentGrowthReward):
            rewards = [rewards for _ in range(max_rank)]
        else:
            rewards = list(rewards)
        if len(rewards) != max_rank:
            raise ValueError("rewards must contain one entry per rank")
        rewards = tuple(
            x if isinstance(x, EquipmentGrowthReward) else EquipmentGrowthReward.from_data(x) for x in rewards
        )
        parsed_prereqs = []
        for entry in prerequisites:
            if isinstance(entry, str):
                parsed_prereqs.append((_id(entry, "prerequisite node"), 1))
            else:
                node, rank = entry
                rank = int(rank)
                if rank < 1:
                    raise ValueError("prerequisite rank must be >= 1")
                parsed_prereqs.append((_id(node, "prerequisite node"), rank))
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "display_name", str(display_name or node_id))
        object.__setattr__(self, "max_rank", max_rank)
        object.__setattr__(self, "rank_requirements", requirements)
        object.__setattr__(self, "rewards", rewards)
        object.__setattr__(self, "prerequisites", tuple(parsed_prereqs))
        object.__setattr__(
            self,
            "exclusive_group",
            None if exclusive_group is None else _id(exclusive_group, "exclusive_group"),
        )
        object.__setattr__(self, "auto_unlock", bool(auto_unlock))
        object.__setattr__(self, "tags", _tags(tags))

    def requirement_for_rank(self, rank):
        rank = int(rank)
        if rank < 1 or rank > self.max_rank:
            raise ValueError("rank outside node range")
        return dict(self.rank_requirements[rank - 1])

    def reward_for_rank(self, rank):
        rank = int(rank)
        if rank < 1 or rank > self.max_rank:
            raise ValueError("rank outside node range")
        return self.rewards[rank - 1]

    def to_data(self):
        return {
            "schema": "asteria.rpg.equipment_growth_node",
            "version": 1,
            "node_id": self.node_id,
            "display_name": self.display_name,
            "max_rank": self.max_rank,
            "rank_requirements": [dict(sorted(x.items())) for x in self.rank_requirements],
            "rewards": [x.to_data() for x in self.rewards],
            "prerequisites": [[node, rank] for node, rank in self.prerequisites],
            "exclusive_group": self.exclusive_group,
            "auto_unlock": self.auto_unlock,
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
            "rank_requirements",
            "rewards",
            "prerequisites",
            "exclusive_group",
            "auto_unlock",
            "tags",
        }
        if (
            set(data) != expected
            or data.get("schema") != "asteria.rpg.equipment_growth_node"
            or data.get("version") != 1
        ):
            raise ValueError("unsupported equipment growth node")
        return cls(
            data["node_id"],
            data["display_name"],
            max_rank=data["max_rank"],
            rank_requirements=data["rank_requirements"],
            rewards=[EquipmentGrowthReward.from_data(x) for x in data["rewards"]],
            prerequisites=[tuple(x) for x in data["prerequisites"]],
            exclusive_group=data["exclusive_group"],
            auto_unlock=data["auto_unlock"],
            tags=data["tags"],
        )


@dataclass(frozen=True, slots=True)
class EquipmentGrowthDefinition:
    growth_id: str
    display_name: str
    nodes: tuple[EquipmentGrowthNodeDefinition, ...]
    tags: tuple[str, ...] = ()

    def __init__(self, growth_id, display_name=None, *, nodes, tags=()):
        growth_id = _id(growth_id, "growth_id")
        nodes = tuple(nodes)
        if not nodes:
            raise ValueError("equipment growth definition requires nodes")
        if any(not isinstance(x, EquipmentGrowthNodeDefinition) for x in nodes):
            raise TypeError("nodes must be EquipmentGrowthNodeDefinition values")
        mapping = {x.node_id: x for x in nodes}
        if len(mapping) != len(nodes):
            raise ValueError("equipment growth node ids must be unique")
        for node in nodes:
            for dep, rank in node.prerequisites:
                if dep not in mapping:
                    raise ValueError(f"node {node.node_id} references unknown prerequisite {dep}")
                if rank > mapping[dep].max_rank:
                    raise ValueError(f"node {node.node_id} prerequisite rank exceeds {dep} max rank")
            socket_ids = set()
            for reward in node.rewards:
                overlap = socket_ids.intersection(reward.unlocked_sockets)
                if overlap:
                    raise ValueError(f"node {node.node_id} duplicates socket unlocks")
                socket_ids.update(reward.unlocked_sockets)
        # Static cycle check.
        edges = {x.node_id: {dep for dep, _ in x.prerequisites} for x in nodes}
        visiting, visited = set(), set()

        def visit(node_id):
            if node_id in visiting:
                raise ValueError("equipment growth graph contains prerequisite cycle")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dep in edges[node_id]:
                visit(dep)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in mapping:
            visit(node_id)
        object.__setattr__(self, "growth_id", growth_id)
        object.__setattr__(self, "display_name", str(display_name or growth_id))
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "tags", _tags(tags))

    def node(self, node_id):
        node_id = str(node_id)
        return next((x for x in self.nodes if x.node_id == node_id), None)

    def require_node(self, node_id):
        node = self.node(node_id)
        if node is None:
            raise KeyError(f"unknown equipment growth node: {node_id}")
        return node

    def to_data(self):
        return {
            "schema": "asteria.rpg.equipment_growth",
            "version": 1,
            "growth_id": self.growth_id,
            "display_name": self.display_name,
            "nodes": [x.to_data() for x in self.nodes],
            "tags": list(self.tags),
        }

    @classmethod
    def from_data(cls, data):
        expected = {"schema", "version", "growth_id", "display_name", "nodes", "tags"}
        if set(data) != expected or data.get("schema") != "asteria.rpg.equipment_growth" or data.get("version") != 1:
            raise ValueError("unsupported equipment growth definition")
        return cls(
            data["growth_id"],
            data["display_name"],
            nodes=[EquipmentGrowthNodeDefinition.from_data(x) for x in data["nodes"]],
            tags=data["tags"],
        )


@dataclass(frozen=True, slots=True)
class EquipmentGrowthContribution:
    modifiers: tuple[StatModifier, ...]
    granted_abilities: tuple[str, ...]
    granted_tags: tuple[str, ...]
    granted_capabilities: tuple[str, ...]
    granted_triggers: tuple[GameplayTrigger, ...]
    unlocked_sockets: tuple[str, ...]
    evolution_equipment_id: str | None


@dataclass(frozen=True, slots=True)
class EquipmentGrowthUnlockPreview:
    node_id: str
    old_rank: int
    new_rank: int
    allowed: bool
    reasons: tuple[str, ...]
    requirements: dict[str, float]


class EquipmentGrowthRuntime:
    """Per-equipment-instance growth state.

    Counters are arbitrary project vocabulary (xp, kills, bond, material_spent,
    boss_flags represented numerically, etc.).  Nodes may auto-unlock when their
    requirements are met or be selected manually for branching/evolution paths.
    """

    SCHEMA = "asteria.rpg.equipment_growth_runtime"
    VERSION = 1

    def __init__(self, definition, *, counters=None, ranks=None, hooks=None, source=None):
        if not isinstance(definition, EquipmentGrowthDefinition):
            raise TypeError("definition must be EquipmentGrowthDefinition")
        self.definition = definition
        self.counters = _nonnegative_map(counters or {}, "growth counter")
        self.ranks = {str(k): int(v) for k, v in dict(ranks or {}).items()}
        self.hooks = hooks
        self.source = source
        self._validate_state()
        self._auto_unlock()

    def _validate_state(self):
        for node_id, rank in self.ranks.items():
            node = self.definition.node(node_id)
            if node is None:
                raise ValueError(f"unknown growth node state: {node_id}")
            if rank < 0 or rank > node.max_rank:
                raise ValueError(f"invalid growth rank for {node_id}")
        groups = {}
        for node in self.definition.nodes:
            if self.rank(node.node_id) <= 0 or node.exclusive_group is None:
                continue
            previous = groups.get(node.exclusive_group)
            if previous is not None and previous != node.node_id:
                raise ValueError(f"exclusive growth group has multiple active nodes: {node.exclusive_group}")
            groups[node.exclusive_group] = node.node_id

    def rank(self, node_id):
        return self.ranks.get(str(node_id), 0)

    def counter(self, counter_id):
        return self.counters.get(str(counter_id), 0.0)

    def add_progress(self, counter_id, amount=1):
        counter_id = _id(counter_id, "growth counter")
        amount = float(amount)
        if amount < 0:
            raise ValueError("growth progress amount must be >= 0")
        old = self.counter(counter_id)
        self.counters[counter_id] = old + amount
        emit_hook(
            self.hooks,
            "rpg.equipment_growth.progressed",
            source=self.source or self.definition.growth_id,
            data={
                "growth_id": self.definition.growth_id,
                "counter_id": counter_id,
                "old": old,
                "new": self.counters[counter_id],
            },
        )
        unlocked = self._auto_unlock()
        return tuple(unlocked)

    def set_progress(self, counter_id, value):
        counter_id = _id(counter_id, "growth counter")
        value = float(value)
        if value < 0:
            raise ValueError("growth progress value must be >= 0")
        self.counters[counter_id] = value
        return tuple(self._auto_unlock())

    def preview_unlock(self, node_id):
        node = self.definition.require_node(node_id)
        old_rank = self.rank(node.node_id)
        new_rank = old_rank + 1
        reasons = []
        requirements = {}
        if new_rank > node.max_rank:
            reasons.append("growth node is already at max rank")
            return EquipmentGrowthUnlockPreview(node.node_id, old_rank, old_rank, False, tuple(reasons), requirements)
        requirements = node.requirement_for_rank(new_rank)
        for counter_id, needed in sorted(requirements.items()):
            current = self.counter(counter_id)
            if current < needed:
                reasons.append(f"requires {counter_id} >= {needed:g}, current {current:g}")
        for dep, rank in node.prerequisites:
            if self.rank(dep) < rank:
                reasons.append(f"requires {dep} rank {rank}")
        if node.exclusive_group:
            for other in self.definition.nodes:
                if (
                    other.node_id != node.node_id
                    and other.exclusive_group == node.exclusive_group
                    and self.rank(other.node_id) > 0
                ):
                    reasons.append(f"exclusive with {other.node_id}")
                    break
        return EquipmentGrowthUnlockPreview(
            node.node_id,
            old_rank,
            new_rank,
            not reasons,
            tuple(reasons),
            requirements,
        )

    def unlock(self, node_id, *, automatic=False):
        node = self.definition.require_node(node_id)
        preview = self.preview_unlock(node.node_id)
        if not preview.allowed:
            raise ValueError("; ".join(preview.reasons))
        if automatic and not node.auto_unlock:
            return None
        self.ranks[node.node_id] = preview.new_rank
        reward = node.reward_for_rank(preview.new_rank)
        emit_hook(
            self.hooks,
            "rpg.equipment_growth.node_unlocked",
            source=self.source or self.definition.growth_id,
            data={
                "growth_id": self.definition.growth_id,
                "node_id": node.node_id,
                "rank": preview.new_rank,
                "automatic": bool(automatic),
                "evolution_equipment_id": reward.evolution_equipment_id,
            },
        )
        return reward

    def _auto_unlock(self):
        unlocked = []
        changed = True
        while changed:
            changed = False
            for node in self.definition.nodes:
                if not node.auto_unlock:
                    continue
                while self.rank(node.node_id) < node.max_rank:
                    preview = self.preview_unlock(node.node_id)
                    if not preview.allowed:
                        break
                    self.unlock(node.node_id, automatic=True)
                    unlocked.append((node.node_id, self.rank(node.node_id)))
                    changed = True
        return unlocked

    def contribution(self):
        modifiers = []
        abilities = []
        tags = set()
        capabilities = set()
        triggers = []
        sockets = []
        evolution = None
        for node in self.definition.nodes:
            for rank in range(1, self.rank(node.node_id) + 1):
                reward = node.reward_for_rank(rank)
                modifiers.extend(reward.modifiers)
                abilities.extend(reward.granted_abilities)
                tags.update(reward.granted_tags)
                capabilities.update(reward.granted_capabilities)
                triggers.extend(reward.granted_triggers)
                sockets.extend(reward.unlocked_sockets)
                if reward.evolution_equipment_id is not None:
                    evolution = reward.evolution_equipment_id
        return EquipmentGrowthContribution(
            tuple(modifiers),
            tuple(dict.fromkeys(abilities)),
            tuple(sorted(tags)),
            tuple(sorted(capabilities)),
            tuple(triggers),
            tuple(dict.fromkeys(sockets)),
            evolution,
        )

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "growth_id": self.definition.growth_id,
            "counters": dict(sorted(self.counters.items())),
            "ranks": {k: self.ranks[k] for k in sorted(self.ranks) if self.ranks[k] > 0},
        }

    @classmethod
    def from_data(cls, data, definitions, *, hooks=None, source=None):
        expected = {"schema", "version", "growth_id", "counters", "ranks"}
        if set(data) != expected or data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported equipment growth runtime")
        definitions = dict(definitions)
        growth_id = data["growth_id"]
        if growth_id not in definitions:
            raise KeyError(f"unknown equipment growth definition: {growth_id}")
        return cls(
            definitions[growth_id],
            counters=data["counters"],
            ranks=data["ranks"],
            hooks=hooks,
            source=source,
        )
