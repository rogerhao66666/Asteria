"""Behavior trees for field AI (RPG-09, ASTERIA_SPEC §28 "behavior trees where justified").

A ``BehaviorTree`` record (RPG database) is a node tree:

composites   ``sequence`` (all children succeed in order; resumes where it was), ``selector`` (first
             child that does not fail; re-checked every tick so a higher-priority branch interrupts
             a running lower one), ``parallel`` (all children each tick; ``success_count`` successes needed)
decorators   ``inverter``, ``succeeder``, ``repeater`` (``count``, 0 = forever), ``cooldown`` (``seconds``)
conditions   ``player_within`` (``radius``), ``player_beyond`` (``radius``), ``switch`` (``name``),
             ``chance`` (``probability``), ``home_within`` (``radius``),
             real-time combat (ASTERIA_SPEC §20): ``hp_below`` / ``hp_above`` (``fraction`` of ``resource``; boss
             phases), ``ability_ready`` (``ability``: off cooldown and affordable), ``has_state`` (``state``),
             ``acting`` (an action timeline is running on it)
actions      ``chase`` (until within ``arrive``; fails beyond ``lose_radius``), ``flee`` (until beyond
             ``radius``), ``move_to`` (``x``, ``y``), ``return_home``, ``patrol`` (``points`` "x,y; x,y"),
             ``wander`` (``radius``),
             ``wait`` (``seconds``), ``face_player``, ``set_switch`` (``name``, ``value``),
             ``start_encounter`` (``encounter_id``),
             real-time combat: ``use_ability`` (``ability``, aimed at the player; ``wait`` until its action ends),
             ``keep_distance`` (``min``, ``max``), ``strafe`` (circle the player: ``direction`` 1 / -1,
             ``seconds``), ``side_patrol`` (side view: walk, turn at walls and ledges; ``seconds`` 0 = forever),
             ``jump`` (side view, when grounded), ``summon`` (``prefab``, ``count``, ``radius``),
             ``apply_state`` (``state`` on ``to`` self / player)

Ticks return ``success``, ``failure`` or ``running``; running nodes resume next tick.
The runtime (``asteria.runtime.behavior_tree``) owns per-entity memory and moves the
entity through its ``CharacterController2D`` intent (or directly when it has none).
"""

from __future__ import annotations

from dataclasses import dataclass, field

COMPOSITES = ("sequence", "selector", "parallel")
DECORATORS = ("inverter", "succeeder", "repeater", "cooldown")
CONDITIONS = (
    "player_within",
    "player_beyond",
    "switch",
    "chance",
    "home_within",
    "hp_below",
    "hp_above",
    "ability_ready",
    "has_state",
    "acting",
)
ACTIONS = (
    "chase",
    "flee",
    "move_to",
    "return_home",
    "patrol",
    "wander",
    "wait",
    "face_player",
    "set_switch",
    "start_encounter",
    "use_ability",
    "keep_distance",
    "strafe",
    "side_patrol",
    "jump",
    "summon",
    "apply_state",
)
NODE_KINDS = COMPOSITES + DECORATORS + CONDITIONS + ACTIONS


@dataclass(frozen=True, slots=True)
class BehaviorNode:
    kind: str
    params: dict = field(default_factory=dict)
    children: tuple = ()
    name: str = ""

    def __post_init__(self):
        if self.kind not in NODE_KINDS:
            raise ValueError(f"unknown behavior node kind {self.kind}")
        children = tuple(c if isinstance(c, BehaviorNode) else BehaviorNode.from_data(c) for c in self.children)
        if self.kind in COMPOSITES and not children:
            raise ValueError(f"{self.kind} needs at least one child")
        if self.kind in DECORATORS and len(children) != 1:
            raise ValueError(f"{self.kind} needs exactly one child")
        if self.kind not in COMPOSITES + DECORATORS and children:
            raise ValueError(f"{self.kind} is a leaf and takes no children")
        object.__setattr__(self, "children", children)
        object.__setattr__(self, "params", dict(self.params or {}))

    def walk(self, path=()):
        yield path, self
        for index, child in enumerate(self.children):
            yield from child.walk((*path, index))

    def to_data(self):
        data = {"kind": self.kind, "params": dict(self.params)}
        if self.name:
            data["name"] = self.name
        if self.children:
            data["children"] = [c.to_data() for c in self.children]
        return data

    @classmethod
    def from_data(cls, data):
        return cls(
            str(data["kind"]), dict(data.get("params", {})), tuple(data.get("children", ())), str(data.get("name", ""))
        )


@dataclass(frozen=True, slots=True)
class BehaviorTree:
    tree_id: str
    root: BehaviorNode
    display_name: str = ""

    def __post_init__(self):
        if not str(self.tree_id).strip():
            raise ValueError("tree_id is required")
        root = self.root if isinstance(self.root, BehaviorNode) else BehaviorNode.from_data(self.root)
        object.__setattr__(self, "root", root)

    def node(self, path):
        node = self.root
        for index in path:
            node = node.children[index]
        return node

    def encounter_ids(self):
        return {n.params.get("encounter_id") for _, n in self.root.walk() if n.kind == "start_encounter"} - {None}

    def to_data(self):
        return {
            "schema": "asteria.rpg.behavior_tree",
            "version": 1,
            "tree_id": self.tree_id,
            "display_name": self.display_name,
            "root": self.root.to_data(),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.behavior_tree" or data.get("version") != 1:
            raise ValueError("unsupported behavior tree")
        return cls(data["tree_id"], BehaviorNode.from_data(data["root"]), data.get("display_name", ""))
