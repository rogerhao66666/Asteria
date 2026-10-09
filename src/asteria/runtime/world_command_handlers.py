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
    "PLAY_BGM",
    "STOP_BGM",
    "PLAY_SE",
    "SCREEN_FADE",
)

PRESENTATION_COMMANDS = ("PLAY_BGM", "STOP_BGM", "PLAY_SE", "SCREEN_FADE")


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
        scene_id = str(command.args.get("scene_id") or command.args.get("destination") or session.scene.id)
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
        session.save.rpg_state.inventory.add(item_id, int(_amount(command, "quantity", 1)))
        return session.save.rpg_state.inventory.count(item_id)

    def take_item(command):
        item_id = str(_required(command, "item_id"))
        if not session.save.rpg_state.inventory.remove(item_id, int(_amount(command, "quantity", 1))):
            raise WorldCommandError(f"not enough {item_id} to take")
        return session.save.rpg_state.inventory.count(item_id)

    def change_currency(command):
        currency_id = str(_required(command, "currency_id"))
        currencies = session.save.rpg_state.currencies
        value = currencies.get(currency_id, 0.0) + _amount(command, "amount", 0)
        if value < 0:
            raise WorldCommandError(f"{currency_id} would become negative")
        currencies[currency_id] = value
        return value

    def presentation_request(command):
        session.presentation_requests.append(command)
        return command

    router.register("START_ENCOUNTER", start_encounter)
    router.register("TRANSFER", transfer)
    router.register("GIVE_ITEM", give_item)
    router.register("TAKE_ITEM", take_item)
    router.register("CHANGE_CURRENCY", change_currency)
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
