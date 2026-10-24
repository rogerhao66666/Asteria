"""Standard WORLD command handlers a game session registers for event programs.

Event programs ask for world operations by name (``WORLD`` instructions);
these handlers carry them out against a :class:`GameSessionRuntime`.
Presentation-only requests (music, sound, screen effects) are queued on the
session for whichever presentation layer is attached, so the event VM never
depends on an audio or render backend.
"""

from __future__ import annotations

from asteria.core import Transform

STANDARD_WORLD_COMMANDS = (
    "START_ENCOUNTER",
    "TRANSFER",
    "GIVE_ITEM",
    "TAKE_ITEM",
    "CHANGE_CURRENCY",
    "OPEN_SHOP",
    "START_QUEST",
    "ADVANCE_QUEST",
    "COMPLETE_QUEST",
    "FAIL_QUEST",
    "CHANGE_REPUTATION",
    "CHANGE_RELATIONSHIP",
    "ADD_COUNTER",
    "LEARN_RECIPE",
    "OPEN_CRAFTING",
    "OPEN_QUEST_BOARD",
    "OPEN_RECRUIT",
    "OPEN_GACHA",
    "PLAY_BGM",
    "STOP_BGM",
    "RESTORE_BGM",
    "PLAY_SE",
    "SCREEN_FADE",
    "CAMERA_FOCUS",
    "CAMERA_RELEASE",
    "CAMERA_SHAKE",
    "PLAY_VFX",
    "PLAY_ACTION",
    "INTERACT",
    "SET_NPC",
    "MOVE_NPC",
    "SUMMON",
    "SHOW_POPUP",
    "SET_CLASSES",
    "JOIN_PARTY",
    "LEAVE_PARTY",
    "BATTLE_SEQUENCE",
    "LEARN_ABILITY",
    "SET_LOCALE",
    "NEW_GAME_PLUS",
    "REST_PARTY",
    "HEAL_PETS",
    "PET_STORAGE",
    "GRANT_EXPERIENCE",
    "REFINE_EQUIPMENT",
    "SOCKET_ITEM",
    "UNSOCKET_ITEM",
    "UPGRADE_EQUIPMENT",
    "EQUIP_ITEM",
    "GIVE_EQUIPMENT",
    "DISASSEMBLE",
)

PRESENTATION_COMMANDS = (
    "PLAY_BGM",
    "STOP_BGM",
    "RESTORE_BGM",
    "PLAY_SE",
    "SCREEN_FADE",
    "CAMERA_FOCUS",
    "CAMERA_RELEASE",
    "CAMERA_SHAKE",
    "PLAY_VFX",
)

