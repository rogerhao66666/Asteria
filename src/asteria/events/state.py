from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventVMStatus(str, Enum):
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass(slots=True)
class EventVMState:
    pc: int = 0
    status: EventVMStatus = EventVMStatus.RUNNING
    wait_remaining: float = 0.0

    def validate(self):
        if not isinstance(self.pc, int) or self.pc < 0:
            raise ValueError("pc must be a non-negative integer")
        if not isinstance(self.status, EventVMStatus):
            self.status = EventVMStatus(self.status)
        self.wait_remaining = float(self.wait_remaining)
        if self.wait_remaining < 0.0:
            raise ValueError("wait_remaining must be >= 0")
        if self.status != EventVMStatus.WAITING and self.wait_remaining != 0.0:
            raise ValueError("only waiting state may have wait_remaining")
        return self

    def to_data(self):
        self.validate()
        return {
            "schema": "asteria.event_vm_state",
            "version": 1,
            "pc": self.pc,
            "status": self.status.value,
            "wait_remaining": self.wait_remaining,
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "schema",
            "version",
            "pc",
            "status",
            "wait_remaining",
        }
        if set(data) != expected:
            raise ValueError("invalid event VM state")
        if data["schema"] != "asteria.event_vm_state" or data["version"] != 1:
            raise ValueError("unsupported event VM state")
        return cls(
            pc=int(data["pc"]),
            status=EventVMStatus(data["status"]),
            wait_remaining=float(data["wait_remaining"]),
        ).validate()
