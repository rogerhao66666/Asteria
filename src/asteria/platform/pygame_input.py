"""pygame-ce device input -> backend-neutral RawInputState (keyboard + gamepads)."""
from __future__ import annotations

from asteria.runtime.input_map import RawInputState


class PygameInputSource:
    """Tracks keys from events and reads every connected joystick each frame.

    Keys are named with ``pygame.key.name`` ("a", "left", "return", ...).
    Joysticks are opened on start and on hot-plug (JOYDEVICEADDED/REMOVED).
    """

    def __init__(self, pg):
        self.pg = pg
        self.keys: set[str] = set()
        self._joysticks = {}
        if not pg.joystick.get_init():
            pg.joystick.init()
        for index in range(pg.joystick.get_count()):
            self._open(index)

    def _open(self, device_index):
        joystick = self.pg.joystick.Joystick(device_index)
        self._joysticks[joystick.get_instance_id()] = joystick

    def handle_event(self, event):
        pg = self.pg
        if event.type == pg.KEYDOWN:
            self.keys.add(pg.key.name(event.key).lower())
        elif event.type == pg.KEYUP:
            self.keys.discard(pg.key.name(event.key).lower())
        elif event.type == getattr(pg, "WINDOWFOCUSLOST", None):
            self.keys.clear()  # releases are not delivered while unfocused
        elif event.type == getattr(pg, "JOYDEVICEADDED", None):
            self._open(event.device_index)
        elif event.type == getattr(pg, "JOYDEVICEREMOVED", None):
            self._joysticks.pop(event.instance_id, None)

    def handle_events(self, events):
        for event in events:
            self.handle_event(event)

    def raw_state(self) -> RawInputState:
        state = RawInputState(keys=set(self.keys))
        for joystick in self._joysticks.values():
            for button in range(joystick.get_numbuttons()):
                if joystick.get_button(button):
                    state.buttons.add(str(button))
            for axis in range(joystick.get_numaxes()):
                value = float(joystick.get_axis(axis))
                key = str(axis)
                if abs(value) > abs(state.axes.get(key, 0.0)):
                    state.axes[key] = value
            for hat in range(joystick.get_numhats()):
                x, y = joystick.get_hat(hat)
                if x:
                    state.hats[f"x:{hat}"] = x
                if y:
                    state.hats[f"y:{hat}"] = y
        return state
