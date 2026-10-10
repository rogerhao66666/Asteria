"""Headless Presentation Editor authoring model.

Edits the SAME canonical Sequence/Node model used by runtime. Qt is a future view/controller.
"""

from __future__ import annotations
from dataclasses import replace
from typing import Callable
from .canonical import Sequence, Node, Kind, Command

_CONTAINER = {Kind.SEQUENCE, Kind.PARALLEL, Kind.BRANCH, Kind.LOOP}


def _map(node: Node, target: str, fn: Callable[[Node], Node]) -> Node:
    if node.id == target:
        return fn(node)
    return replace(
        node,
        children=tuple(_map(c, target, fn) for c in node.children),
        else_children=tuple(_map(c, target, fn) for c in node.else_children),
    )


def _find(node: Node, target: str):
    if node.id == target:
        return node
    for c in node.children + node.else_children:
        x = _find(c, target)
        if x:
            return x
    return None


class PresentationEditorModel:
    def __init__(self, sequence: Sequence):
        sequence.validate()
        self.sequence = sequence
        self.selected_id = sequence.root.id
        self._undo = []
        self._redo = []

    def select(self, node_id):
        if _find(self.sequence.root, node_id) is None:
            raise KeyError(node_id)
        self.selected_id = node_id

    @property
    def selected(self):
        return _find(self.sequence.root, self.selected_id)

    def _commit(self, new_root):
        old = self.sequence.root
        candidate = replace(self.sequence, root=new_root)
        candidate.validate()
        self._undo.append(old)
        self._redo.clear()
        self.sequence = candidate
        if _find(new_root, self.selected_id) is None:
            self.selected_id = new_root.id

    def undo(self):
        if not self._undo:
            return False
        cur = self.sequence.root
        root = self._undo.pop()
        self._redo.append(cur)
        self.sequence = replace(self.sequence, root=root)
        if _find(root, self.selected_id) is None:
            self.selected_id = root.id
        return True

    def redo(self):
        if not self._redo:
            return False
        cur = self.sequence.root
        root = self._redo.pop()
        self._undo.append(cur)
        self.sequence = replace(self.sequence, root=root)
        return True

    def insert(self, parent_id, node, index=None, branch="children"):
        if _find(self.sequence.root, node.id):
            raise ValueError("duplicate node id")

        def op(p):
            if p.kind not in _CONTAINER:
                raise ValueError("target is not a container")
            attr = "else_children" if branch == "else" else "children"
            xs = list(getattr(p, attr))
            xs.insert(len(xs) if index is None else index, node)
            return replace(p, **{attr: tuple(xs)})

        self._commit(_map(self.sequence.root, parent_id, op))
        self.selected_id = node.id

    def delete(self, node_id):
        if node_id == self.sequence.root.id:
            raise ValueError("cannot delete root")

        def rec(n):
            return replace(
                n,
                children=tuple(rec(c) for c in n.children if c.id != node_id),
                else_children=tuple(rec(c) for c in n.else_children if c.id != node_id),
            )

        if not _find(self.sequence.root, node_id):
            raise KeyError(node_id)
        self._commit(rec(self.sequence.root))

    def update_node(self, node_id, **changes):
        self._commit(_map(self.sequence.root, node_id, lambda n: replace(n, **changes)))

    def move(self, node_id, new_parent_id, index=None, branch="children"):
        node = _find(self.sequence.root, node_id)
        if node is None:
            raise KeyError(node_id)
        if node_id == self.sequence.root.id:
            raise ValueError("cannot move root")
        # reject moving a node under itself/its descendants
        if _find(node, new_parent_id):
            raise ValueError("cycle")

        def remove(n):
            return replace(
                n,
                children=tuple(remove(c) for c in n.children if c.id != node_id),
                else_children=tuple(remove(c) for c in n.else_children if c.id != node_id),
            )

        base = remove(self.sequence.root)

        def add(p):
            if p.kind not in _CONTAINER:
                raise ValueError("target is not a container")
            attr = "else_children" if branch == "else" else "children"
            xs = list(getattr(p, attr))
            xs.insert(len(xs) if index is None else index, node)
            return replace(p, **{attr: tuple(xs)})

        self._commit(_map(base, new_parent_id, add))
        self.selected_id = node_id

    def issues(self):
        issues = []
        try:
            self.sequence.validate()
        except ValueError as e:
            issues.append(("technical", str(e)))

        def walk(n):
            if n.kind == Kind.COMMAND and n.command and not n.command.channel:
                issues.append(("technical", f"{n.id}: empty channel"))
            if n.kind == Kind.LOOP and n.loop_count > 10000:
                issues.append(("authoring", f"{n.id}: unusually large loop"))
            for c in n.children + n.else_children:
                walk(c)

        walk(self.sequence.root)
        return tuple(issues)

    def tree_rows(self, query=""):
        out = []

        def walk(n, depth, path):
            label = n.command.action if n.command else n.kind.value
            if not query.lower() in (n.id + " " + label).lower() if query else False:
                pass
            else:
                out.append((n.id, depth, label, path))
            for i, c in enumerate(n.children):
                walk(c, depth + 1, path + (("children", i),))
            for i, c in enumerate(n.else_children):
                walk(c, depth + 1, path + (("else", i),))

        walk(self.sequence.root, 0, ())
        return tuple(out)
