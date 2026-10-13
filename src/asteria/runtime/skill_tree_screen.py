"""Skill tree screen for real-time play (D22 A10): the player's progression graphs, drawn as a
tree, learned with the keyboard or a gamepad.

Which graphs are shown: those of the actor's active classes - a graph tagged ``class:<id>`` or
named ``<id>_tree`` - plus graphs tagged ``shared`` (every class sees them). When nothing matches,
every graph the actor has is shown, so a classless game still gets its tree. Node positions are the
graph's authored ``node_positions``; graphs without them are laid out by prerequisite depth.

Nothing here knows a game: costs, ranks, prerequisites and rewards all come from the graph data,
and learning goes through ``GameSessionRuntime.allocate_progression`` (the fight refreshes).
"""

from __future__ import annotations

from math import hypot

NODE_W, NODE_H = 128, 44
COLORS = {
    "learned": (64, 150, 96),
    "maxed": (196, 156, 62),
    "available": (58, 92, 150),
    "locked": (44, 48, 60),
}


def actor_graphs(database, progression, allocation):
    """Graph ids shown for an actor: its active classes' graphs plus shared ones."""
    known = [g for g in database.progression_graphs if g in allocation.definitions]
    classes = [c.lower() for c in progression.active_class_ids]
    chosen = []
    for graph_id in known:
        graph = database.progression_graphs[graph_id]
        tags = {t.lower() for t in graph.tags}
        if (
            any(f"class:{c}" in tags or graph_id.lower() == f"{c}_tree" for c in classes)
            or "shared" in tags
        ):
            chosen.append(graph_id)
    # the class trees first, shared trees after
    chosen.sort(key=lambda g: "shared" in database.progression_graphs[g].tags)
    return chosen or known


def layout(graph):
    """``{node_id: (x, y)}`` in graph units: authored positions, else rows by prerequisite
    depth."""
    if graph.node_positions:
        return {n.node_id: tuple(graph.node_positions.get(n.node_id, (0, 0))) for n in graph.nodes}
    depth = {}

    def visit(node_id, seen=()):
        if node_id in depth:
            return depth[node_id]
        node = graph.node(node_id)
        reqs = [r.node_id for r in node.prerequisites + node.any_prerequisites]
        value = (
            0 if not reqs else 1 + max(visit(r, seen + (node_id,)) for r in reqs if r not in seen)
        )
        depth[node_id] = value
        return value

    rows = {}
    for node in graph.nodes:
        rows.setdefault(visit(node.node_id), []).append(node.node_id)
    positions = {}
    for row, ids in rows.items():
        for col, node_id in enumerate(ids):
            positions[node_id] = ((col - (len(ids) - 1) / 2) * 170.0, row * 90.0)
    return positions


def describe_reward(reward, labels):
    parts = []
    for stat, value in sorted(reward.stat_bonuses.items()):
        parts.append(f"{stat} +{value:g}")
    for name, value in sorted(reward.resource_bonuses.items()):
        parts.append(f"max {name} +{value:g}")
    for ability in reward.granted_abilities:
        parts.append("Skill: " + (labels.get(ability, {}).get("label") or ability))
    for passive in reward.unlocked_passives:
        parts.append(f"Passive: {passive}")
    parts += [f"Tag: {t}" for t in reward.granted_tags]
    return parts


