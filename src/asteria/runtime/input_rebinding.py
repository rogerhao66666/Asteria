"""Key / gamepad rebinding (ENG-15): player overrides over the project's InputActionMap.

``ControlsMenu`` is the logic of the in-game Controls screen: pick an action,
then the next key or gamepad button pressed becomes its binding for that
device (exclusive: it is removed from other actions). Overrides are stored per
player (``GameSettings.input_overrides``), never in the project, and
``effective_input_map`` lays them over the project defaults.
"""

from __future__ import annotations

from .input_map import InputActionMap, InputBinding


def effective_input_map(base, overrides):
    """A copy of ``base`` with each overridden action's bindings replaced."""
    result = InputActionMap.from_data(base.to_data())
    for action_id, bindings in (overrides or {}).items():
        if action_id in result.actions():
            result.set_bindings(action_id, [InputBinding.from_data(b) for b in bindings])
    return result


def _english(key, english, **params):
    return english.format(**params) if params else english


def describe_binding(binding, tr=None):
    """A binding as the Controls screen shows it; ``tr`` (``GameSessionRuntime.tr``) words
    the pad in the player's language."""
    tr = tr or _english
    if binding.device == "key":
        return binding.code.upper() if len(binding.code) == 1 else binding.code.title()
    if binding.device == "gamepad_button":
        return tr("controls.pad_button", "Pad {button}", button=binding.code)
    sign = "+" if binding.direction > 0 else "−"
    kind = binding.device.removeprefix("gamepad_")
    if kind == "axis":
        kind = tr("controls.pad_stick", "stick")
    elif kind == "hat":
        kind = tr("controls.pad_hat", "d-pad")
    axis = f"{kind} {binding.code}{sign}"
    return tr("controls.pad_axis", "Pad {axis}", axis=axis)


class ControlsMenu:
    def __init__(self, base_map, overrides=None, *, tr=None):
        self.base = base_map
        self.overrides = {k: list(v) for k, v in dict(overrides or {}).items()}
        self.row = 0
        self.capturing = None  # action id waiting for an input
        self.message = ""
        self.tr = tr or _english  # GameSessionRuntime.tr: the screen's words

    def action_name(self, action):
        """An input action as the player reads it: ``controls.action.<id>`` in the project's
        translations, else its id."""
        return self.tr(f"controls.action.{action}", action)

    @property
    def input_map(self):
        return effective_input_map(self.base, self.overrides)

    def rows(self):
        current = self.input_map
        rows = [
            (
                action,
                ", ".join(describe_binding(b, self.tr) for b in current.bindings(action)) or "—",
            )
            for action in current.actions()
        ]
        return [*rows, ("reset_all", self.tr("controls.reset_all", "Reset all to defaults"))]

    def move(self, step):
        self.row = (self.row + step) % len(self.rows())

    def select(self):
        action = self.rows()[self.row][0]
        if action == "reset_all":
            self.overrides = {}
            self.message = self.tr("controls.all_reset", "All controls reset")
            return None
        self.capturing = action
        self.message = self.tr(
            "controls.press",
            "Press a key or pad button for {action} (Esc cancels)",
            action=self.action_name(action),
        )
        return action

    def cancel_capture(self):
        self.capturing = None
        self.message = ""

    def capture(self, binding):
        """Bind ``binding`` to the action being captured, replacing that action's binding on the
        same device."""
        action = self.capturing
        if action is None:
            return False
        current = self.input_map
        same_device = [b for b in current.bindings(action) if b.device == binding.device]
        current.rebind(action, same_device[0] if same_device else None, binding, exclusive=True)
        # store every action that changed (exclusive rebinding may have freed the input elsewhere)
        for other in current.actions():
            if [b.to_data() for b in current.bindings(other)] != [
                b.to_data() for b in self.base.bindings(other)
            ]:
                self.overrides[other] = [b.to_data() for b in current.bindings(other)]
            else:
                self.overrides.pop(other, None)
        self.capturing = None
        self.message = f"{self.action_name(action)} → {describe_binding(binding, self.tr)}"
        return True

    def reset(self, action):
        self.overrides.pop(str(action), None)