# Argument names each standard command reads; editors use these as prompts.
WORLD_COMMAND_ARGUMENTS = {
    "START_ENCOUNTER": ("encounter_id",),
    "TRANSFER": ("scene_id", "x", "y", "facing"),
    "GIVE_ITEM": ("item_id", "quantity"),
    "TAKE_ITEM": ("item_id", "quantity"),
    "CHANGE_CURRENCY": ("currency_id", "amount"),
    "OPEN_SHOP": ("shop_id",),
    "START_QUEST": ("quest_id",),
    "ADVANCE_QUEST": ("quest_id", "objective_id", "amount"),
    "COMPLETE_QUEST": ("quest_id",),
    "FAIL_QUEST": ("quest_id",),
    "CHANGE_REPUTATION": ("faction_id", "amount"),
    "CHANGE_RELATIONSHIP": ("subject_id", "amount"),
    "ADD_COUNTER": ("counter_id", "amount"),
    "LEARN_RECIPE": ("recipe_id",),
    "OPEN_CRAFTING": ("station",),
    "OPEN_QUEST_BOARD": ("board_id",),
    "OPEN_RECRUIT": ("office_id",),
    "OPEN_GACHA": ("banner_id",),
    "PLAY_BGM": ("asset_id", "fade", "volume", "temporary"),
    "STOP_BGM": ("fade",),
    "RESTORE_BGM": (),
    "PLAY_SE": ("asset_id", "volume"),
    "SCREEN_FADE": ("to", "duration", "color"),
    "PLAY_VFX": ("asset_id", "entity", "x", "y", "scale", "anchor"),
    "PLAY_ACTION": ("entity", "timeline_id"),
    "INTERACT": ("interaction_id",),
    "SET_NPC": ("npc", "key", "value"),
    "MOVE_NPC": ("npc", "scene_id", "x", "y"),
    "CAMERA_FOCUS": ("entity", "x", "y", "zoom", "blend", "ease"),
    "CAMERA_RELEASE": ("blend", "ease"),
    "CAMERA_SHAKE": ("intensity", "duration"),
    "SUMMON": ("enemy_id", "actor_id", "count", "owner_id"),
    "SHOW_POPUP": ("text", "entity", "duration_ms", "kind"),
    "SET_CLASSES": ("actor_id", "class_ids", "unlock"),
    "JOIN_PARTY": ("actor_id", "active"),
    "BATTLE_SEQUENCE": ("sequence_id", "actor_id", "target_id"),
    "LEARN_ABILITY": ("actor_id", "ability_id"),
    "SET_LOCALE": ("locale",),
    "NEW_GAME_PLUS": ("rules_id",),
    "LEAVE_PARTY": ("actor_id",),
    "REST_PARTY": (),
    "HEAL_PETS": ("party_only",),
    "PET_STORAGE": (),
    "GRANT_EXPERIENCE": ("actor_id", "amount", "threshold", "points", "level_track"),
    "REFINE_EQUIPMENT": ("actor_id", "instance_id", "protect"),
    "SOCKET_ITEM": ("actor_id", "instance_id", "socket_id", "item_id"),
    "UNSOCKET_ITEM": ("actor_id", "instance_id", "socket_id"),
    "UPGRADE_EQUIPMENT": ("actor_id", "instance_id", "node_id"),
    "EQUIP_ITEM": ("actor_id", "equipment_id", "slot_id", "index"),
    "GIVE_EQUIPMENT": ("equipment_id", "quantity"),
    "DISASSEMBLE": ("item_id",),
    "WALK_TO": ("entity", "x", "y", "speed"),
    "MOVE_ROUTE": ("entity", "route", "step", "speed"),
    "GRID_ROUTE": ("entity", "steps"),
    "SET_POSITION": ("entity", "x", "y", "facing", "permanent"),
    "GIVE_PET": ("species_id", "level", "nickname", "moves"),
    "SET_LOOK": ("entity", "sprite_sheet_asset_id", "clip_set_id"),
    "SET_RESPAWN": ("scene_id", "x", "y", "facing"),
    "SHOW_ENTITY": ("entity", "shown"),
    "SET_MOVEMENT": ("entity", "behaviour", "facing"),
    "PARTY_STASH": (),
    "PARTY_RESTORE": (),
    "SHOW_BALLOON": ("entity", "balloon", "duration_ms"),
    "SET_ENTITY_ICON": ("entity", "icon_id"),
    "SPAWN_ENTITY": ("prefab_id", "x", "y", "name"),
    "COPY_ENTITY": ("entity", "x", "y", "name"),
    "MORPH_ENTITY": ("entity", "prefab_id"),
    "SET_BATTLE_WEATHER": ("kind", "intensity", "wind"),
    "SHOW_PICTURE": (
        "picture_id",
        "asset_id",
        "x",
        "y",
        "scale",
        "opacity",
        "frame",
        "columns",
        "rows",
        "layer",
        "click_event",
    ),
    "MOVE_PICTURE": ("picture_id", "x", "y", "scale", "opacity", "duration", "easing"),
    "SET_PICTURE_FRAME": ("picture_id", "frame"),
    "ERASE_PICTURE": ("picture_id",),
    "TIMER_START": ("timer_id", "seconds", "on_expire", "count_up", "show"),
    "TIMER_STOP": ("timer_id",),
    "TIMER_PAUSE": ("timer_id",),
    "TIMER_RESUME": ("timer_id",),
    "TIMER_ADD": ("timer_id", "seconds"),
}


class WorldCommandError(RuntimeError):
    pass


def _required(command, key):
    value = command.args.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise WorldCommandError(f"{command.name} requires {key}")
    return value


