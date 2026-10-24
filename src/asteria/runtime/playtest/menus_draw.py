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

# the menus' own colours (a menu theme or a layout element may give others, U2)
TITLE, PICKED, TEXT, MUTED = (255, 220, 124), (255, 226, 129), (235, 238, 245), (170, 210, 240)
GREY, LACKING, DIM = (130, 135, 150), (200, 130, 130), (120, 125, 140)


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
        c = self.menu_canvas("controls")
        self._draw_backdrop(canvas=c)
        menu = self.controls_menu
        c.panel("frame", (60, 30, self.width - 120, self.height - 60))
        tr = self.game.tr
        title = tr("controls.title", "Controls")
        c.text(
            "title", title, self.width / 2, 44, size=32, color=c.tone("title", TITLE), center=True
        )
        rows = menu.rows()
        at = c.place("options", (90, 92, self.width - 180, len(rows) * 30), 30)
        size = c.size("options", 21)
        for i, (action, bindings) in enumerate(rows):
            y = at.y(92) + i * at.row
            selected = i == menu.row
            color = (
                c.tone("selected", PICKED)
                if selected
                else c.color("options", c.tone("text", TEXT))
            )
            name = menu.action_name(action)
            self.menu_row(name, at.x(90), y, selected=selected, size=size, color=color)
            self.text(bindings, at.x(self.width / 2), y, size=size, color=c.tone("muted", MUTED))
        hint = menu.message or tr(
            "controls.hint", "Enter: rebind   Backspace: reset action   Esc: save and back"
        )
        c.text("hint", hint, self.width / 2, self.height - 58, size=19, color=PICKED, center=True)
        c.finish()

    def _draw_crafting(self):
        screen = self._crafting_screen
        station = screen.station if screen is not None else ""
        c = self.menu_canvas("crafting", {"station.name": station.replace("_", " ").title()})
        self._draw_backdrop(canvas=c)
        if screen is None:
            return
        c.panel("frame", (60, 40, self.width - 120, self.height - 80))
        tr = self.game.tr
        title = tr("pause.crafting", "Crafting") + (
            f" — {screen.station.replace('_', ' ').title()}" if screen.station else ""
        )
        c.text("title", title, 90, 54, size=30, color=c.tone("title", TITLE))
        rows = screen.rows()
        if not rows:
            empty = tr("crafting.none", "No known recipes here.")
            c.text("empty", empty, 90, 110, size=22, color=c.tone("muted", MUTED))
        at = c.place("rows", (90, 104, self.width - 180, self.height - 150 - 104), 56)
        y = at.y(104)
        for i, row in enumerate(rows):
            if y > at.bottom:
                break
            selected = i == screen.index
            normal = c.color("rows", c.tone("text", TEXT))
            color = c.tone("selected", PICKED) if selected else normal if row.craftable else GREY
            name = f"{row.name}  ->  {row.outputs}"
            self.menu_row(
                name, at.x(90), y, selected=selected, size=c.size("rows", 22), color=color
            )
            y += 26
            materials = "   ".join(f"{name} {have}/{need}" for name, need, have in row.materials)
            muted = c.tone("muted", MUTED)
            self.text(materials, at.x(120), y, size=17, color=muted if row.craftable else LACKING)
            y += at.row - 26
        hidden = screen.undiscovered()
        if hidden:
            self.text(
                tr("crafting.hidden", "??? {count} recipe(s) not yet discovered", count=hidden),
                at.x(90),
                self.height - 128,
                size=18,
                color=(150, 155, 175),
            )
        if screen.message:
            c.text("message", screen.message, 90, self.height - 100, size=20, color=TITLE)
        hint = tr("crafting.hint", "Up/Down: select   Enter: craft   Esc: back")
        c.text("hint", hint, 90, self.height - 72, size=18, color=c.tone("muted", MUTED))
        c.finish()

    def _draw_list_screen(self, kind):
        c = self.menu_canvas(kind)
        self._draw_backdrop(canvas=c)
        c.panel("frame", (60, 40, self.width - 120, self.height - 80))
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
            c.text(
                "title",
                tr(
                    "achievements.title",
                    "Achievements  {done}/{count}",
                    done=done,
                    count=len(rows),
                ),
                self.width / 2,
                56,
                size=30,
                color=c.tone("title", TITLE),
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
            c.text(
                "title",
                tr("bestiary.title", "Bestiary  {seen}/{count} seen", seen=seen, count=len(rows)),
                self.width / 2,
                56,
                size=30,
                color=c.tone("title", TITLE),
                center=True,
            )
            lines = [
                (name, self._bestiary_detail(row), (235, 238, 245) if row[1] else (150, 155, 175))
                for row in rows
                for name in (row[0],)
            ]
        if not lines:
            empty = tr("status.empty", "Nothing here yet.")
            c.text("empty", empty, 90, 110, size=22, color=c.tone("muted", MUTED))
        self._list_scroll = min(self._list_scroll, max(0, len(lines) - 1))
        at = c.place("rows", (90, 104, self.width - 180, self.height - 110 - 104), 24)
        icon_size = c.icon_size("rows", 24)
        y = at.y(104)
        shift = icon_size + 6 if any(line_icons) else 0
        size = c.size("rows", 22)
        for number, (title, detail, color) in enumerate(lines[self._list_scroll :]):
            if y > at.bottom:
                break
            index = self._list_scroll + number
            if index < len(line_icons) and line_icons[index]:
                self._draw_icon(line_icons[index], at.x(90), y - 2, icon_size)
            self.text(title, at.x(90) + shift, y, size=size, color=color)
            y += at.row
            for part in detail.split("\n") if detail else ():
                self.text(part, at.x(120), y, size=17, color=c.tone("muted", MUTED))
                y += 22
            y += 6
        c.text(
            "hint",
            tr("list.hint", "Up/Down: scroll   Enter / Esc: back"),
            self.width - 360,
            self.height - 72,
            size=18,
            color=c.tone("muted", MUTED),
        )
        c.finish()

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
        c = self.menu_canvas("settings")
        self._draw_backdrop(canvas=c)
        cursor = self._settings_menu
        tall = max(260, 120 + len(cursor.options) * 38)  # every row inside the panel
        x, y = self.width / 2 - 220, self.height / 2 - tall / 2
        x, y, _w, tall = c.panel("frame", (x, y, 440, tall))
        tr = self.game.tr
        title = tr("pause.settings", "Settings")
        top = y + 18
        c.text("title", title, x + 220, top, size=34, color=c.tone("title", TITLE), center=True)
        labels = cursor.labels(tr)
        at = c.place("options", (x + 40, y + 76, 360, len(labels) * 38), 38)
        size = c.size("options", 24)
        for i, (key, label) in enumerate(labels):
            selected = i == cursor.index
            color = (
                c.tone("selected", PICKED)
                if selected
                else c.color("options", c.tone("text", TEXT))
            )
            row_y = at.y(y + 76) + i * at.row
            self.menu_row(label, at.x(x + 40), row_y, selected=selected, size=size, color=color)
            if key == "language":
                value = self._language_name()
            else:
                value = self.settings.value_text(key, tr)
            if value:
                shown = f"< {value} >" if selected else value
                self.text(shown, at.x(x + 300), row_y, size=size, color=color)
        c.text(
            "hint",
            tr("settings.hint", "Left/Right: change   Esc: save and back"),
            x + 220,
            y + tall - 24,
            size=16,
            color=c.tone("muted", MUTED),
            center=True,
        )
        c.finish()

    def _draw_backdrop(self, base="field", canvas=None):
        """The map (or the battle) darkened behind a menu; a layout's own background colour
        or picture replaces it, and its ``dim`` sets how dark (U2)."""
        layout = canvas.layout if canvas is not None else None
        if layout is None or (layout.background_color is None and not layout.background_image):
            if base == "battle":
                self._battle_presentation.draw()  # the canonical battle screen as it was left
            else:
                self._draw_field(False)
            dim = 170 if layout is None or layout.dim < 0 else layout.dim
            if dim:
                shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
                shade.fill((5, 8, 16, dim))
                self.screen.blit(shade, (0, 0))
        if canvas is not None:
            canvas.begin()

    def _draw_overlay_menu(self, title, cursor, base="field", screen_id="pause"):
        c = self.menu_canvas(screen_id, self._menu_fields())
        self._draw_backdrop(base, canvas=c)
        height = 90 + 34 * len(cursor.options)
        shift = 30 if cursor.icons else 0  # room for the rows' icons: the panel grows with it
        x, y = self.width / 2 - 170 - shift / 2, self.height / 2 - height / 2
        x, y, width, height = c.panel("frame", (x, y, 340 + shift, height))
        middle = x + width / 2
        c.text("title", title, middle, y + 18, size=34, color=c.tone("title", TITLE), center=True)
        labels = cursor.labels(self.game.tr)
        at = c.place("options", (x + 36, y + 68, width - 72, 34 * len(labels)), 34)
        size = c.size("options", 24)
        icon = c.icon_size("options", 26)
        for i, (option_id, label) in enumerate(labels):
            selected = i == cursor.index
            row_y = at.y(y + 68) + i * at.row
            if option_id in cursor.icons:
                self._draw_icon(cursor.icons[option_id], round(at.x(x + 36)), round(row_y), icon)
            normal = c.color("options", c.tone("text", TEXT))
            self.menu_row(
                label,
                at.x(x + 40 + shift),
                row_y + 2,
                selected=selected,
                size=size,
                color=c.tone("selected", PICKED) if selected else normal,
            )
        if self.message and self.pg.time.get_ticks() < self.message_until:
            self.text(
                self.message,
                middle,
                y + height + 14,
                size=20,
                color=(175, 235, 255),
                center=True,
            )
        c.finish()

    def _menu_fields(self):
        """Fields every overlay menu offers the author's own texts (U2)."""
        game = self.game
        party = game.save.rpg_state.party_actor_ids
        leader = party[0] if party else ""
        gold = game.save.rpg_state.currencies.get("gold", 0)
        return {
            "party.leader": lambda: game.name_of(
                self.project.rpg_database.actors.get(leader), leader
            ),
            "wallet.gold": gold,
            "map.name": lambda: self._map_title(),
            "game.title": self.manifest.get("title", ""),
        }

    def _map_title(self):
        scene = getattr(self, "scene", None)
        name = getattr(scene, "name", "") if scene is not None else ""
        return self.game.map_name(getattr(scene, "id", ""), name) if name else ""

    def _draw_quests(self):
        c = self.menu_canvas("quests")
        self._draw_backdrop(canvas=c)
        c.panel("frame", (60, 40, self.width - 120, self.height - 80))
        tr = self.game.tr
        title = tr("pause.quests", "Quest Log")
        c.text(
            "title", title, self.width / 2, 56, size=32, color=c.tone("title", TITLE), center=True
        )
        rows = quest_rows(self.game)
        if not rows:
            none = tr("quests.none", "No quests yet.")
            c.text("empty", none, 90, 110, size=22, color=c.tone("muted", MUTED))
        at = c.place("rows", (90, 104, self.width - 180, self.height - 110 - 104), 30)
        y = at.y(104)
        colors = {
            "active": c.color("rows", c.tone("text", TEXT)),
            "completed": (130, 220, 150),
            "failed": (230, 120, 120),
        }
        icon_size = c.icon_size("rows", 24)
        for row in rows:
            if y > at.bottom:
                break
            icon = self.project.rpg_database.quests[row.quest_id].icon_id
            if icon:
                self._draw_icon(icon, at.x(90), y - 2, icon_size)
            status = tr(f"quests.status.{row.status}", row.status)  # the status is an id
            self.text(
                f"{row.name}  [{status}]",
                at.x(90) + (icon_size + 6 if icon else 0),
                y,
                size=c.size("rows", 24),
                color=colors[row.status],
            )
            y += at.row
            for description, value, required, done in row.objectives:
                self.text(
                    f"{'[x]' if done else '[ ]'} {description}  {value}/{required}",
                    at.x(120),
                    y,
                    size=19,
                    color=c.tone("muted", MUTED),
                )
                y += 24
            y += 8
        c.text(
            "hint",
            tr("quests.hint", "Enter / Esc: back"),
            self.width - 260,
            self.height - 72,
            size=18,
            color=c.tone("muted", MUTED),
        )
        c.finish()

    def _draw_shop(self):
        screen = self._shop_screen
        shop = screen.shop if screen is not None else None
        c = self.menu_canvas(
            "shop",
            {
                "shop.name": lambda: self.game.name_of(shop) if shop is not None else "",
                "wallet.gold": self.game.save.rpg_state.currencies.get("gold", 0),
            },
        )
        self._draw_backdrop(canvas=c)
        if screen is None or screen.shop is None:
            return
        c.panel("frame", (60, 40, self.width - 120, self.height - 80))
        shop_icon = screen.shop.icon_id
        if shop_icon and c.shown("title"):
            self._draw_icon(shop_icon, 90, 50, 32)
        c.text(
            "title",
            self.game.name_of(screen.shop),
            90 + (40 if shop_icon else 0),
            54,
            size=30,
            color=c.tone("title", TITLE),
        )
        tr = self.game.tr
        tabs = c.place("tabs", (self.width - 300, 60, 200, 30), 100)
        if c.shown("tabs"):
            for i, tab in enumerate(("buy", "sell")):
                self.text(
                    tr(f"shop.{tab}", tab.title()),
                    tabs.x(self.width - 300) + i * tabs.row,
                    tabs.y(60),
                    size=c.size("tabs", 24),
                    color=c.tone("selected", PICKED) if screen.tab == tab else (130, 140, 160),
                )
        from asteria.runtime.menu_icons import record_icon_id

        at = c.place("rows", (90, 134, self.width - 180, self.height - 130 - 134), 30)
        heads = c.place("columns", (90, 104, 680, 24))
        muted = c.tone("muted", MUTED)
        if c.shown("columns"):
            for word, x in (
                (tr("shop.item", "Item"), 90),
                (tr("shop.price", "Price"), 420),
                (tr("shop.stock", "Stock"), 640),
                (tr("shop.owned", "Owned"), 740),
            ):
                self.text(word, heads.x(x), heads.y(104), size=19, color=c.color("columns", muted))
        rows = screen.rows()
        icons = [record_icon_id(self.project, "item", r.item_id) for r in rows]
        icon_size = c.icon_size("rows", 22)
        name_x = at.x(90) + (icon_size + 8 if any(icons) else 0)
        # a long list scrolls with the cursor (D61: a shop of 38 wares), "n/total" above it
        fit = max(1, (at.bottom - at.y(134)) // at.row + 1)
        first = min(max(0, screen.index - fit // 2), max(0, len(rows) - fit))
        if len(rows) > fit:
            where = f"{min(screen.index, len(rows) - 1) + 1}/{len(rows)}"
            c.text("count", where, heads.x(840), heads.y(104), size=19, color=muted)
        size = c.size("rows", 22)
        for i, row in enumerate(rows):
            if i < first:
                continue
            y = at.y(134) + (i - first) * at.row
            if y > at.bottom:
                break
            normal = c.color("rows", c.tone("text", TEXT))
            selected = i == screen.index
            color = c.tone("selected", PICKED) if selected else normal if row.available else DIM
            if selected:
                self.menu_mark(at.x(72), y, size=size, color=color)
            self._draw_icon(icons[i], at.x(90), y - 2, icon_size)
            self.text(row.name, name_x, y, size=size, color=color)
            self.text(row.price, at.x(420), y, size=size, color=color)
            self.text(row.stock, at.x(640), y, size=size, color=color)
            self.text(str(row.owned), at.x(740), y, size=size, color=color)
        c.text("wallet", screen.wallet(), 90, self.height - 100, size=20, color=(175, 235, 255))
        if screen.message:
            c.text(
                "message", screen.message, self.width / 2, self.height - 100, size=20, color=TITLE
            )
        c.text(
            "hint",
            tr(
                "shop.hint",
                "Up/Down: select   Left/Right: buy/sell   Enter: confirm   Esc: leave",
            ),
            90,
            self.height - 72,
            size=18,
            color=muted,
        )
        c.finish()
