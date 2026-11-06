"""Behavior tree editor API (RPG-09): create trees, add / edit / remove / move nodes — each one
undo step.

The GUI (``behavior_tree_widget``) and scripts share these calls; records are the
canonical ``BehaviorTree`` in ``project.rpg_database.behavior_trees``.
Nodes are addressed by their path from the root (tuple of child indices).
"""

from __future__ import annotations

from dataclasses import replace

from asteria.rpg.behavior_tree import (
    ACTIONS,
    COMPOSITES,
    CONDITIONS,
    DECORATORS,
    BehaviorNode,
    BehaviorTree,
)

from .record_vocabulary import resource_order, vocabulary_for, words
from .rpg_actor_class_authoring import _DefinitionCommand

# Editable parameters per node kind (name, default) — the form shows exactly these.
PARAMS = {
    "sequence": (),
    "selector": (),
    "parallel": (("success_count", 1),),
    "inverter": (),
    "succeeder": (),
    "repeater": (("count", 0),),
    "cooldown": (("seconds", 1.0),),
    "player_within": (("radius", 64.0),),
    "player_beyond": (("radius", 64.0),),
    "switch": (("name", ""),),
    "chance": (("probability", 0.5),),
    "home_within": (("radius", 4.0),),
    "chase": (("arrive", 4.0), ("lose_radius", 160.0), ("speed", 40.0)),
    "flee": (("radius", 96.0), ("speed", 40.0)),
    "move_to": (("x", 0.0), ("y", 0.0), ("arrive", 2.0), ("speed", 40.0)),
    "return_home": (("arrive", 2.0), ("speed", 40.0)),
    "patrol": (("points", "0,0; 32,0"), ("arrive", 2.0), ("speed", 40.0), ("once", False)),
    "wander": (("radius", 48.0), ("arrive", 2.0), ("speed", 40.0)),
    "wait": (("seconds", 1.0),),
    "face_player": (),
    "set_switch": (("name", ""), ("value", True)),
    "start_encounter": (("encounter_id", ""),),
    # real-time combat (ASTERIA_SPEC §20)
    "hp_below": (("fraction", 0.5), ("resource", "hp")),
    "hp_above": (("fraction", 0.5), ("resource", "hp")),
    "ability_ready": (("ability", ""),),
    "has_state": (("state", ""),),
    "acting": (),
    "use_ability": (("ability", ""), ("wait", False)),
    "keep_distance": (("min", 48.0), ("max", 96.0), ("speed", 40.0)),
    "strafe": (("direction", 1), ("seconds", 1.0), ("speed", 40.0)),
    "side_patrol": (("seconds", 0.0),),
    "jump": (),
    "summon": (("prefab", ""), ("count", 1), ("radius", 32.0)),
    "apply_state": (("state", ""), ("to", "self")),
}

# Left out of the data these mean what no number says: a chase that never gives up, a parallel
# that needs all of its nodes. The field reads 0 for that and 0 is saved as leaving it out. A
# patrol going round and round is left out too, as its data always had it.
ABSENT_AT_ZERO = frozenset(
    {("chase", "lose_radius"), ("parallel", "success_count"), ("patrol", "once")}
)
KIND_GROUPS = (
    ("Run several nodes", COMPOSITES),
    ("Change one node", DECORATORS),
    ("Conditions", CONDITIONS),
    ("Actions", ACTIONS),
)
# Settings that name something in the project, and the vocabulary that lists them.
REFERENCE_SOURCES = {
    "ability": "abilities",
    "encounter_id": "encounters",
    "prefab": "prefabs",
    "resource": "resources",
    "state": "states",
}


class BehaviorTreeAuthoringError(ValueError):
    pass


def parse_points(text):
    """A patrol's places: ``"x,y; x,y"`` as ``[(x, y), ...]`` (a ValueError when it isn't)."""
    points = []
    for chunk in str(text or "").split(";"):
        if chunk.strip():
            x, y = chunk.split(",")
            points.append((float(x), float(y)))
    return points


def default_node(kind):
    params = dict(PARAMS.get(kind, ()))
    if kind in COMPOSITES:
        return BehaviorNode(kind, params, (BehaviorNode("wait", {"seconds": 1.0}),))
    if kind in DECORATORS:
        return BehaviorNode(kind, params, (BehaviorNode("wait", {"seconds": 1.0}),))
    return BehaviorNode(kind, params)


def _rebuild(node, path, change):
    """Return ``node`` with the node at ``path`` replaced by ``change(old)`` (None removes it)."""
    if not path:
        return change(node)
    children = list(node.children)
    index = path[0]
    new_child = _rebuild(children[index], path[1:], change)
    if new_child is None:
        children.pop(index)
    else:
        children[index] = new_child
    return replace(node, children=tuple(children))


