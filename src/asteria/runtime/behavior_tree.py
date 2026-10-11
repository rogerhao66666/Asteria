"""Behavior tree runtime for field entities (RPG-09).

``BehaviorTreeSystem`` ticks the tree named by each enabled ``AIController2D``
whose driver is ``behavior_tree``. Per-entity memory (running child indices,
timers, patrol progress, home point) lives in the system; movement goes through
the entity's ``CharacterController2D`` intent when it has one (same collision as
the player), otherwise the entity is stepped directly at ``speed``.
"""

from __future__ import annotations

import random
from math import cos, hypot, pi, sin

from asteria.core import System, Transform

from .character_control import AIController2DComponent, CharacterController2DComponent

SUCCESS, FAILURE, RUNNING = "success", "failure", "running"


def _points(text):
    points = []
    for chunk in str(text or "").split(";"):
        if chunk.strip():
            x, y = chunk.split(",")
            points.append((float(x), float(y)))
    return points


class BehaviorTreeSystem(System):
    order = 20

    def __init__(
        self,
        trees,
        *,
        target_id="",
        switches=None,
        set_switch=None,
        start_encounter=None,
        rng=None,
    ):
        self.trees = trees  # mapping tree_id -> BehaviorTree (e.g. project.rpg_database.behavior_trees)
        self.target_id = str(target_id or "")
        self.switches = switches or (lambda _name: False)
        self.set_switch = set_switch or (lambda _name, _value: None)
        self.start_encounter = start_encounter or (lambda _encounter_id: None)
        self.rng = rng or random.Random(0)
        self.memory: dict[str, dict] = {}
        self.status: dict[str, str] = {}  # last root status per entity (inspection / debugger)

    # -- movement ----------------------------------------------------------------------------------
    def _move(self, ctx, goal, params, *, away=False):
        t = ctx["transform"]
        dx, dy = goal[0] - t.x, goal[1] - t.y
        if away:
            dx, dy = -dx, -dy
        distance = hypot(dx, dy)
        if distance <= 1e-9:
            return 0.0
        controller = ctx["controller"]
        if controller is not None:
            scale = 1.0 if away else min(1.0, distance / max(controller.speed * ctx["dt"], 1e-9))
            controller.set_intent(dx / distance * scale, dy / distance * scale)
        else:
            step = (
                min(distance, float(params.get("speed", 40.0)) * ctx["dt"])
                if not away
                else float(params.get("speed", 40.0)) * ctx["dt"]
            )
            t.x += dx / distance * step
            t.y += dy / distance * step
        return distance

    def _target(self, ctx):
        if ctx["target"] is None:
            return None
        t = ctx["target"].get(Transform)
        return (t.x, t.y)

    def _distance_to(self, ctx, point):
        t = ctx["transform"]
        return hypot(point[0] - t.x, point[1] - t.y)

    @staticmethod
    def _forget(ctx, prefix):
        """Drop the memory of an interrupted branch so it starts fresh next time."""
        for key in [k for k in ctx["memory"] if k[: len(prefix)] == prefix]:
            del ctx["memory"][key]

    # -- ticking ----------------------------------------------------------------------------------
    def _tick(self, node, path, ctx):
        mem = ctx["memory"]
        state = mem.setdefault(path, {})
        kind, p = node.kind, node.params
        if kind == "selector":
            # Reactive: higher-priority children are re-checked every tick and interrupt a running lower one.
            for index, child in enumerate(node.children):
                result = self._tick(child, (*path, index), ctx)
                if result != FAILURE:
                    previous = state.get("running")
                    if previous is not None and previous != index:
                        self._forget(ctx, (*path, previous))
                    state["running"] = index if result == RUNNING else None
                    return result
            state["running"] = None
            return FAILURE
        if kind == "sequence":
            stop_on = FAILURE
            index = state.get("index", 0)
            while index < len(node.children):
                result = self._tick(node.children[index], (*path, index), ctx)
                if result == RUNNING:
                    state["index"] = index
                    return RUNNING
                if result == stop_on:
                    state["index"] = 0
                    return stop_on
                index += 1
            state["index"] = 0
            return SUCCESS
        if kind == "parallel":
            results = [self._tick(c, (*path, i), ctx) for i, c in enumerate(node.children)]
            need = int(p.get("success_count", len(node.children)))
            if results.count(SUCCESS) >= need:
                return SUCCESS
            if results.count(FAILURE) > len(node.children) - need:
                return FAILURE
            return RUNNING
        if kind == "inverter":
            result = self._tick(node.children[0], (*path, 0), ctx)
            return {SUCCESS: FAILURE, FAILURE: SUCCESS}.get(result, RUNNING)
        if kind == "succeeder":
            result = self._tick(node.children[0], (*path, 0), ctx)
            return RUNNING if result == RUNNING else SUCCESS
        if kind == "repeater":
            result = self._tick(node.children[0], (*path, 0), ctx)
            if result == RUNNING:
                return RUNNING
            state["done"] = state.get("done", 0) + 1
            count = int(p.get("count", 0))
            if count and state["done"] >= count:
                state["done"] = 0
                return SUCCESS
            return RUNNING
        if kind == "cooldown":
            if state.get("ready_at", 0.0) > ctx["time"]:
                return FAILURE
            result = self._tick(node.children[0], (*path, 0), ctx)
            if result == SUCCESS:
                state["ready_at"] = ctx["time"] + float(p.get("seconds", 1.0))
            return result
        # conditions
        target = self._target(ctx)
        if kind == "player_within":
            return (
                SUCCESS
                if target is not None and self._distance_to(ctx, target) <= float(p.get("radius", 64))
                else FAILURE
            )
        if kind == "player_beyond":
            return SUCCESS if target is None or self._distance_to(ctx, target) > float(p.get("radius", 64)) else FAILURE
        if kind == "home_within":
            return SUCCESS if self._distance_to(ctx, ctx["home"]) <= float(p.get("radius", 4)) else FAILURE
        if kind == "switch":
            return SUCCESS if self.switches(str(p.get("name", ""))) else FAILURE
        if kind == "chance":
            return SUCCESS if self.rng.random() < float(p.get("probability", 0.5)) else FAILURE
        # actions
        if kind == "chase":
            lose = p.get("lose_radius")
            if target is None or (lose is not None and self._distance_to(ctx, target) > float(lose)):
                return FAILURE
            if self._distance_to(ctx, target) <= float(p.get("arrive", 4.0)):
                return SUCCESS
            self._move(ctx, target, p)
            return RUNNING
        if kind == "flee":
            if target is None or self._distance_to(ctx, target) > float(p.get("radius", 96.0)):
                return SUCCESS
            self._move(ctx, target, p, away=True)
            return RUNNING
        if kind in ("move_to", "return_home"):
            goal = ctx["home"] if kind == "return_home" else (float(p.get("x", 0)), float(p.get("y", 0)))
            if self._distance_to(ctx, goal) <= float(p.get("arrive", 2.0)):
                return SUCCESS
            self._move(ctx, goal, p)
            return RUNNING
        if kind == "patrol":
            points = _points(p.get("points"))
            if not points:
                return FAILURE
            index = state.get("index", 0) % len(points)
            if self._distance_to(ctx, points[index]) <= float(p.get("arrive", 2.0)):
                state["index"] = (index + 1) % len(points)
                return SUCCESS if state["index"] == 0 and p.get("once") else RUNNING
            self._move(ctx, points[index], p)
            return RUNNING
        if kind == "wander":
            goal = state.get("goal")
            if goal is None:
                angle, reach = self.rng.uniform(0, 2 * pi), self.rng.uniform(0, float(p.get("radius", 48.0)))
                goal = state["goal"] = (ctx["home"][0] + cos(angle) * reach, ctx["home"][1] + sin(angle) * reach)
            if self._distance_to(ctx, goal) <= float(p.get("arrive", 2.0)):
                state.pop("goal", None)
                return SUCCESS
            self._move(ctx, goal, p)
            return RUNNING
        if kind == "wait":
            started = state.setdefault("started", ctx["time"])
            if ctx["time"] - started >= float(p.get("seconds", 1.0)) - 1e-9:
                state.pop("started", None)
                return SUCCESS
            return RUNNING
        if kind == "face_player":
            ctx["facing"] = target
            return SUCCESS if target is not None else FAILURE
        if kind == "set_switch":
            self.set_switch(str(p.get("name", "")), bool(p.get("value", True)))
            return SUCCESS
        if kind == "start_encounter":
            self.start_encounter(str(p.get("encounter_id", "")))
            return SUCCESS
        return FAILURE

    def update(self, scene, dt):
        target = scene.get_entity(self.target_id) if self.target_id else None
        for entity, ai, transform in scene.query(AIController2DComponent, Transform):
            if not ai.enabled or ai.driver != "behavior_tree":
                continue
            tree = self.trees.get(ai.tree_id)
            if tree is None:
                self.status[entity.id] = FAILURE
                continue
            entry = self.memory.setdefault(entity.id, {"nodes": {}, "home": (transform.x, transform.y), "time": 0.0})
            entry["time"] += dt
            controller = entity.try_get(CharacterController2DComponent)
            if controller is not None and controller.enabled:
                controller.set_intent(0.0, 0.0)
            else:
                controller = None
            ctx = {
                "transform": transform,
                "controller": controller,
                "target": target if target is not None and target.has(Transform) else None,
                "dt": dt,
                "time": entry["time"],
                "home": entry["home"],
                "memory": entry["nodes"],
                "facing": None,
            }
            self.status[entity.id] = self._tick(tree.root, (), ctx)
