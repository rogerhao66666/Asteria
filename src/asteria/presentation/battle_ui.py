from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from asteria.runtime import Camera2D

from .battle import BattlePresentationScene
from .battle_action_menu import BattleActionMenuView
from .battle_action_workflow import BattleActionWorkflowView
from .battle_camera_feedback import BattleCameraFeedbackFrame
from .battle_feedback import BattleFeedbackRuntime, BattleValueKind
from .battle_hud import BattleHudMember
from .battle_party_layout import BattlePartyLayoutPolicy
from .battle_result import BattleResultView
from .battle_runtime import BattlePresentationFrame
from .battle_turn_timeline import BattleTurnTimelineView
from .battle_ui_polish import BattleUiPolishProfile


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class BattleUiLayoutProfile:
    virtual_width: int = 320
    virtual_height: int = 180
    margin: float = 8.0
    hud_panel_width: float = 112.0
    hud_row_height: float = 10.0
    timeline_y: float = 7.0
    result_panel_width: float = 196.0
    result_panel_height: float = 116.0
    # Side-view staging options (defaults keep the original column HUD):
    # party_hud "column" | "bottom_row" (one compact cell per member along the bottom) |
    # "side_list" (a panel per member down the party's edge: name, status chips, one
    # "label  current / maximum" line with a bar per resource - the Octopath Traveler look);
    # overhead_zones: placement zones whose members show a bar over their sprite
    # instead of a HUD panel; action_menu_placement "bottom" | "actor" (beside the
    # acting member); stage_top: fraction of the height where the ground begins;
    # stage_front: how far in from each edge the front columns stand (fraction of the stage width).
    party_hud: str = "column"
    overhead_zones: tuple = ()
    # hidden_zones: placement zones whose members get no HUD at all (no panel, bar or name),
    # e.g. enemies in a game that never shows their health
    hidden_zones: tuple = ()
    # front_large_zones: placement zones where oversized combatants (a summon, a mount) stand in
    # front of the others, toward the centre of the stage, instead of behind them
    front_large_zones: tuple = ()
    action_menu_placement: str = "bottom"
    # column_size: how many combatants of one side share a column of the stage before the next
    # column starts behind them
    column_size: int = 3
    # menu_over_stage: the command menu stands right beside the acting member even when it
    # overlaps the other party members (it is drawn see-through); it never covers the acting
    # member or an enemy
    menu_over_stage: bool = False
    # row_buttons: every row of a menu gets a panel of its own (roles button, button:selected,
    # button:disabled) so a skin can draw buttons; off = rows are plain text
    row_buttons: bool = False
    # overhead_below: an overhead name and bar sit under the sprite's feet (they never cover the
    # body or the combatant behind); off = floating above the head
    overhead_below: bool = True
    # command_counts: a top-level command shows a number beside it (how many choices it opens,
    # Escape's chance); off = names alone
    command_counts: bool = False
    # overhead_bars: an overhead member shows its top resource as a bar under the name; off = the
    # name alone (a game that keeps enemy health hidden)
    overhead_bars: bool = True
    stage_top: float = 0.0
    stage_front: float = 0.30
    # stage_front_right: the same for the side standing on the right (None = stage_front), so the
    # party can stand nearer its edge while the foes stand nearer the middle
    stage_front_right: float | None = None

    def __post_init__(self):
        if self.virtual_width <= 0 or self.virtual_height <= 0:
            raise ValueError("virtual battle UI size must be positive")
        object.__setattr__(self, "overhead_zones", tuple(str(x) for x in self.overhead_zones))
        object.__setattr__(self, "hidden_zones", tuple(str(x) for x in self.hidden_zones))
        object.__setattr__(
            self, "front_large_zones", tuple(str(x) for x in self.front_large_zones)
        )
        if int(self.column_size) < 1:
            raise ValueError("column_size must be >= 1")
        if self.party_hud not in {"column", "bottom_row", "side_list"}:
            raise ValueError("party_hud must be 'column', 'bottom_row' or 'side_list'")
        if self.action_menu_placement not in {"bottom", "actor", "actor_bottom_right"}:
            raise ValueError(
                "action_menu_placement must be 'bottom', 'actor' or 'actor_bottom_right'"
            )
        if not 0.0 <= float(self.stage_top) < 1.0:
            raise ValueError("stage_top must be in [0, 1)")
        if self.stage_front_right is not None and not 0.0 <= float(self.stage_front_right) <= 0.5:
            raise ValueError("stage_front_right must be in [0, 0.5]")
        if not 0.0 <= float(self.stage_front) <= 0.5:
            raise ValueError("stage_front must be in [0, 0.5]")
        for name in (
            "margin",
            "hud_panel_width",
            "hud_row_height",
            "result_panel_width",
            "result_panel_height",
        ):
            if _finite(getattr(self, name), name) < 0:
                raise ValueError(f"{name} must be >= 0")


@dataclass(frozen=True, slots=True)
class BattleUiText:
    text: str
    x: float
    y: float
    role: str = "body"
    align: str = "left"
    member_id: str = ""


@dataclass(frozen=True, slots=True)
class BattleUiPanel:
    panel_id: str
    x: float
    y: float
    width: float
    height: float
    role: str = "panel"
    member_id: str = ""


@dataclass(frozen=True, slots=True)
class BattleUiGaugeBar:
    member_id: str
    resource_id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    normalized: float
    current: float
    maximum: float
    presentation: str = "bar"
    segments: int = 0
    icon_asset_id: str | None = None


@dataclass(frozen=True, slots=True)
class BattleUiIcon:
    asset_id: str
    x: float
    y: float
    role: str
    member_id: str = ""
    label: str = ""


@dataclass(frozen=True, slots=True)
class BattleUiMarker:
    member_id: str
    x: float
    y: float
    primary: bool = False


@dataclass(frozen=True, slots=True)
class BattleUiFrame:
    scene_id: str
    background_asset_id: str
    combatant_draws: tuple
    panels: tuple[BattleUiPanel, ...]
    texts: tuple[BattleUiText, ...]
    gauges: tuple[BattleUiGaugeBar, ...]
    icons: tuple[BattleUiIcon, ...]
    markers: tuple[BattleUiMarker, ...]
    vfx: tuple
    screen_fx: tuple


