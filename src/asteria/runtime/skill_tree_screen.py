"""Skill tree screen for real-time play (D22 A10): the player's progression graphs, drawn as a
tree, learned with the keyboard or a gamepad.

Which graphs are shown: those of the actor's active classes - a graph tagged ``class:<id>`` or
named ``<id>_tree`` - plus graphs tagged ``shared`` (every class sees them). When nothing matches,
every graph the actor has is shown, so a classless game still gets its tree. Node positions are the
graph's authored ``node_positions``; graphs without them are laid out by prerequisite depth.
The view zooms (wheel, + / -), pans (drag, or by choosing a node) and fits (R); positions are
spread just enough that no two nodes ever overlap, however long the tree is.

Nothing here knows a game: costs, ranks, prerequisites and rewards all come from the graph data,
and learning goes through ``GameSessionRuntime.allocate_progression`` (the fight refreshes).
"""

from __future__ import annotations

from math import hypot

NODE_W, NODE_H = 148, 44
GAP = 16  # the least space left between two nodes at zoom 1
ZOOM_MIN, ZOOM_MAX = 0.3, 2.5
ICON = 30  # a node's picture: the icon of the first ability it grants
COLORS = {
    "learned": (64, 150, 96),
    "maxed": (196, 156, 62),
    "available": (58, 92, 150),
    "locked": (44, 48, 60),
}
STATUS_WORDS = {status: f"skill_tree.status.{status}" for status in COLORS}  # drawn words


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


def _english(key, english, **params):
    return english.format(**params) if params else english


def describe_reward(reward, labels, names=None, tr=None):
    """Reward lines; ``names`` maps stat / resource ids to the project's names (STR, HP);
    ``tr`` (``GameSessionRuntime.tr``) words them in the player's language."""
    names = names or {}
    tr = tr or _english
    parts = []
    for stat, value in sorted(reward.stat_bonuses.items()):
        parts.append(f"{names.get(stat, stat)} +{value:g}")
    for name, value in sorted(reward.resource_bonuses.items()):
        label = names.get(name, name)
        parts.append(tr("skill_tree.max", "max {name} +{value}", name=label, value=f"{value:g}"))
    for ability in reward.granted_abilities:
        label = labels.get(ability, {}).get("label") or ability
        parts.append(tr("skill_tree.skill", "Skill: {name}", name=label))
    for passive in reward.unlocked_passives:
        parts.append(tr("skill_tree.passive", "Passive: {name}", name=passive))
    parts += [tr("skill_tree.tag", "Tag: {name}", name=t) for t in reward.granted_tags]
    return parts


class StatNames:
    """``names.get(stat_id)`` for ``describe_reward``: the stat's name in the player's language
    (``GameSessionRuntime.stat_name``: the locale table, the character screen, the id)."""

    def __init__(self, game):
        self.game = game

    def get(self, stat_id, _default=None):
        return self.game.stat_name(stat_id)