class SkillTreeScreen:
    """Made when opened; each frame ``handle(dt)`` then ``draw()``; ``closed`` ends it."""

    def __init__(self, runtime):
        self.rt = runtime
        self.graph_index = 0
        self.node_id = None
        self.closed = False
        self.message, self.message_left = "", 0.0

    # -- data ------------------------------------------------------------------------------------
    @property
    def actor_id(self):
        game = self.rt.game
        return game._actor_of(game.player) or (game.save.rpg_state.party_actor_ids or (None,))[0]

    def _allocation(self):
        return self.rt.game.save.rpg_state.progression_allocations.get(self.actor_id)

    def graphs(self):
        actor_id = self.actor_id
        if actor_id is None:
            return []
        game = self.rt.game
        allocation = self._allocation()
        if allocation is None:
            return []
        progression = game.ensure_actor_progression(actor_id)
        return actor_graphs(game.project.rpg_database, progression, allocation)

    def graph(self):
        ids = self.graphs()
        if not ids:
            return None
        self.graph_index %= len(ids)
        return self.rt.game.project.rpg_database.progression_graphs[ids[self.graph_index]]

    def status(self, graph, node):
        allocation = self._allocation()
        rank = allocation.rank(graph.graph_id, node.node_id)
        if rank >= node.max_rank:
            return "maxed"
        if rank:
            return "learned"
        reasons = allocation.preview_allocate(graph.graph_id, node.node_id, 1).reasons
        # only short of points: it can be learned once more are earned
        return "available" if all(r.startswith("insufficient") for r in reasons) else "locked"

    # -- input -----------------------------------------------------------------------------------
    def _move(self, graph, dx, dy):
        positions = layout(graph)
        here = positions.get(self.node_id)
        if here is None:
            self.node_id = graph.nodes[0].node_id
            return
        best, score = None, None
        for node_id, (x, y) in positions.items():
            vx, vy = x - here[0], y - here[1]
            along = vx * dx + vy * dy
            if node_id == self.node_id or along <= 0:
                continue
            value = hypot(vx, vy) + abs(vx * dy - vy * dx) * 1.5
            if score is None or value < score:
                best, score = node_id, value
        if best is not None:
            self.node_id = best

    def learn(self):
        graph = self.graph()
        if graph is None or self.node_id is None:
            return False
        game = self.rt.game
        allocation = self._allocation()
        preview = allocation.preview_allocate(graph.graph_id, self.node_id, 1)
        node = graph.node(self.node_id)
        if not preview.allowed:
            reason = (preview.reasons or ("requirements not met",))[0]
            for other in sorted(graph.nodes, key=lambda x: -len(x.node_id)):
                reason = reason.replace(other.node_id, other.display_name)  # ids -> names
            self._say(f"Cannot learn {node.display_name}: {reason}")
            return False
        game.allocate_progression(self.actor_id, graph.graph_id, self.node_id)
        rank = allocation.rank(graph.graph_id, self.node_id)
        self._say(f"Learned {node.display_name} (rank {rank}/{node.max_rank})")
        return True

    def _say(self, text):
        self.message, self.message_left = text, 2.5

    def handle(self, dt=0.0):
        inp = self.rt.input
        self.message_left = max(0.0, self.message_left - dt)
        graph = self.graph()
        if inp.just_pressed("cancel") or inp.just_pressed("menu"):
            self.closed = True
            return
        if graph is None:
            return
        if self.node_id is None or self.node_id not in {n.node_id for n in graph.nodes}:
            self.node_id = graph.nodes[0].node_id
        for action, (dx, dy) in (
            ("move_left", (-1, 0)),
            ("move_right", (1, 0)),
            ("move_up", (0, -1)),
            ("move_down", (0, 1)),
        ):
            if inp.just_pressed(action):
                self._move(graph, dx, dy)
        if inp.just_pressed("lock_switch") and len(self.graphs()) > 1:
            self.graph_index += 1
            self.node_id = None
        if inp.just_pressed("confirm") or inp.just_pressed("interact"):
            self.learn()

    # -- drawing ---------------------------------------------------------------------------------
    def draw(self):
        rt = self.rt
        pg, screen = rt.pg, rt.screen
        screen.fill((10, 12, 20))
        graph = self.graph()
        actor_id = self.actor_id
        game = rt.game
        rt.text("Skill Tree", 36, 22, size=34, color=(255, 220, 124))
        if graph is None or actor_id is None:
            rt.text("No skill tree for this character.", 36, 80, size=22)
            return
        allocation = self._allocation()
        progression = game.ensure_actor_progression(actor_id)
        balances = "   ".join(
            f"{currency.upper()} {allocation.balance(currency):g}"
            for currency in sorted(
                {c for n in graph.nodes for cost in n.rank_costs for c in cost} or {"ap"}
            )
        )
        classes = ", ".join(
            game.project.rpg_database.classes[c].display_name
            for c in progression.active_class_ids
            if c in game.project.rpg_database.classes
        )
        rt.text(
            f"{graph.display_name}   ·   {classes or '—'}   ·   Lv {progression.level}",
            36,
            62,
            size=21,
            color=(190, 205, 230),
        )
        rt.text(balances, rt.width - 36 - 300, 30, size=24, color=(140, 230, 170))
        count = len(self.graphs())
        if count > 1:
            rt.text(
                f"Tree {self.graph_index % count + 1}/{count}  (O: next tree)",
                rt.width - 336,
                62,
                size=18,
                color=(170, 180, 200),
            )
        positions = layout(graph)
        area = (36, 100, rt.width - 36 - 330 - 24, rt.height - 100 - 64)
        xs = [p[0] for p in positions.values()]
        ys = [p[1] for p in positions.values()]
        span_x, span_y = max(xs) - min(xs) or 1.0, max(ys) - min(ys) or 1.0
        scale = min((area[2] - NODE_W) / span_x, (area[3] - NODE_H) / span_y, 1.4)
        ox = area[0] + (area[2] - span_x * scale) / 2 - min(xs) * scale
        oy = area[1] + (area[3] - span_y * scale) / 2 - min(ys) * scale

        def centre(node_id):
            x, y = positions[node_id]
            return ox + x * scale, oy + y * scale

        for node in graph.nodes:
            cx, cy = centre(node.node_id)
            for req in node.prerequisites + node.any_prerequisites:
                px, py = centre(req.node_id)
                met = allocation.rank(graph.graph_id, req.node_id) >= req.minimum_rank
                color = (150, 200, 160) if met else (80, 88, 110)
                pg.draw.line(screen, color, (int(px), int(py)), (int(cx), int(cy)), 3)
        for node in graph.nodes:
            cx, cy = centre(node.node_id)
            status = self.status(graph, node)
            rect = pg.Rect(int(cx - NODE_W / 2), int(cy - NODE_H / 2), NODE_W, NODE_H)
            pg.draw.rect(screen, COLORS[status], rect, border_radius=8)
            selected = node.node_id == self.node_id
            border = (255, 220, 124) if selected else (150, 160, 190)
            pg.draw.rect(screen, border, rect, 3 if selected else 1, border_radius=8)
            rank = allocation.rank(graph.graph_id, node.node_id)
            text_color = (245, 245, 250) if status != "locked" else (150, 156, 172)
            rt.text(node.display_name[:16], cx, cy - 12, size=18, color=text_color, center=True)
            rt.text(f"{rank}/{node.max_rank}", cx, cy + 8, size=16, color=text_color, center=True)
        self._draw_details(graph, allocation)
        rt.text(
            "Arrows: choose   Enter: learn   O: next tree   C / Esc: back",
            rt.width / 2,
            rt.height - 24,
            size=18,
            color=(170, 180, 200),
            center=True,
        )
        if self.message_left > 0:
            rt.text(
                self.message,
                rt.width / 2,
                rt.height - 52,
                size=20,
                color=(175, 235, 255),
                center=True,
            )

    def _draw_details(self, graph, allocation):
        rt = self.rt
        node = graph.node(self.node_id) if self.node_id else None
        x, y, w = rt.width - 330, 100, 300
        rt.panel((x, y, w, rt.height - 100 - 60), fill=(16, 20, 32, 235))
        if node is None:
            return
        labels = rt.manifest.get("battle", {}).get("skills", {})
        rank = allocation.rank(graph.graph_id, node.node_id)
        rt.text(node.display_name, x + 16, y + 14, size=24, color=(255, 220, 124))
        status = self.status(graph, node)
        rt.text(
            f"Rank {rank}/{node.max_rank}   ·   {status}",
            x + 16,
            y + 44,
            size=18,
            color=(190, 205, 230),
        )
        row = y + 78
        if rank < node.max_rank:
            cost = node.cost_for_rank(rank + 1)
            text = ", ".join(f"{v:g} {k.upper()}" for k, v in sorted(cost.items())) or "free"
            rt.text(f"Next rank costs {text}", x + 16, row, size=18)
            row += 28
            rt.text("Next rank gives:", x + 16, row, size=18, color=(140, 230, 170))
            row += 24
            for line in describe_reward(node.reward_for_rank(rank + 1), labels)[:6]:
                rt.text("  " + line, x + 16, row, size=18)
                row += 22
        if rank:
            row += 8
            rt.text("Learned so far:", x + 16, row, size=18, color=(140, 230, 170))
            row += 24
            totals = {}
            for r in range(1, rank + 1):
                for line in describe_reward(node.reward_for_rank(r), labels):
                    totals[line] = totals.get(line, 0) + 1
            for line in list(totals)[:5]:
                rt.text("  " + line, x + 16, row, size=18)
                row += 22
        reqs = node.prerequisites + node.any_prerequisites
        if reqs:
            row += 8
            rt.text("Needs:", x + 16, row, size=18, color=(255, 190, 150))
            row += 24
            for req in reqs:
                have = allocation.rank(graph.graph_id, req.node_id)
                mark = "✓" if have >= req.minimum_rank else "·"
                name = graph.node(req.node_id).display_name
                rt.text(f"  {mark} {name} {req.minimum_rank}", x + 16, row, size=18)
                row += 22


__all__ = ["SkillTreeScreen", "actor_graphs", "describe_reward", "layout"]
