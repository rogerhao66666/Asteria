"""The action menu's commands: its layout, help box and the action workflow."""

from __future__ import annotations

from asteria.presentation.battle.action_menu import BattleActionMenuView
from asteria.presentation.battle.action_workflow import BattleActionWorkflowView
from asteria.presentation.battle.ui_parts import (
    _MENU_LAYOUT_FIELDS,
    MENU_COST_GAP,
    BattleUiIcon,
    BattleUiPanel,
    BattleUiText,
    _category_strip,
    _mark_gutter,
    _marked,
)
from asteria.presentation.text.cells import cells, cut, wrap


class ActionMenuCompositionMixin:
    """The action menu's commands: its layout, help box and the action workflow."""

    def _action_menu_commands(self, menu):
        """The command menu: laid out again only when the menu, the stage or a label it keeps
        clear of changed since the last frame, else the last frame's commands."""
        if menu is None:
            return [], [], []
        if not isinstance(menu, BattleActionMenuView):
            raise TypeError("action_menu must be BattleActionMenuView")
        camera = self._camera
        stage = None
        if camera is not None:
            stage = tuple(
                camera.world_to_screen(v.anchor.x, v.anchor.y) for v in self.scene.combatants
            )
        key = (
            tuple(getattr(menu, name) for name in _MENU_LAYOUT_FIELDS),
            self._focus,
            self._member_heights,
            self.overhead_labels,
            self.scene.combatants,
            stage,
            self.layout,
            self.polish,
            self._category_names,
            self._tr("battle.menu.filter", "Filter: {query}"),  # the language of its own words
            self.text_width,
            self.portrait_boxes,  # a new dict each frame: the kept key is never changed in place
        )
        cached = self._menu_cache
        if cached is not None and cached[0] == key:
            return tuple(list(x) for x in cached[1])
        out = self._action_menu_layout(menu)
        key = key[:3] + (dict(self.overhead_labels),) + key[4:]
        self._menu_cache = (key, tuple(tuple(x) for x in out))
        return out

    def _action_menu_layout(self, menu):
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
        # as wide as the longest row (name + cost) needs, so costs never run into names:
        # measured as the backend draws them, else estimated
        gutter = _mark_gutter(P.selected_prefix, P.idle_prefix)
        if self.text_width is not None:
            units = max((self._row_units(e) + 2 + gutter for e in menu.entries), default=0)
        else:
            chars = max(
                (
                    cells(e.label) + 2 + (cells(e.cost_text) + 2 if e.cost_text else 0)
                    for e in menu.entries
                ),
                default=0,
            )
            units = chars * 3.8
        # rows with an icon (a skill's ``icon_id``) start 8 layout units further right
        icon_pad = 8.0 if any(e.icon_asset_id for e in menu.entries) else 0.0
        wanted = min(width, max(88.0, min(150.0, units + 2 * P.interaction_padding + icon_pad)))
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
        # it may cover a HUD panel, never a portrait on one
        x, y, width = self._clear_of_portraits(x, y, width, height, min(width, 80.0))
        role = "interaction:float" if L.party_hud == "side_list" else "interaction:action_menu"
        panels.append(BattleUiPanel("action_menu", x, y, width, height, role))

        ty = y + P.interaction_padding
        if menu.categories:
            category_text = _category_strip(
                menu.categories,
                menu.active_category,
                width - 2 * P.interaction_padding,
                self._category_names,
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
                    self._tr("battle.menu.filter", "Filter: {query}", query=menu.query),
                    x + P.interaction_padding,
                    ty,
                    "action_filter",
                    "left",
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
                gutter = _mark_gutter(P.selected_prefix, P.idle_prefix)
                label = entry.label
                if self.text_width is not None:  # measured: never into the cost
                    room = width - 2 * P.interaction_padding - 2 - icon_pad - gutter
                    if entry.cost_text:
                        room -= MENU_COST_GAP + self._drawn_width(entry.cost_text, "action_cost")
                    label = self._fit_width(label, room)
                elif icon_pad:  # the icon took room from the name: never run into the cost
                    cost_room = (cells(entry.cost_text) + 2) * 3.8 if entry.cost_text else 0.0
                    fit = int((width - 2 * P.interaction_padding - icon_pad - cost_room) / 3.8)
                    fit -= round(gutter / 3.8)
                    if cells(label) > fit:  # a crowded row keeps a letter and ".."
                        label = cut(label, max(1, fit - 2)).rstrip() + ".."
                left = x + P.interaction_padding + 2 + icon_pad
                texts.extend(_marked(prefix, label, left, gutter, ty, role))
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
                    # inside the row's frame, clear of its border and level in the row (on the
                    # border, the selection frame ran through the icon)
                    icons.append(
                        BattleUiIcon(
                            entry.icon_asset_id,
                            x + P.interaction_padding - 1,
                            ty - 2 + (P.interaction_row_height - 8.0) / 2,
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
                room = width - 2 * P.interaction_padding - (14.0 if menu.page_count > 1 else 0)
                fit = max(4, int(room // 4.4))
                skill_text = footer_role == "action_detail" and selected.category != "Command"
                if footer and cells(footer) > fit and skill_text:
                    # a skill's whole description: a help box over the menu, words wrapped
                    help_panels, help_texts = self._help_box(footer, x, y, width, role)
                    panels += help_panels
                    texts += help_texts
                    footer = ""
                if footer:
                    if cells(footer) > fit:  # never wider than the menu
                        footer = cut(footer, fit - 2).rstrip() + ".."
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

    def _help_lines(self, text, width):
        """``text`` wrapped for a help box ``width`` wide (three lines at most), and the box's
        height."""
        P = self.polish
        per_line = max(8, int((width - 2 * P.interaction_padding) // 3.4))
        lines = wrap(text, per_line)  # at spaces, and between Chinese / Japanese characters
        if len(lines) > 3:
            lines = lines[:3]
            lines[2] = cut(lines[2], per_line - 2).rstrip() + ".."
        return lines, 2 * P.interaction_padding + len(lines) * P.interaction_header_height

    def _help_box(self, text, menu_x, menu_y, menu_width, role):
        """A panel over the action menu holding ``text`` word-wrapped (three lines at most),
        its right edge on the menu's."""
        L, P = self.layout, self.polish
        width = min(L.virtual_width - 2 * L.margin, max(menu_width * 1.7, menu_width + 60.0))
        lines, height = self._help_lines(text, width)
        x = max(L.margin, min(menu_x + menu_width - width, L.virtual_width - L.margin - width))
        y = max(L.margin, menu_y - height - 3.0)
        x, y, narrow = self._clear_of_portraits(x, y, width, height, min(width, menu_width))
        if narrow != width:  # narrower beside a portrait: the words wrap again
            width = narrow
            lines, height = self._help_lines(text, width)
            y = max(L.margin, menu_y - height - 3.0)
            x, y, _ = self._clear_of_portraits(x, y, width, height, width)
        panels = [BattleUiPanel("action_help", x, y, width, height, role)]
        texts = [
            BattleUiText(
                value,
                x + P.interaction_padding,
                y + P.interaction_padding + i * P.interaction_header_height,
                "action_detail",
                "left",
            )
            for i, value in enumerate(lines)
        ]
        return panels, texts

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
        x, y, width = self._clear_of_portraits(x, y, width, height, min(width, 120.0))
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
                    self._tr("battle.workflow.ready", "Ready"),
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
        gutter = _mark_gutter(P.selected_option_prefix, P.idle_prefix)
        for option in workflow.options:
            is_selected = option.option_id in selected
            mark = P.selected_option_prefix if is_selected else P.idle_prefix
            if is_selected:
                role = "workflow_option_selected"
            else:
                role = "workflow_option" if option.enabled else "workflow_option_disabled"
            left = x + P.interaction_padding + 3
            texts.extend(_marked(mark, option.label, left, gutter, oy, role))
            if option.icon_asset_id:
                icons.append(
                    BattleUiIcon(
                        option.icon_asset_id, x + 1, oy, "workflow_option", "", option.label
                    )
                )
            oy += P.interaction_row_height
        return panels, texts, icons
