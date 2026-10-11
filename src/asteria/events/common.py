"""Common events (EVT-03): project-wide event programs with a trigger.

``call``     — only run through ``CALL`` (a reusable routine any event can call)
``autorun``  — runs while its switch is on and blocks the player (e.g. a story beat)
``parallel`` — runs alongside play while its switch is on (e.g. a timer, ambient effects)

The programs are ordinary ``EventProgram`` records in the project registry;
the game session schedules autorun / parallel ones with ``EventScheduler``.
"""

from __future__ import annotations

from dataclasses import dataclass

COMMON_TRIGGERS = ("call", "autorun", "parallel")


@dataclass(frozen=True, slots=True)
class CommonEvent:
    program_id: str
    trigger: str = "call"
    switch: str = ""  # autorun / parallel run only while this switch is on ("" = always)

    def __post_init__(self):
        if not str(self.program_id).strip():
            raise ValueError("common event program_id is required")
        if self.trigger not in COMMON_TRIGGERS:
            raise ValueError(f"common event trigger must be one of {COMMON_TRIGGERS}")

    def active(self, context):
        return self.trigger != "call" and (not self.switch or context.get_switch(self.switch))

    def to_data(self):
        return {"program_id": self.program_id, "trigger": self.trigger, "switch": self.switch}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"program_id", "trigger", "switch"}:
            raise ValueError("invalid common event")
        return cls(str(data["program_id"]), str(data["trigger"]), str(data["switch"]))
