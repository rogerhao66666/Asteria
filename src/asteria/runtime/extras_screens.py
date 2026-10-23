"""Pause-menu extras: the message log, the music room and the credits.

Each screen is made when opened; every frame ``handle(dt, events)`` then ``draw()``; ``closed``
ends it. They read the session and the project's data and know no game.
"""

from __future__ import annotations

from asteria.rpg.built_in_text import translated

MUTED, TITLE, GOOD = (150, 160, 180), (255, 220, 124), (130, 230, 150)


class _Screen:
    def __init__(self, runtime):
        self.rt = runtime
        self.index = 0
        self.closed = False

    @property
    def game(self):
        return self.rt.game

    def tr(self, key, english, **params):
        """The screen's own words in the player's language (``rpg.built_in_text``)."""
        return self.rt.game.tr(key, english, **params)

    def _move(self, count):
        inp = self.rt.input
        if inp.just_pressed("cancel"):
            self.closed = True
        elif count:
            if inp.just_pressed("move_up"):
                self.index = (self.index - 1) % count
            if inp.just_pressed("move_down"):
                self.index = (self.index + 1) % count


class BacklogScreen(_Screen):
    """The lines read so far; opens on the newest, Up / Down scroll."""

    PAGE = 8

    def __init__(self, runtime):
        super().__init__(runtime)
        self.index = max(0, len(runtime.game.backlog) - 1)

    def handle(self, dt=0.0, events=()):
        self._move(len(self.game.backlog))

    def visible(self):
        entries = self.game.backlog.entries()
        top = max(0, min(self.index - self.PAGE + 1, len(entries) - self.PAGE))
        return top, entries[top : top + self.PAGE]

    def draw(self):
        rt = self.rt
        rt.screen.fill((10, 12, 20))
        rt.text(self.tr("backlog.title", "Message Log"), 36, 22, size=34, color=TITLE)
        hint = self.tr("backlog.hint", "Up / Down: scroll   Esc: back")
        rt.text(hint, 36, 62, size=18, color=MUTED)
        top, entries = self.visible()
        if not entries:
            empty = self.tr("backlog.empty", "Nothing has been said yet.")
            rt.text(empty, 36, 110, size=22, color=MUTED)
            return
        y = 100
        for offset, entry in enumerate(entries):
            current = top + offset == self.index
            color = (255, 255, 255) if current else (190, 196, 210)
            if entry.speaker:
                rt.text(entry.speaker, 36, y, size=22, color=TITLE)
                y += 26
            rt.text(entry.text, 60, y, size=22, color=color)
            y += 38


class MusicRoomScreen(_Screen):
    """Tracks the player has heard (or that are always open); Enter plays, Esc closes."""

    def __init__(self, runtime):
        super().__init__(runtime)
        self.playing = ""

    def tracks(self):
        tracks = sorted(
            self.game.project.rpg_database.music_tracks.values(), key=lambda t: t.track_id
        )
        return [(t, self.unlocked(t)) for t in tracks]

    def unlocked(self, track):
        context = self.game.save.event_context
        if not track.unlock_switch:
            return True
        return context.get_switch(track.unlock_switch) or context.get_switch(
            f"music.heard.{track.track_id}"
        )

    def handle(self, dt=0.0, events=()):
        rows = self.tracks()
        self._move(len(rows))
        inp = self.rt.input
        if rows and (inp.just_pressed("confirm") or inp.just_pressed("interact")):
            track = rows[min(self.index, len(rows) - 1)][0]
            if self.unlocked(track):
                self.rt.audio.play_music(track.asset_id, fade_in=0.3)
                self.playing = track.track_id
        if self.closed:
            self.rt.audio.stop_music(fade_out=0.3)

    def draw(self):
        rt = self.rt
        rt.screen.fill((10, 12, 20))
        rt.text(self.tr("music.title", "Music Room"), 36, 22, size=34, color=TITLE)
        hint = self.tr("music.hint", "Up / Down: choose   Enter: play   Esc: back")
        rt.text(hint, 36, 62, size=18, color=MUTED)
        rows = self.tracks()
        if not rows:
            rt.text(self.tr("music.empty", "There are no tracks."), 36, 110, size=22, color=MUTED)
            return
        for i, (track, _) in enumerate(rows):
            open_ = self.unlocked(track)
            y = 100 + i * 36
            selected = i == min(self.index, len(rows) - 1)
            name = track.name if open_ else self.tr("music.locked", "? ? ?")
            color = (255, 255, 255) if selected else ((190, 196, 210) if open_ else (96, 102, 120))
            rt.text(">" if selected else "", 22, y, size=26, color=color)
            # an opened track shows its picture; a closed one keeps it secret
            shown = open_ and rt._draw_icon(track.icon_id, 36, y - 3, 28)
            rt.text(name, 72 if shown else 44, y, size=26, color=color)
            if track.track_id == self.playing:
                playing = self.tr("music.playing", "PLAYING")
                rt.text(playing, rt.width - 140, y + 4, size=20, color=GOOD)
            elif open_ and track.note:
                rt.text(track.note, rt.width - 360, y + 6, size=18, color=MUTED)


