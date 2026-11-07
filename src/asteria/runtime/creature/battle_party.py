"""The party screen and the bag opened from a creature battle."""

from __future__ import annotations

from asteria.runtime.creature.battle_style import (
    BAR_TRACK,
    CMD_EDGE,
    CMD_LINE,
    HP_GREEN,
    HP_RED,
    HP_YELLOW,
    PARTY_BG,
    PARTY_SEL,
    PARTY_SLOT,
    WHITE,
    H,
    W,
)


class BattlePartyMixin:
    """The party screen and the bag opened from a creature battle."""

    def _party_art(self, name, state=None):
        """A picture of the party screen (``battle.creature_screen.party``)."""
        party = self.settings.get("party") or {}
        value = party.get(name)
        if isinstance(value, dict):
            value = value.get(state)
        key = ("party", name, state)
        if key not in self._images:
            image = None
            if isinstance(value, str) and self._path(value).is_file():
                image = self.pg.image.load(str(self._path(value))).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _icon(self, species):
        image = self._image("icon", species, None)
        if image is not None and image.get_height() > image.get_width():
            image = image.subsurface((0, 0, image.get_width(), image.get_width()))
        return image

    def slot_label(self, pet):
        """Words shown in a party slot instead of its HP (None: the HP)."""
        return None

    def _draw_party(self):
        main, self.font = self.font, self.font_small
        try:
            self._draw_party_screen()
        finally:
            self.font = main

    def _draw_party_screen(self):
        pg, s = self.pg, self.surface
        background = self._party_art("background")
        if background is None:
            self._draw_party_drawn()
            return
        s.blit(background, (0, 0))
        pets = self._party()
        letter, shadow = (248, 248, 248), (112, 112, 112)
        for index in range(6):
            x, y, _w, _h = self.PARTY_SLOTS[index]
            kind = "main" if index == 0 else "wide"
            pet = pets[index] if index < len(pets) else None
            if pet is None:
                frame = self._party_art(f"slot_{kind}_empty") if kind == "wide" else None
                if frame is not None:
                    s.blit(frame, (x, y))
                continue
            member_id = self.game.pet_member_id(pet)
            current, top = self._pet_health(pet, member_id)
            selected = index == self.list_cursor
            state = ("fainted_" if current <= 0 else "") + ("selected" if selected else "")
            state = state.rstrip("_") or "normal"
            frame = self._party_art(f"slot_{kind}", state)
            if frame is not None:
                s.blit(frame, (x, y))
            ball = self._party_art("ball_open" if selected else "ball_closed")
            if ball is not None:
                s.blit(ball, self.PARTY_BALL[index])
            species = self.game.pet_species(pet)
            icon = self._icon(pet.species_id)
            if icon is not None:
                bob = -2 if selected and int(self.time * 6) % 2 else 0
                s.blit(icon, (self.PARTY_ICON[index][0], self.PARTY_ICON[index][1] + bob))
            name_at, level_at, hp_at, top_at, bar_at = self.PARTY_TEXT[kind]
            self._text(pet.name(species), x + name_at[0], y + name_at[1], letter, shadow)
            level = self.tr("creature.level", "Lv{level}", level=pet.level)
            self._text(level, x + level_at[0], y + level_at[1], letter, shadow)
            label = self.slot_label(pet)
            if label is not None:  # ABLE / NOT ABLE... in place of the HP (a TM chosen)
                self._text(label, x + top_at[0], y + hp_at[1], letter, shadow, anchor="topright")
                continue
            self._text(
                f"{current:.0f}", x + hp_at[0], y + hp_at[1], letter, shadow, anchor="topright"
            )
            self._text("/", x + hp_at[0] + 1, y + hp_at[1], letter, shadow)
            self._text(
                f"{top:.0f}", x + top_at[0], y + top_at[1], letter, shadow, anchor="topright"
            )
            self._party_bar(x + bar_at[0], y + bar_at[1], current, top)
        if not self.forced_switch:
            selected = self.list_cursor >= len(pets)
            cancel = self._party_art("cancel_selected" if selected else "cancel_normal")
            if cancel is not None:
                s.blit(cancel, self.PARTY_CANCEL)
            label = self.tr("creature.cancel", "CANCEL")
            cx = self.PARTY_CANCEL[0] + 28
            self._text(label, cx, self.PARTY_CANCEL[1] + 1, letter, shadow, anchor="midtop")
        message = self._party_art("message")
        if message is not None:
            s.blit(message, self.PARTY_MESSAGE)
        text = self.party_note or self.tr("creature.choose", "Choose a creature.")
        self._text(
            text, self.PARTY_MESSAGE[0] + 8, self.PARTY_MESSAGE[1] + 8, *self.colours["menu"]
        )
        _ = pg

    def _draw_party_drawn(self):
        """The party screen without project pictures: shapes in the same places."""
        pg, s = self.pg, self.surface
        s.fill(PARTY_BG)
        for y in range(0, H, 8):
            pg.draw.line(s, (64, 144, 176), (0, y), (W, y))
        pets = self._party()
        for index in range(6):
            pet = pets[index] if index < len(pets) else None
            rect = pg.Rect(self.PARTY_SLOTS[index])
            selected = index == self.list_cursor
            fill = PARTY_SLOT if pet is not None else (72, 120, 144)
            member_id = self.game.pet_member_id(pet) if pet is not None else None
            current, top = self._pet_health(pet, member_id) if pet is not None else (0, 1)
            if pet is not None and current <= 0:
                fill = (200, 104, 96)
            edge = PARTY_SEL if selected else (32, 80, 104)
            pg.draw.rect(s, edge, rect.inflate(2, 2), border_radius=5)
            pg.draw.rect(s, fill, rect, border_radius=4)
            if pet is None:
                continue
            species = self.game.pet_species(pet)
            kind = "main" if index == 0 else "wide"
            icon = self._icon(pet.species_id) or self.pg.transform.scale(
                self._creature_picture(member_id, "enemies"), (32, 32)
            )
            s.blit(icon, self.PARTY_ICON[index])
            name_at, level_at, hp_at, top_at, bar_at = self.PARTY_TEXT[kind]
            x, y = rect.x, rect.y
            white, grey = (248, 248, 248), (64, 64, 64)
            self._text(pet.name(species), x + name_at[0], y + name_at[1], white, grey)
            level = self.tr("creature.level", "Lv{level}", level=pet.level)
            self._text(level, x + level_at[0], y + level_at[1], white, grey)
            self._text(
                f"{current:.0f}/{top:.0f}",
                x + top_at[0],
                y + top_at[1],
                white,
                grey,
                anchor="topright",
            )
            self._party_bar(x + bar_at[0], y + bar_at[1], current, top)
        if not self.forced_switch:
            cancel = pg.Rect(self.PARTY_CANCEL, (52, 18))
            selected = self.list_cursor >= len(pets)
            pg.draw.rect(
                s, PARTY_SEL if selected else (32, 80, 104), cancel.inflate(2, 2), border_radius=5
            )
            pg.draw.rect(s, PARTY_SLOT, cancel, border_radius=4)
            label = self.tr("creature.cancel", "CANCEL")
            self._text(
                label, cancel.centerx, cancel.y + 3, (248, 248, 248), (64, 64, 64), anchor="midtop"
            )
        box = pg.Rect(2, 132, 178 if not self.forced_switch else 236, 26)
        self._window(box, WHITE, CMD_EDGE, CMD_LINE)
        text = self.party_note or self.tr("creature.choose", "Choose a creature.")
        self._text(text, box.x + 8, box.y + 6)

    def _pet_health(self, pet, member_id):
        if self.game.battle is not None and member_id in self.game.battle.members:
            return max(0.0, self._hp(member_id)), self._max_hp(member_id)
        resource = self.game.rules.knockout_resource_id
        top = self.game.pet_resources_at(pet).get(resource, 1.0)
        return pet.resources.get(resource, top), top

    def _party_bar(self, x, y, current, top):
        pg, s = self.pg, self.surface
        share = max(0.0, min(1.0, current / max(1.0, top)))
        colour = HP_GREEN if share > 0.5 else HP_YELLOW if share > 0.2 else HP_RED
        filled = round(48 * share)
        if share > 0 and filled == 0:
            filled = 1
        pg.draw.rect(s, colour, (x, y, filled, 3))
        pg.draw.rect(s, BAR_TRACK, (x + filled, y, 48 - filled, 3))

    def _bag_art(self, name):
        bag = self.settings.get("bag") or {}
        value = bag.get(name)
        key = ("bag", name)
        if key not in self._images:
            image = None
            if isinstance(value, str) and self._path(value).is_file():
                image = self.pg.image.load(str(self._path(value))).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _bag_picture(self, pocket):
        bag = self.settings.get("bag") or {}
        pattern = bag.get("bag")
        key = ("bag_picture", pocket)
        if key not in self._images:
            image = None
            if isinstance(pattern, str):
                path = self._path(pattern.format(pocket=pocket))
                if path.is_file():
                    image = self.pg.image.load(str(path)).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _draw_bag(self):
        background = self._bag_art("background")
        if background is None:
            self._draw_bag_drawn()
            return
        pg, s = self.pg, self.surface
        s.blit(background, (0, 0))
        picture = self._bag_picture(self.BAG_POCKETS[self.pocket])
        if picture is not None:
            s.blit(picture, picture.get_rect(center=self.BAG_CENTRE))
        pockets = (
            self.tr("creature.pocket.items", "ITEMS"),
            self.tr("creature.pocket.balls", "BALLS"),
        )
        self._text(
            pockets[self.pocket],
            *self.BAG_POCKET_NAME,
            (248, 248, 248),
            (232, 64, 56),
            anchor="midtop",
        )
        arrow = self._bag_art("arrow")
        if arrow is not None and int(self.time * 3) % 2:
            s.blit(arrow, self.BAG_ARROWS[0])
            s.blit(pg.transform.flip(arrow, True, False), self.BAG_ARROWS[1])
        items = self._bag_items()
        db = self.game.project.rpg_database
        left, top, width = self.BAG_LIST
        ink, ink_shadow = (72, 72, 72), (208, 208, 200)
        rows = [(i, db.items[i].display_name, f"x{n}") for i, n in items]
        rows.append(("", self.tr("creature.close_bag", "CLOSE BAG"), ""))
        for i, (_item, name, count) in enumerate(rows[:8]):
            y = top + 1 + i * 16
            self._text(name, left + 8, y, ink, ink_shadow)
            if count:
                self._text(count, left + width - 4, y, ink, ink_shadow, anchor="topright")
            if i == self.list_cursor:
                self.font_cursor(left, y)
        if self.list_cursor < len(items):
            item_id = items[self.list_cursor][0]
            item = db.items[item_id]
            icon = self._image("item_icon", item_id, None)
            if icon is not None:
                s.blit(icon, self.BAG_ICON)
            # Players See It and the player's language, as the shop (game.description_of)
            words = self.game.description_of(item, "") or item.display_name
            for i, line in enumerate(self.wrap(words, 104)[:3]):
                y = self.BAG_DESCRIPTION[1] + i * 14
                self._text(line, self.BAG_DESCRIPTION[0], y, (248, 248, 248), (98, 98, 98))

    def font_cursor(self, x, y):
        letter, shadow = self.colours["menu"]
        if self.font is not None and self.font.covers("▶"):
            self.font.render(self.surface, "▶", x, y, letter, shadow)
        else:
            self._cursor(x, y + 2)

    def _draw_bag_drawn(self):
        """The bag without project pictures: shapes in the same places."""
        pg, s = self.pg, self.surface
        s.fill((232, 208, 152))
        for y in range(0, H, 6):
            pg.draw.line(s, (224, 192, 136), (0, y), (W, y))
        pockets = (
            self.tr("creature.pocket.items", "ITEMS"),
            self.tr("creature.pocket.balls", "BALLS"),
        )
        tab = pg.Rect(8, 8, 80, 18)
        self._window(tab, (248, 232, 184), (144, 96, 48))
        self._text(f"< {pockets[self.pocket]} >", tab.centerx, tab.y + 3, anchor="midtop")
        bag = pg.Rect(16, 34, 64, 70)
        pg.draw.rect(s, (200, 120, 72), bag, border_radius=10)
        pg.draw.rect(s, (136, 72, 40), bag, 2, border_radius=10)
        listing = pg.Rect(96, 6, 140, 98)
        self._window(listing, (248, 248, 232), (144, 96, 48))
        items = self._bag_items()
        db = self.game.project.rpg_database
        for i, (item_id, count) in enumerate(items[:6]):
            y = listing.y + 6 + i * 15
            self._text(db.items[item_id].display_name, listing.x + 14, y)
            self._text(f"x{count}", listing.right - 6, y, anchor="topright")
            if i == self.list_cursor:
                self._cursor(listing.x + 5, y + 2)
        if not items:
            self._text(
                self.tr("creature.bag_empty", "Nothing here."), listing.x + 14, listing.y + 6
            )
