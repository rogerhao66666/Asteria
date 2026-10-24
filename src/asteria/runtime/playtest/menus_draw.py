"""Controls and rebinding (ENG-15), and the crafting, list, settings, quest and shop
screens as drawn."""

from __future__ import annotations

from asteria.runtime.game_menus import (
    achievement_rows,
    bestiary_rows,
    quest_rows,
)
from asteria.runtime.input_map import InputActionTracker

from .support import (  # noqa: F401 - the names the moved methods use
    BESTIARY_TAG_KINDS,
    FIELD_BODY_HEIGHT,
    WALK_PATTERN_SEQUENCE,
    WALK_ROW_BY_FACING,
    _load_manifest,
    field_player_render_size,
    walking_pattern_index,
    walking_row_index,
)


class MenusDrawMixin:
    # -- controls / rebinding (ENG-15) ------------------------------------------------------------
    def _controls_input(self, events):
        from asteria.runtime.input_map import InputBinding

        menu = self.controls_menu
        for event in events:
            if menu.capturing is not None:
                if event.type == self.pg.KEYDOWN and event.key == self.pg.K_ESCAPE:
                    menu.cancel_capture()
                elif event.type == self.pg.KEYDOWN:
                    menu.capture(InputBinding("key", self.pg.key.name(event.key)))
                    self._apply_controls()
                elif event.type == getattr(self.pg, "JOYBUTTONDOWN", -1):
                    menu.capture(InputBinding("gamepad_button", str(event.button)))
                    self._apply_controls()
                continue
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key == self.pg.K_ESCAPE:
                self.settings.save(self._settings_path())
                self._ui_mode = "settings"
            elif event.key in (self.pg.K_UP, self.pg.K_w):
                menu.move(-1)
            elif event.key in (self.pg.K_DOWN, self.pg.K_s):
                menu.move(1)
            elif event.key in (self.pg.K_RETURN, self.pg.K_SPACE):
                menu.select()
                if menu.capturing is None:  # reset all
                    self._apply_controls()
            elif event.key in (self.pg.K_BACKSPACE, self.pg.K_DELETE):
                menu.reset(menu.rows()[menu.row][0])
                self._apply_controls()

    def _apply_controls(self):
        from asteria.runtime.input_rebinding import effective_input_map

        self.settings.input_overrides = dict(self.controls_menu.overrides)
        self.input = InputActionTracker(
            effective_input_map(self.project.input_map, self.settings.input_overrides)
        )
        self.settings.save(self._settings_path())

    def _draw_controls(self):
        self._draw_backdrop()
        menu = self.controls_menu
        self.panel((60, 30, self.width - 120, self.height - 60))
        tr = self.game.tr
        title = tr("controls.title", "Controls")
        self.text(title, self.width / 2, 44, size=32, color=(255, 220, 124), center=True)
        for i, (action, bindings) in enumerate(menu.rows()):
            y = 92 + i * 30
            selected = i == menu.row
            color = (255, 226, 129) if selected else (235, 238, 245)
            self.menu_row(menu.action_name(action), 90, y, selected=selected, size=21, color=color)
            self.text(bindings, self.width / 2, y, size=21, color=(170, 210, 240))
        hint = menu.message or tr(
            "controls.hint", "Enter: rebind   Backspace: reset action   Esc: save and back"
        )
        self.text(
            hint, self.width / 2, self.height - 58, size=19, color=(255, 226, 129), center=True
        )

    def _draw_crafting(self):
        screen = self._crafting_screen
        self._draw_backdrop()
        if screen is None:
            return
        self.panel((60, 40, self.width - 120, self.height - 80))
        tr = self.game.tr
        title = tr("pause.crafting", "Crafting") + (
            f" — {screen.station.replace('_', ' ').title()}" if screen.station else ""
        )
        self.text(title, 90, 54, size=30, color=(255, 220, 124))
        rows = screen.rows()
        if not rows:
            empty = tr("crafting.none", "No known recipes here.")
            self.text(empty, 90, 110, size=22, color=(170, 210, 240))
        y = 104
        for i, row in enumerate(rows):
            if y > self.height - 150:
                break
            selected = i == screen.index
            color = (
                (255, 226, 129)
                if selected
                else (235, 238, 245)
                if row.craftable
                else (130, 135, 150)
            )
            self.menu_row(
                f"{row.name}  ->  {row.outputs}", 90, y, selected=selected, size=22, color=color
            )
            y += 26
            materials = "   ".join(f"{name} {have}/{need}" for name, need, have in row.materials)
            self.text(
                materials,
                120,
                y,
                size=17,
                color=(170, 210, 240) if row.craftable else (200, 130, 130),
            )
            y += 30
        hidden = screen.undiscovered()
        if hidden:
            self.text(
                tr("crafting.hidden", "??? {count} recipe(s) not yet discovered", count=hidden),
                90,
                self.height - 128,
                size=18,
                color=(150, 155, 175),
            )
        if screen.message:
            self.text(screen.message, 90, self.height - 100, size=20, color=(255, 220, 124))
        self.text(
            tr("crafting.hint", "Up/Down: select   Enter: craft   Esc: back"),
            90,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )

    def _draw_list_screen(self, kind):
        self._draw_backdrop()
        self.panel((60, 40, self.width - 120, self.height - 80))
        tr = self.game.tr
        line_icons = []  # an icon per line (achievements may carry one)
        if kind == "achievements":
            rows = achievement_rows(self.game)
            by_name = {
                self.game.name_of(a): a.icon_id
                for a in self.project.rpg_database.achievements.values()
            }
            line_icons = [by_name.get(name, "") for name, _description, _unlocked in rows]
            done = sum(1 for r in rows if r[2])
            self.text(
                tr(
                    "achievements.title",
                    "Achievements  {done}/{count}",
                    done=done,
                    count=len(rows),
                ),
                self.width / 2,
                56,
                size=30,
                color=(255, 220, 124),
                center=True,
            )
            lines = [
                (
                    (("[x] " if unlocked else "[ ] ") + name),
                    description,
                    (130, 220, 150) if unlocked else (150, 155, 175),
                )
                for name, description, unlocked in rows
            ]
        else:
            rows = bestiary_rows(self.game)
            seen = sum(1 for r in rows if r[1])
            self.text(
                tr("bestiary.title", "Bestiary  {seen}/{count} seen", seen=seen, count=len(rows)),
                self.width / 2,
                56,
                size=30,
                color=(255, 220, 124),
                center=True,
            )
            lines = [
                (name, self._bestiary_detail(row), (235, 238, 245) if row[1] else (150, 155, 175))
                for row in rows
                for name in (row[0],)
            ]
        if not lines:
            self.text(
                tr("status.empty", "Nothing here yet."), 90, 110, size=22, color=(170, 210, 240)
            )
        self._list_scroll = min(self._list_scroll, max(0, len(lines) - 1))
        y = 104
        shift = 30 if any(line_icons) else 0
        for number, (title, detail, color) in enumerate(lines[self._list_scroll :]):
            if y > self.height - 110:
                break
            index = self._list_scroll + number
            if index < len(line_icons) and line_icons[index]:
                self._draw_icon(line_icons[index], 90, y - 2, 24)
            self.text(title, 90 + shift, y, size=22, color=color)
            y += 24
            for part in detail.split("\n") if detail else ():
                self.text(part, 120, y, size=17, color=(170, 210, 240))
                y += 22
            y += 6
        self.text(
            tr("list.hint", "Up/Down: scroll   Enter / Esc: back"),
            self.width - 360,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )

    def _resource_labels(self):
        """Resource id -> the short label the battle HUD gives it (``vitality`` -> ``HP``)."""
        labels = {}
        library = getattr(self.project, "battle_presentation_library", None)
        for key in library.ids("hud") if library is not None else ():
            for style in getattr(library.require("hud", key), "resources", ()):
                labels.setdefault(style.resource_id, style.label or style.resource_id)
        return labels

    def _bestiary_detail(self, row):
        """The lines under a bestiary entry: counts; weaknesses and resources once one fell;
        the drops that really fell."""
        _name, seen, defeated, captured, tags, resources, drops = row
        if not seen:
            return ""
        tr = self.game.tr
        lines = [
            tr(
                "bestiary.counts",
                "seen {seen}   defeated {defeated}   captured {captured}",
                seen=seen,
                defeated=defeated,
                captured=captured,
            )
        ]
        if defeated:
            labels = self._resource_labels()
            known = [f"{labels.get(r, r)} {v:,.0f}" for r, v in resources]
            groups = {}
            for tag in tags:
                kind, _, what = tag.partition(".")
                groups.setdefault(kind, []).append(what.replace("_", " "))
            for kind, names in sorted(groups.items()):  # weak / resist...: the kind is drawn
                word = tr(f"bestiary.tag.{kind}", kind) if kind in BESTIARY_TAG_KINDS else kind
                known.append(f"{word}: {', '.join(names)}")
            lines.append("   ".join(known) or tr("bestiary.nothing_special", "nothing special"))
        else:
            lines.append(tr("bestiary.unknown", "Defeat one to learn its weaknesses and health."))
        if drops:
            found = ", ".join(f"{n} x{t}" for n, t in drops)
            lines.append(tr("bestiary.drops", "Drops: {items}", items=found))
        else:
            lines.append(tr("bestiary.no_drops", "Drops: none seen yet"))
        return "\n".join(lines)

    def _language_name(self):
        """The chosen locale as its own table calls it (``language.name``), else its code."""
        localizer = self.game.localizer
        return localizer.tr("language.name", localizer.locale)

    def _draw_settings(self):
        self._draw_backdrop()
        cursor = self._settings_menu
        tall = max(260, 120 + len(cursor.options) * 38)  # every row inside the panel
        x, y = self.width / 2 - 220, self.height / 2 - tall / 2
        self.panel((x, y, 440, tall))
        tr = self.game.tr
        title = tr("pause.settings", "Settings")
        self.text(title, self.width / 2, y + 18, size=34, color=(255, 220, 124), center=True)
        for i, (key, label) in enumerate(cursor.labels(tr)):
            selected = i == cursor.index
            color = (255, 226, 129) if selected else (235, 238, 245)
            self.menu_row(label, x + 40, y + 76 + i * 38, selected=selected, size=24, color=color)
            if key == "language":
                value = self._language_name()
            else:
                value = self.settings.value_text(key, tr)
            if value:
                self.text(
                    f"< {value} >" if selected else value,
                    x + 300,
                    y + 76 + i * 38,
                    size=24,
                    color=color,
                )
        self.text(
            tr("settings.hint", "Left/Right: change   Esc: save and back"),
            self.width / 2,
            y + tall - 24,
            size=16,
            color=(170, 210, 240),
            center=True,
        )

    def _draw_backdrop(self, base="field"):
        if base == "battle":
            self._battle_presentation.draw()  # the canonical battle screen as it was left
        else:
            self._draw_field(False)
        shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        shade.fill((5, 8, 16, 170))
        self.screen.blit(shade, (0, 0))

    def _draw_overlay_menu(self, title, cursor, base="field"):
        self._draw_backdrop(base)
        height = 90 + 34 * len(cursor.options)
        shift = 30 if cursor.icons else 0  # room for the rows' icons: the panel grows with it
        x, y = self.width / 2 - 170 - shift / 2, self.height / 2 - height / 2
        self.panel((x, y, 340 + shift, height))
        self.text(title, self.width / 2, y + 18, size=34, color=(255, 220, 124), center=True)
        for i, (option_id, label) in enumerate(cursor.labels(self.game.tr)):
            selected = i == cursor.index
            if option_id in cursor.icons:
                self._draw_icon(cursor.icons[option_id], round(x + 36), round(y + 68 + i * 34), 26)
            self.menu_row(
                label,
                x + 40 + shift,
                y + 70 + i * 34,
                selected=selected,
                size=24,
                color=(255, 226, 129) if selected else (235, 238, 245),
            )
        if self.message and self.pg.time.get_ticks() < self.message_until:
            self.text(
                self.message,
                self.width / 2,
                y + height + 14,
                size=20,
                color=(175, 235, 255),
                center=True,
            )

    def _draw_quests(self):
        self._draw_backdrop()
        self.panel((60, 40, self.width - 120, self.height - 80))
        tr = self.game.tr
        title = tr("pause.quests", "Quest Log")
        self.text(title, self.width / 2, 56, size=32, color=(255, 220, 124), center=True)
        rows = quest_rows(self.game)
        if not rows:
            self.text(tr("quests.none", "No quests yet."), 90, 110, size=22, color=(170, 210, 240))
        y = 104
        colors = {
            "active": (235, 238, 245),
            "completed": (130, 220, 150),
            "failed": (230, 120, 120),
        }
        for row in rows:
            if y > self.height - 110:
                break
            icon = self.project.rpg_database.quests[row.quest_id].icon_id
            if icon:
                self._draw_icon(icon, 90, y - 2, 24)
            status = tr(f"quests.status.{row.status}", row.status)  # the status is an id
            self.text(
                f"{row.name}  [{status}]",
                90 + (30 if icon else 0),
                y,
                size=24,
                color=colors[row.status],
            )
            y += 30
            for description, value, required, done in row.objectives:
                self.text(
                    f"{'[x]' if done else '[ ]'} {description}  {value}/{required}",
                    120,
                    y,
                    size=19,
                    color=(170, 210, 240),
                )
                y += 24
            y += 8
        self.text(
            tr("quests.hint", "Enter / Esc: back"),
            self.width - 260,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )

    def _draw_shop(self):
        screen = self._shop_screen
        self._draw_backdrop()
        if screen is None or screen.shop is None:
            return
        self.panel((60, 40, self.width - 120, self.height - 80))
        shop_icon = screen.shop.icon_id
        if shop_icon:
            self._draw_icon(shop_icon, 90, 50, 32)
        self.text(
            self.game.name_of(screen.shop),
            90 + (40 if shop_icon else 0),
            54,
            size=30,
            color=(255, 220, 124),
        )
        tr = self.game.tr
        for i, tab in enumerate(("buy", "sell")):
            self.text(
                tr(f"shop.{tab}", tab.title()),
                self.width - 300 + i * 100,
                60,
                size=24,
                color=(255, 226, 129) if screen.tab == tab else (130, 140, 160),
            )
        self.text(tr("shop.item", "Item"), 90, 104, size=19, color=(170, 210, 240))
        self.text(tr("shop.price", "Price"), 420, 104, size=19, color=(170, 210, 240))
        self.text(tr("shop.stock", "Stock"), 640, 104, size=19, color=(170, 210, 240))
        self.text(tr("shop.owned", "Owned"), 740, 104, size=19, color=(170, 210, 240))
        from asteria.runtime.menu_icons import record_icon_id

        rows = screen.rows()
        icons = [record_icon_id(self.project, "item", r.item_id) for r in rows]
        name_x = 90 + (30 if any(icons) else 0)
        # a long list scrolls with the cursor (D61: a shop of 38 wares), "n/total" above it
        fit = max(1, (self.height - 130 - 134) // 30 + 1)
        first = min(max(0, screen.index - fit // 2), max(0, len(rows) - fit))
        if len(rows) > fit:
            where = f"{min(screen.index, len(rows) - 1) + 1}/{len(rows)}"
            self.text(where, 840, 104, size=19, color=(170, 210, 240))
        for i, row in enumerate(rows):
            if i < first:
                continue
            y = 134 + (i - first) * 30
            if y > self.height - 130:
                break
            color = (
                (255, 226, 129)
                if i == screen.index
                else (235, 238, 245)
                if row.available
                else (120, 125, 140)
            )
            if i == screen.index:
                self.menu_mark(72, y, size=22, color=color)
            self._draw_icon(icons[i], 90, y - 2)
            self.text(row.name, name_x, y, size=22, color=color)
            self.text(row.price, 420, y, size=22, color=color)
            self.text(row.stock, 640, y, size=22, color=color)
            self.text(str(row.owned), 740, y, size=22, color=color)
        self.text(screen.wallet(), 90, self.height - 100, size=20, color=(175, 235, 255))
        if screen.message:
            self.text(
                screen.message, self.width / 2, self.height - 100, size=20, color=(255, 220, 124)
            )
        self.text(
            tr(
                "shop.hint",
                "Up/Down: select   Left/Right: buy/sell   Enter: confirm   Esc: leave",
            ),
            90,
            self.height - 72,
            size=18,
            color=(170, 210, 240),
        )
