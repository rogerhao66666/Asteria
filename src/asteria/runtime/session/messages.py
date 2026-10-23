"""Messages, translation, the message log, battle weather, dialogue and event updates."""

from __future__ import annotations

from asteria.presentation.message_codes import MessageContext, expand_message, plain_message

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class MessagesMixin:
    # --- messages, translation and the message log ------------------------------------------
    @property
    def message_settings(self):
        values = self.project.rpg_database.message_settings
        return values[sorted(values)[0]] if values else None

    def _backlog_limit(self):
        settings = self.message_settings
        return settings.backlog_limit if settings is not None else 0

    LOCALE_VARIABLE = "locale.current"

    @property
    def localizer(self):
        """The project's translations (``rpg.localization``) at the player's chosen locale."""
        localizer = self._localizer
        if localizer is None:  # made once: the screens ask for their words every frame
            from asteria.rpg.localization import Localizer

            settings = self.message_settings
            localizer = self._localizer = Localizer(
                self.project.rpg_database.locale_tables.values(),
                default_locale=settings.default_locale if settings else "",
            )
        chosen = self.save.event_context.get_variable(self.LOCALE_VARIABLE, "")
        localizer.locale = str(chosen or localizer.default_locale)
        return localizer

    def set_locale(self, locale):
        if str(locale) not in self.localizer.locales():
            raise GameSessionError(f"unknown locale: {locale}")
        self.save.event_context.set_variable(self.LOCALE_VARIABLE, str(locale))
        return str(locale)

    def tr(self, key, default=None, **params):
        return self.localizer.tr(key, default, **params)

    def message_context(self):
        """What ``\\V[..]``, ``\\N[..]``, ``\\G``, ``\\M[..]`` and ``\\T[..]`` read."""
        db = self.project.rpg_database
        state = self.save.rpg_state
        settings = self.message_settings
        context = self.save.event_context
        currency = settings.currency_id if settings else "gold"

        def variable(name):
            value = context.get_variable(name)
            return None if value is None else value

        def party(index):
            ids = state.party_active_actor_ids
            actor = db.actors.get(ids[index - 1]) if 0 < index <= len(ids) else None
            return None if actor is None else actor.display_name

        def actor_name(actor_id):
            actor = db.actors.get(actor_id)
            return None if actor is None else actor.display_name

        return MessageContext(
            variable=variable,
            switch=context.get_switch,
            actor_name=actor_name,
            party_name=party,
            currency_label=(settings.currency_label if settings else "") or currency,
            currency_amount=lambda: state.currencies.get(currency, 0.0),
            macros=dict(settings.macros) if settings else None,
            translate=self.localizer.lookup,
        )

    def expand_message(self, text, *, plain=False):
        """A message with its data codes replaced; ``plain`` also drops the formatting codes."""
        if plain:
            return plain_message(text, self.message_context())
        return expand_message(text, self.message_context())

    def message_icon(self, number):
        """The icon asset for ``\\I[number]``: the project's message settings map numbers to icon
        ids; with no mapping the number is itself tried as an icon id."""
        settings = self.message_settings
        mapped = dict(settings.icons) if settings is not None else {}
        return mapped.get(str(number), "")

    BATTLE_WEATHER = "battle.weather"  # event variable: rain, snow, leaves, dust or "" for none
    BATTLE_WEATHER_INTENSITY = "battle.weather.intensity"
    WEATHER_TAG_PREFIX = "weather."

    def battle_weather(self):
        """``(kind, intensity, wind)`` of the weather set for battles, or ``None``. It is separate
        from the map's weather: set it with ``SET_BATTLE_WEATHER`` or the event variables."""
        kind = str(self.save.event_context.get_variable(self.BATTLE_WEATHER, "") or "")
        if not kind or kind == "none":
            return None
        intensity = float(
            self.save.event_context.get_variable(self.BATTLE_WEATHER_INTENSITY, 0.6) or 0.0
        )
        return (
            kind,
            max(0.0, min(1.0, intensity)),
            float(self.save.event_context.get_variable("battle.weather.wind", 0.0) or 0.0),
        )

    def set_battle_weather(self, kind, intensity=0.6, wind=0.0):
        """Choose the weather the next battles (and the running one) have; ``"none"`` clears it.
        Every fighter carries the tag ``weather.<kind>`` while it lasts, so interaction rules can
        react to it (rain strengthens lightning, snow slows...)."""
        from asteria.runtime.environment2d import WEATHER_KINDS

        kind = str(kind or "none")
        if kind not in WEATHER_KINDS:
            raise GameSessionError(f"unknown weather {kind!r}; choose from {WEATHER_KINDS}")
        context = self.save.event_context
        context.set_variable(self.BATTLE_WEATHER, "" if kind == "none" else kind)
        context.set_variable(self.BATTLE_WEATHER_INTENSITY, float(intensity))
        context.set_variable("battle.weather.wind", float(wind))
        if self.mode == "battle" and self.battle is not None:
            self._sync_weather_tags()
        return self.battle_weather()

    def _sync_weather_tags(self):
        weather = self.battle_weather()
        for member in self.battle.members.values():
            tags = member.subject.tags
            for tag in [t for t in tags.values() if t.startswith(self.WEATHER_TAG_PREFIX)]:
                tags.remove(tag)
            if weather is not None:
                tags.add(f"{self.WEATHER_TAG_PREFIX}{weather[0]}")

    def click_picture(self, x, y, size_of):
        """The player clicked the screen at ``(x, y)``: the topmost clickable picture there starts
        its event program (queued behind a running event). Returns that picture, or ``None``."""
        if self.mode != "field":
            return None
        picture = self.pictures.hit_test(x, y, size_of)
        if picture is not None:
            self.pending_followups.append(picture.click_event)
        return picture

    def note_music_heard(self, asset_id):
        """Playing a track opens it in the music room (``music.heard.<track id>``)."""
        for track in self.project.rpg_database.music_tracks.values():
            if track.asset_id == str(asset_id):
                self.save.event_context.set_switch(f"music.heard.{track.track_id}", True)

    def acknowledge_dialogue(self):
        runner = self._dialogue_runner()
        if runner is None:
            raise GameSessionError("no dialogue is waiting")
        runner.acknowledge_dialogue()
        return self.update_events(0.0)

    def choose(self, index):
        runner = self._dialogue_runner()
        if runner is None:
            raise GameSessionError("no choice is waiting")
        selected = runner.choose(index)
        self.update_events(0.0)
        return selected

    def update_events(self, dt=0.0):
        """Advance running event programs. Failures stop that event and are kept in
        event_errors."""
        output = ()
        try:
            output = self.events.update(dt)
        except Exception as exc:
            self.event_errors.append(exc)
            self.events.stop()
        if not self.events.busy:
            self.events.clear_completed()
        if self.scene_events is not None and self.mode == "field" and not self.events.busy:
            try:
                self.scene_events.update(dt)
            except Exception as exc:
                self.event_errors.append(exc)
                self.scene_events.scheduler.stop_all()
        if self.mode == "field" and not self.events.busy:
            try:
                self._refresh_common_events()
                self.common_events.update(dt)
            except Exception as exc:
                self.event_errors.append(exc)
                self.common_events.stop_all()
        self.pictures.update(dt)
        if self.mode == "field":
            for finished in self.timers.update(dt):  # event timers (TIMER_START ...)
                if finished.on_expire:
                    self.pending_followups.append(finished.on_expire)
        if self.pending_followups and not self.events.busy:
            self.events.clear_completed()
            self.events.start(self.pending_followups.pop(0))  # an interaction's follow-up event
        if self.mode == "battle" and self.battle_events is not None and not self.events.busy:
            self.battle_events.pump()  # queued battle events start once the previous one finished
        return output
