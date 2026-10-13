"""Pets screen (pause menu > Pets): the creatures the player owns.

A list of owned pets with icon, nickname and species, level, an experience bar and the species'
stats at that level. Up / Down choose, Enter makes the highlighted pet the active one (the one
abilities send out), R renames it (type, Enter keeps, Esc cancels), Esc / P close.
Everything comes from the project's pet species and the save; nothing here knows a game.
"""

from __future__ import annotations

MUTED, TITLE, GOOD = (150, 160, 180), (255, 220, 124), (130, 230, 150)


class PetsScreen:
    """Made when opened; each frame ``handle(dt, events)`` then ``draw()``; ``closed`` ends it."""

    def __init__(self, runtime):
        self.rt = runtime
        self.index = 0
        self.closed = False
        self.renaming = None  # the text being typed, or None
        self.message, self.message_left = "", 0.0

    @property
    def game(self):
        return self.rt.game

    def pets(self):
        return self.game.pets()

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
            self.game.set_active_pet(pet.instance_id)
            self._say(f"{pet.name(self.game.pet_species(pet))} will be sent out")
        for event in events:
            if event.type == pg.KEYDOWN and event.key == pg.K_r:
                self.renaming = pet.nickname

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
                self._say("Renamed")
            elif event.key == pg.K_BACKSPACE:
                self.renaming = self.renaming[:-1]
            elif getattr(event, "unicode", "") and event.unicode.isprintable():
                if len(self.renaming) < 24:
                    self.renaming += event.unicode

    # -- drawing ---------------------------------------------------------------------------------
    def draw(self):
        rt = self.rt
        pg, screen = rt.pg, rt.screen
        game = self.game
        screen.fill((10, 12, 20))
        rt.text("Pets", 36, 22, size=34, color=TITLE)
        hint = "Up / Down: choose   Enter: send this one out   R: rename   Esc: back"
        rt.text(hint, 36, 62, size=18, color=MUTED)
        pets = self.pets()
        if not pets:
            rt.text("You have no pets yet.", 36, 110, size=22, color=MUTED)
            return
        active = game.active_pet()
        row_h = 64
        for i, pet in enumerate(pets):
            species = game.pet_species(pet)
            y = 100 + i * (row_h + 8)
            rect = pg.Rect(36, y, rt.width - 72, row_h)
            selected = i == min(self.index, len(pets) - 1)
            pg.draw.rect(screen, (30, 40, 62) if selected else (20, 24, 38), rect, border_radius=8)
            pg.draw.rect(
                screen, TITLE if selected else (60, 66, 84), rect, 2 if selected else 1, 8
            )
            if not (species and species.icon_id and rt._draw_icon(species.icon_id, 48, y + 8, 48)):
                rt.text(
                    pet.species_id[:2].upper(),
                    72,
                    y + row_h / 2,
                    size=28,
                    color=TITLE,
                    anchor="center",
                )
            name = pet.name(species)
            if self.renaming is not None and selected:
                name = self.renaming + "_"
            rt.text(name, 112, y + 8, size=24, color=(255, 255, 255))
            kind = species.display_name if species else pet.species_id
            rt.text(f"{kind}   Lv {pet.level}", 112, y + 36, size=18, color=MUTED)
            if pet is active:
                rt.text("ACTIVE", rect.right - 100, y + 10, size=20, color=GOOD)
            need = species.exp_to_next(pet.level) if species else 1.0
            full = species is not None and pet.level >= species.max_level
            fraction = 1.0 if full else max(0.0, min(1.0, pet.experience / need))
            bar = pg.Rect(rect.right - 260, y + 40, 220, 10)
            pg.draw.rect(screen, (14, 16, 24), bar.inflate(2, 2), border_radius=4)
            pg.draw.rect(
                screen, (214, 172, 58), (bar.x, bar.y, int(bar.w * fraction), bar.h), 0, 4
            )
            if species is not None:
                stats = "   ".join(
                    f"{k.replace('_', ' ').capitalize()} {v:g}"
                    for k, v in species.stats_at(pet.level).items()
                )
                rt.text(stats, rect.right - 560, y + 12, size=18, color=(170, 210, 240))
        if self.renaming is not None:
            rt.text(
                "Type a name, Enter keeps it, Esc cancels",
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