def _amount(command, key, default):
    try:
        return float(command.args.get(key, default))
    except (TypeError, ValueError) as exc:
        raise WorldCommandError(f"{command.name} {key} must be a number") from exc


def register_standard_world_commands(router, session):
    """Register every handler in ``STANDARD_WORLD_COMMANDS`` on ``router``."""

    def start_encounter(command):
        return session.start_encounter(_required(command, "encounter_id"))

    def transfer(command):
        scene_id = str(
            command.args.get("scene_id") or command.args.get("destination") or session.scene.id
        )
        return session.transfer_player(
            scene_id,
            command.args.get("x"),
            command.args.get("y"),
            facing=command.args.get("facing"),
        )

    def give_item(command):
        item_id = str(_required(command, "item_id"))
        if item_id not in session.project.rpg_database.items:
            raise WorldCommandError(f"unknown item: {item_id}")
        inventory = session.save.rpg_state.inventory
        before, lost = inventory.count(item_id), len(inventory.overflow)
        inventory.add(item_id, int(_amount(command, "quantity", 1)))
        name = session.name_of(session.project.rpg_database.items[item_id])
        if inventory.count(item_id) > before:
            gained = inventory.count(item_id) - before
            text = session.tr("notice.gained", "+{count} {name}", count=gained, name=name)
            session.notify(text, kind="item")
        if len(inventory.overflow) > lost:
            text = session.tr("notice.no_room", "No room for {name}", name=name)
            session.notify(text, kind="warning")
        session.refresh_quests()
        return inventory.count(item_id)

    def show_popup(command):
        session.notify(
            str(_required(command, "text")),
            entity=command.args.get("entity") or None,
            duration_ms=float(command.args.get("duration_ms") or 1100.0),
            kind=str(command.args.get("kind") or "info"),
        )
        return True

    def take_item(command):
        item_id = str(_required(command, "item_id"))
        if not session.save.rpg_state.inventory.remove(
            item_id, int(_amount(command, "quantity", 1))
        ):
            raise WorldCommandError(f"not enough {item_id} to take")
        session.refresh_quests()
        return session.save.rpg_state.inventory.count(item_id)

    def change_currency(command):
        currency_id = str(_required(command, "currency_id"))
        currencies = session.save.rpg_state.currencies
        value = currencies.get(currency_id, 0.0) + _amount(command, "amount", 0)
        if value < 0:
            raise WorldCommandError(f"{currency_id} would become negative")
        currencies[currency_id] = value
        return value

    def quest_command(method, *, objective=False):
        def handler(command):
            from asteria.rpg.quests import QuestError

            quest_id = str(_required(command, "quest_id"))
            args = (
                (
                    quest_id,
                    str(_required(command, "objective_id")),
                    int(_amount(command, "amount", 1)),
                )
                if objective
                else (quest_id,)
            )
            try:
                return getattr(session, method)(*args)
            except QuestError as exc:
                raise WorldCommandError(str(exc)) from exc

        return handler

    def open_shop(command):
        shop_id = str(_required(command, "shop_id"))
        if shop_id not in session.project.rpg_database.shops:
            raise WorldCommandError(f"unknown shop: {shop_id}")
        return session.open_shop(shop_id)

    def presentation_request(command):
        session.presentation_requests.append(command)
        return command

    def summon(command):
        enemy_id, actor_id = (
            command.args.get("enemy_id") or None,
            command.args.get("actor_id") or None,
        )
        try:
            return session.summon(
                enemy_id=enemy_id,
                actor_id=actor_id,
                count=int(_amount(command, "count", 1)),
                owner_id=command.args.get("owner_id") or None,
            )
        except Exception as exc:
            raise WorldCommandError(str(exc)) from exc

    router.register("SUMMON", summon)
    router.register("SHOW_POPUP", show_popup)
    router.register("START_ENCOUNTER", start_encounter)
    router.register("TRANSFER", transfer)
    router.register("GIVE_ITEM", give_item)
    router.register("TAKE_ITEM", take_item)
    router.register("CHANGE_CURRENCY", change_currency)
    router.register("OPEN_SHOP", open_shop)
    router.register("START_QUEST", quest_command("start_quest"))
    router.register("ADVANCE_QUEST", quest_command("advance_quest", objective=True))
    router.register("COMPLETE_QUEST", quest_command("complete_quest"))
    router.register("FAIL_QUEST", quest_command("fail_quest"))

    def change_reputation(command):
        faction_id = str(_required(command, "faction_id"))
        if faction_id not in session.project.rpg_database.factions:
            raise WorldCommandError(f"unknown faction: {faction_id}")
        return session.change_reputation(faction_id, _amount(command, "amount", 0))

    router.register("CHANGE_REPUTATION", change_reputation)
    router.register(
        "CHANGE_RELATIONSHIP",
        lambda c: session.change_relationship(
            str(_required(c, "subject_id")), _amount(c, "amount", 0)
        ),
    )

    def learn_recipe(command):
        recipe_id = str(_required(command, "recipe_id"))
        if recipe_id not in session.project.rpg_database.composition_recipes:
            raise WorldCommandError(f"unknown recipe: {recipe_id}")
        return session.learn_recipe(recipe_id)

    def open_crafting(command):
        session.open_crafting_station = str(command.args.get("station") or "")
        return session.open_crafting_station

    def open_service(kind, arg, store):
        # a quest board, a recruiting office or a gacha banner (U5): the runtime opens its
        # screen once the event is done (``session.open_service``)
        def handler(command):
            record_id = str(_required(command, arg))
            if record_id not in getattr(session.project.rpg_database, store):
                raise WorldCommandError(f"unknown {kind}: {record_id}")
            session.open_service = (kind, record_id)
            return session.open_service

        return handler

    router.register(
        "SET_NPC",
        lambda c: session.set_npc(
            str(_required(c, "npc")), str(_required(c, "key")), c.args.get("value")
        ),
    )
    router.register(
        "MOVE_NPC",
        lambda c: session.move_npc(
            str(_required(c, "npc")),
            str(_required(c, "scene_id")),
            _amount(c, "x", 0),
            _amount(c, "y", 0),
        ),
    )
    router.register(
        "INTERACT", lambda c: session.perform_interaction(str(_required(c, "interaction_id")))[0]
    )
    router.register(
        "PLAY_ACTION",
        lambda c: session.play_action(
            str(_required(c, "entity")), str(_required(c, "timeline_id"))
        ),
    )

    def set_classes(command):
        raw = _required(command, "class_ids")
        values = raw.replace(";", ",").split(",") if isinstance(raw, str) else list(raw)
        unlock = command.args.get("unlock", True)
        if isinstance(unlock, str):
            unlock = unlock.strip().lower() not in ("0", "false", "no", "")
        return session.set_classes(
            str(command.args.get("actor_id") or ""), values, unlock=bool(unlock)
        )

    router.register("SET_CLASSES", set_classes)

    def gear_command(name, action):
        def handler(command):
            try:
                return action(command)
            except WorldCommandError:
                raise
            except Exception as exc:  # noqa: BLE001 - a bad actor or item is the program's mistake
                raise WorldCommandError(f"{name}: {exc}") from exc

        router.register(name, handler)

    def grant_experience(command):
        points = {}
        raw = str(command.args.get("points") or "")
        for part in raw.replace(";", ",").split(","):
            key, _, amount = part.partition("=")
            if key.strip():
                points[key.strip()] = float(amount or 1)
        extra = {
            "level_threshold": _amount(command, "threshold", 1000.0),
            "level_track": str(command.args.get("level_track") or ""),
        }
        return session.grant_actor_experience(
            str(_required(command, "actor_id")),
            _amount(command, "amount", 0),
            points_per_level=points or None,
            **extra,
        )

    gear_command("GRANT_EXPERIENCE", grant_experience)
    gear_command(
        "BATTLE_SEQUENCE",
        lambda c: session.battle_sequence(
            str(_required(c, "sequence_id")),
            str(_required(c, "actor_id")),
            str(c.args.get("target_id", "")),
        ),
    )
    gear_command(
        "JOIN_PARTY",
        lambda c: session.join_party(
            str(_required(c, "actor_id")),
            active=str(c.args.get("active", "true")).lower() != "false",
        ),
    )
    gear_command("SET_LOCALE", lambda c: session.set_locale(str(_required(c, "locale"))))
    gear_command(
        "NEW_GAME_PLUS",
        lambda c: session.request_new_game_plus(str(c.args.get("rules_id", "")) or None),
    )
    gear_command(
        "LEARN_ABILITY",
        lambda c: session.learn_ability(
            str(_required(c, "actor_id")), str(_required(c, "ability_id"))
        ),
    )
    gear_command("LEAVE_PARTY", lambda c: session.leave_party(str(_required(c, "actor_id"))))
    gear_command("REST_PARTY", lambda c: session.rest_party())
    gear_command(
        "HEAL_PETS",
        lambda c: session.heal_pets(
            party_only=str(c.args.get("party_only", "")).lower() in ("1", "true", "yes")
        ),
    )
    gear_command("PET_STORAGE", lambda c: session.open_pet_storage())
    gear_command(
        "REFINE_EQUIPMENT",
        lambda c: session.refine_equipment(
            str(_required(c, "actor_id")),
            str(_required(c, "instance_id")),
            protect=str(c.args.get("protect", "")).lower() in ("1", "true", "yes"),
        ),
    )
    gear_command(
        "SOCKET_ITEM",
        lambda c: session.socket_item(
            str(_required(c, "actor_id")),
            str(_required(c, "instance_id")),
            str(_required(c, "socket_id")),
            str(_required(c, "item_id")),
        ),
    )
    gear_command(
        "UPGRADE_EQUIPMENT",
        lambda c: session.upgrade_equipment(
            str(_required(c, "actor_id")),
            str(_required(c, "instance_id")),
            str(_required(c, "node_id")),
        ),
    )
    gear_command(
        "EQUIP_ITEM",
        lambda c: session.rearm(
            str(_required(c, "actor_id")),
            str(_required(c, "equipment_id")),
            slot_id=c.args.get("slot_id") or None,
            index=int(c.args.get("index", 0)),
        ),
    )
    gear_command(  # into the equipment bag; the inventory rules may ask to wear it
        "GIVE_EQUIPMENT",
        lambda c: session.gain_equipment(
            str(_required(c, "equipment_id")), int(c.args.get("quantity", 1) or 1)
        ),
    )
    gear_command("DISASSEMBLE", lambda c: session.disassemble(str(_required(c, "item_id"))))
    gear_command(
        "UNSOCKET_ITEM",
        lambda c: session.unsocket_item(
            str(_required(c, "actor_id")),
            str(_required(c, "instance_id")),
            str(_required(c, "socket_id")),
        ),
    )

    def walk_to(command):
        try:
            return session.walk_to(
                _required(command, "entity"),
                _amount(command, "x", 0),
                _amount(command, "y", 0),
                speed=_amount(command, "speed", 60.0),
            )
        except Exception as exc:  # noqa: BLE001 - a bad entity is the program's mistake
            raise WorldCommandError(f"WALK_TO: {exc}") from exc

    router.register("WALK_TO", walk_to)

    def move_route(command):
        try:
            return session.move_route(
                _required(command, "entity"),
                str(_required(command, "route")),
                step=_amount(command, "step", 32.0),
                speed=_amount(command, "speed", 60.0),
            )
        except WorldCommandError:
            raise
        except Exception as exc:  # noqa: BLE001 - a bad route is the program's mistake
            raise WorldCommandError(f"MOVE_ROUTE: {exc}") from exc

    def show_balloon(command):
        session.show_balloon(
            _required(command, "entity"),
            str(command.args.get("balloon") or "exclamation"),
            duration_ms=_amount(command, "duration_ms", 1000.0),
        )
        return True

    def entity_command(method, arguments, named=()):
        def handler(command):
            values = []
            for name, kind in arguments:
                if kind == "number":
                    values.append(_amount(command, name, 0.0))
                else:
                    values.append(str(_required(command, name)))
            extra = {n: str(command.args[n]) for n in named if command.args.get(n)}
            try:
                return getattr(session, method)(*values, **extra)
            except WorldCommandError:
                raise
            except Exception as exc:  # noqa: BLE001 - a bad entity or prefab is the program's mistake
                raise WorldCommandError(f"{command.name}: {exc}") from exc

        return handler

    router.register(
        "SPAWN_ENTITY",
        entity_command(
            "spawn_prefab",
            (("prefab_id", "text"), ("x", "number"), ("y", "number")),
            named=("name",),
        ),
    )
    router.register(
        "COPY_ENTITY",
        entity_command(
            "copy_entity",
            (("entity", "text"), ("x", "number"), ("y", "number")),
            named=("name",),
        ),
    )
    router.register(
        "MORPH_ENTITY",
        entity_command("morph_entity", (("entity", "text"), ("prefab_id", "text"))),
    )

    def set_entity_icon(command):
        try:
            return session.set_entity_icon(
                _required(command, "entity"), str(command.args.get("icon_id") or "")
            )
        except Exception as exc:  # noqa: BLE001 - a bad entity is the program's mistake
            raise WorldCommandError(f"SET_ENTITY_ICON: {exc}") from exc

    router.register("SET_ENTITY_ICON", set_entity_icon)
    router.register("MOVE_ROUTE", move_route)

    def _entity_or_self(command):
        entity = _required(command, "entity")  # "self": the entity whose event this is
        return command.source_entity_id or entity if entity == "self" else entity

    def grid_route(command):
        steps = command.args.get("steps") or ()
        if isinstance(steps, str):
            steps = [x.strip() for x in steps.split(",") if x.strip()]
        try:
            return session.grid_route(_entity_or_self(command), steps)
        except Exception as exc:  # noqa: BLE001 - a bad route is the program's mistake
            raise WorldCommandError(f"GRID_ROUTE: {exc}") from exc

    def set_position(command):
        return session.set_entity_position(
            _entity_or_self(command),
            _amount(command, "x", 0.0),
            _amount(command, "y", 0.0),
            facing=command.args.get("facing") or None,
            permanent=bool(command.args.get("permanent")),
        )

    def give_pet(command):
        pet = session.add_pet(
            str(_required(command, "species_id")),
            level=int(_amount(command, "level", 1)),
            nickname=str(command.args.get("nickname") or ""),
        )
        if command.args.get("moves"):
            pet.moves = [str(m) for m in command.args["moves"]]
        return pet.instance_id

    def set_look(command):
        from asteria.runtime.components2d import Animator2DComponent, SpriteRenderer2D

        entity = session._sequence_entity(_required(command, "entity"))
        sprite, animator = entity.try_get(SpriteRenderer2D), entity.try_get(Animator2DComponent)
        if sprite is not None and command.args.get("sprite_sheet_asset_id"):
            sprite.sprite_sheet_asset_id = str(command.args["sprite_sheet_asset_id"])
        if animator is not None and command.args.get("clip_set_id"):
            animator.clip_set_id = str(command.args["clip_set_id"])
        return entity.id

    def set_respawn(command):
        session.save.event_context.set_variable(
            session.RESPAWN_VARIABLE,
            "|".join(
                (
                    str(_required(command, "scene_id")),
                    str(_amount(command, "x", 0.0)),
                    str(_amount(command, "y", 0.0)),
                    str(command.args.get("facing") or "down"),
                )
            ),
        )
        return True

    def show_entity(command):
        return session.show_entity(_entity_or_self(command), bool(command.args.get("shown", True)))

    def set_movement(command):
        return session.set_entity_movement(
            _entity_or_self(command),
            str(command.args.get("behaviour") or ""),
            str(command.args.get("facing") or ""),
        )

    for name, handler in (
        ("PARTY_STASH", lambda command: session.stash_pets()),
        ("PARTY_RESTORE", lambda command: session.restore_pets()),
        ("SET_MOVEMENT", set_movement),
        ("SHOW_ENTITY", show_entity),
        ("GRID_ROUTE", grid_route),
        ("SET_POSITION", set_position),
        ("GIVE_PET", give_pet),
        ("SET_LOOK", set_look),
        ("SET_RESPAWN", set_respawn),
    ):
        router.register(name, handler)
    router.register("SHOW_BALLOON", show_balloon)

    def set_battle_weather(command):
        try:
            return session.set_battle_weather(
                command.args.get("kind", "none"),
                _amount(command, "intensity", 0.6),
                _amount(command, "wind", 0.0),
            )
        except Exception as exc:  # noqa: BLE001
            raise WorldCommandError(f"SET_BATTLE_WEATHER: {exc}") from exc

    router.register("SET_BATTLE_WEATHER", set_battle_weather)

    def picture_command(name):
        def handler(command):
            picture_id = str(_required(command, "picture_id"))
            args = command.args
            try:
                if name == "show":
                    return session.pictures.show(
                        picture_id,
                        _required(command, "asset_id"),
                        _amount(command, "x", 0),
                        _amount(command, "y", 0),
                        scale=_amount(command, "scale", 1.0),
                        opacity=_amount(command, "opacity", 1.0),
                        frame=int(_amount(command, "frame", 0)),
                        columns=int(_amount(command, "columns", 1)),
                        rows=int(_amount(command, "rows", 1)),
                        layer=int(_amount(command, "layer", 0)),
                        click_event=str(args.get("click_event", "")),
                    )
                if name == "move":
                    pick = lambda key: _amount(command, key, 0) if key in args else None  # noqa: E731
                    return session.pictures.move(
                        picture_id,
                        x=pick("x"),
                        y=pick("y"),
                        scale=pick("scale"),
                        opacity=pick("opacity"),
                        duration=_amount(command, "duration", 0.0),
                        easing=str(args.get("easing", "linear")),
                    )
                if name == "frame":
                    return session.pictures.set_frame(
                        picture_id, int(_amount(command, "frame", 0))
                    )
                return session.pictures.erase(picture_id)
            except (KeyError, ValueError) as exc:
                raise WorldCommandError(f"{command.name}: {exc}") from exc

        return handler

    for command_name, method in (
        ("SHOW_PICTURE", "show"),
        ("MOVE_PICTURE", "move"),
        ("SET_PICTURE_FRAME", "frame"),
        ("ERASE_PICTURE", "erase"),
    ):
        router.register(command_name, picture_command(method))

    def timer_command(name):
        def handler(command):
            timer_id = str(_required(command, "timer_id"))
            timers = session.timers
            try:
                if name == "start":
                    return timers.start(
                        timer_id,
                        _amount(command, "seconds", 0),
                        on_expire=str(command.args.get("on_expire", "")),
                        count_up=bool(command.args.get("count_up", False)),
                        show=bool(command.args.get("show", True)),
                    )
                if name == "add":
                    return timers.add(timer_id, _amount(command, "seconds", 0))
                return getattr(timers, name)(timer_id)
            except (KeyError, ValueError) as exc:
                raise WorldCommandError(f"{command.name}: {exc}") from exc

        return handler

    for command_name, method in (
        ("TIMER_START", "start"),
        ("TIMER_STOP", "stop"),
        ("TIMER_PAUSE", "pause"),
        ("TIMER_RESUME", "resume"),
        ("TIMER_ADD", "add"),
    ):
        router.register(command_name, timer_command(method))
    router.register("LEARN_RECIPE", learn_recipe)
    router.register("OPEN_CRAFTING", open_crafting)
    router.register("OPEN_QUEST_BOARD", open_service("quest_board", "board_id", "quest_boards"))
    router.register("OPEN_RECRUIT", open_service("recruit", "office_id", "recruit_offices"))
    router.register("OPEN_GACHA", open_service("gacha", "banner_id", "gacha_banners"))
    router.register(
        "ADD_COUNTER",
        lambda c: session.add_counter(str(_required(c, "counter_id")), _amount(c, "amount", 1)),
    )
    for name in PRESENTATION_COMMANDS:
        router.register(name, presentation_request)
    return router


def move_entity_to_scene(entity, old_scene, new_scene, x=None, y=None):
    """Detach ``entity`` from ``old_scene`` (if different) and place it in ``new_scene``."""
    if new_scene is not old_scene:
        old_scene.detach_entity(entity)
        new_scene.add_entity(entity)
    transform = entity.get(Transform)
    if x is not None:
        transform.x = float(x)
    if y is not None:
        transform.y = float(y)
    return transform