class SkillTreeScreen:
    """Made when opened; each frame ``handle(dt)`` then ``draw()``; ``closed`` ends it."""

    def __init__(self, runtime):
        self.rt = runtime
        self.graph_index = 0
        self.node_id = None
        self.closed = False
        self.back = "field"  # the mode it returns to (the pause menu when opened there)
        self.message, self.message_left = "", 0.0
        self.zoom, self.origin = 1.0, [0.0, 0.0]  # screen position of the graph's (0, 0)
        self._view_for = None  # the graph the view was fitted to
        self._spread = {}  # graph id -> pixels per graph unit that keep nodes apart
        self._layouts = {}  # graph id -> (graph, positions): laid out once, not per node
        self._drag = None

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

    # -- the view --------------------------------------------------------------------------------
    def positions(self, graph):
        """The graph's node positions, laid out once per graph (``layout`` walks every
        prerequisite: done per node and per line each frame it made a long tree stutter)."""
        layouts = self.__dict__.setdefault("_layouts", {})
        cached = layouts.get(graph.graph_id)
        if cached is None or cached[0] is not graph:  # an edited graph is a new object
            cached = (graph, layout(graph))
            layouts[graph.graph_id] = cached
        return cached[1]

    def area(self):
        rt = self.rt
        return (36, 100, rt.width - 36 - 330 - 24, rt.height - 100 - 64)

    def spread(self, graph):
        """Pixels per graph unit at zoom 1: the least that leaves every pair of nodes apart."""
        cached = self._spread.get(graph.graph_id)
        if cached is not None:
            return cached
        points = list(self.positions(graph).values())
        factor = 1.0
        for i, (ax, ay) in enumerate(points):
            for bx, by in points[i + 1 :]:
                dx, dy = abs(ax - bx), abs(ay - by)
                need = min(
                    (NODE_W + GAP) / dx if dx else float("inf"),
                    (NODE_H + GAP) / dy if dy else float("inf"),
                )
                if need != float("inf"):
                    factor = max(factor, need)
        self._spread[graph.graph_id] = factor
        return factor

    def node_point(self, graph, node_id):
        """The centre of a node on the screen."""
        x, y = self.positions(graph)[node_id]
        k = self.spread(graph) * self.zoom
        return self.origin[0] + x * k, self.origin[1] + y * k

    def fit(self, graph):
        """Zoom and place the whole tree in the area (never larger than life)."""
        positions = self.positions(graph)
        k = self.spread(graph)
        xs = [p[0] * k for p in positions.values()]
        ys = [p[1] * k for p in positions.values()]
        left, top, width, height = self.area()
        span_x, span_y = max(xs) - min(xs) + NODE_W + 32, max(ys) - min(ys) + NODE_H + 32
        self.zoom = max(ZOOM_MIN, min(1.0, width / span_x, height / span_y))
        self.origin[0] = left + width / 2 - (min(xs) + max(xs)) / 2 * self.zoom
        self.origin[1] = top + height / 2 - (min(ys) + max(ys)) / 2 * self.zoom
        self._view_for = graph.graph_id

    def zoom_by(self, factor, anchor=None):
        left, top, width, height = self.area()
        ax, ay = anchor or (left + width / 2, top + height / 2)
        new = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom * factor))
        ratio = new / self.zoom
        self.origin[0] = ax - (ax - self.origin[0]) * ratio
        self.origin[1] = ay - (ay - self.origin[1]) * ratio
        self.zoom = new

    def reveal(self, graph):
        """Scroll so the chosen node is inside the area."""
        if self.node_id is None:
            return
        left, top, width, height = self.area()
        x, y = self.node_point(graph, self.node_id)
        half_w, half_h = NODE_W * self.zoom / 2 + 12, NODE_H * self.zoom / 2 + 12
        if x - half_w < left:
            self.origin[0] += left - (x - half_w)
        elif x + half_w > left + width:
            self.origin[0] -= (x + half_w) - (left + width)
        if y - half_h < top:
            self.origin[1] += top - (y - half_h)
        elif y + half_h > top + height:
            self.origin[1] -= (y + half_h) - (top + height)

    def node_at(self, graph, point):
        half_w, half_h = NODE_W * self.zoom / 2, NODE_H * self.zoom / 2
        for node in graph.nodes:
            x, y = self.node_point(graph, node.node_id)
            if abs(point[0] - x) <= half_w and abs(point[1] - y) <= half_h:
                return node.node_id
        return None

    def _events(self, graph, events):
        pg = self.rt.pg
        left, top, width, height = self.area()
        inside = lambda p: left <= p[0] <= left + width and top <= p[1] <= top + height  # noqa: E731
        for event in events:
            if event.type == pg.MOUSEWHEEL:
                self.zoom_by(1.12**event.y, pg.mouse.get_pos())
            elif event.type == pg.KEYDOWN:
                if event.key in (pg.K_EQUALS, pg.K_PLUS, pg.K_KP_PLUS):
                    self.zoom_by(1.2)
                elif event.key in (pg.K_MINUS, pg.K_KP_MINUS):
                    self.zoom_by(1 / 1.2)
                elif event.key == pg.K_r:
                    self.fit(graph)
            elif event.type == pg.MOUSEBUTTONDOWN and event.button in (1, 2, 3):
                if inside(event.pos):
                    self._drag = [event.pos, list(self.origin), False, event.button]
            elif event.type == pg.MOUSEMOTION and self._drag is not None:
                start, origin, moved, _button = self._drag
                dx, dy = event.pos[0] - start[0], event.pos[1] - start[1]
                if moved or abs(dx) + abs(dy) > 4:
                    self._drag[2] = True
                    self.origin[0], self.origin[1] = origin[0] + dx, origin[1] + dy
            elif event.type == pg.MOUSEBUTTONUP and self._drag is not None:
                moved, button = self._drag[2], self._drag[3]
                self._drag = None
                if not moved and button == 1:  # a click chooses a node
                    hit = self.node_at(graph, event.pos)
                    if hit is not None:
                        self.node_id = hit

    # -- input -----------------------------------------------------------------------------------
    def _move(self, graph, dx, dy):
        positions = self.positions(graph)
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
            unmet = game.tr("skill_tree.unmet", "requirements not met")
            reason = (preview.reasons or (unmet,))[0]
            for other in sorted(graph.nodes, key=lambda x: -len(x.node_id)):
                reason = reason.replace(other.node_id, game.name_of(other))  # ids -> names
            self._say(
                game.tr(
                    "skill_tree.cannot_learn",
                    "Cannot learn {name}: {reason}",
                    name=game.name_of(node),
                    reason=reason,
                )
            )
            return False
        game.allocate_progression(self.actor_id, graph.graph_id, self.node_id)
        rank = allocation.rank(graph.graph_id, self.node_id)
        self._say(
            game.tr(
                "skill_tree.learned",
                "Learned {name} (rank {rank}/{max})",
                name=game.name_of(node),
                rank=rank,
                max=node.max_rank,
            )
        )
        return True

    def _say(self, text):
        self.message, self.message_left = text, 2.5

    def handle(self, dt=0.0, events=()):
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
        if self._view_for != graph.graph_id:
            self.fit(graph)
        self._events(graph, events)
        before = self.node_id
        for action, (dx, dy) in (
            ("move_left", (-1, 0)),
            ("move_right", (1, 0)),
            ("move_up", (0, -1)),
            ("move_down", (0, 1)),
        ):
            if inp.just_pressed(action):
                self._move(graph, dx, dy)
        if self.node_id != before:
            self.reveal(graph)
        if inp.just_pressed("lock_switch") and len(self.graphs()) > 1:
            self.graph_index += 1
            self.node_id = None
            self._view_for = None
        if inp.just_pressed("confirm") or inp.just_pressed("interact"):
            self.learn()

    # -- drawing ---------------------------------------------------------------------------------
    def draw(self):
        rt = self.rt
        pg, screen = rt.pg, rt.screen
        graph = self.graph()
        actor_id = self.actor_id
        game = rt.game
        db = game.project.rpg_database
        c = self.canvas = rt.menu_canvas(
            "skill_tree",
            {"member.name": lambda: game.name_of(db.actors.get(actor_id), actor_id or "")},
        )
        layout = c.layout
        if layout is None or (layout.background_color is None and not layout.background_image):
            screen.fill((10, 12, 20))
        c.begin()
        tr = game.tr
        title = tr("skill_tree.title", "Skill Tree")
        c.text("title", title, 36, 22, size=34, color=c.tone("title", (255, 220, 124)))
        if graph is None or actor_id is None:
            rt.text(tr("skill_tree.none", "No skill tree for this character."), 36, 80, size=22)
            c.finish()
            return
        allocation = self._allocation()
        progression = game.ensure_actor_progression(actor_id)
        balances = "   ".join(
            f"{game.points_name(currency)} {allocation.balance(currency):g}"
            for currency in sorted(
                {c for n in graph.nodes for cost in n.rank_costs for c in cost} or {"ap"}
            )
        )
        classes = ", ".join(
            game.name_of(game.project.rpg_database.classes[c])
            for c in progression.active_class_ids
            if c in game.project.rpg_database.classes
        )
        c.text(
            "header",
            tr(
                "skill_tree.header",
                "{tree}   ·   {classes}   ·   Lv {level}",
                tree=game.name_of(graph),
                classes=classes or "—",
                level=progression.level,
            ),
            36,
            62,
            size=21,
            color=(190, 205, 230),
        )
        drawn = c.text("points", balances, rt.width - 36 - 300, 30, size=24, color=(140, 230, 170))
        if drawn is not None and c.element("points_icon") is not None:
            side = drawn.height
            c.picture("points_icon", (drawn.x - side - 6, drawn.y, side, side), mode="fit")
        count = len(self.graphs())
        if count > 1:
            c.text(
                "trees",
                tr(
                    "skill_tree.trees",
                    "Tree {index}/{count}  (O: next tree)",
                    index=self.graph_index % count + 1,
                    count=count,
                ),
                rt.width - 336,
                62,
                size=18,
                color=(170, 180, 200),
            )
        if self._view_for != graph.graph_id:
            self.fit(graph)
        area = pg.Rect(self.area())
        zoom = self.zoom
        node_w, node_h = NODE_W * zoom, NODE_H * zoom
        previous_clip = screen.get_clip()
        screen.set_clip(area)  # a long tree scrolls under the header and the details
        links = {  # the lines' colours and widths: the layout's, else the engine's
            True: (c.color("link_met", (150, 200, 160)), c.size("link_met", 3)),
            False: (c.color("link_unmet", (80, 88, 110)), c.size("link_unmet", 3)),
        }
        for node in graph.nodes:
            cx, cy = self.node_point(graph, node.node_id)
            for req in node.prerequisites + node.any_prerequisites:
                px, py = self.node_point(graph, req.node_id)
                met = allocation.rank(graph.graph_id, req.node_id) >= req.minimum_rank
                link = links[met]
                pg.draw.line(
                    screen, link[0], (int(px), int(py)), (int(cx), int(cy)),
                    max(1, round(link[1] * zoom)),
                )  # fmt: skip
        for node in graph.nodes:
            cx, cy = self.node_point(graph, node.node_id)
            rect = pg.Rect(int(cx - node_w / 2), int(cy - node_h / 2), int(node_w), int(node_h))
            if not rect.colliderect(area):
                continue
            status = self.status(graph, node)
            selected = node.node_id == self.node_id
            # the author's frame for the node's status, else the engine's
            if not c.picture(f"node_{status}", rect, repeated=True):
                pg.draw.rect(screen, COLORS[status], rect, border_radius=max(2, round(8 * zoom)))
                border = (255, 220, 124) if selected else (150, 160, 190)
                radius = max(2, round(8 * zoom))
                pg.draw.rect(screen, border, rect, 3 if selected else 1, border_radius=radius)
            if selected:
                c.picture("node_selected", rect, repeated=True)
            rank = allocation.rank(graph.graph_id, node.node_id)
            text_color = (245, 245, 250) if status != "locked" else (150, 156, 172)
            icon_size = max(8, round(ICON * zoom))
            shift = 0
            if rt._draw_icon(
                self.node_icon(node), rect.x + round(6 * zoom), int(cy - icon_size / 2), icon_size
            ):
                shift = (icon_size + round(6 * zoom)) // 2
            if zoom < 0.55:  # zoomed far out: pictures and ranks only
                continue
            room = node_w - shift * 2 - icon_size - 16 * zoom
            name, size = rt.game.name_of(node), max(10, round(18 * zoom))
            while size > 9 and rt.text_width(name, size) > room:
                size -= 1
            while len(name) > 4 and rt.text_width(name, size) > room:
                name = name[:-2].rstrip() + "."
            rt.text(name, cx + shift, cy - 12 * zoom, size=size, color=text_color, center=True)
            rt.text(
                f"{rank}/{node.max_rank}",
                cx + shift,
                cy + 8 * zoom,
                size=max(11, round(16 * zoom)),
                color=text_color,
                center=True,
            )
        screen.set_clip(previous_clip)
        self._draw_details(graph, allocation)
        c.text(
            "hint",
            tr(
                "skill_tree.hint",
                "Arrows: choose   Enter: learn   Wheel / + -: zoom   Drag: move   R: fit   "
                "O: next tree   C: back",
            ),
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
        c.finish()

    def node_icon(self, node):
        """The node's own icon, else the first granted ability's icon, else ``""``."""
        if node.icon_id:
            return node.icon_id
        abilities = self.rt.project.gameplay_library.abilities
        for reward in node.rewards:
            for ability_id in reward.granted_abilities:
                try:
                    icon = abilities.get(ability_id).icon_id
                except KeyError:
                    continue
                if icon:
                    return icon
        return ""

    def _draw_details(self, graph, allocation):
        rt = self.rt
        node = graph.node(self.node_id) if self.node_id else None
        canvas = getattr(self, "canvas", None) or rt.menu_canvas("skill_tree")
        if not canvas.shown("detail"):
            return
        default = (rt.width - 330, 100, 300, rt.height - 100 - 60)
        x, y, w, _h = canvas.panel("detail", default, fill=(16, 20, 32, 235))
        if node is None:
            return
        labels = rt.manifest.get("battle", {}).get("skills", {})
        names = StatNames(rt.game)
        tr = rt.game.tr
        rank = allocation.rank(graph.graph_id, node.node_id)
        icon = rt._draw_icon(self.node_icon(node), x + 16, y + 10, 36)
        rt.text(
            rt.game.name_of(node),
            x + (60 if icon else 16),
            y + 14,
            size=24,
            color=(255, 220, 124),
        )
        status = self.status(graph, node)
        status = tr(STATUS_WORDS[status], status)  # the status is an id: its word is drawn
        rt.text(
            tr(
                "skill_tree.rank",
                "Rank {rank}/{max}   ·   {status}",
                rank=rank,
                max=node.max_rank,
                status=status,
            ),
            x + 16,
            y + 44,
            size=18,
            color=(190, 205, 230),
        )
        row = y + 78
        if rank < node.max_rank:
            cost = node.cost_for_rank(rank + 1)
            text = ", ".join(f"{v:g} {rt.game.points_name(k)}" for k, v in sorted(cost.items()))
            text = text or tr("skill_tree.free", "free")
            rt.text(
                tr("skill_tree.cost", "Next rank costs {cost}", cost=text), x + 16, row, size=18
            )
            row += 28
            gives = tr("skill_tree.gives", "Next rank gives:")
            rt.text(gives, x + 16, row, size=18, color=(140, 230, 170))
            row += 24
            for line in describe_reward(node.reward_for_rank(rank + 1), labels, names, tr)[:6]:
                rt.text("  " + line, x + 16, row, size=18)
                row += 22
        if rank:
            row += 8
            so_far = tr("skill_tree.so_far", "Learned so far:")
            rt.text(so_far, x + 16, row, size=18, color=(140, 230, 170))
            row += 24
            totals = {}
            for r in range(1, rank + 1):
                for line in describe_reward(node.reward_for_rank(r), labels, names, tr):
                    totals[line] = totals.get(line, 0) + 1
            for line in list(totals)[:5]:
                rt.text("  " + line, x + 16, row, size=18)
                row += 22
        reqs = node.prerequisites + node.any_prerequisites
        if reqs:
            row += 8
            rt.text(tr("skill_tree.needs", "Needs:"), x + 16, row, size=18, color=(255, 190, 150))
            row += 24
            for req in reqs:
                have = allocation.rank(graph.graph_id, req.node_id)
                mark = "✓" if have >= req.minimum_rank else "·"
                name = rt.game.name_of(graph.node(req.node_id))
                rt.text(f"  {mark} {name} {req.minimum_rank}", x + 16, row, size=18)
                row += 22


__all__ = ["SkillTreeScreen", "actor_graphs", "describe_reward", "layout"]
