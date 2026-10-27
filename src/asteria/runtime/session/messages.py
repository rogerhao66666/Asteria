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

    @property
    def data_lookup(self):
        """``Localizer.lookup`` when the project has translations, else None (the screens then
        draw the records' own text without looking anything up)."""
        localizer = self.localizer
        return localizer.lookup if localizer.tables else None

    def name_of(self, record, fallback=None):
        """A project record's name in the player's language (``rpg/data_text.py``, D60)."""
        from asteria.rpg.data_text import name_of

        return name_of(self.data_lookup, record, fallback)

    def stat_name(self, stat_id, *, short=False):
        """A stat's (or resource's) name in the player's language: the locale table's
        ``data.stat.<id>.name``, else its stat definition's (D91), else the id in words.
        ``short``: the short name (STR) where one is given."""
        from asteria.rpg.data_text import stat_name, stat_short_name

        db = getattr(self.project, "rpg_database", None)
        definition = getattr(db, "stat_definitions", {}).get(str(stat_id))
        find = stat_short_name if short else stat_name
        return find(self.data_lookup, stat_id, {}, definition)

    def slot_name(self, slot_id):
        """An equipment slot's name (``data.slot.<id>.name``, else the slot definition's name,
        else the engine's word for it)."""
        from asteria.rpg.data_text import slot_name

        labels = {}
        db = getattr(self.project, "rpg_database", None)
        definition = getattr(db, "equipment_slots", {}).get(str(slot_id))
        own = self.name_of(definition, "") if definition is not None else ""
        if own:
            labels[str(slot_id)] = own
        return slot_name(self.data_lookup, slot_id, labels)

    def socket_name(self, equipment, socket_id):
        """A socket's name: ``data.socket.<equipment id>.<socket id>`` in the locale table,
        else the socket's own label, else "Socket <n>" by its place on the equipment (U1)."""
        from asteria.rpg.data_text import PREFIX

        sockets = tuple(getattr(equipment, "sockets", ()) or ())
        index = next((i for i, s in enumerate(sockets) if s.socket_id == socket_id), None)
        lookup = self.data_lookup
        equipment_id = getattr(equipment, "equipment_id", "")
        found = None
        if lookup is not None and equipment_id:
            found = lookup(f"{PREFIX}socket.{equipment_id}.{socket_id}.name")
        if found:
            return found
        if index is not None and sockets[index].label:
            return sockets[index].label
        number = index + 1 if index is not None else socket_id
        return self.tr("socket.number", "Socket {number}", number=number)

    def tag_name(self, tag):
        """A tag's name (a socket accepts "gem", "card"...): ``data.tag.<tag>.name``, else its
        definition's name (Game Systems ▸ Tags, D91), else the tag in words (U3)."""
        from asteria.rpg.data_text import key, words

        record = getattr(self.project.rpg_database, "tag_definitions", {}).get(str(tag).lower())
        named = self.name_of(record, "") if record is not None else ""
        if named:
            return named
        lookup = self.data_lookup
        return (lookup(key("tag", tag)) if lookup is not None else None) or words(tag)

    def points_name(self, currency):
        """A skill-tree point's short name: ``data.points.<id>.name``, else the built-in
        words (AP, SP, stat points, "<class> JP" for ``jp.<class>``), else the id."""
        from asteria.rpg.data_text import key, words

        currency = str(currency)
        lookup = self.data_lookup
        found = lookup(key("points", currency)) if lookup is not None else None
        if found:
            return found
        if currency.startswith("jp."):
            job = currency[3:]
            name = self.name_of(self.project.rpg_database.classes.get(job), words(job))
            return self.tr("points.jp", "{name} JP", name=name)
        if currency == "ap":
            return self.tr("points.ap", "AP")
        if currency == "skill_points":
            return self.tr("points.skill_points", "SP")
        if currency == "stat_points":
            return self.tr("points.stat_points", "Stat points")
        return words(currency).upper() if len(currency) <= 3 else words(currency)

    def stat_amount(self, stat_id, value, operation="add"):
        """``value`` of a stat written its way (Game Systems ▸ Stats): ``+12``, ``+3%``,
        ``x1.6`` (D91)."""
        from asteria.rpg.effect_text import amount

        definition = getattr(self.project.rpg_database, "stat_definitions", {}).get(stat_id)
        return amount(value, operation, definition)

    def effect_lines(self, modifiers):
        """What ``modifiers`` (a passive's, a state's, gear's) do, a line per stat, in the
        player's language: ``MAG +18``, ``Crit Rate +3% (when Sword)`` (D91)."""
        from asteria.rpg.effect_text import modifier_lines

        return modifier_lines(
            modifiers,
            lambda stat: self.stat_name(stat, short=True),
            getattr(self.project.rpg_database, "stat_definitions", {}),
            self.tag_name,
            self.tr,
        )

    def description_of(self, record, fallback=""):
        """A project record's description in the player's language (D60)."""
        from asteria.rpg.data_text import description_of

        return description_of(self.data_lookup, record, fallback)

    def line_text(self, line):
        """A dialogue line's (or choice's) text in the player's language: the locale table's
        text under its ``text_key``, else the text as written (D60)."""
        from asteria.rpg.data_text import text_by_key

        return text_by_key(self.data_lookup, getattr(line, "text_key", ""), line.text)

    def speaker_of(self, line):
        """Who speaks ``line``, in the player's language (``data.speaker.<name>.name``)."""
        from asteria.rpg.data_text import speaker_name

        return speaker_name(self.data_lookup, line.speaker)

    TITLE_ACTIONS = ("new_game", "continue", "load", "screen", "quit")

    def request_title(self, action, screen=""):
        """TITLE_COMMAND, from a title screen's event program (``title_screen.program``): the
        host starts a new game, continues the latest save, opens the load slots, opens a game
        menu ``screen`` by itself (``options``, ``dex``...; leaving it comes back to the title)
        or quits."""
        action = str(action or "")
        if action not in self.TITLE_ACTIONS:
            raise GameSessionError(f"TITLE_COMMAND action is one of {self.TITLE_ACTIONS}")
        if action == "screen" and not str(screen or ""):
            raise GameSessionError("TITLE_COMMAND screen needs the screen to open")
        self.title_request = {"action": action, "screen": str(screen or "")}
        return self.title_request

    def update_title(self, dt=0.0):
        """A title screen's frame: its event program and the pictures only (no scene, common
        or timer events: no game has started)."""
        try:
            self.events.update(dt)
        except Exception as exc:  # noqa: BLE001 - a broken title: kept in event_errors
            self.event_errors.append(exc)
            self.events.stop()
        self.pictures.update(dt)

    def request_name_input(self, target, *, max_length=7, title="", default="", initial=""):
        """NAME_INPUT: the name screen opens (the host draws it); ``finish_name_input`` gives
        the name to ``target`` - ``variable:<name>`` or ``pet:last`` / ``pet:<instance id>``."""
        target = str(target or "")
        if not target.startswith(("variable:", "pet:")):
            raise GameSessionError("NAME_INPUT target is variable:<name> or pet:<id>")
        self.name_input_request = {
            "target": target,
            "max_length": int(max_length or 7),
            "title": str(title or ""),
            "default": str(default or ""),
            "initial": str(initial or ""),
        }
        return self.name_input_request

    def name_input_pet(self):
        """The creature being named by the open name screen, or None."""
        request = getattr(self, "name_input_request", None) or {}
        target = str(request.get("target", ""))
        if not target.startswith("pet:"):
            return None
        pets = list(self.pets())
        if target == "pet:last":
            return pets[-1] if pets else None
        return next((p for p in pets if p.instance_id == target[4:]), None)

    def finish_name_input(self, name):
        """The name screen's answer: the variable or the creature's nickname gets ``name``."""
        request = getattr(self, "name_input_request", None)
        if not request:
            return False
        target = request["target"]
        if target.startswith("variable:"):
            self.save.event_context.set_variable(target[len("variable:") :], str(name))
        else:
            pet = self.name_input_pet()
            if pet is not None:
                pet.nickname = str(name)
        self.name_input_request = None
        return True

    def request_picture_choice(self, layout, variable):
        """PICTURE_CHOICE: the host shows the layout's pictured options; the chosen one's value
        goes to ``variable`` (``finish_picture_choice``)."""
        self.picture_choice_request = {"layout": str(layout), "variable": str(variable)}
        return self.picture_choice_request

    def finish_picture_choice(self, value):
        request = getattr(self, "picture_choice_request", None)
        if not request:
            return False
        if request["variable"] and value is not None:
            self.save.event_context.set_variable(request["variable"], value)
        self.picture_choice_request = None
        return True

    @property
    def held_dialogue(self):
        """The line shown without waiting for a key (DIALOGUE ``wait`` false), or None."""
        return next((r.dialogue.held for r in self._all_runners() if r.dialogue.held), None)

    def prompt_of(self, request):
        """A choice's prompt in the player's language (its ``prompt_key``), else as written."""
        from asteria.rpg.data_text import text_by_key

        return text_by_key(self.data_lookup, getattr(request, "prompt_key", ""), request.prompt)

    def speaker_name(self, name):
        """A person's name as written in the events or on an entity, in the player's language
        (``data.speaker.<name>.name``): NPCs carry their speaking name."""
        from asteria.rpg.data_text import speaker_name

        return speaker_name(self.data_lookup, name)

    def map_name(self, scene_id, own):
        """A map's name in the player's language (``data.map.<scene id>.name``, D60)."""
        from asteria.rpg.data_text import map_name

        return map_name(self.data_lookup, scene_id, own)

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
            return self._message_word(name) if value is None else value

        def party(index):
            ids = state.party_active_actor_ids
            actor = db.actors.get(ids[index - 1]) if 0 < index <= len(ids) else None
            return None if actor is None else self.name_of(actor)

        def actor_name(actor_id):
            actor = db.actors.get(actor_id)
            return None if actor is None else self.name_of(actor)

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

    def _message_word(self, name):
        """The words ``\\V[...]`` has for a name no variable holds: ``play.time`` (the time
        played, ``h:mm``) and ``creatures.owned`` (species owned now or ever caught)."""
        if name == "play.time":
            seconds = int(self.world.counters.get("play.seconds", 0.0))
            return f"{seconds // 3600}:{seconds % 3600 // 60:02d}"
        if name == "creatures.owned":
            owned = {p.species_id for p in self.pets()}
            owned |= {k for k, v in self.world.bestiary.items() if v.get("captured", 0) > 0}
            return len(owned)
        return None

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

    def hover_choice(self, index):
        """The pointer came to choice ``index`` of the waiting choice: its ``hover`` commands
        run (errors are kept in ``event_errors``)."""
        runner = self._dialogue_runner()
        if runner is None:
            return False
        try:
            return runner.hover_choice(index)
        except Exception as exc:  # noqa: BLE001 - a wrong hover command: the event's error
            self.event_errors.append(exc)
            return False

    def cancel_choice(self):
        """The cancel key on the waiting choice: its ``cancel`` value when it has one (True),
        else nothing happens (False)."""
        runner = self._dialogue_runner()
        if runner is None or not runner.cancel_choice():
            return False
        self.update_events(0.0)
        return True

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
