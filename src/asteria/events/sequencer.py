"""Event sequencer (EVT-04, ASTERIA_SPEC §27): parallel tracks inside one event program.

A ``SEQUENCE`` instruction holds tracks; each track is an ordinary
instruction list run by its own ``EventVM`` (same context, switches and
locals as the event), so the canonical event data model is reused:

    {"opcode": "SEQUENCE", "args": {
        "tracks": [{"name": "hero", "instructions": [...]}, ...],
        "cutscene": true,      # player input is locked while it runs
        "skippable": true,     # the player may skip; see ``skip``
        "wait": "all"}}        # "all": the event waits for every track; "none": runs alongside

Track instructions: everything the Event VM runs (WAIT, SET_*, JUMP, IF...),
``DIALOGUE`` (one dialogue box at a time across tracks; a track whose line
can't show yet waits its turn), ``WORLD`` (music, SFX, VFX, camera, fades,
transfers... through the world command router; ``"wait": seconds`` holds the
track while the effect plays), and the movement/animation commands carried
out through the host:

* ``MOVE``    ``entity``, ``x``, ``y`` (``relative``), ``duration`` or ``speed``; ``wait`` (default true)
* ``FACE``    ``entity``, ``facing``
* ``ANIMATE`` ``entity``, ``clip``

Movement tweens are part of the sequence state, so a save taken in the middle
of a cutscene resumes it. ``skip`` fast-forwards every track to its end state
(moves land on their targets, waits end, dialogue lines are passed, world
commands still run) so a skipped cutscene leaves the world exactly as a
watched one; ``cancel`` stops the tracks where they are.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .program import EventInstruction, EventProgram
from .state import EventVMStatus
from .vm import EventVM

INTRINSIC = {"WAIT", "END", "SET_SWITCH", "SET_VARIABLE", "SET_LOCAL", "LABEL", "JUMP", "JUMP_IF", "IF_FALSE_SKIP"}
HOST_OPCODES = {"MOVE", "FACE", "ANIMATE"}
TRACK_FORBIDDEN = {"CHOICE", "CALL", "RETURN", "SEQUENCE"}


class SequenceError(RuntimeError):
    pass


def track_program(raw):
    instructions = raw.get("instructions") if isinstance(raw, dict) else None
    if not isinstance(instructions, list):
        raise SequenceError("each SEQUENCE track needs an instructions list")
    program = EventProgram(tuple(EventInstruction.from_data(x) for x in instructions), name=str(raw.get("name", "")))
    bad = sorted({i.opcode for i in program.instructions if i.opcode in TRACK_FORBIDDEN})
    if bad:
        raise SequenceError(f"not allowed inside a sequence track: {', '.join(bad)}")
    return program


def validate_sequence_args(args):
    tracks = args.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise SequenceError("SEQUENCE needs at least one track")
    for raw in tracks:
        track_program(raw)
    if args.get("wait", "all") not in ("all", "none"):
        raise SequenceError("SEQUENCE wait must be 'all' or 'none'")


@dataclass(slots=True)
class _Tween:
    entity_id: str
    start: tuple
    end: tuple
    duration: float
    elapsed: float = 0.0

    def to_data(self):
        return {
            "entity_id": self.entity_id,
            "start": list(self.start),
            "end": list(self.end),
            "duration": self.duration,
            "elapsed": self.elapsed,
        }

    @classmethod
    def from_data(cls, data):
        return cls(data["entity_id"], tuple(data["start"]), tuple(data["end"]), data["duration"], data["elapsed"])


@dataclass(slots=True)
class _Track:
    name: str
    vm: EventVM
    tween: _Tween | None = None
    pending_dialogue: EventInstruction | None = None  # a line waiting for the shared dialogue box

    @property
    def done(self):
        return self.vm.state.status in (EventVMStatus.COMPLETED, EventVMStatus.STOPPED) and self.tween is None


@dataclass(slots=True)
class EventSequence:
    """Runs the tracks of one ``SEQUENCE`` instruction. Owned by an ``EventRunner``."""

    args: dict
    runner: object  # EventRunner (dialogue, world commands, host, local scope)
    pc: int  # program counter of the SEQUENCE instruction in the owning program
    tracks: list = field(default_factory=list)
    skipping: bool = False

    @classmethod
    def start(cls, instruction, runner, pc):
        validate_sequence_args(instruction.args)
        sequence = cls(dict(instruction.args), runner, pc)
        for index, raw in enumerate(instruction.args["tracks"]):
            program = track_program(raw)
            vm = EventVM(program, context=runner.context, local_scope_id=runner.local_scope or None)
            sequence.tracks.append(_Track(str(raw.get("name") or f"track{index + 1}"), vm))
        return sequence

    @property
    def cutscene(self):
        return bool(self.args.get("cutscene", False))

    @property
    def skippable(self):
        return bool(self.args.get("skippable", False))

    @property
    def blocking(self):
        return self.args.get("wait", "all") == "all"

    @property
    def done(self):
        return all(t.done for t in self.tracks)

    # -- host operations -------------------------------------------------------------------
    def _host(self, opcode):
        host = self.runner.sequence_host
        if host is None:
            raise SequenceError(f"{opcode} needs a sequence host (the game session)")
        return host

    def _begin_move(self, track, args):
        host = self._host("MOVE")
        entity = str(args.get("entity", "")).strip()
        if not entity:
            raise SequenceError("MOVE needs entity")
        sx, sy = host.position(entity)
        x, y = float(args.get("x", 0.0)), float(args.get("y", 0.0))
        if args.get("relative"):
            x, y = sx + x, sy + y
        if "duration" in args:
            duration = max(0.0, float(args["duration"]))
        else:
            speed = float(args.get("speed", 60.0))
            if speed <= 0:
                raise SequenceError("MOVE speed must be > 0")
            duration = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5 / speed
        tween = _Tween(entity, (sx, sy), (x, y), duration)
        if duration <= 0:
            host.set_position(entity, x, y)
            return
        if args.get("wait", True):
            track.tween = tween
        else:
            self.runner.background_tweens.append(tween)

    def _host_instruction(self, track, instruction):
        args = instruction.args
        if instruction.opcode == "MOVE":
            self._begin_move(track, args)
        elif instruction.opcode == "FACE":
            self._host("FACE").set_facing(str(args.get("entity", "")), str(args.get("facing", "down")))
        elif instruction.opcode == "ANIMATE":
            self._host("ANIMATE").play_animation(str(args.get("entity", "")), str(args.get("clip", "")))

    # -- stepping -----------------------------------------------------------------------------
    def _advance_tween(self, tween, dt):
        tween.elapsed = min(tween.duration, tween.elapsed + dt) if not self.skipping else tween.duration
        k = 1.0 if tween.duration <= 0 else tween.elapsed / tween.duration
        x = tween.start[0] + (tween.end[0] - tween.start[0]) * k
        y = tween.start[1] + (tween.end[1] - tween.start[1]) * k
        self.runner.sequence_host.set_position(tween.entity_id, x, y)
        return tween.elapsed >= tween.duration

    def _try_dialogue(self, track):
        if self.skipping:
            track.pending_dialogue = None  # skipping passes the line
            return True
        if self.runner.dialogue.blocked:
            return False
        self.runner._open_dialogue(track.pending_dialogue)
        track.pending_dialogue = None
        return True

    def _step_track(self, track, dt):
        if track.tween is not None:
            if not self._advance_tween(track.tween, dt):
                return
            track.tween = None
        if track.pending_dialogue is not None and not self._try_dialogue(track):
            return
        vm = track.vm
        if vm.waiting:
            if self.skipping:
                vm.state.wait_remaining = 0.0
            vm.update_wait(dt)
        while vm.state.status == EventVMStatus.RUNNING:
            instruction = vm.step().instruction
            if instruction is None:
                break
            if instruction.opcode == "DIALOGUE":
                track.pending_dialogue = instruction
                if not self._try_dialogue(track):
                    break
                if not self.skipping:
                    break  # the line is on screen; this track resumes after it is acknowledged
            elif instruction.opcode == "WORLD":
                self.runner._dispatch_world_command(instruction)
                hold = float(instruction.args.get("wait", 0) or 0)
                if hold > 0 and not self.skipping and vm.state.status != EventVMStatus.STOPPED:
                    vm.state.status = EventVMStatus.WAITING
                    vm.state.wait_remaining = hold
            elif instruction.opcode in HOST_OPCODES:
                self._host_instruction(track, instruction)
                if track.tween is not None:
                    if self.skipping:
                        self._advance_tween(track.tween, 0.0)
                        track.tween = None
                    else:
                        break
            elif instruction.opcode not in INTRINSIC:
                raise SequenceError(f"unsupported instruction in a sequence track: {instruction.opcode}")
            if self.skipping and vm.waiting:
                vm.state.wait_remaining = 0.0
                vm.update_wait(0.0)

    def update(self, dt):
        if self.runner.dialogue.blocked and not self.skipping:
            # The dialogue box pauses the whole scene, as in the main event.
            return self.done
        for track in self.tracks:
            if not track.done:
                self._step_track(track, dt)
        return self.done

    def skip(self, max_steps=10000):
        """Fast-forward every track to its end state."""
        if not self.skippable:
            raise SequenceError("this sequence is not skippable")
        self.skipping = True
        self.runner.dialogue.clear()
        for _ in range(max_steps):
            if self.update(0.0):
                return True
        raise SequenceError("sequence did not finish while skipping")

    def cancel(self):
        """Stop every track where it is (moves stay where they reached)."""
        for track in self.tracks:
            track.vm.stop()
            track.tween = None
            track.pending_dialogue = None

    # -- save / load ------------------------------------------------------------------------------
    def to_data(self):
        return {
            "pc": self.pc,
            "skipping": self.skipping,
            "tracks": [
                {
                    "vm_state": t.vm.state.to_data(),
                    "tween": None if t.tween is None else t.tween.to_data(),
                    "pending_dialogue": None if t.pending_dialogue is None else t.pending_dialogue.to_data(),
                }
                for t in self.tracks
            ],
        }

    @classmethod
    def from_data(cls, data, program, runner):
        instruction = program.instruction(int(data["pc"]))
        if instruction.opcode != "SEQUENCE":
            raise SequenceError("saved sequence does not point at a SEQUENCE instruction")
        sequence = cls.start(instruction, runner, int(data["pc"]))
        sequence.skipping = bool(data.get("skipping", False))
        for track, saved in zip(sequence.tracks, data["tracks"], strict=True):
            track.vm = EventVM.restore(
                track.vm.program, saved["vm_state"], context=runner.context, local_scope_id=runner.local_scope or None
            )
            track.tween = None if saved["tween"] is None else _Tween.from_data(saved["tween"])
            pending = saved.get("pending_dialogue")
            track.pending_dialogue = None if pending is None else EventInstruction.from_data(pending)
        return sequence
