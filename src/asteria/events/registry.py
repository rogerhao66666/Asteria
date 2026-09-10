from __future__ import annotations

from dataclasses import dataclass, field

from .program import EventProgram


@dataclass(slots=True)
class EventProgramRegistry:
    """Stable-ID registry for event programs.

    Persistent data should reference programs by stable ID, never by display name.
    """

    _programs: dict[str, EventProgram] = field(default_factory=dict)

    def register(self, program_id: str, program: EventProgram) -> EventProgram:
        program_id = str(program_id).strip()
        if not program_id:
            raise ValueError("event program ID is required")
        if not isinstance(program, EventProgram):
            raise TypeError("program must be EventProgram")
        if program_id in self._programs:
            raise ValueError(f"duplicate event program ID: {program_id}")
        self._programs[program_id] = program
        return program

    def replace(self, program_id: str, program: EventProgram) -> EventProgram:
        program_id = str(program_id).strip()
        if not program_id:
            raise ValueError("event program ID is required")
        if not isinstance(program, EventProgram):
            raise TypeError("program must be EventProgram")
        self._programs[program_id] = program
        return program

    def unregister(self, program_id: str) -> EventProgram:
        return self._programs.pop(str(program_id))

    def get(self, program_id: str) -> EventProgram | None:
        return self._programs.get(str(program_id))

    def require(self, program_id: str) -> EventProgram:
        program = self.get(program_id)
        if program is None:
            raise KeyError(f"unknown event program ID: {program_id}")
        return program

    def ids(self):
        return tuple(self._programs)

    def programs(self):
        return tuple(self._programs.values())

    def __contains__(self, program_id: str):
        return str(program_id) in self._programs

    def __len__(self):
        return len(self._programs)
