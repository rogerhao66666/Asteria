"""Action timeline editor API (EDT-06, ANI-05 presentation side).

Edits the battle presentation library's ``motion_sequences``: per-ability
choreography of timed beats on the channels ``animation`` (cue = role),
``vfx`` (cue = sprite sheet asset), ``audio`` (cue = audio id), ``camera``,
``screen_fx`` (cue = effect), ``timing`` (hit_stop), ``motion_fx``
(afterimage / trail) and ``move`` (the actor steps toward its target / back). These are
exactly the sequences the canonical battle screen plays. Changes are undoable document commands;
``preview`` reports what has fired at a given time.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.presentation.battle_motion_sequence import BattleMotionBeat, BattleMotionSequence

CHANNELS = ("animation", "vfx", "audio", "camera", "screen_fx", "timing", "motion_fx", "move")
TIMING_CUES = ("hit_stop",)
MOVE_CUES = ("advance", "return")  # advance: to the first target; return: back to its place
MOTION_FX_CUES = ("afterimage", "trail")  # payload: duration, interval, count, fade, lifetime
ROLES = ("idle", "attack", "hit", "ko")
TARGETS = ("@source", "@target")
CATEGORY = "motion_sequences"


class ActionTimelineError(ValueError):
    pass


@dataclass(slots=True)
class _LibraryCommand:
    library: object
    key: str
    before: object
    after: object
    description: str

    @property
    def label(self):
        return self.description

    def _apply(self, value):
        if value is None:
            if self.key in self.library.ids(CATEGORY):
                self.library.remove(CATEGORY, self.key)
        else:
            self.library.set(CATEGORY, self.key, value)

    def redo(self):
        self._apply(self.after)

    def undo(self):
        self._apply(self.before)


def _beat(beat_id, at, channel, cue, member_id, payload):
    return BattleMotionBeat(
        beat_id, at, channel, cue, member_id=member_id, payload=payload or None
    )


class ActionTimelineController:
    def __init__(self, document):
        self.document = document

    @property
    def library(self):
        if self.document.project is None:
            raise ActionTimelineError("project required")
        return self.document.project.battle_presentation_library

    def sequences(self):
        return tuple(sorted(self.library.ids(CATEGORY)))

    def get(self, sequence_id):
        if sequence_id not in self.library.ids(CATEGORY):
            raise ActionTimelineError(f"unknown sequence {sequence_id}")
        return self.library.require(CATEGORY, sequence_id)

    def beats(self, sequence_id):
        return tuple(self.get(sequence_id).beats)

    # -- validation ------------------------------------------------------------------
    def animation_cues(self):
        """What an animation beat can play: the basic roles plus every visual state the
        project's combatant profiles define (a character with three attacks, a transform)."""
        cues = list(ROLES)
        library = self.document.project.battle_presentation_library
        for profile_id in library.ids("combatant_visuals"):
            for state in library.require("combatant_visuals", profile_id).states:
                if state.state_id not in cues:
                    cues.append(state.state_id)
        return tuple(cues)

    def known_vfx(self):
        return tuple(
            sorted(
                a.asset_id
                for a in self.document.project.assets.query()
                if "vfx" in a.tags and a.kind in ("sprite_sheet", "particle_effect")
            )
        )

    def problems(self, sequence):
        found = []
        vfx = set(self.known_vfx())
        for beat in sequence.beats:
            where = f"{sequence.sequence_id}.{beat.beat_id}"
            if beat.channel not in CHANNELS:
                found.append(f"{where}: unknown channel {beat.channel}")
            if beat.channel == "animation" and beat.cue not in self.animation_cues():
                found.append(f"{where}: animation cue must be one of {self.animation_cues()}")
            if beat.channel == "timing" and beat.cue not in TIMING_CUES:
                found.append(f"{where}: timing cue must be one of {TIMING_CUES}")
            if beat.channel == "motion_fx" and beat.cue not in MOTION_FX_CUES:
                found.append(f"{where}: motion_fx cue must be one of {MOTION_FX_CUES}")
            if beat.channel == "move" and beat.cue not in MOVE_CUES:
                found.append(f"{where}: move cue must be one of {MOVE_CUES}")
            if beat.channel == "vfx" and vfx and beat.cue not in vfx:
                found.append(f"{where}: unknown VFX sheet {beat.cue}")
            if beat.member_id not in (None, *TARGETS):
                found.append(f"{where}: member must be @source or @target")
        return found

    def _commit(self, sequence_id, after, label):
        if after is not None:
            problems = self.problems(after)
            if problems:
                raise ActionTimelineError("; ".join(problems))
        before = (
            self.library.get(CATEGORY, sequence_id)
            if sequence_id in self.library.ids(CATEGORY)
            else None
        )
        self.document.execute(_LibraryCommand(self.library, sequence_id, before, after, label))
        return after

    def _rebuild(self, sequence, *, duration=None, beats=None):
        try:
            return BattleMotionSequence(
                sequence.sequence_id,
                sequence.duration if duration is None else float(duration),
                tuple(sequence.beats if beats is None else beats),
                recovery_at=sequence.recovery_at,
            )
        except (TypeError, ValueError) as exc:
            raise ActionTimelineError(str(exc)) from exc

    # -- edits -----------------------------------------------------------------------
    def create(self, sequence_id, duration=0.8):
        sequence_id = str(sequence_id).strip()
        if not sequence_id or sequence_id in self.library.ids(CATEGORY):
            raise ActionTimelineError(f"sequence id {sequence_id!r} is empty or taken")
        beats = (_beat("swing", 0.0, "animation", "attack", "@source", None),)
        return self._commit(
            sequence_id,
            BattleMotionSequence(sequence_id, float(duration), beats),
            f"New timeline {sequence_id}",
        )

    def duplicate(self, sequence_id, new_id):
        source = self.get(sequence_id)
        if new_id in self.library.ids(CATEGORY):
            raise ActionTimelineError(f"sequence id {new_id} is taken")
        copy = BattleMotionSequence(
            new_id, source.duration, source.beats, recovery_at=source.recovery_at
        )
        return self._commit(new_id, copy, f"Duplicate timeline {sequence_id}")

    def delete(self, sequence_id):
        self.get(sequence_id)
        return self._commit(sequence_id, None, f"Delete timeline {sequence_id}")

    def set_duration(self, sequence_id, duration):
        sequence = self.get(sequence_id)
        return self._commit(
            sequence_id,
            self._rebuild(sequence, duration=duration),
            f"Timeline length {sequence_id}",
        )

    def add_beat(self, sequence_id, beat_id, at, channel, cue, member="@target", **payload):
        sequence = self.get(sequence_id)
        if any(b.beat_id == beat_id for b in sequence.beats):
            raise ActionTimelineError(f"beat id {beat_id} is taken")
        beat = _beat(beat_id, float(at), channel, cue, member, payload)
        return self._commit(
            sequence_id,
            self._rebuild(sequence, beats=sequence.beats + (beat,)),
            f"Add beat {beat_id}",
        )

    def edit_beat(self, sequence_id, beat_id, **changes):
        sequence = self.get(sequence_id)
        beats = []
        found = False
        for beat in sequence.beats:
            if beat.beat_id == beat_id:
                found = True
                payload = dict(beat.payload_dict())
                payload.update(changes.pop("payload", {}) or {})
                beat = _beat(
                    beat_id,
                    float(changes.get("at", beat.at)),
                    changes.get("channel", beat.channel),
                    changes.get("cue", beat.cue),
                    changes.get("member", beat.member_id),
                    payload,
                )
            beats.append(beat)
        if not found:
            raise ActionTimelineError(f"unknown beat {beat_id}")
        return self._commit(
            sequence_id, self._rebuild(sequence, beats=beats), f"Edit beat {beat_id}"
        )

    def move_beat(self, sequence_id, beat_id, at):
        at = max(0.0, min(float(at), self.get(sequence_id).duration))
        return self.edit_beat(sequence_id, beat_id, at=round(at, 3))

    def remove_beat(self, sequence_id, beat_id):
        sequence = self.get(sequence_id)
        beats = tuple(b for b in sequence.beats if b.beat_id != beat_id)
        if len(beats) == len(sequence.beats):
            raise ActionTimelineError(f"unknown beat {beat_id}")
        return self._commit(
            sequence_id, self._rebuild(sequence, beats=beats), f"Remove beat {beat_id}"
        )

    # -- preview ---------------------------------------------------------------------
    def preview(self, sequence_id, time):
        """Beats released by ``time`` (in order) and whether the sequence has finished."""
        sequence = self.get(sequence_id)
        released = [b for b in sequence.beats if b.at <= float(time) + 1e-9]
        return {
            "released": [(b.at, b.channel, b.cue, b.member_id) for b in released],
            "finished": float(time) >= sequence.duration,
        }
