"""The editor asks for what a world command fails without: the table must say what the engine
says."""

from unittest.mock import MagicMock

from asteria.events.world_commands import WorldCommand
from asteria.runtime.world_command_handlers import (
    WORLD_COMMAND_ARGUMENTS,
    WORLD_COMMAND_REQUIRED,
    WorldCommandError,
    register_standard_world_commands,
)


class _Router:
    def __init__(self):
        self.handlers = {}

    def register(self, name, handler):
        self.handlers[name] = handler


def _needs(handler, name):
    """Run the handler with nothing, adding each argument it says it requires."""
    args, needed = {}, []
    for _attempt in range(8):
        try:
            handler(WorldCommand(name, dict(args)))
        except WorldCommandError as exc:
            said = str(exc)
            if " requires " not in said:
                break
            key = said.rsplit(" requires ", 1)[1].split()[0].strip("'\"")
            if key in args:
                break
            needed.append(key)
            args[key] = "x"
        except Exception:  # the mock session can't go further: what it asked for still stands
            break
        else:
            break
    return needed


def test_the_required_table_matches_the_handlers():
    router = _Router()
    register_standard_world_commands(router, MagicMock())
    found = {}
    for name, handler in router.handlers.items():
        needed = _needs(handler, name)
        if needed:
            found[name] = tuple(needed)
    assert found == {k: v for k, v in WORLD_COMMAND_REQUIRED.items() if k in found}
    assert set(WORLD_COMMAND_REQUIRED) <= set(WORLD_COMMAND_ARGUMENTS)
    for name, keys in WORLD_COMMAND_REQUIRED.items():
        assert set(keys) <= set(WORLD_COMMAND_ARGUMENTS[name]), name