class BattleUiComposer:
    """Composes existing Battle Presentation view-state into adapter-ready UI.

    This layer owns layout only. It never reads or mutates Battle Core, resolves
    targets, changes resources, advances scheduler time, or applies rewards.
    """

    MIN_MENU_WIDTH = 96.0
    TIMELINE_CHAR_WIDTH = 5.0

    def __init__(
        self, scene: BattlePresentationScene, layout=None, party_layout=None, polish=None
    ):
        if not isinstance(scene, BattlePresentationScene):
            raise TypeError("scene must be BattlePresentationScene")
        self.scene = scene
        self.layout = layout or BattleUiLayoutProfile()
        if not isinstance(self.layout, BattleUiLayoutProfile):
            raise TypeError("layout must be BattleUiLayoutProfile")
        self.party_layout = party_layout or BattlePartyLayoutPolicy()
        if not isinstance(self.party_layout, BattlePartyLayoutPolicy):
            raise TypeError("party_layout must be BattlePartyLayoutPolicy")
        self.polish = polish or BattleUiPolishProfile()
        if not isinstance(self.polish, BattleUiPolishProfile):
            raise TypeError("polish must be BattleUiPolishProfile")
        self._display_names = {}
        self._member_heights = {}
        self._camera = None
        self._focus = None
        self.overhead_labels = {}  # member_id: (x, y, w, h) of its overhead label, last frame

    def _name(self, member_id):
        return self._display_names.get(str(member_id), str(member_id))

    @staticmethod
    def _fit(text, max_chars):
        """Shorten to ``max_chars``, keeping the last word (e.g. "Hero 06" -> "H06")."""
        text = str(text)
        if len(text) <= max_chars:
            return text
        words = text.split()
        if len(words) > 1:
            short = "".join(w[0] for w in words[:-1]) + words[-1]
            if len(short) <= max_chars:
                return short
        return text[: max(1, max_chars - 1)] + "."

    def _anchor_screen(self, camera, member_id):
        try:
            visual = self.scene.visual_for(member_id)
        except KeyError:
            return None
        return camera.world_to_screen(visual.anchor.x, visual.anchor.y)

    def _hud_commands(
        self, members, side_by_member, placement_by_member=None, focus_member_id=None
    ):
        panels, texts, gauges, icons = [], [], [], []
        L = self.layout

        # Explicit presentation placement wins. Legacy side metadata remains only
        # for backward compatibility with pre-Batch-105 projects.
        explicit = {str(k): str(v) for k, v in dict(placement_by_member or {}).items()}
        legacy = {str(k): str(v) for k, v in dict(side_by_member or {}).items()}

        # Legacy direct-call compatibility groups members by opaque side ID, but
        # never interprets side names. Distinct groups are assigned visual zones
        # deterministically by first appearance. Projects should prefer explicit
        # placement metadata when more than two presentation zones are desired.
        side_order = []
        for member in members:
            side = legacy.get(member.member_id, "")
            if side and side not in side_order:
                side_order.append(side)
        fallback_zone = {
            side: ("left" if index % 2 == 0 else "right") for index, side in enumerate(side_order)
        }

        zone_by_member = {}
        for member in members:
            member_id = member.member_id
            if member_id in explicit:
                zone_by_member[member_id] = explicit[member_id]
            else:
                side = legacy.get(member_id, "")
                zone_by_member[member_id] = fallback_zone.get(side, self.party_layout.default_zone)

        members = [m for m in members if zone_by_member[m.member_id] not in L.hidden_zones]
        overhead = [m for m in members if zone_by_member[m.member_id] in L.overhead_zones]
        if overhead:
            o_panels, o_texts, o_gauges = self._overhead_commands(overhead)
            panels.extend(o_panels)
            texts.extend(o_texts)
            gauges.extend(o_gauges)
            members = [m for m in members if zone_by_member[m.member_id] not in L.overhead_zones]
        if L.party_hud == "bottom_row":
            b_panels, b_texts, b_gauges = self._bottom_row_commands(members, focus_member_id)
            panels.extend(b_panels)
            texts.extend(b_texts)
            gauges.extend(b_gauges)
            return panels, texts, gauges, icons
        if L.party_hud == "side_list":
            s_panels, s_texts, s_gauges = self._side_list_commands(members, focus_member_id)
            panels.extend(s_panels)
            texts.extend(s_texts)
            gauges.extend(s_gauges)
            return panels, texts, gauges, icons

        available_height = max(1.0, L.virtual_height - L.timeline_y - 42.0 - L.margin)
        layout = self.party_layout.resolve(
            [x.member_id for x in members],
            zone_by_member=zone_by_member,
            focus_member_id=focus_member_id,
            available_height=available_height,
        )
        member_by_id = {x.member_id: x for x in members}

        for zone_layout in layout.zones:
            density = zone_layout.density
            row_height = self.party_layout.row_height(density)
            right = zone_layout.zone == "right"
            center = zone_layout.zone == "center"
            stacked = 0.0
            for member_id in zone_layout.visible_member_ids:
                member = member_by_id[member_id]
                if center:
                    x = (L.virtual_width - L.hud_panel_width) / 2
                elif right:
                    x = L.virtual_width - L.margin - L.hud_panel_width
                else:
                    x = L.margin

                # Stack upward from the lower battle HUD safe area; each row
                # advances by at least its own panel height so panels never overlap.
                base_y = L.virtual_height - L.margin - 8.0
                y = base_y - stacked

                resource_limit = self.party_layout.resource_limit(density)
                ordered_gauges = sorted(
                    member.gauges,
                    key=lambda g: (-int(getattr(g, "priority", 0)), g.order, g.resource_id),
                )
                selected = (
                    ordered_gauges if resource_limit is None else ordered_gauges[:resource_limit]
                )
                selected_ids = {g.resource_id for g in selected}
                selected = [g for g in member.gauges if g.resource_id in selected_ids]

                status_limit = self.party_layout.status_limit(density)
                selected_statuses = list(member.statuses)
                if status_limit is not None:
                    selected_statuses = selected_statuses[:status_limit]

                if density == "expanded":
                    height = max(24.0, 18.0 + len(selected) * L.hud_row_height)
                elif density == "compact":
                    height = max(20.0, 14.0 + len(selected) * 8.0)
                else:
                    height = 16.0

                panel_y = y - height
                stacked += max(row_height, height + 2.0)
                focused = (
                    self.polish.focus_member_emphasis
                    and focus_member_id is not None
                    and member.member_id == str(focus_member_id)
                )
                panel_role = f"hud:{density}:focus" if focused else f"hud:{density}"
                name_role = f"member_name:{density}:focus" if focused else f"member_name:{density}"
                panels.append(
                    BattleUiPanel(
                        f"hud:{member.member_id}",
                        x,
                        panel_y,
                        L.hud_panel_width,
                        height,
                        panel_role,
                        member.member_id,
                    )
                )
                texts.append(
                    BattleUiText(
                        self._name(member.member_id),
                        x + 4,
                        panel_y + 3,
                        name_role,
                        "left",
                        member.member_id,
                    )
                )

                gy = panel_y + (13 if density != "minimal" else 9)
                for gauge in selected:
                    mode = str(gauge.presentation)
                    if density == "minimal":
                        # Minimal density shows only the highest-priority resource
                        # with no redundant label/value unless the project uses a
                        # number-style resource.
                        if mode in {"number", "contextual"}:
                            texts.append(
                                BattleUiText(
                                    f"{gauge.current:g}",
                                    x + L.hud_panel_width - 4,
                                    panel_y + 3,
                                    f"resource_value:{mode}",
                                    "right",
                                    member.member_id,
                                )
                            )
                        else:
                            gauges.append(
                                BattleUiGaugeBar(
                                    member.member_id,
                                    gauge.resource_id,
                                    gauge.label,
                                    x + 38,
                                    panel_y + 6,
                                    max(8.0, L.hud_panel_width - 44),
                                    4.0,
                                    max(0.0, min(1.0, float(gauge.normalized))),
                                    float(gauge.current),
                                    float(gauge.maximum),
                                    mode,
                                    int(gauge.segments),
                                    gauge.icon_asset_id,
                                )
                            )
                        continue

                    if gauge.show_label and density == "expanded":
                        texts.append(
                            BattleUiText(
                                self._fit(gauge.label, 5),
                                x + 4,
                                gy,
                                "gauge_label",
                                "left",
                                member.member_id,
                            )
                        )

                    if mode in {"number", "contextual"}:
                        if gauge.show_value:
                            texts.append(
                                BattleUiText(
                                    f"{gauge.current:g}",
                                    x + L.hud_panel_width - 4,
                                    gy,
                                    f"resource_value:{mode}",
                                    "right",
                                    member.member_id,
                                )
                            )
                    else:
                        label_space = 30 if (gauge.show_label and density == "expanded") else 4
                        value_space = (
                            26
                            if (gauge.show_value and not gauge.compact and density == "expanded")
                            else 8
                        )
                        bar_x = x + label_space
                        bar_w = max(8.0, L.hud_panel_width - label_space - value_space)
                        gauges.append(
                            BattleUiGaugeBar(
                                member.member_id,
                                gauge.resource_id,
                                gauge.label,
                                bar_x,
                                gy,
                                bar_w,
                                5.0 if density == "expanded" else 4.0,
                                max(0.0, min(1.0, float(gauge.normalized))),
                                float(gauge.current),
                                float(gauge.maximum),
                                mode,
                                int(gauge.segments),
                                gauge.icon_asset_id,
                            )
                        )
                        if gauge.show_value and not gauge.compact and density == "expanded":
                            texts.append(
                                BattleUiText(
                                    f"{gauge.current:g}/{gauge.maximum:g}",
                                    x + L.hud_panel_width - 4,
                                    gy,
                                    "gauge_value",
                                    "right",
                                    member.member_id,
                                )
                            )
                    gy += L.hud_row_height if density == "expanded" else 8.0

                if density != "minimal":
                    ix = x + 4
                    iy = y - 8
                    for status in selected_statuses:
                        if status.icon_asset_id:
                            icons.append(
                                BattleUiIcon(
                                    status.icon_asset_id,
                                    ix,
                                    iy,
                                    "status",
                                    member.member_id,
                                    status.label,
                                )
                            )
                            ix += 10

            if zone_layout.overflow_count:
                if zone_layout.zone == "right":
                    ox = L.virtual_width - L.margin
                    align = "right"
                elif zone_layout.zone == "center":
                    ox = L.virtual_width / 2
                    align = "center"
                else:
                    ox = L.margin
                    align = "left"
                texts.append(
                    BattleUiText(
                        f"+{zone_layout.overflow_count}",
                        ox,
                        L.timeline_y + 31.0,
                        "hud_overflow",
                        align,
                        "",
                    )
                )
        return panels, texts, gauges, icons

    @staticmethod
    def _ranked_gauges(member, limit):
        ordered = sorted(
            member.gauges, key=lambda g: (-int(getattr(g, "priority", 0)), g.order, g.resource_id)
        )
        return [
            g for g in ordered if str(g.presentation) not in {"number", "contextual", "hidden"}
        ][:limit]

    def _bar(self, member_id, gauge, x, y, width, height):
        return BattleUiGaugeBar(
            member_id,
            gauge.resource_id,
            gauge.label,
            x,
            y,
            width,
            height,
            max(0.0, min(1.0, float(gauge.normalized))),
            float(gauge.current),
            float(gauge.maximum),
            str(gauge.presentation),
            int(gauge.segments),
            gauge.icon_asset_id,
        )

    # room an overhead label keeps: a line of state names (drawn by the runtime) over the name
    OVERHEAD_CAPTION = 8.0
    OVERHEAD_CHAR = 4.4  # virtual width of one character of a name

    def _combatant_boxes(self):
        """``member_id: (x, y, w, h)`` of every combatant's figure on screen (virtual pixels),
        with the strip under the feet where shield and weakness tiles stand."""
        boxes = {}
        for visual in self.scene.combatants:
            pos = (
                None
                if self._camera is None
                else self._anchor_screen(self._camera, visual.member_id)
            )
            if pos is None:
                continue
            body = float(self._member_heights.get(visual.member_id, 32.0))
            half = max(8.0, body * 0.32)
            boxes[visual.member_id] = (pos[0] - half, pos[1] - body, 2 * half, body + 9.0)
        return boxes

    def _overhead_commands(self, members):
        """Name (and, with ``overhead_bars``, the top-priority bar) over each member's sprite.
        A label never covers another combatant, another label or the turn bar: it moves up until
        it is clear, else below the feet row. ``overhead_labels`` keeps where each one went."""
        panels, texts, gauges = [], [], []
        L = self.layout
        camera = self._camera
        boxes = self._combatant_boxes()
        placed = []
        self.overhead_labels = {}

        def free(rect, own):
            x, y, w, h = rect
            if y < L.timeline_y + 24.0 or y + h > L.virtual_height:
                return False
            others = [b for k, b in boxes.items() if k != own] + placed
            return all(
                x + w <= bx or bx + bw <= x or y + h <= by or by + bh <= y
                for bx, by, bw, bh in others
            )

        for member in members:
            anchor = None if camera is None else self._anchor_screen(camera, member.member_id)
            if anchor is None:
                continue
            ax, ay = anchor
            top = ay - float(self._member_heights.get(member.member_id, 32.0))
            name = self._fit(self._name(member.member_id), 14)
            ranked = self._ranked_gauges(member, 1) if L.overhead_bars else ()
            states = " ".join(str(st.label or st.state_id) for st in member.statuses)[:30]
            width = max(
                44.0 if ranked else 0.0,
                len(name) * self.OVERHEAD_CHAR + 4.0,
                len(states) * 1.9,  # the state names over it (small type)
            )
            height = self.OVERHEAD_CAPTION + 9.0 + (5.0 if ranked else 0.0)
            home_x = ax - width / 2
            # (y, cost): over the head first, a little higher, else under the feet row (close to
            # its owner beats far above someone else's head)
            below = [(ay + 10.0 + i * 3.0, 24.0 + i * 3.0) for i in range(8)]
            if L.overhead_below:
                ys = [(cy, cost - 24.0) for cy, cost in below]
            else:
                base = top - height - 1.0
                ys = [(base - i * 3.0, i * 3.0) for i in range(30)] + below
            shifts = [0.0]
            reach = max(width, 36.0)  # a short name still steps clear of a whole figure
            for step in (0.35, 0.7, 1.05, 1.4):
                shifts += [-step * reach, step * reach]
            tries = sorted(
                ((cy, home_x + dx, cost + 1.2 * abs(dx)) for cy, cost in ys for dx in shifts),
                key=lambda t: t[2],
            )
            right = L.virtual_width - L.margin - width

            def clamp(cx, right=right):
                return max(L.margin, min(right, cx))

            y, x = next(
                (
                    (cy, clamp(cx))
                    for cy, cx, _cost in tries
                    if free((clamp(cx), cy, width, height), member.member_id)
                ),
                (ys[0][0], clamp(home_x)),
            )
            placed.append((x, y, width, height))
            name_y = y + self.OVERHEAD_CAPTION
            self.overhead_labels[member.member_id] = (x, y, width, height)
            cx = x + width / 2
            texts.append(
                BattleUiText(name, cx, name_y, "overhead_name", "center", member.member_id)
            )
            if ranked:
                gauges.append(
                    self._bar(member.member_id, ranked[0], cx - 22.0, name_y + 10.0, 44.0, 3.0)
                )
        return panels, texts, gauges

    @staticmethod
    def _chip(label):
        """A short status label: initials of a multi-word name, else the first three letters."""
        words = str(label).replace(".", " ").replace("_", " ").split()
        if len(words) > 1:
            return "".join(w[0] for w in words[:3]).upper()
        return (words[0] if words else "?")[:3].upper()

    def _side_list_commands(self, members, focus_member_id):
        """One panel per member down the party's edge, under the turn bar: name and status chips
        on top, then a ``label  current / maximum`` line with a thin bar per resource (pips
        resources, like boost points, draw as dots). Panels shrink their row count, never
        overlap, and never leave the screen."""
        panels, texts, gauges = [], [], []
        L = self.layout
        if not members:
            return panels, texts, gauges
        width = float(L.hud_panel_width)
        x = L.virtual_width - L.margin - width
        top = L.timeline_y + 24.0
        available = L.virtual_height - L.margin - top
        gap, header, row, pad = 2.0, 9.0, 10.0, 3.0
        ranked = {m.member_id: self._ranked_gauges(m, 4) for m in members}
        rows = 4
        while (
            rows > 1
            and sum(pad + header + row * min(rows, len(ranked[m.member_id])) for m in members)
            + gap * (len(members) - 1)
            > available
        ):
            rows -= 1
        y = top
        for member in members:
            shown = ranked[member.member_id][:rows]
            height = pad + header + row * len(shown)
            focused = focus_member_id is not None and member.member_id == str(focus_member_id)
            panels.append(
                BattleUiPanel(
                    f"hud:{member.member_id}",
                    x,
                    y,
                    width,
                    height,
                    "hud:side:focus" if focused else "hud:side",
                    member.member_id,
                )
            )
            chips = " ".join(self._chip(s.label or s.state_id) for s in member.statuses[:4])
            name_room = max(6, int((width - 8 - 4 * len(chips)) // 4.4))
            texts.append(
                BattleUiText(
                    self._fit(self._name(member.member_id), name_room),
                    x + 3,
                    y + 2,
                    "member_name:side:focus" if focused else "member_name:side",
                    "left",
                    member.member_id,
                )
            )
            if chips:
                texts.append(
                    BattleUiText(
                        chips, x + width - 3, y + 2, "status_chip", "right", member.member_id
                    )
                )
            gy = y + pad + header
            for gauge in shown:
                label = self._fit(gauge.label, 3)
                texts.append(
                    BattleUiText(label, x + 3, gy, "gauge_label", "left", member.member_id)
                )
                if str(gauge.presentation) in {"pips", "segmented_bar", "icon_stack"}:
                    gauges.append(
                        self._bar(member.member_id, gauge, x + 22, gy + 1.5, width - 28, 4.0)
                    )
                else:
                    value = f"{gauge.current:,.0f} / {gauge.maximum:,.0f}"
                    texts.append(
                        BattleUiText(
                            value, x + width - 3, gy, "side_value", "right", member.member_id
                        )
                    )
                    gauges.append(
                        self._bar(member.member_id, gauge, x + 3, gy + row - 3.0, width - 6, 1.6)
                    )
                gy += row
            y += height + gap
        return panels, texts, gauges

    def _bottom_row_commands(self, members, focus_member_id):
        """Compact party cells in one row along the bottom (name + up to two bars)."""
        panels, texts, gauges = [], [], []
        L = self.layout
        if not members:
            return panels, texts, gauges
        gap = 3.0
        count = len(members)
        width = min(120.0, (L.virtual_width - 2 * L.margin - gap * (count - 1)) / count)
        height = 24.0
        total = count * width + gap * (count - 1)
        x0 = L.virtual_width - L.margin - total  # anchored to the party's side (right)
        y = L.virtual_height - L.margin - height
        for index, member in enumerate(members):
            x = x0 + index * (width + gap)
            focused = focus_member_id is not None and member.member_id == str(focus_member_id)
            panels.append(
                BattleUiPanel(
                    f"hud:{member.member_id}",
                    x,
                    y,
                    width,
                    height,
                    "hud:compact:focus" if focused else "hud:compact",
                    member.member_id,
                )
            )
            texts.append(
                BattleUiText(
                    self._fit(self._name(member.member_id), int(width // 5)),
                    x + 3,
                    y + 2,
                    "member_name:compact:focus" if focused else "member_name:compact",
                    "left",
                    member.member_id,
                )
            )
            for row, gauge in enumerate(self._ranked_gauges(member, 2)):
                gauges.append(
                    self._bar(member.member_id, gauge, x + 3, y + 12 + row * 6, width - 6, 3.0)
                )
        return panels, texts, gauges

    def _action_menu_commands(self, menu):
        panels, texts, icons = [], [], []
        if menu is None:
            return panels, texts, icons
        if not isinstance(menu, BattleActionMenuView):
            raise TypeError("action_menu must be BattleActionMenuView")
        L, P = self.layout, self.polish
        if not L.command_counts and any(e.action_id.startswith("root:") for e in menu.entries):
            from dataclasses import replace

            menu = replace(  # the top-level commands show their names alone
                menu,
                entries=tuple(
                    replace(e, cost_text="") if e.action_id.startswith("root:") else e
                    for e in menu.entries
                ),
            )
        width = min(P.interaction_width, L.virtual_width - 2 * L.margin)
        # as wide as the longest row (name + cost) needs, so costs never run into names
        chars = max(
            (
                len(e.label) + 2 + (len(e.cost_text) + 2 if e.cost_text else 0)
                for e in menu.entries
            ),
            default=0,
        )
        # rows with an icon (a skill's ``icon_id``) start 8 layout units further right
        icon_pad = 8.0 if any(e.icon_asset_id for e in menu.entries) else 0.0
        wanted = min(
            width, max(88.0, min(150.0, chars * 3.8 + 2 * P.interaction_padding + icon_pad))
        )
        # Keep the menu between left/right HUD columns when there is room for it.
        hud_gap = L.virtual_width - 2 * (L.margin + L.hud_panel_width) - 2 * L.margin
        if hud_gap >= self.MIN_MENU_WIDTH:
            width = min(width, max(hud_gap, wanted))
        x = (L.virtual_width - width) / 2
        if L.party_hud == "side_list":
            # between the far side's combatants and the party's, left of the party's list
            width = min(width, wanted)
            left = L.margin
            right = L.virtual_width - L.margin - L.hud_panel_width - L.margin
            centre = L.virtual_width / 2
            for visual in self.scene.combatants:
                # a combatant also owns its overhead name/bar (>= 44 wide) and shield row
                half = max(float(self._member_heights.get(visual.member_id, 32.0)) / 2, 24.0) + 6.0
                pos = (
                    None
                    if self._camera is None
                    else self._anchor_screen(self._camera, visual.member_id)
                )
                px = visual.anchor.x if pos is None else pos[0]
                if px <= centre:
                    left = max(left, px + half)
                elif px < right:
                    right = min(right, px - half)
            if right - left >= self.MIN_MENU_WIDTH:
                width = min(width, right - left)
                x = (left + right - width) / 2
            else:  # no gap: the lower-left corner, under the far side
                x = L.margin
        header_rows = (1 if menu.categories else 0) + (1 if menu.query else 0)
        body_rows = max(1, len(menu.entries))
        height = (
            2 * P.interaction_padding
            + header_rows * P.interaction_header_height
            + body_rows * P.interaction_row_height
            + P.interaction_footer_height
        )
        y = max(
            L.timeline_y + 28.0,
            L.virtual_height - L.margin - P.interaction_bottom_gap - height,
        )
        if L.party_hud == "side_list" and self._camera is not None:
            # Kept clear: the acting member and every enemy (name and bar above, sprite, shield
            # row under the feet), whatever ``menu_over_stage`` says. Only the other party
            # members may sit behind the (see-through) menu.
            boxes = []
            boxed = []
            for visual in self.scene.combatants:
                pos = self._anchor_screen(self._camera, visual.member_id)
                if pos is None:
                    continue
                if self._stands_right(visual.member_id) and visual.member_id != self._focus:
                    continue
                body = float(self._member_heights.get(visual.member_id, 32.0))
                half = max(body / 2, 24.0)
                boxes.append((pos[0] - half, pos[1] - body - 22.0, 2 * half, body + 22.0 + 30.0))
                boxed.append(visual)
                label = self.overhead_labels.get(visual.member_id)
                if label is not None:  # a name that moved up to stay clear stays uncovered
                    boxes.append(label)
                    boxed.append(visual)

            def clear(cx, cy, w):
                return all(
                    cx + w <= bx - 2 or bx + bw <= cx - 2 or cy + height <= by or by + bh <= cy
                    for bx, by, bw, bh in boxes
                )

            hero_left = L.virtual_width - 2 * L.margin - L.hud_panel_width
            # first choice: beside the acting member, on the side facing the enemies
            lefts = [box[0] for box, v in zip(boxes, boxed) if self._stands_right(v.member_id)]
            actor_at = (
                None if self._focus is None else self._anchor_screen(self._camera, self._focus)
            )
            found = None
            if lefts and actor_at is not None:
                # fixed spot: right beside the acting member, narrower rather than moved
                top_y = L.timeline_y + 28.0
                low_y = L.virtual_height - 3.0 - height
                mid_y = min(low_y, max(top_y, actor_at[1] - height / 2 - 14.0))
                for w in dict.fromkeys((width, 120.0, 104.0, 92.0, 84.0)):
                    w = min(w, width)
                    cx = min(lefts) - 4.0 - w
                    for cy in dict.fromkeys((mid_y, low_y, top_y)):
                        if cx >= L.margin and clear(cx, cy, w):
                            found = (cx, cy, w)
                            break
                    if found:
                        break
            for w in dict.fromkeys((width, min(width, 120.0), min(width, 104.0))):
                if found:
                    break
                xs = []
                ys = [y, L.timeline_y + 28.0]
                if lefts and actor_at is not None:
                    xs.append(min(lefts) - 4.0 - w)
                    ys.insert(0, max(L.timeline_y + 28.0, actor_at[1] - height / 2 - 14.0))
                xs += [x, L.margin]
                xs += [bx + bw + 4.0 for bx, _, bw, _ in boxes]
                ys += [by + bh + 2.0 for _, by, _, bh in boxes]
                for cy in dict.fromkeys(ys):
                    if cy + height > L.virtual_height - 3.0 or cy < L.timeline_y + 24.0:
                        continue
                    for cx in dict.fromkeys(xs):
                        if L.margin <= cx and cx + w <= hero_left and clear(cx, cy, w):
                            found = (cx, cy, w)
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                x, y, width = found
        anchor = None
        if (
            L.action_menu_placement == "actor"
            and L.party_hud != "side_list"
            and self._focus is not None
            and self._camera is not None
        ):
            anchor = self._anchor_screen(self._camera, self._focus)
        if anchor is not None:
            # Beside the acting member's group, on the side facing the stage
            # centre, so the menu never covers other party members; as wide as its longest row
            # (name + cost) needs, within 88..150 virtual pixels.
            width = min(width, wanted)
            ax, ay = anchor
            body = float(self._member_heights.get(self._focus, 32.0))
            right_side = ax > L.virtual_width / 2
            group = []
            for visual in self.scene.combatants:
                if (visual.anchor.x > L.virtual_width / 2) != right_side:
                    continue
                gx, _ = self._camera.world_to_screen(visual.anchor.x, visual.anchor.y)
                half = float(self._member_heights.get(visual.member_id, 32.0)) / 2
                group.append(gx - half if right_side else gx + half)
            edge = (
                (min(group) if right_side else max(group))
                if group
                else (ax - body / 2 if right_side else ax + body / 2)
            )
            # never across the stage centre: the other side's combatants stay visible
            centre = L.virtual_width / 2
            room = (edge - 6 - (centre + 2)) if right_side else ((centre - 2) - (edge + 6))
            if room >= self.MIN_MENU_WIDTH:
                width = min(width, room)
            x = edge - 6 - width if right_side else edge + 6
            x = max(L.margin, min(L.virtual_width - L.margin - width, x))
            limit = (
                L.virtual_height
                - L.margin
                - (28.0 if L.party_hud == "bottom_row" else 0.0)
                - height
            )
            y = max(L.timeline_y + 28.0, min(limit, ay - body / 2 - height / 2))
        if (
            L.action_menu_placement == "actor_bottom_right"
            and self._focus is not None
            and self._camera is not None
        ):
            spot = self._anchor_screen(self._camera, self._focus)
            if spot is not None:
                # always at the acting member's lower right, touching the figure, so it is
                # plain who acts; it may cover others (even a HUD panel when there is no room)
                body = float(self._member_heights.get(self._focus, 32.0))
                width = min(width, wanted)
                half = max(8.0, body * 0.32)
                x = spot[0] + half + 2.0
                room = L.virtual_width - 2.0 - x
                if room >= 80.0:  # narrower rather than over the one who acts
                    width = min(width, room)
                else:  # no room on the right at all: the lower left instead
                    x = spot[0] - half - 2.0 - width
                y = spot[1] - body * 0.5
                x = max(L.margin, min(L.virtual_width - 2.0 - width, x))
                y = max(L.timeline_y + 24.0, min(L.virtual_height - 2.0 - height, y))
        role = "interaction:float" if L.party_hud == "side_list" else "interaction:action_menu"
        panels.append(BattleUiPanel("action_menu", x, y, width, height, role))

        ty = y + P.interaction_padding
        if menu.categories:
            category_text = "  ".join(
                f"[{value}]" if value == menu.active_category else value
                for value in menu.categories
            )
            texts.append(
                BattleUiText(
                    category_text, x + P.interaction_padding, ty, "action_categories", "left"
                )
            )
            ty += P.interaction_header_height

        if menu.query:
            texts.append(
                BattleUiText(
                    f"Filter: {menu.query}", x + P.interaction_padding, ty, "action_filter", "left"
                )
            )
            ty += P.interaction_header_height

        if not menu.entries:
            texts.append(
                BattleUiText(P.empty_label, x + width / 2, ty + 3, "action_empty", "center")
            )
        else:
            for index, entry in enumerate(menu.entries):
                selected = index == menu.cursor
                if L.row_buttons:
                    button = (
                        "button:selected"
                        if selected
                        else ("button" if entry.enabled else "button:disabled")
                    )
                    panels.append(
                        BattleUiPanel(
                            f"button:{index}",
                            x + P.interaction_padding - 3,
                            ty - 2,
                            width - 2 * (P.interaction_padding - 3),
                            P.interaction_row_height,
                            button,
                        )
                    )
                role = (
                    "action_selected"
                    if selected
                    else ("action_entry" if entry.enabled else "action_disabled")
                )
                prefix = P.selected_prefix if selected else P.idle_prefix
                label = entry.label
                if icon_pad:  # the icon took room from the name: never run into the cost
                    cost_room = (len(entry.cost_text) + 2) * 3.8 if entry.cost_text else 0.0
                    fit = int((width - 2 * P.interaction_padding - icon_pad - cost_room) / 3.8)
                    fit -= len(prefix)
                    if fit >= 4 and len(label) > fit:
                        label = label[: fit - 2].rstrip() + ".."
                texts.append(
                    BattleUiText(
                        prefix + label,
                        x + P.interaction_padding + 2 + icon_pad,
                        ty,
                        role,
                        "left",
                    )
                )
                if entry.cost_text:
                    texts.append(
                        BattleUiText(
                            entry.cost_text,
                            x + width - P.interaction_padding,
                            ty,
                            "action_cost" if entry.enabled else "action_cost_disabled",
                            "right",
                        )
                    )
                if entry.icon_asset_id:
                    icons.append(
                        BattleUiIcon(
                            entry.icon_asset_id,
                            x + P.interaction_padding - 4,
                            ty - 1,
                            "action",
                            "",
                            entry.label,
                        )
                    )
                ty += P.interaction_row_height

            selected = menu.selected
            if selected is not None:
                footer = selected.detail
                footer_role = "action_detail"
                if not selected.enabled and selected.disabled_reason:
                    footer = selected.disabled_reason
                    footer_role = "action_disabled_reason"
                if footer:
                    room = width - 2 * P.interaction_padding - (14.0 if menu.page_count > 1 else 0)
                    fit = max(4, int(room // 4.4))
                    if len(footer) > fit:  # never wider than the menu
                        footer = footer[: fit - 2].rstrip() + ".."
                    texts.append(
                        BattleUiText(
                            footer,
                            x + P.interaction_padding,
                            y + height - P.interaction_footer_height,
                            footer_role,
                            "left",
                        )
                    )

        if menu.page_count > 1:
            texts.append(
                BattleUiText(
                    f"{menu.page + 1}{P.page_separator}{menu.page_count}",
                    x + width - P.interaction_padding,
                    y + height - P.interaction_footer_height,
                    "action_page",
                    "right",
                )
            )
        return panels, texts, icons

    def _workflow_commands(self, workflow):
        panels, texts, icons = [], [], []
        if workflow is None:
            return panels, texts, icons
        if not isinstance(workflow, BattleActionWorkflowView):
            raise TypeError("action_workflow must be BattleActionWorkflowView")
        L, P = self.layout, self.polish
        width = min(P.interaction_width + 10.0, L.virtual_width - 2 * L.margin)
        x = (L.virtual_width - width) / 2
        option_rows = max(1, len(workflow.options))
        height = (
            2 * P.interaction_padding
            + 2 * P.interaction_header_height
            + option_rows * P.interaction_row_height
            + P.interaction_footer_height
        )
        y = max(
            L.timeline_y + 28.0,
            L.virtual_height - L.margin - P.interaction_bottom_gap - height,
        )
        panels.append(
            BattleUiPanel("action_workflow", x, y, width, height, "interaction:workflow")
        )
        texts.append(
            BattleUiText(
                workflow.label,
                x + P.interaction_padding,
                y + P.interaction_padding,
                "workflow_title",
                "left",
            )
        )

        if workflow.complete:
            texts.append(
                BattleUiText(
                    "Ready",
                    x + width / 2,
                    y + P.interaction_padding + P.interaction_header_height + 4,
                    "workflow_complete",
                    "center",
                )
            )
            return panels, texts, icons

        step = workflow.step
        step_y = y + P.interaction_padding + P.interaction_header_height
        texts.append(
            BattleUiText(
                f"{workflow.step_index + 1}{P.page_separator}{workflow.step_count}  {step.label}",
                x + P.interaction_padding,
                step_y,
                "workflow_step",
                "left",
            )
        )
        selected = set()
        for value in workflow.selections:
            if value.step_id == step.step_id:
                selected.update(value.option_ids)

        oy = step_y + P.interaction_header_height
        for option in workflow.options:
            is_selected = option.option_id in selected
            mark = P.selected_option_prefix if is_selected else P.idle_prefix
            if is_selected:
                role = "workflow_option_selected"
            else:
                role = "workflow_option" if option.enabled else "workflow_option_disabled"
            texts.append(
                BattleUiText(mark + option.label, x + P.interaction_padding + 3, oy, role, "left")
            )
            if option.icon_asset_id:
                icons.append(
                    BattleUiIcon(
                        option.icon_asset_id, x + 1, oy, "workflow_option", "", option.label
                    )
                )
            oy += P.interaction_row_height
        return panels, texts, icons

    def _stands_right(self, member_id):
        """True for a member standing on the right half of the stage (the party's side by the
        usual staging); the turn bar only uses it to tint the tiles."""
        try:
            visual = self.scene.visual_for(member_id)
        except KeyError:
            return True
        return visual.anchor.x > self.layout.virtual_width / 2

    def _timeline_commands(self, timeline):
        panels, texts = [], []
        if timeline is None:
            return panels, texts
        L = self.layout
        slot, padding = 32.0, 9.0
        capacity = max(1, int((L.virtual_width - 2 * L.margin - 2 * padding) // slot))
        turns = tuple(timeline.turns)[:capacity]
        width = 2 * padding + slot * len(turns)
        panels.append(
            BattleUiPanel(
                "timeline", (L.virtual_width - width) / 2, L.timeline_y, width, 24.0, "timeline"
            )
        )
        x = (L.virtual_width - width) / 2 + padding + slot / 2
        max_chars = max(3, int(slot // self.TIMELINE_CHAR_WIDTH))
        for entry in turns:
            # a tile per turn, tinted by the side of the field the member stands on
            ally = self._stands_right(entry.member_id)
            kind = "current" if entry.is_current else ("ally" if ally else "enemy")
            panels.append(
                BattleUiPanel(
                    f"turn:{entry.member_id}",
                    x - slot / 2 + 1.0,
                    L.timeline_y + 1.0,
                    slot - 2.0,
                    22.0,
                    f"timeline_tile:{kind}",
                    entry.member_id,
                )
            )
            role = "timeline_current" if entry.is_current else "timeline_entry"
            texts.append(
                BattleUiText(
                    self._fit(self._name(entry.member_id), max_chars),
                    x,
                    L.timeline_y + 7,
                    role,
                    "center",
                    entry.member_id,
                )
            )
            if timeline.scheduler_mode == "continuous":
                texts.append(
                    BattleUiText(
                        f"{entry.ready_time:.1f}",
                        x,
                        L.timeline_y + 16,
                        "timeline_time",
                        "center",
                        entry.member_id,
                    )
                )
            x += slot
        for i, cast in enumerate(timeline.casts):
            texts.append(
                BattleUiText(
                    f"{cast.actor_id}: {cast.ability_id} {int(round(cast.progress * 100))}%",
                    L.margin,
                    L.timeline_y + 26 + i * 9,
                    "cast",
                    "left",
                    cast.actor_id,
                )
            )
        return panels, texts

    def _feedback_commands(self, camera, feedback):
        texts = []
        if feedback is None:
            return texts
        for value in feedback.values:
            pos = self._anchor_screen(camera, value.target_id)
            if pos is None:
                continue
            x, y = pos
            lift = 10.0 + 12.0 * min(1.0, value.age / max(value.duration, 1e-9))
            sign = "+" if value.kind == BattleValueKind.HEAL and value.value >= 0 else ""
            texts.append(
                BattleUiText(
                    f"{sign}{value.value:g}",
                    x,
                    y - lift,
                    f"value:{value.kind.value}",
                    "center",
                    value.target_id,
                )
            )
        per_target = {}
        for label in feedback.labels:
            pos = self._anchor_screen(camera, label.target_id)
            if pos is None:
                continue
            offset = per_target.get(label.target_id, 0)
            per_target[label.target_id] = offset + 1
            texts.append(
                BattleUiText(
                    label.label,
                    pos[0],
                    pos[1] - 24.0 - offset * 8.0,
                    "feedback_label",
                    "center",
                    label.target_id,
                )
            )
        return texts

    def _result_commands(self, result):
        panels, texts = [], []
        if result is None or not result.finished:
            return panels, texts
        L = self.layout
        x = (L.virtual_width - L.result_panel_width) / 2
        y = (L.virtual_height - L.result_panel_height) / 2
        panels.append(
            BattleUiPanel(
                "battle_result", x, y, L.result_panel_width, L.result_panel_height, "result"
            )
        )
        texts.append(
            BattleUiText(result.headline, L.virtual_width / 2, y + 12, "result_headline", "center")
        )
        line_y = y + 28
        for reward in result.currencies:
            texts.append(
                BattleUiText(
                    f"{reward.label}  +{reward.amount:g}", x + 12, line_y, "reward", "left"
                )
            )
            line_y += 9
        for reward in result.items:
            texts.append(
                BattleUiText(f"{reward.label}  x{reward.amount}", x + 12, line_y, "reward", "left")
            )
            line_y += 9
        for reward in result.progression:
            suffix = (
                f"  Rank {reward.old_rank} → {reward.new_rank}"
                if reward.new_rank != reward.old_rank
                else ""
            )
            texts.append(
                BattleUiText(
                    f"{reward.label}  +{reward.new_total - reward.old_total:g}{suffix}",
                    x + 12,
                    line_y,
                    "progression",
                    "left",
                )
            )
            line_y += 9
        return panels, texts

    def compose(
        self,
        camera: Camera2D,
        battle_frame: BattlePresentationFrame,
        *,
        hud_members=(),
        timeline: BattleTurnTimelineView | None = None,
        feedback: BattleFeedbackRuntime | None = None,
        camera_feedback: BattleCameraFeedbackFrame | None = None,
        result: BattleResultView | None = None,
        action_menu: BattleActionMenuView | None = None,
        action_workflow: BattleActionWorkflowView | None = None,
        side_by_member=None,
        placement_by_member=None,
        focus_member_id=None,
        display_names=None,
        member_heights=None,
    ):
        """``display_names`` maps member ids to the labels shown in HUD and timeline;
        ``member_heights`` (logical sprite heights) positions overhead bars and the
        actor-anchored action menu."""
        self._display_names = {str(k): str(v) for k, v in dict(display_names or {}).items()}
        self._member_heights = {str(k): float(v) for k, v in dict(member_heights or {}).items()}
        self._camera = camera
        self._focus = None if focus_member_id is None else str(focus_member_id)
        if not isinstance(camera, Camera2D):
            raise TypeError("camera must be Camera2D")
        if not isinstance(battle_frame, BattlePresentationFrame):
            raise TypeError("battle_frame must be BattlePresentationFrame")
        if battle_frame.scene_id != self.scene.scene_id:
            raise ValueError("battle frame scene mismatch")
        hud_members = tuple(hud_members)
        if any(not isinstance(x, BattleHudMember) for x in hud_members):
            raise TypeError("hud_members must contain BattleHudMember")
        side_by_member = dict(side_by_member or {})

        panels, texts, gauges, icons = self._hud_commands(
            hud_members, side_by_member, placement_by_member, focus_member_id
        )
        pw, tw, iw = self._workflow_commands(action_workflow)
        panels.extend(pw)
        texts.extend(tw)
        icons.extend(iw)
        if action_workflow is None:
            pa, ta, ia = self._action_menu_commands(action_menu)
            panels.extend(pa)
            texts.extend(ta)
            icons.extend(ia)
        p2, t2 = self._timeline_commands(timeline)
        panels.extend(p2)
        texts.extend(t2)
        texts.extend(self._feedback_commands(camera, feedback))
        p3, t3 = self._result_commands(result)
        panels.extend(p3)
        texts.extend(t3)

        markers = ()
        screen_fx = ()
        if camera_feedback is not None:
            markers = tuple(
                BattleUiMarker(x.member_id, x.screen_x, x.screen_y, x.primary)
                for x in camera_feedback.targets
            )
            screen_fx = tuple(camera_feedback.screen_fx)

        if feedback is None:
            vfx = ()
        else:
            vfx = tuple(
                sorted(
                    feedback.vfx,
                    key=lambda item: (
                        int(dict(item.payload.get("staging", {}) or {}).get("layer", 0)),
                        -int(dict(item.payload.get("staging", {}) or {}).get("priority", 0)),
                        item.sequence,
                    ),
                )
            )
        return BattleUiFrame(
            self.scene.scene_id,
            battle_frame.background_asset_id,
            tuple(battle_frame.combatant_draws),
            tuple(panels),
            tuple(texts),
            tuple(gauges),
            tuple(icons),
            markers,
            vfx,
            screen_fx,
        )
