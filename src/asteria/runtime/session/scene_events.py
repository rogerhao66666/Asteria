"""Visible encounters, the scene's event runners, cutscenes and the sequence host."""

from __future__ import annotations

from asteria.core import Transform
from asteria.events import SceneEventRuntime

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class SceneEventsMixin:
    def check_visible_encounter(self):
        """Start the encounter of a field enemy (VisibleEncounterComponent) the player touches."""
        from asteria.runtime.field_ai import VisibleEncounterComponent, touched_encounter

        if self.mode != "field" or self.event_busy:
            return None
        entity = touched_encounter(self.scene, self.player)
        if entity is None:
            return None
        spec = entity.get(VisibleEncounterComponent)
        encounter_id = spec.encounter_id
        if spec.remove_on_start:
            self.scene.remove_entity(entity)
        self.start_encounter(encounter_id)
        return encounter_id

    def _build_scene_events(self):
        bindings = self.project.scene_event_bindings.get(self.scene.id)
        self.scene_events = (
            None
            if bindings is None
            else SceneEventRuntime.build(
                bindings,
                self.project.event_programs,
                context=self.save.event_context,
                world_commands=self.world_commands,
                sequence_host=self,
            )
        )

    @property
    def event_busy(self):
        """True while a foreground or autorun event blocks player control."""
        return (
            self.events.busy
            or (self.scene_events is not None and self.scene_events.scheduler.autorun_busy)
            or self.common_events.autorun_busy
            or getattr(self, "sighting", None) is not None
        )

    def _all_runners(self):
        yield self.events
        if self.scene_events is not None:
            yield from self.scene_events.scheduler.runners()
        yield from self.common_events.runners()

    def _dialogue_runner(self):
        return next((r for r in self._all_runners() if r.dialogue.blocked), None)

    # -- cutscenes and the sequence host (EVT-03 / EVT-04) ------------------------------------
    @property
    def cutscene_active(self):
        """A cutscene sequence is running: hosts lock player control (and may letterbox)."""
        return any(r.cutscene for r in self._all_runners())

    @property
    def cutscene_skippable(self):
        return any(r.can_skip for r in self._all_runners())

    def skip_cutscene(self):
        """Fast-forward skippable cutscenes to their end state (moves land, world commands still
        run)."""
        skipped = sum(r.skip_sequences() for r in self._all_runners())
        self.update_events(0.0)
        return skipped

    def _sequence_entity(self, key):
        key = str(key)
        if key.startswith("var:"):  # the entity a variable names (set earlier by the event)
            key = str(self.save.event_context.get_variable(key[4:], ""))
        if key in ("player", "@player", self.player.id):
            return self.player
        entity = self.scene.get_entity(key) or next(
            (e for e in self.scene.entities() if e.name == key), None
        )
        if entity is None or not entity.has(Transform):
            raise GameSessionError(
                f"sequence: no entity {key} with a position in {self.scene.name}"
            )
        return entity

    def position(self, key):
        t = self._sequence_entity(key).get(Transform)
        return (t.x, t.y)

    def set_position(self, key, x, y):
        entity = self._sequence_entity(key)
        if entity is self.player:
            return self.set_player_position(x, y)
        t = entity.get(Transform)
        t.x, t.y = float(x), float(y)
        self._record_npc(entity)
        return (t.x, t.y)
