from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EventInstruction:
    """Backend-neutral event instruction.

    `opcode` identifies behavior; `args` contains deterministic JSON-compatible
    instruction operands. Batch 36 only gives intrinsic meaning to WAIT and END.
    Other opcodes are surfaced to a host executor in later batches.
    """

    opcode: str
    args: dict[str, Any]

    def __init__(self, opcode: str, args: dict[str, Any] | None = None):
        opcode = str(opcode).strip().upper()
        if not opcode:
            raise ValueError("instruction opcode is required")
        object.__setattr__(self, "opcode", opcode)
        object.__setattr__(self, "args", dict(args or {}))

    def to_data(self):
        return {"opcode": self.opcode, "args": dict(self.args)}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"opcode", "args"}:
            raise ValueError("invalid event instruction")
        if not isinstance(data["args"], dict):
            raise TypeError("instruction args must be a dict")
        return cls(data["opcode"], data["args"])


@dataclass(frozen=True, slots=True)
class EventProgram:
    instructions: tuple[EventInstruction, ...]
    name: str = ""
    _labels: dict[str, int] = None

    def __init__(
        self,
        instructions: Iterable[EventInstruction],
        *,
        name: str = "",
    ):
        items = tuple(instructions)
        if any(not isinstance(item, EventInstruction) for item in items):
            raise TypeError("EventProgram requires EventInstruction values")
        labels = {}
        for index, item in enumerate(items):
            if item.opcode != "LABEL":
                continue
            label = str(item.args.get("name", "")).strip()
            if not label:
                raise ValueError("LABEL requires name")
            if label in labels:
                raise ValueError(f"duplicate event label: {label}")
            labels[label] = index
        object.__setattr__(self, "instructions", items)
        object.__setattr__(self, "name", str(name))
        object.__setattr__(self, "_labels", labels)

    def __len__(self):
        return len(self.instructions)

    def instruction(self, pc: int):
        if not 0 <= int(pc) < len(self.instructions):
            raise IndexError("program counter outside event program")
        return self.instructions[int(pc)]

    def label_pc(self, name: str) -> int:
        try:
            return self._labels[str(name)]
        except KeyError as exc:
            raise KeyError(f"unknown event label: {name}") from exc

    def to_data(self):
        return {
            "schema": "asteria.event_program",
            "version": 1,
            "name": self.name,
            "instructions": [item.to_data() for item in self.instructions],
        }

    @classmethod
    def from_data(cls, data):
        expected = {"schema", "version", "name", "instructions"}
        if set(data) != expected:
            raise ValueError("invalid event program")
        if data["schema"] != "asteria.event_program" or data["version"] != 1:
            raise ValueError("unsupported event program")
        if not isinstance(data["instructions"], list):
            raise TypeError("instructions must be a list")
        return cls(
            (EventInstruction.from_data(item) for item in data["instructions"]),
            name=data["name"],
        )