class BehaviorTreeAuthoring:
    def __init__(self, document):
        self.document = document

    @property
    def trees(self):
        if self.document.project is None:
            raise BehaviorTreeAuthoringError("project required")
        return self.document.project.rpg_database.behavior_trees

    def ids(self):
        return tuple(sorted(self.trees))

    def get(self, tree_id):
        tree = self.trees.get(str(tree_id))
        if tree is None:
            raise BehaviorTreeAuthoringError(f"unknown behavior tree {tree_id}")
        return tree

    def _store(self, tree, old, label):
        try:
            tree = BehaviorTree(
                tree.tree_id, BehaviorNode.from_data(tree.root.to_data()), tree.display_name
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise BehaviorTreeAuthoringError(str(exc)) from exc
        self.document.execute(_DefinitionCommand(self.trees, tree.tree_id, tree, old, label))
        return tree

    def create(self, tree_id, root_kind="selector"):
        tree_id = str(tree_id).strip()
        if not tree_id or tree_id in self.trees:
            raise BehaviorTreeAuthoringError(f"tree id {tree_id!r} is empty or taken")
        return self._store(
            BehaviorTree(tree_id, default_node(root_kind), tree_id),
            None,
            f"Add Behavior Tree {words(tree_id)}",
        )

    def delete(self, tree_id):
        old = self.get(tree_id)
        self.document.execute(
            _DefinitionCommand(
                self.trees, old.tree_id, None, old, f"Delete Behavior Tree {words(old.tree_id)}"
            )
        )

    def fresh_node(self, kind):
        """A new ``kind`` node that works as it is: what it refers to is the project's first."""
        node = default_node(kind)
        params = dict(node.params)
        vocabulary = vocabulary_for(self.document)
        for name, value in node.params.items():
            if (kind, name) in ABSENT_AT_ZERO and not value:
                del params[name]  # left out, as Apply leaves it
            elif name == "name":
                params[name] = self._first_switch()
            elif name in REFERENCE_SOURCES:
                values = [c.value for c in vocabulary.choices(REFERENCE_SOURCES[name])]
                if name == "resource":
                    values.sort(key=resource_order)
                if values and value not in values:
                    params[name] = values[0]
        return replace(node, params=params)

    def _first_switch(self):
        from .event_flow_authoring import EventFlowAuthoring

        used = EventFlowAuthoring(self.document).names_used("switch")
        return used[0] if used else "new_switch"

    def _edit(self, tree_id, path, change, label):
        old = self.get(tree_id)
        try:
            root = _rebuild(old.root, tuple(path), change)
        except (IndexError, TypeError, ValueError) as exc:
            raise BehaviorTreeAuthoringError(str(exc)) from exc
        if root is None:
            raise BehaviorTreeAuthoringError("the root node cannot be removed")
        return self._store(replace(old, root=root), old, label)

    def add_child(self, tree_id, path, kind):
        if kind not in PARAMS:
            raise BehaviorTreeAuthoringError(f"unknown node kind {kind}")

        def change(node):
            if node.kind not in COMPOSITES + DECORATORS:
                raise BehaviorTreeAuthoringError("This node cannot hold other nodes")
            if node.kind in DECORATORS:
                return replace(
                    node, children=(self.fresh_node(kind),)
                )  # a decorator wraps exactly one child
            return replace(node, children=(*node.children, self.fresh_node(kind)))

        return self._edit(tree_id, path, change, "Add node")

    def set_params(self, tree_id, path, **params):
        def change(node):
            known = dict(PARAMS.get(node.kind, ()))
            unknown = set(params) - set(known)
            if unknown:
                raise BehaviorTreeAuthoringError(
                    f"{node.kind} has no parameters {sorted(unknown)}"
                )
            values = dict(node.params)
            for key, value in params.items():
                default = known[key]
                if (node.kind, key) in ABSENT_AT_ZERO and not value:
                    values.pop(key, None)
                    continue
                values[key] = type(default)(value) if not isinstance(default, str) else str(value)
            return replace(node, params=values)

        return self._edit(tree_id, path, change, "Edit node")

    def set_kind(self, tree_id, path, kind):
        def change(node):
            fresh = self.fresh_node(kind)
            if kind in COMPOSITES and node.children:
                return replace(fresh, children=node.children)
            if kind in DECORATORS and node.children:
                return replace(fresh, children=node.children[:1])
            return fresh

        return self._edit(tree_id, path, change, "Change node kind")

    def remove(self, tree_id, path):
        return self._edit(tree_id, path, lambda _node: None, "Remove node")

    def move(self, tree_id, path, delta):
        path = tuple(path)
        if not path:
            raise BehaviorTreeAuthoringError("the root node cannot move")
        parent_path, index = path[:-1], path[-1]

        def change(parent):
            children = list(parent.children)
            target = index + int(delta)
            if not 0 <= target < len(children):
                raise BehaviorTreeAuthoringError("cannot move further")
            children[index], children[target] = children[target], children[index]
            return replace(parent, children=tuple(children))

        return self._edit(tree_id, parent_path, change, "Move node")
