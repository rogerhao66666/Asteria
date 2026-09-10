from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventCallFrame:
    program_id: str
    source_entity_id: str
    local_scope_id: str
    vm_state: dict

    def to_data(self):
        return {
            "program_id": self.program_id,
            "source_entity_id": self.source_entity_id,
            "local_scope_id": self.local_scope_id,
            "vm_state": dict(self.vm_state),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "program_id",
            "source_entity_id",
            "local_scope_id",
            "vm_state",
        }
        if set(data) != expected:
            raise ValueError("invalid event call frame")
        if not isinstance(data["vm_state"], dict):
            raise TypeError("event call frame vm_state must be a dict")
        return cls(
            program_id=str(data["program_id"]),
            source_entity_id=str(data["source_entity_id"]),
            local_scope_id=str(data["local_scope_id"]),
            vm_state=dict(data["vm_state"]),
        )
