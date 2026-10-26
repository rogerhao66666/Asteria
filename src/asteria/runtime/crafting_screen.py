"""The crafting screen of a workstation (U4; ``rpg/workstations.py``).

``OPEN_CRAFTING`` opens the station it names. The screen has a tab per category of the station
(Tab / Q / E change tab) and, when the station allows it, a disassembly tab. The recipe list
shows each product's icon; the panel on the right shows what the chosen recipe makes, the
materials it needs against those held (short ones in red), its success chance and quality
tiers, and how many will be made (left / right change it, up to the station's limit and what
the materials allow). Recipes not discovered yet are ``???`` rows when the station shows them.
The disassembly tab lists the bag's items the project can break down and what each gives.

A station the project does not define opens with one tab of every recipe it can make.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from asteria.rpg.built_in_text import translated
from asteria.rpg.workstations import WorkstationDefinition

from .bag_screen import BAD, GOOD, MUTED, TITLE

TEXT = (236, 238, 245)
GREY = (130, 134, 150)
ROWS = (48, 124, 520, 500)
DETAIL = (584, 124, 648, 500)
DISASSEMBLE = "disassemble"


def wrap(rt, words, size, width):
    """``words`` in lines no wider than ``width`` at ``size``: broken at spaces, or between
    any two characters in a text without spaces (Chinese)."""
    words = str(words)
    if rt.text_width(words, size) <= width:
        return [words]
    parts = words.split(" ") if " " in words else list(words)
    joiner = " " if " " in words else ""
    lines, line = [], ""
    for part in parts:
        trial = f"{line}{joiner}{part}" if line else part
        if line and rt.text_width(trial, size) > width:
            lines.append(line)
            line = part
        else:
            line = trial
    return [*lines, line] if line else lines


@dataclass(frozen=True, slots=True)
class CraftingRow:
    recipe_id: str  # the recipe (disassembly rows: the item broken down)
    name: str
    outputs: str
    materials: tuple  # (item name, needed, owned)
    craftable: bool
    known: bool = True
    icon_id: str = ""
    chance: float = 1.0
    qualities: tuple = ()  # (quality, threshold)
    makes: int = 0  # how many the materials allow
    item_id: str = ""  # disassembly rows: the item broken down


class CraftingScreen:
    """Recipes usable at ``station`` (empty: the recipes that need no station)."""

    def __init__(self, game, station=""):
        self.game = game
        self.station = str(station or "")
        self.index = 0
        self.tab = 0
        self.quantity = 1
        self.message = ""
        self.flash_until = 0.0  # the station's success picture shows until then

    # -- the station -------------------------------------------------------------------------
    def workstation(self):
        found = self.game.project.rpg_database.workstations.get(self.station)
        return found or WorkstationDefinition(self.station or "crafting")

    def station_name(self):
        record = self.game.project.rpg_database.workstations.get(self.station)
        if record is not None:
            return self.game.name_of(record)
        return self.station.replace("_", " ").title()

    def layout_id(self, runtime):
        """The menu layout the screen draws through: the station's ``layout``, else its own
        ``crafting.<station>`` when the project has one, else ``crafting``."""
        station = self.workstation()
        if station.layout:
            return station.layout
        own = f"crafting.{self.station}"
        return own if self.station and runtime.menu_layout(own) is not None else "crafting"

    def tabs(self):
        """``[(tab id, words)]``: the station's categories, then disassembly."""
        station = self.workstation()
        tr = self.game.tr
        out = [(c.category_id, self.game.name_of(c)) for c in station.categories]
        if not out:
            out = [("", tr("crafting.all", "Recipes"))]
        if station.disassembly:
            out.append((DISASSEMBLE, tr("crafting.disassemble", "Disassemble")))
        return out

    @property
    def page(self):
        tabs = self.tabs()
        return tabs[min(self.tab, len(tabs) - 1)][0]

    def switch_tab(self, step=1):
        self.tab = (self.tab + int(step)) % len(self.tabs())
        self.index, self.quantity, self.message = 0, 1, ""

    # -- rows ----------------------------------------------------------------------------------
    def _item(self, item_id):
        return self.game.project.rpg_database.items.get(item_id)

    def _name(self, item_id):
        return self.game.name_of(self._item(item_id), item_id)

    def _icon(self, item_id):
        item = self._item(item_id)
        if item is None:
            item = self.game.project.rpg_database.equipment.get(item_id)
        return getattr(item, "icon_id", "") or ""

    def quality_name(self, quality):
        from asteria.rpg.data_text import quality_name

        return quality_name(self.game.data_lookup, quality)

    def recipes(self):
        """Every recipe of this tab usable here, known or not, by id."""
        station = self.workstation()
        page = self.page
        out = []
        recipes = self.game.project.rpg_database.composition_recipes
        for _recipe_id, recipe in sorted(recipes.items()):
            if recipe.station and recipe.station != self.station:
                continue
            if station.categories and station.category_of(recipe) != page:
                continue
            out.append(recipe)
        return out

    def rows(self):
        if self.page == DISASSEMBLE:
            return self.disassembly_rows()
        inventory = self.game.save.rpg_state.inventory
        known, hidden = [], []
        show_hidden = self.workstation().show_undiscovered
        for recipe in self.recipes():
            if not self.game.recipe_known(recipe.recipe_id):
                if show_hidden:
                    unknown = self.game.tr("achievements.hidden_name", "???")
                    hidden.append(
                        CraftingRow(recipe.recipe_id, unknown, unknown, (), False, known=False)
                    )
                continue
            needed = {}
            for selection in recipe.selections:
                for item_id in selection.item_ids:
                    needed[item_id] = needed.get(item_id, 0) + 1
            materials = tuple(
                (self._name(k), n, inventory.count(k)) for k, n in sorted(needed.items())
            )
            makes = min((have // need for _n, need, have in materials), default=0)
            outputs = ", ".join(f"{self._name(o.item_id)} x{o.amount}" for o in recipe.outputs)
            known.append(
                CraftingRow(
                    recipe.recipe_id,
                    self.game.name_of(recipe),
                    outputs,
                    materials,
                    makes > 0,
                    icon_id=self._icon(recipe.outputs[0].item_id),
                    chance=recipe.success_chance,
                    qualities=tuple((t.quality, t.threshold) for t in recipe.quality_tiers),
                    makes=makes,
                )
            )
        return tuple(known + hidden)

    def disassembly_rows(self):
        """The bag's items the project can break down (the station's tags, when it names
        some): what each gives and its fee."""
        db = self.game.project.rpg_database
        inventory = self.game.save.rpg_state.inventory
        tags = set(self.workstation().disassembly_tags)
        rows = []
        for item_id, recipe in sorted(db.disassembly_recipes.items()):
            owned = inventory.count(item_id)
            item = self._item(item_id)
            if not owned or (tags and not tags & set(getattr(item, "tags", ()) or ())):
                continue
            gives = ", ".join(
                f"{self._name(y.item_id)} x{y.minimum}"
                + (f"-{y.maximum}" if y.maximum != y.minimum else "")
                + (f" ({round(y.chance * 100)}%)" if y.chance < 1 else "")
                for y in recipe.yields
            )
            rows.append(
                CraftingRow(
                    item_id,
                    self._name(item_id),
                    gives,
                    ((self._name(item_id), 1, owned),),
                    True,
                    icon_id=self._icon(item_id),
                    makes=owned,
                    item_id=item_id,
                )
            )
        return tuple(rows)

    def selected(self):
        rows = self.rows()
        if not rows:
            return None
        self.index = min(self.index, len(rows) - 1)
        return rows[self.index]

    def undiscovered(self):
        recipes = self.game.project.rpg_database.composition_recipes
        return sum(1 for k in recipes if not self.game.recipe_known(k))

    def move(self, delta):
        rows = self.rows()
        if rows:
            self.index = (self.index + int(delta)) % len(rows)
            self.quantity = 1

    def limit(self):
        """The most the player can make (or break down) of the chosen row at once."""
        row = self.selected()
        if row is None or not row.known:
            return 1
        return max(1, min(self.workstation().max_quantity, row.makes))

    def _point(self, row):
        """The mouse over a recipe (D85): the cursor there (the amount starts again at 1)."""
        if row != self.index:
            self.index, self.quantity, self.message = row, 1, ""

    def change_quantity(self, delta):
        self.quantity = max(1, min(self.limit(), self.quantity + int(delta)))

    # -- making ---------------------------------------------------------------------------------
    def confirm(self, rng=None):
        """Make the chosen recipe ``quantity`` times (or break the item down). Returns the last
        result, or None when nothing was made; ``message`` says what happened."""
        row = self.selected()
        if row is None:
            return None
        tr = self.game.tr
        if not row.known:
            self.message = tr("crafting.unknown", "You have not discovered this recipe yet.")
            return None
        if self.page == DISASSEMBLE:
            return self._disassemble(row)
        recipe = self.game.project.rpg_database.composition_recipes[row.recipe_id]
        payload = {s.step_id: list(s.item_ids) for s in recipe.selections}
        made, results = {}, []
        for _ in range(max(1, min(self.quantity, self.limit()))):
            try:
                result = self.game.craft(payload, station=self.station, rng=rng)
            except ValueError as exc:
                if not results:
                    self.message = translated(exc, tr)
                    return None
                break
            results.append(result)
            for item_id, amount in result.produced:
                made[item_id] = made.get(item_id, 0) + amount
        self.quantity = max(1, min(self.quantity, self.limit()))
        words = ", ".join(f"{self._name(k)} x{n}" for k, n in made.items())
        words = words or tr("crafting.nothing", "nothing")
        last = results[-1]
        successes = sum(1 for r in results if r.success)
        if not successes:
            self.message = tr("crafting.failed", "Crafting failed — got {items}", items=words)
        elif last.quality and len(results) == 1:
            self.message = tr(
                "crafting.crafted_quality",
                "Crafted {items} ({quality})",
                items=words,
                quality=self.quality_name(last.quality),
            )
        elif successes < len(results):
            self.message = tr(
                "crafting.crafted_some",
                "Crafted {items} ({done} of {count} succeeded)",
                items=words,
                done=successes,
                count=len(results),
            )
        else:
            self.message = tr("crafting.crafted", "Crafted {items}", items=words)
        if successes:
            self.flash_until = time.monotonic() + self.workstation().success_seconds
        return last

    def _disassemble(self, row):
        tr = self.game.tr
        got, last = {}, None
        for _ in range(max(1, min(self.quantity, self.limit()))):
            try:
                last = self.game.disassemble(row.item_id)
            except Exception as exc:  # noqa: BLE001 - shown to the player
                if last is None:
                    self.message = translated(exc, tr)
                    return None
                break
            for item_id, amount in dict(last.gained).items():
                got[item_id] = got.get(item_id, 0) + amount
        self.quantity = 1
        words = ", ".join(f"{self._name(k)} x{n}" for k, n in got.items())
        self.message = tr(
            "crafting.disassembled",
            "Broke down {item}: {items}",
            item=row.name,
            items=words or tr("crafting.nothing", "nothing"),
        )
        self.flash_until = time.monotonic() + self.workstation().success_seconds
        return last

    def close(self):
        self.game.open_crafting_station = None

    # -- drawing --------------------------------------------------------------------------------
    def draw(self, rt):
        game = self.game
        tr = game.tr
        station = self.workstation()
        fields = {
            "station.name": self.station_name(),
            "page": self.page,
            "quantity": self.quantity,
            "wallet.gold": game.save.rpg_state.currencies.get("gold", 0),
        }
        canvas = rt.menu_canvas(self.layout_id(rt), fields)
        rt._draw_backdrop(canvas=canvas)
        if station.music:
            rt._music(station.music)
        canvas.panel("frame", (24, 20, rt.width - 48, rt.height - 40), fill=(11, 15, 25, 236))
        title = canvas.tone("title", TITLE)
        muted = canvas.tone("muted", MUTED)
        if station.icon_id:
            rt._draw_icon(station.icon_id, 48, 30, 40)
        heading = self.station_name() if self.station else tr("pause.crafting", "Crafting")
        canvas.text("title", heading, 100 if station.icon_id else 48, 32, size=32, color=title)
        gold = tr("crafting.gold", "Gold {gold}", gold=int(fields["wallet.gold"]))
        canvas.text("wallet", gold, rt.width - 48, 40, size=20, color=TEXT, anchor="topright")
        self.draw_tabs(rt, canvas)
        self.draw_rows(rt, canvas)
        self.draw_detail(rt, canvas)
        hidden = sum(1 for r in self.rows() if not r.known)
        if hidden:
            words = tr("crafting.hidden", "??? {count} recipe(s) not yet discovered", count=hidden)
            canvas.text("undiscovered", words, 48, rt.height - 84, size=18, color=GREY)
        if self.message:
            canvas.text(
                "message", self.message, rt.width / 2, rt.height - 84, size=20,
                color=(175, 235, 255), anchor="midtop",
            )  # fmt: skip
        hint = tr(
            "crafting.hint",
            "Up/Down: recipe   Left/Right: how many   Enter: make   Tab / Q / E: tab   Esc: back",
        )
        canvas.text("hint", hint, 48, rt.height - 52, size=18, color=muted)
        self.draw_flash(rt, canvas)
        canvas.finish()

    def draw_tabs(self, rt, canvas):
        default = (48, 76, 760, 36)
        if not canvas.shown("tabs"):
            canvas.rect("tabs", default)
            return
        place = canvas.place("tabs", default)
        width = canvas.number("tabs", "cell", 150)
        gap = canvas.number("tabs", "gap", 10)
        title = canvas.tone("title", TITLE)
        station = self.workstation()
        icons = {c.category_id: c.icon_id for c in station.categories}
        for n, (tab_id, words) in enumerate(self.tabs()):
            rect = (place.x(48) + n * (width + gap), place.y(76), width, 34)
            rt.hotspot(  # a click opens the tab
                rect, lambda n=n: n != self.tab and self.switch_tab(n - self.tab), key=""
            )
            if n == self.tab:
                canvas.selection(
                    "tabs", rect,
                    lambda rect=rect: rt.pg.draw.rect(rt.screen, (60, 72, 110), rect,
                                                      border_radius=6),
                )  # fmt: skip
            else:
                rt.pg.draw.rect(rt.screen, (40, 46, 64), rect, 1, border_radius=6)
            icon = icons.get(tab_id, "")
            centre = rect[0] + width / 2 + (12 if icon else 0)
            if icon:
                rt._draw_icon(icon, rect[0] + 8, rect[1] + 5, 24)
            rt.text(words, centre, rect[1] + 6, size=18,
                    color=title if n == self.tab else TEXT, anchor="midtop")  # fmt: skip

    def draw_rows(self, rt, canvas):
        tr = self.game.tr
        if not canvas.shown("rows"):
            canvas.rect("rows", ROWS)
            return
        x, y, w, h = canvas.panel("rows", ROWS, fill=(16, 20, 32, 236))
        head = (
            tr("crafting.items", "Items to break down")
            if self.page == DISASSEMBLE
            else tr("crafting.recipes", "Recipes")
        )
        rt.text(head, x + 14, y + 10, size=18, color=canvas.tone("title", TITLE))
        rows = self.rows()
        if not rows:
            empty = (
                tr("crafting.nothing_to_break", "Nothing in the bag can be broken down.")
                if self.page == DISASSEMBLE
                else tr("crafting.none", "No known recipes here.")
            )
            canvas.text("empty", empty, x + 14, y + 42, size=17, color=canvas.tone("muted", MUTED))
            return
        row_h = canvas.row_height("rows", 44)
        icon = canvas.icon_size("rows", 32)
        top = y + 40
        visible = max(1, (h - 48) // row_h)
        chosen = min(self.index, len(rows) - 1)
        first = max(0, min(chosen - visible + 1, len(rows) - visible)) if chosen else 0
        normal = canvas.color("rows", canvas.tone("text", TEXT))
        for n, row in enumerate(rows[first : first + visible]):
            ry = top + n * row_h
            rect = (x + 6, ry - 2, w - 12, row_h - 4)
            rt.hotspot(rect, lambda k=first + n: self._point(k))
            if first + n == chosen:
                canvas.selection(
                    "rows", rect,
                    lambda rect=rect: rt.pg.draw.rect(rt.screen, (52, 62, 92), rect,
                                                      border_radius=6),
                )  # fmt: skip
            if row.known and row.icon_id:
                rt._draw_icon(row.icon_id, x + 12, ry + (row_h - 4 - icon) // 2, icon)
            elif not row.known:
                box = (x + 12, ry + (row_h - 4 - icon) // 2, icon, icon)
                rt.pg.draw.rect(rt.screen, (150, 155, 175), box, 1, border_radius=4)
            color = normal if row.craftable else GREY
            rt.text(row.name, x + 22 + icon, ry + 2, size=18, color=color)
            if row.known:
                count = tr("crafting.can_make", "can make {count}", count=row.makes)
                if self.page == DISASSEMBLE:
                    count = tr("crafting.owned", "x{count}", count=row.makes)
                rt.text(count, x + w - 16, ry + 4, size=15,
                        color=GOOD if row.makes else BAD, anchor="topright")  # fmt: skip
                rt.text(row.outputs, x + 22 + icon, ry + 22, size=14, color=MUTED)

    def detail_lines(self):
        """``[(words, colour, size)]`` of the panel on the right."""
        tr = self.game.tr
        row = self.selected()
        if row is None:
            return []
        if not row.known:
            return [
                (row.name, TITLE, 24),
                (tr("crafting.unknown", "You have not discovered this recipe yet."), MUTED, 18),
                (tr("crafting.unknown_hint", "Learn it, or make it by its exact materials."),
                 MUTED, 16),
            ]  # fmt: skip
        lines = [(row.name, TITLE, 24)]
        if self.page == DISASSEMBLE:
            lines.append((tr("crafting.gives", "Gives"), TITLE, 18))
            lines.append((row.outputs or tr("crafting.nothing", "nothing"), TEXT, 18))
            recipe = self.game.project.rpg_database.disassembly_recipes.get(row.item_id)
            if recipe is not None and recipe.fee:
                lines.append(
                    (tr("crafting.fee", "Fee {fee} {currency}", fee=int(recipe.fee),
                        currency=recipe.fee_currency), TEXT, 18)
                )  # fmt: skip
        else:
            lines.append((tr("crafting.makes", "Makes"), TITLE, 18))
            lines.append((row.outputs, TEXT, 18))
            recipe = self.game.project.rpg_database.composition_recipes[row.recipe_id]
            product = self._item(recipe.outputs[0].item_id)
            about = self.game.description_of(product) if product is not None else ""
            if about:
                lines.append((about, MUTED, 16))
            lines.append(("", TEXT, 6))
            lines.append((tr("crafting.materials", "Materials (held / needed)"), TITLE, 18))
            for name, need, have in row.materials:
                total = need * self.quantity
                color = GOOD if have >= total else BAD
                lines.append((f"{name}   {have} / {total}", color, 18))
            lines.append(("", TEXT, 6))
            chance = round(row.chance * 100)
            lines.append((tr("crafting.chance", "Success chance {chance}%", chance=chance),
                          GOOD if chance >= 100 else TEXT, 18))  # fmt: skip
            if row.qualities:
                tiers = "   ".join(
                    tr("crafting.quality_tier", "{quality} {percent}%+",
                       quality=self.quality_name(q), percent=round(t * 100))
                    for q, t in row.qualities
                )  # fmt: skip
                lines.append((tr("crafting.qualities", "Quality: {tiers}", tiers=tiers),
                              TEXT, 18))  # fmt: skip
        lines.append(("", TEXT, 6))
        lines.append(
            (tr("crafting.quantity", "How many: {count}  (most {limit})",
                count=self.quantity, limit=self.limit()), TITLE, 20)
        )  # fmt: skip
        return lines

    def draw_detail(self, rt, canvas):
        if not canvas.shown("detail"):
            canvas.rect("detail", DETAIL)
            return
        x, y, w, h = canvas.panel("detail", DETAIL, fill=(16, 20, 32, 240))
        row = self.selected()
        top = y + 12
        if row is not None and row.known and row.icon_id:
            size = canvas.icon_size("detail", 64)
            rt._draw_icon(row.icon_id, x + w - size - 16, y + 14, size)
        for words, color, size in self.detail_lines():
            for line in wrap(rt, words, size, w - 32) if words else [""]:
                if top > y + h - 24:
                    break
                if line:
                    rt.text(line, x + 16, top, size=size, color=color)
                top += size + 6
        canvas.rect("quantity", (x + 16, y + h - 40, w - 32, 28))

    def draw_flash(self, rt, canvas):
        """The station's success picture, fading out (``success_image``)."""
        station = self.workstation()
        left = self.flash_until - time.monotonic()
        if not station.success_image or left <= 0 or not station.success_seconds:
            return
        image = rt.skin_image(station.success_image)
        if image is None:
            return
        rect = canvas.rect("flash", (rt.width / 2 - 96, rt.height / 2 - 96, 192, 192))
        picture = rt.scaled_image(image, rect[2:]).copy()
        picture.set_alpha(int(255 * min(1.0, left / station.success_seconds)))
        rt.screen.blit(picture, rect[:2])