class CreditsScreen(_Screen):
    """The credits pages in order; Left / Right (or Enter) turn the page."""

    def pages(self):
        return sorted(
            self.game.project.rpg_database.credits_pages.values(),
            key=lambda p: (p.order, p.page_id),
        )

    def handle(self, dt=0.0, events=()):
        inp = self.rt.input
        pages = self.pages()
        if inp.just_pressed("cancel"):
            self.closed = True
            return
        if pages:
            if inp.just_pressed("move_right") or inp.just_pressed("confirm"):
                self.index = (self.index + 1) % len(pages)
            if inp.just_pressed("move_left"):
                self.index = (self.index - 1) % len(pages)

    def draw(self):
        rt = self.rt
        rt.screen.fill((10, 12, 20))
        pages = self.pages()
        title = self.tr("credits.title", "Credits")
        if not pages:
            rt.text(title, 36, 22, size=34, color=TITLE)
            return
        page = pages[min(self.index, len(pages) - 1)]
        rt.text(page.title or title, rt.width / 2, 60, size=40, color=TITLE, center=True)
        for row, line in enumerate(page.lines):
            rt.text(
                line, rt.width / 2, 130 + row * 30, size=24, color=(230, 232, 240), center=True
            )
        rt.text(
            self.tr(
                "credits.hint",
                "Left / Right: page   {page}/{pages}   Esc: back",
                page=self.index + 1,
                pages=len(pages),
            ),
            rt.width / 2,
            rt.height - 36,
            size=18,
            color=MUTED,
            center=True,
        )


__all__ = ["BacklogScreen", "CreditsScreen", "MusicRoomScreen"]


class AbilitySlotsScreen(_Screen):
    """Skill slots (``AbilityLoadoutRules``): the party member's learned abilities; Enter puts one
    in a slot or takes it out, Left / Right change the member, Esc closes."""

    def __init__(self, runtime):
        super().__init__(runtime)
        self.member = 0
        self.message, self.message_left = "", 0.0

    def actors(self):
        return tuple(self.game.save.rpg_state.party_actor_ids)

    def actor_id(self):
        actors = self.actors()
        return actors[self.member % len(actors)] if actors else None

    def learned(self, actor_id):
        return self.game.slot_candidates(actor_id)

    def handle(self, dt=0.0, events=()):
        from asteria.runtime.game_session import GameSessionError

        actor_id = self.actor_id()
        learned = self.learned(actor_id) if actor_id else ()
        self.message_left = max(0.0, self.message_left - dt)
        self._move(len(learned))
        inp = self.rt.input
        actors = self.actors()
        if actors and inp.just_pressed("move_left"):
            self.member, self.index = (self.member - 1) % len(actors), 0
        if actors and inp.just_pressed("move_right"):
            self.member, self.index = (self.member + 1) % len(actors), 0
        if not learned or not (inp.just_pressed("confirm") or inp.just_pressed("interact")):
            return
        ability_id = learned[self.index % len(learned)]
        equipped, _capacity = self.game.ability_slots(actor_id)
        try:
            if ability_id in equipped:
                self.game.unequip_ability(actor_id, ability_id)
            else:
                self.game.equip_ability(actor_id, ability_id)
        except GameSessionError as exc:
            self.message, self.message_left = translated(exc, self.game.tr), 2.5

    def draw(self):
        rt = self.rt
        rt.screen.fill((10, 12, 20))
        rt.text(self.tr("skill_slots.title", "Skill Slots"), 36, 22, size=34, color=TITLE)
        rt.text(
            self.tr(
                "skill_slots.hint",
                "Up / Down: choose   Enter: equip / remove   Left / Right: member   Esc: back",
            ),
            36,
            62,
            size=18,
            color=MUTED,
        )
        actor_id = self.actor_id()
        if actor_id is None:
            empty = self.tr("skill_slots.no_party", "No party members.")
            rt.text(empty, 36, 110, size=22, color=MUTED)
            return
        actor = self.game.project.rpg_database.actors.get(actor_id)
        equipped, capacity = self.game.ability_slots(actor_id)
        name = self.game.name_of(actor, actor_id)
        slots = self.tr(
            "skill_slots.count",
            "{name}   Slots {used}/{capacity}",
            name=name,
            used=len(equipped),
            capacity=capacity,
        )
        rt.text(slots, 36, 96, size=24, color=(255, 255, 255))
        learned = self.learned(actor_id)
        if not learned:
            empty = self.tr("skill_slots.nothing", "Nothing learned yet.")
            rt.text(empty, 36, 140, size=22, color=MUTED)
        library = self.game.project.gameplay_library.abilities
        for row, ability_id in enumerate(learned):
            definition = library.get(ability_id)
            label = self.game.name_of(definition) or ability_id.replace("_", " ").title()
            on = ability_id in equipped
            current = row == self.index % len(learned)
            color = GOOD if on else ((255, 255, 255) if current else (190, 196, 210))
            y = 140 + row * 32
            shown = rt._draw_icon(getattr(definition, "icon_id", ""), 36, y - 3, 28)
            rt.menu_row(label, 72 if shown else 36, y, selected=current, size=24, color=color)
            mark = self.tr("skill_slots.equipped", "EQUIPPED") if on else ""
            rt.text(mark, rt.width - 200, y, size=20, color=GOOD)
        if self.message_left > 0:
            rt.text(
                self.message,
                rt.width / 2,
                rt.height - 40,
                size=20,
                color=(255, 190, 160),
                center=True,
            )
