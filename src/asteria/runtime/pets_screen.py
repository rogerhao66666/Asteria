"""Pets screen (pause menu > Pets): the creatures the player owns.

A list of owned pets with icon, nickname and species, level, an experience bar and the species'
stats at that level. Up / Down choose, Enter makes the highlighted pet the active one (the one
abilities send out), R renames it (type, Enter keeps, Esc cancels), E evolves it, Esc / P close.

Under the project's Pet Rules the screen has two columns, **Party** and **Storage** (when the
rules keep storage): Left / Right move between them and Enter moves the highlighted pet to the
other column (the party keeps at most ``party_size``, and never loses its last standing one).
Each row also shows the pet's current health and moves. Everything comes from the project's
pet species and the save; nothing here knows a game.
"""

from __future__ import annotations

MUTED, TITLE, GOOD = (150, 160, 180), (255, 220, 124), (130, 230, 150)
HEALTH, HEALTH_BG = (90, 203, 130), (48, 53, 66)


class PetsScreen:
    """Made when opened; each frame ``handle(dt, events)`` then ``draw()``; ``closed`` ends it.
    ``back`` is the host mode to return to; ``storage`` opens on the storage column."""

    def __init__(self, runtime, *, back="pause", storage=False):
        self.rt = runtime
        self.index = 0
        self.closed = False
        self.back = back
        self.renaming = None  # the text being typed, or None
        self.message, self.message_left = "", 0.0
        self.column = "storage" if storage and self.two_columns() else "party"

    @property
    def game(self):
        return self.rt.game

    def two_columns(self):
        rules = self.game.pet_rules
        return rules is not None and (rules.storage or bool(rules.party_size))

    def pets(self):
        if not self.two_columns():
            return self.game.pets()
        return self.game.party_pets() if self.column == "party" else self.game.stored_pets()

    def selected(self):
        pets = self.pets()
        return pets[min(self.index, len(pets) - 1)] if pets else None

    def _say(self, text):
        self.message, self.message_left = text, 2.5

    # -- input -----------------------------------------------------------------------------------
    def handle(self, dt=0.0, events=()):
        rt, pg = self.rt, self.rt.pg
        self.message_left = max(0.0, self.message_left - dt)
        if self.renaming is not None:
            self._typing(events)
            return
        inp = rt.input
        if inp.just_pressed("cancel"):
            self.closed = True
            return
        if self.two_columns() and (
            inp.just_pressed("move_left") or inp.just_pressed("move_right")
        ):
            self.column = "storage" if self.column == "party" else "party"
            self.index = 0
        count = len(self.pets())
        if count:
            if inp.just_pressed("move_up"):
                self.index = (self.index - 1) % count
            if inp.just_pressed("move_down"):
                self.index = (self.index + 1) % count
        pet = self.selected()
        if pet is None:
            return
        if inp.just_pressed("confirm") or inp.just_pressed("interact"):
            if self.two_columns():
                self._move(pet)
            else:
                self.game.set_active_pet(pet.instance_id)
                name = self.game.pet_display(pet)
                self._say(self.game.tr("pets.sent_out", "{name} will be sent out", name=name))
        for event in events:
            if event.type == pg.KEYDOWN and event.key == pg.K_r:
                self.renaming = pet.nickname
            if event.type == pg.KEYDOWN and event.key == pg.K_e:
                self._evolve(pet)

    def _move(self, pet):
        """Enter in the two-column screen: the pet crosses to the other column."""
        from asteria.rpg.built_in_text import translated

        game = self.game
        name = game.pet_display(pet)
        try:
            if self.column == "party":
                game.move_pet_to_storage(pet.instance_id)
                self._say(game.tr("pets.moved_out", "{name} goes into storage", name=name))
            else:
                game.move_pet_to_party(pet.instance_id)
                self._say(game.tr("pets.moved_in", "{name} joins the party", name=name))
        except Exception as exc:
            self._say(translated(exc, game.tr))
        self.index = min(self.index, max(0, len(self.pets()) - 1))

    def _evolve(self, pet):
        """E: evolve the pet if it qualifies (with a bag item when one is needed)."""
        game = self.game
        species = game.pet_species(pet)
        if species is None:
            return
        inventory = game.save.rpg_state.inventory
        for evolution in species.evolutions:
            if evolution.item_id and inventory.count(evolution.item_id) < 1:
                continue
            if game.pet_evolution(pet.instance_id, item_id=evolution.item_id) is evolution:
                game.evolve_pet(pet.instance_id, item_id=evolution.item_id)
                self._say(game.tr("pets.evolved", "{name} evolved!", name=game.pet_display(pet)))
                return
        self._say(game.tr("pets.not_ready", "Not ready to evolve"))

    def _typing(self, events):
        pg = self.rt.pg
        pet = self.selected()
        for event in events:
            if event.type != pg.KEYDOWN:
                continue
            if event.key == pg.K_ESCAPE:
                self.renaming = None
            elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                self.game.rename_pet(pet.instance_id, self.renaming)
                self.renaming = None
                self._say(self.game.tr("pets.renamed", "Renamed"))
            elif event.key == pg.K_BACKSPACE:
                self.renaming = self.renaming[:-1]
            elif getattr(event, "unicode", "") and event.unicode.isprintable():
                if len(self.renaming) < 24:
                    self.renaming += event.unicode

    # -- drawing ---------------------------------------------------------------------------------
    def _move_names(self, pet):
        library = self.game.project.gameplay_library.abilities
        names = []
        for ability_id in self.game.pet_moves(pet):
            definition = library.get(ability_id)
            name = self.game.name_of(definition) or ability_id
            left = self.game.pet_uses_left(pet, ability_id)
            names.append(name if left is None else f"{name} {left}/{definition.max_uses}")
        return names

    def draw(self):
        rt = self.rt
        pg, screen = rt.pg, rt.screen
        game = self.game
        c = self.canvas = rt.menu_canvas("pets")
        layout = c.layout
        if layout is None or (layout.background_color is None and not layout.background_image):
            screen.fill((10, 12, 20))
        c.begin()
        tr = game.tr
        two = self.two_columns()
        c.text("title", tr("pets.title", "Pets"), 36, 22, size=34, color=c.tone("title", TITLE))
        if two:
            hint = tr(
                "pets.party_hint",
                "Up / Down: choose   Left / Right: party / storage   Enter: move   R: rename"
                "   Esc: back",
            )
        else:
            hint = tr(
                "pets.hint", "Up / Down: choose   Enter: send this one out   R: rename   Esc: back"
            )
        c.text("help", hint, 36, 62, size=18, color=c.tone("muted", MUTED))
        if two:
            rules = game.pet_rules
            party = tr("pets.party", "Party")
            if rules.party_size:
                party += f"  {len(game.party_pets())}/{rules.party_size}"
            storage = tr("pets.storage", "Storage")
            if rules.storage:
                storage += f"  {len(game.stored_pets())}"
            for label, key, x in ((party, "party", 36), (storage, "storage", rt.width / 2 + 8)):
                color = TITLE if self.column == key else MUTED
                rt.text(label, x, 92, size=24, color=color)
        pets = self.pets()
        top = 124 if two else 100
        if not pets:
            rt.text(tr("pets.none", "You have no pets yet."), 36, top + 10, size=22, color=MUTED)
            self._footer()
            c.finish()
            return
        active = game.active_pet()
        at = c.place("rows", (36, top, rt.width - 72, rt.height - top - 70), 64 if not two else 78)
        row_h = at.row
        width = at.rect[2]
        x0 = at.x(36)
        top = at.y(top)
        if two:
            width = rt.width / 2 - 44
            x0 = 36 if self.column == "party" else rt.width / 2 + 8
            other = game.stored_pets() if self.column == "party" else game.party_pets()
            ox = rt.width / 2 + 8 if self.column == "party" else 36
            for i, pet in enumerate(other):  # the other column, dimmed
                y = top + i * (row_h + 8)
                rect = pg.Rect(ox, y, width, row_h)
                self._spot(rect, "storage" if self.column == "party" else "party", i)
                pg.draw.rect(screen, (16, 19, 30), rect, border_radius=8)
                pg.draw.rect(screen, (50, 56, 72), rect, 1, 8)
                self._row(pet, rect, selected=False, active=active, dim=True)
        element = c.element("rows")
        for i, pet in enumerate(pets):
            y = top + i * (row_h + 8)
            rect = pg.Rect(x0, y, width, row_h)
            self._spot(rect, self.column, i)
            selected = i == min(self.index, len(pets) - 1)
            if element is not None and (element.skin or element.image):
                c._draw_look(element, tuple(rect))  # the layout's row picture
            else:
                fill = (30, 40, 62) if selected else (20, 24, 38)
                pg.draw.rect(screen, fill, rect, border_radius=8)
            if selected:
                c.selection(
                    "rows",
                    tuple(rect),
                    lambda rect=rect: pg.draw.rect(screen, TITLE, rect, 2, 8),
                )
            else:
                pg.draw.rect(screen, (60, 66, 84), rect, 1, 8)
            self._row(pet, rect, selected=selected, active=active, dim=False)
        self._footer()
        c.finish()

    def _spot(self, rect, column, index):
        """A pet's row as a mouse hotspot (D85): pointing picks it (in either column), a click
        is Enter; nothing while a name is being typed."""
        if self.renaming is None:
            self.rt.hotspot(tuple(rect), lambda: self._point(column, index))

    def _point(self, column, index):
        self.column, self.index = column, index

    def _row(self, pet, rect, *, selected, active, dim):
        rt, pg, screen, game, tr = self.rt, self.rt.pg, self.rt.screen, self.game, self.game.tr
        y = rect.y
        species = game.pet_species(pet)
        text_color = (120, 124, 140) if dim else (255, 255, 255)
        if not (
            species and species.icon_id and rt._draw_icon(species.icon_id, rect.x + 12, y + 8, 48)
        ):
            rt.text(
                pet.species_id[:2].upper(),
                rect.x + 36,
                y + rect.h / 2,
                size=28,
                color=TITLE,
                anchor="center",
            )
        name = self.game.pet_display(pet)
        if self.renaming is not None and selected:
            name = self.renaming + "_"
        rt.text(name, rect.x + 76, y + 8, size=24, color=text_color)
        kind = self.game.name_of(species, pet.species_id)
        line = tr("pets.level", "{kind}   Lv {level}", kind=kind, level=pet.level)
        if species is not None and pet.affinity:
            line += "   " + tr("pets.bond", "Bond {bond}", bond=f"{pet.affinity:g}")
        rt.text(line, rect.x + 76, y + 36, size=18, color=MUTED)
        if pet is active and not self.two_columns():
            rt.text(tr("pets.active", "ACTIVE"), rect.right - 100, y + 10, size=20, color=GOOD)
        need = species.exp_to_next(pet.level) if species else 1.0
        full = species is not None and pet.level >= species.max_level
        fraction = 1.0 if full else max(0.0, min(1.0, pet.experience / need))
        bar = pg.Rect(rect.right - 260, y + 40, 220, 10)
        pg.draw.rect(screen, (14, 16, 24), bar.inflate(2, 2), border_radius=4)
        pg.draw.rect(screen, (214, 172, 58), (bar.x, bar.y, int(bar.w * fraction), bar.h), 0, 4)
        if not self.two_columns():
            if species is not None:
                stats = "   ".join(
                    f"{game.stat_name(k)} {v:g}" for k, v in game.pet_stats_at(pet).items()
                )
                rt.text(stats, rect.right - 560, y + 12, size=18, color=(170, 210, 240))
            return
        hp = game.rules.knockout_resource_id
        maxima = game.pet_resources_at(pet)
        if hp and hp in maxima:
            current = pet.resources.get(hp, maxima[hp])
            health = pg.Rect(rect.right - 260, y + 14, 220, 10)
            pg.draw.rect(screen, HEALTH_BG, health, border_radius=4)
            share = max(0.0, min(1.0, current / max(1.0, maxima[hp])))
            colour = HEALTH if share > 0.5 else ((230, 190, 80) if share > 0.2 else (220, 90, 80))
            pg.draw.rect(
                screen, colour, (health.x, health.y, int(health.w * share), health.h), 0, 4
            )
            label = tr(
                "pets.health",
                "HP {current}/{maximum}",
                current=f"{current:g}",
                maximum=f"{maxima[hp]:g}",
            )
            rt.text(label, rect.right - 260, y + 26, size=14, color=MUTED)
        moves = "   ".join(self._move_names(pet))
        rt.text(moves, rect.x + 76, y + 56, size=15, color=(170, 210, 240) if not dim else MUTED)

    def _footer(self):
        rt = self.rt
        if self.renaming is not None:
            rt.text(
                rt.game.tr("pets.rename_hint", "Type a name, Enter keeps it, Esc cancels"),
                rt.width / 2,
                rt.height - 60,
                size=20,
                color=(175, 235, 255),
                anchor="center",
            )
        elif self.message_left > 0:
            rt.text(
                self.message,
                rt.width / 2,
                rt.height - 40,
                size=20,
                color=(175, 235, 255),
                anchor="center",
            )


__all__ = ["PetsScreen"]
