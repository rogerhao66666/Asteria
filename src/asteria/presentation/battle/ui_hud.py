"""The battle HUD's commands: each side's columns, gauges, portraits, overhead labels and lists."""

from __future__ import annotations

from asteria.presentation.battle.ui_parts import (
    BAR_MIN,
    BOTTOM_ROW_HEIGHT,
    BattleUiGaugeBar,
    BattleUiIcon,
    BattleUiPanel,
    BattleUiText,
    _gap,
)
from asteria.presentation.text.cells import cells, cut


class HudCompositionMixin:
    """The battle HUD's commands: columns, gauges, portraits, overhead labels and lists."""

    def _hud_commands(
        self, members, side_by_member, placement_by_member=None, focus_member_id=None
    ):
        """The member HUD (panels, overhead labels): laid out again only when something it
        reads changed since the last frame, else the last frame's commands."""
        L = self.layout
        anchors = None
        if L.overhead_zones and self._camera is not None:  # overhead labels follow the figures
            to_screen = self._camera.world_to_screen
            anchors = tuple(
                (v.member_id, to_screen(v.anchor.x, v.anchor.y)) for v in self.scene.combatants
            )
        key = (
            tuple(members),
            dict(side_by_member or {}),
            dict(placement_by_member or {}),
            focus_member_id,
            self._display_names,
            self._member_heights,
            anchors,
            L,
            self._member_extents,
            self._overhead_hidden,
            None if self._camera is None else self._camera.zoom,
            self.party_layout,
            self.polish,
            self._portraits,
        )
        cached = self._hud_cache
        if cached is not None and cached[0] == key:
            self.overhead_labels = dict(cached[2])
            return tuple(list(x) for x in cached[1])
        out = self._hud_layout(*key[:4])
        self._hud_cache = (key, tuple(tuple(x) for x in out), dict(self.overhead_labels))
        return out

    def _hud_layout(self, members, side_by_member, placement_by_member, focus_member_id):
        panels, texts, gauges, icons, portraits = [], [], [], [], []
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
        if overhead and self._overhead_hidden:  # the camera is zoomed in: names wait
            self.overhead_labels = {}
            members = [m for m in members if zone_by_member[m.member_id] not in L.overhead_zones]
        elif overhead:
            o_panels, o_texts, o_gauges = self._overhead_commands(overhead)
            panels.extend(o_panels)
            texts.extend(o_texts)
            gauges.extend(o_gauges)
            members = [m for m in members if zone_by_member[m.member_id] not in L.overhead_zones]
        if L.party_hud == "bottom_row":
            b_panels, b_texts, b_gauges, b_portraits = self._bottom_row_commands(
                members, focus_member_id
            )
            panels.extend(b_panels)
            texts.extend(b_texts)
            gauges.extend(b_gauges)
            return panels, texts, gauges, icons, b_portraits
        if L.party_hud == "side_list":
            s_panels, s_texts, s_gauges, s_portraits = self._side_list_commands(
                members, focus_member_id
            )
            panels.extend(s_panels)
            texts.extend(s_texts)
            gauges.extend(s_gauges)
            return panels, texts, gauges, icons, s_portraits

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
            shared = self._column_portrait_side(zone_layout, member_by_id, available_height)
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

                selected = self._column_gauges(member, density)

                status_limit = self.party_layout.status_limit(density)
                selected_statuses = list(member.statuses)
                if status_limit is not None:
                    selected_statuses = selected_statuses[:status_limit]

                height = self._column_height(len(selected), density)
                # the member's portrait, one size down the column: beside the rows (they move
                # aside and narrow, never under BAR_MIN) or over them (the card grows taller)
                room = min(self._column_room(selected, density), shared)
                side, picture = self._card_portrait(member.member_id, height, room)
                cx, cw, lift, height = self._portrait_rows(side, x, L.hud_panel_width, height)

                panel_y = y - height
                stacked += max(row_height, height + 2.0)
                if side:
                    card = (x, panel_y, L.hud_panel_width, height)
                    portraits.append(self._portrait(member.member_id, picture, side, card, 4.0))
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
                name = self._name(member.member_id)
                if side:  # the rows are narrower: the name keeps within them
                    name = self._fit(name, max(4, int((cw - 8) // 4.4)))
                texts.append(
                    BattleUiText(
                        name,
                        cx + 4,
                        panel_y + lift + 3,
                        name_role,
                        "left",
                        member.member_id,
                    )
                )

                gy = panel_y + lift + (13 if density != "minimal" else 9)
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
                                    cx + cw - 4,
                                    panel_y + lift + 3,
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
                                    cx + 38,
                                    panel_y + lift + 6,
                                    max(8.0, cw - 44),
                                    4.0,
                                    max(0.0, min(1.0, float(gauge.normalized))),
                                    float(gauge.current),
                                    float(gauge.maximum),
                                    mode,
                                    int(gauge.segments),
                                    gauge.icon_asset_id,
                                    getattr(gauge, "color", ""),
                                )
                            )
                        continue

                    if gauge.show_label and density == "expanded":
                        texts.append(
                            BattleUiText(
                                self._fit(gauge.label, 5),
                                cx + 4,
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
                                    cx + cw - 4,
                                    gy,
                                    f"resource_value:{mode}",
                                    "right",
                                    member.member_id,
                                )
                            )
                    else:
                        label_space = self._label_space(gauge, density)
                        value_space = self._value_space(gauge, density)
                        bar_x = cx + label_space
                        bar_w = max(8.0, cw - label_space - value_space)
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
                                getattr(gauge, "color", ""),
                            )
                        )
                        if gauge.show_value and not gauge.compact and density == "expanded":
                            texts.append(
                                BattleUiText(
                                    f"{gauge.current:g}/{gauge.maximum:g}",
                                    cx + cw - 4,
                                    gy,
                                    "gauge_value",
                                    "right",
                                    member.member_id,
                                )
                            )
                    gy += L.hud_row_height if density == "expanded" else 8.0

                if density != "minimal":
                    ix = cx + 4
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
        return panels, texts, gauges, icons, portraits

    def _column_height(self, rows, density):
        """A column HUD card's height for ``rows`` resource rows at ``density``."""
        if density == "expanded":
            return max(24.0, 18.0 + rows * self.layout.hud_row_height)
        if density == "compact":
            return max(20.0, 14.0 + rows * 8.0)
        return 16.0

    @staticmethod
    def _label_space(gauge, density):
        """Room a column card keeps before a resource's bar (for its label when it shows one)."""
        return 30 if (gauge.show_label and density == "expanded") else 4

    @staticmethod
    def _value_space(gauge, density):
        """Room a column card keeps after a resource's bar (for its numbers when it shows
        them)."""
        return 26 if (gauge.show_value and not gauge.compact and density == "expanded") else 8

    def _column_gauges(self, member, density):
        """The resources a column card shows at ``density``: those of highest priority, in the
        member's own order."""
        limit = self.party_layout.resource_limit(density)
        ordered = sorted(
            member.gauges,
            key=lambda g: (-int(getattr(g, "priority", 0)), g.order, g.resource_id),
        )
        chosen = {g.resource_id for g in (ordered if limit is None else ordered[:limit])}
        return [g for g in member.gauges if g.resource_id in chosen]

    def _column_room(self, selected, density):
        """The most a portrait may take of a column card's width: beside the rows, what leaves
        their labels, numbers and a BAR_MIN bar; over them, the card's width inside."""
        if self.layout.hud_portraits == "above":
            return self.layout.hud_panel_width - 8.0
        widest = 44.0  # a minimal card: its one bar starts 38 in and ends 6 short
        if selected and density != "minimal":
            widest = max(
                self._label_space(g, density) + self._value_space(g, density) for g in selected
            )
        return self.layout.hud_panel_width - 2.0 - BAR_MIN - widest

    def _column_portrait_side(self, zone_layout, member_by_id, available):
        """The side the portraits of one HUD column share: the smallest any of its cards has
        room for - over the rows, out of the height the column has left in ``available``,
        shared. 0 when none shows one."""
        density = zone_layout.density
        ids = zone_layout.visible_member_ids
        owners = [m for m in ids if self._portraits.get(m)]
        if not owners or self.layout.hud_portraits == "off":
            return 0.0
        share = float("inf")
        if self.layout.hud_portraits == "above":
            row_height = self.party_layout.row_height(density)
            used = 0.0
            for member_id in ids:
                rows = len(self._column_gauges(member_by_id[member_id], density))
                used += max(row_height, self._column_height(rows, density) + 2.0)
            share = (available - used) / len(owners) - 2.0
        sides = []
        for member_id in owners:
            selected = self._column_gauges(member_by_id[member_id], density)
            height = self._column_height(len(selected), density)
            room = min(self._column_room(selected, density), share)
            sides.append(self._card_portrait(member_id, height, room)[0])
        return min((side for side in sides if side), default=0.0)

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
            getattr(gauge, "color", ""),
        )

    def _combatant_boxes(self):
        """``member_id: (x, y, w, h)`` of every combatant's figure on screen (virtual pixels),
        with the strip under the feet where shield and weakness tiles stand."""
        boxes = {}
        zoom = 1.0 if self._camera is None else float(self._camera.zoom)
        for visual in self.scene.combatants:
            pos = (
                None
                if self._camera is None
                else self._anchor_screen(self._camera, visual.member_id)
            )
            if pos is None:
                continue
            extent = self._member_extents.get(visual.member_id)
            if extent is not None:  # the figure's visible pixels, every frame of it, as drawn
                left, top, right, bottom = (v * zoom for v in extent)
                bottom = max(bottom, 0.0) + 9.0
                boxes[visual.member_id] = (pos[0] + left, pos[1] + top, right - left, bottom - top)
                continue
            body = float(self._member_heights.get(visual.member_id, 32.0)) * zoom
            half = max(8.0, body * 0.32)
            boxes[visual.member_id] = (pos[0] - half, pos[1] - body, 2 * half, body + 9.0)
        return boxes

    def _overhead_commands(self, members):
        """Name (and, with ``overhead_bars``, the top-priority bar) over each member's sprite.
        A label never covers a combatant (its own too), another label or the turn bar, and it
        stays by its owner: just over the head, a little higher or to the side, else just under
        the feet row, else beside the head. Where none of those is clear the name is not shown -
        never somewhere far from its owner. ``overhead_labels`` keeps where each shown one went."""
        panels, texts, gauges = [], [], []
        L = self.layout
        camera = self._camera
        boxes = self._combatant_boxes()
        placed = []
        self.overhead_labels = {}
        floor, margin = L.timeline_y + 24.0, L.margin  # a label stays under the turn bar

        for member in members:
            anchor = None if camera is None else self._anchor_screen(camera, member.member_id)
            if anchor is None:
                continue
            ax, ay = anchor
            own = boxes.get(member.member_id)
            top = (
                own[1]
                if own is not None
                else ay - float(self._member_heights.get(member.member_id, 32.0))
            )
            name = self._fit(self._name(member.member_id), 14)
            ranked = self._ranked_gauges(member, 1) if L.overhead_bars else ()
            states = cut(" ".join(str(st.label or st.state_id) for st in member.statuses), 30)
            width = max(
                44.0 if ranked else 0.0,
                cells(name) * self.OVERHEAD_CHAR + 4.0,
                cells(states) * 1.9,  # the state names over it (small type)
            )
            height = self.OVERHEAD_CAPTION + 9.0 + (5.0 if ranked else 0.0)
            home_x = ax - width / 2
            # (y, cost): over the head first, a little higher, else under the feet row (close to
            # its owner beats far above someone else's head)
            feet = own[1] + own[3] if own is not None else ay + 9.0
            below = [(feet + 1.0 + i * 3.0, 24.0 + i * 3.0) for i in range(4)]
            if L.overhead_below:
                ys = [(cy, cost - 24.0) for cy, cost in below]
            else:
                base = top - height - 1.0
                ys = [(base - i * 3.0, i * 3.0) for i in range(5)] + below
            shifts = [0.0]
            for step in (0.25, 0.5):  # a little to the side, still over its owner
                shifts += [-step * width, step * width]
            spots = [(cy, home_x + dx, cost + 1.2 * abs(dx)) for cy, cost in ys for dx in shifts]
            if own is not None:  # beside the head, touching the figure's side, last
                bx, by, bw, bh = own
                for i in range(4):
                    cy = by + i * 3.0
                    if cy + height > by + bh / 2:
                        break
                    spots += [(cy, bx - width - 2.0, 40.0 + i), (cy, bx + bw + 2.0, 41.0 + i)]
            tries = sorted(spots, key=lambda t: t[2])
            right = L.virtual_width - L.margin - width
            # the first (cheapest) spot that is on screen, by its owner, and covers no figure
            # (its own too) and no other label
            others = list(boxes.values()) + placed
            spot = None
            for cy, cx, _cost in tries:
                if cy < floor or cy + height > L.virtual_height:
                    continue
                cx = max(margin, min(right, cx))
                if own is not None and _gap((cx, cy, width, height), own) > 12.0:
                    continue  # pushed along by the screen edge, away from its owner
                if all(
                    cx + width <= bx or bx + bw <= cx or cy + height <= by or by + bh <= cy
                    for bx, by, bw, bh in others
                ):
                    spot = (cy, cx)
                    break
            if spot is None:
                continue  # no clear place by its owner: no name rather than one far away
            y, x = spot
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
        """A short status label: initials of a multi-word name, else the first three letters
        (the first two characters of a Chinese or Japanese name)."""
        words = str(label).replace(".", " ").replace("_", " ").split()
        if len(words) > 1:
            return cut("".join(w[0] for w in words[:3]).upper(), 4)
        word = words[0] if words else "?"
        return word[:3].upper() if word.isascii() else cut(word, 4)

    def _side_list_commands(self, members, focus_member_id):
        """One panel per member down the party's edge, under the turn bar: name and status chips
        on top, then a ``label  current / maximum`` line with a thin bar per resource (pips
        resources, like boost points, draw as dots). Panels shrink their row count, never
        overlap, and never leave the screen. A member's portrait stands at its panel's left or
        right end (the rows narrow) or over its rows (the panel grows into the room the list has
        left; the row count is what it would be without portraits)."""
        panels, texts, gauges, portraits = [], [], [], []
        L = self.layout
        if not members:
            return panels, texts, gauges, portraits
        width = float(L.hud_panel_width)
        x = L.virtual_width - L.margin - width
        top = L.timeline_y + 24.0
        available = L.virtual_height - L.margin - top
        gap, header, row, pad = 2.0, 9.0, 10.0, 3.0
        ranked = {m.member_id: self._ranked_gauges(m, 4) for m in members}

        def plan(rows, cap=None):
            """``(height, side, picture)`` of each member's panel with ``rows`` resource rows
            and a portrait of at most ``cap``."""
            out = []
            for member in members:
                shown = ranked[member.member_id][:rows]
                base = pad + header + row * len(shown)
                side, picture = 0.0, ""
                if self._portraits.get(member.member_id):  # rows measured only for a portrait
                    if L.hud_portraits == "above":
                        room = width - 6.0
                    else:
                        room = width - 2.0 - self._side_rows_need(shown)
                    side, picture = self._card_portrait(
                        member.member_id, base, room if cap is None else min(room, cap)
                    )
                out.append((self._portrait_rows(side, x, width, base)[3], side, picture))
            return out

        def total(cards):
            return sum(c[0] for c in cards) + gap * (len(members) - 1)

        rows = 4  # as many as fit without portraits: a portrait never takes another's rows
        while rows > 1 and total(plan(rows, 0.0)) > available:
            rows -= 1
        cap = None  # beside the rows a portrait never makes its panel taller
        if L.hud_portraits == "above":  # over them: the room the list has left, shared
            owners = sum(1 for m in members if self._portraits.get(m.member_id))
            cap = (available - total(plan(rows, 0.0))) / max(1, owners) - 2.0
        cards = plan(rows, cap)
        sides = [c[1] for c in cards if c[1]]
        if sides and min(sides) < max(sides):  # one size down the list: the smallest any has
            cards = plan(rows, min(sides))
        y = top
        for member, (height, side, picture) in zip(members, cards):
            shown = ranked[member.member_id][:rows]
            cx, cw, lift, _ = self._portrait_rows(side, x, width, pad + header + row * len(shown))
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
            if side:
                card = (x, y, width, height)
                portraits.append(self._portrait(member.member_id, picture, side, card, 3.0))
            chips = " ".join(self._chip(s.label or s.state_id) for s in member.statuses[:4])
            name_room = max(6, int((cw - 8 - 4 * cells(chips)) // 4.4))
            texts.append(
                BattleUiText(
                    self._fit(self._name(member.member_id), name_room),
                    cx + 3,
                    y + lift + 2,
                    "member_name:side:focus" if focused else "member_name:side",
                    "left",
                    member.member_id,
                )
            )
            if chips:
                texts.append(
                    BattleUiText(
                        chips, cx + cw - 3, y + lift + 2, "status_chip", "right", member.member_id
                    )
                )
            gy = y + lift + pad + header
            for gauge in shown:
                label = self._fit(gauge.label, 3)
                texts.append(
                    BattleUiText(label, cx + 3, gy, "gauge_label", "left", member.member_id)
                )
                if str(gauge.presentation) in {"pips", "segmented_bar", "icon_stack"}:
                    gauges.append(
                        self._bar(member.member_id, gauge, cx + 22, gy + 1.5, cw - 28, 4.0)
                    )
                else:
                    value = f"{gauge.current:,.0f} / {gauge.maximum:,.0f}"
                    texts.append(
                        BattleUiText(
                            value, cx + cw - 3, gy, "side_value", "right", member.member_id
                        )
                    )
                    gauges.append(
                        self._bar(member.member_id, gauge, cx + 3, gy + row - 3.0, cw - 6, 1.6)
                    )
                gy += row
            y += height + gap
        return panels, texts, gauges, portraits

    def _side_rows_need(self, shown):
        """How wide a side-list panel's rows must stay beside a portrait: six letters of the
        name, and each resource line's label with its numbers at their maximum (so the portrait
        keeps its size while they change) or with its pips."""
        need = 6 + 6 * 4.4
        for gauge in shown:
            label = self._drawn_width(self._fit(gauge.label, 3), "gauge_label")
            if str(gauge.presentation) in {"pips", "segmented_bar", "icon_stack"}:
                need = max(need, 28 + BAR_MIN)
            else:
                value = f"{gauge.maximum:,.0f} / {gauge.maximum:,.0f}"
                need = max(need, 10 + label + self._drawn_width(value, "side_value"))
        return need

    def _bottom_row_commands(self, members, focus_member_id):
        """Compact party cells in one row along the bottom (name + up to two bars). A member's
        portrait stands at its cell's left or right end, or over its rows (the cell grows up,
        ``bottom_row_height``)."""
        panels, texts, gauges, portraits = [], [], [], []
        L = self.layout
        if not members:
            return panels, texts, gauges, portraits
        gap = 3.0
        count = len(members)
        width = min(120.0, (L.virtual_width - 2 * L.margin - gap * (count - 1)) / count)
        total = count * width + gap * (count - 1)
        x0 = L.virtual_width - L.margin - total  # anchored to the party's side (right)
        if L.hud_portraits == "above":  # as wide as the cell; the row stays in the lower half
            room = min(width - 6.0, L.virtual_height / 2 - BOTTOM_ROW_HEIGHT - 2.0)
        else:
            room = width - 8.0 - BAR_MIN
        for index, member in enumerate(members):
            x = x0 + index * (width + gap)
            side, picture = self._card_portrait(member.member_id, BOTTOM_ROW_HEIGHT, room)
            cx, cw, lift, height = self._portrait_rows(side, x, width, BOTTOM_ROW_HEIGHT)
            y = L.virtual_height - L.margin - height
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
            if side:
                card = (x, y, width, height)
                portraits.append(self._portrait(member.member_id, picture, side, card, 3.0))
            texts.append(
                BattleUiText(
                    self._fit(self._name(member.member_id), int(cw // 5)),
                    cx + 3,
                    y + lift + 2,
                    "member_name:compact:focus" if focused else "member_name:compact",
                    "left",
                    member.member_id,
                )
            )
            for row, gauge in enumerate(self._ranked_gauges(member, 2)):
                gauges.append(
                    self._bar(
                        member.member_id, gauge, cx + 3, y + lift + 12 + row * 6, cw - 6, 3.0
                    )
                )
        return panels, texts, gauges, portraits

    def _clear_of_portraits(self, x, y, width, height, least):
        """``(x, y, width)`` for a ``width`` x ``height`` panel wanted at ``(x, y)`` (the command
        menu, its help box, the action workflow) that covers no party card's portrait: where it
        was when it covers none, else the nearest clear place - narrower on the portraits' side
        (down to ``least`` wide) rather than moved far. Where no place is clear it stays."""
        boxes = list(self.portrait_boxes.values())

        def clear(cx, cy, w):
            return all(
                cx + w <= bx - 1 or bx + bw + 1 <= cx or cy + height <= by - 1 or by + bh + 1 <= cy
                for bx, by, bw, bh in boxes
            )

        if clear(x, y, width):
            return x, y, width
        L = self.layout
        ys = {y}
        for _bx, by, _bw, bh in boxes:  # just above or just below a portrait
            ys.update((by - 1.0 - height, by + bh + 1.0))
        spots = []  # (cost, x, y, width)
        for cy in ys:
            if cy < L.timeline_y + 24.0 or cy + height > L.virtual_height - 2.0:
                continue
            fits = [(x, width)]
            for bx, _by, bw, _bh in boxes:
                fits += [
                    (x, bx - 1.0 - x),  # ends before the portrait
                    (bx + bw + 1.0, x + width - bx - bw - 1.0),  # starts after it
                    (bx - 1.0 - width, width),  # moved to its left
                    (bx + bw + 1.0, width),  # moved to its right
                ]
            for cx, w in fits:
                if least <= w <= width and cx >= 2.0 and cx + w <= L.virtual_width - 2.0:
                    if clear(cx, cy, w):
                        spots.append((2.0 * abs(cy - y) + abs(cx - x) + width - w, cx, cy, w))
        if not spots:
            return x, y, width
        _, cx, cy, w = min(spots)
        return cx, cy, w
