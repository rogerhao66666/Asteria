"""Battle presentation adapters for the playable runtime (CB2, incremental).

Both adapters consume the same canonical ``BattleLogEntry`` stream produced by
``GameSessionRuntime``; neither decides any battle rule. ``LegacyPygameBattle
Adapter`` keeps the original hand-drawn pygame screen. ``CanonicalBattle
Adapter`` routes the log through ``BattleScreenRuntime`` (HUD, turn timeline,
action menu, value popups, camera feedback, result) and renders it with
``PygameBattleUiBackend``. Combatant sprites come from authored combatant
visuals when a project provides them; until then the legacy world layer is
drawn underneath.

``entry_semantics`` is the comparison contract for behaviour parity tests:
each adapter records, in ``trace``, what it understood from the log.
"""
from __future__ import annotations

from typing import Protocol

from asteria.gameplay import ActionCue, ActionCueKind, PresentationCue
from asteria.presentation import (
    BattlePresentationEventKind,
    BattlePresentationScene,
    BattleScreenRuntime,
    BattleUiRenderer,
)
from asteria.presentation.battle_action_menu import BattleActionEntry
from asteria.rpg import BattleOutcome
from asteria.runtime.camera import Camera2D

PRESENTATION_PROFILE_CATEGORIES = {
    "feedback_profile": "feedback",
    "hud_profile": "hud",
    "result_profile": "results",
    "layout": "ui_layout",
    "party_layout": "party_layout",
    "action_menu_policy": "action_menu",
    "director_profile": "director",
    "animation_timing_profile": "animation_timing",
    "layering_profile": "layering",
    "ui_polish_profile": "ui_polish",
}


def _value(outcome):
    value = getattr(outcome, "value", None)
    return round(float(getattr(value, "resolved_value", 0.0)), 6)


def entry_semantics(entry):
    """Rule-relevant meaning of one battle log entry, for parity comparison."""
    if entry.kind == "action":
        return (
            "action", entry.member_id, entry.ability_id, tuple(entry.target_ids),
            tuple((t, _value(o), tuple(sorted(getattr(o, "outcome_tags", ())))) for t, o in entry.outcomes),
        )
    if entry.kind == "turn":
        return ("turn", entry.member_id)
    if entry.kind == "gauge":
        return ("gauge", entry.member_id, entry.data.composition_id,
                tuple(x.threshold_id for x in entry.data.thresholds))
    if entry.kind == "battle_finished":
        return ("battle_finished", tuple(entry.data["winning_sides"]))
    return (entry.kind,)


class BattlePresentationAdapter(Protocol):
    name: str
    trace: list

    def begin(self) -> None: ...
    def consume(self, entries) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self) -> None: ...


class LegacyPygameBattleAdapter:
    """The original pygame battle screen, unchanged, behind the adapter interface."""

    name = "legacy"

    def __init__(self, host):
        self.host = host
        self.trace = []

    def begin(self):
        self.trace.clear()

    def consume(self, entries):
        self.trace.extend(entry_semantics(e) for e in entries)

    def update(self, dt):
        pass

    def draw(self):
        self.host._draw_battle_world()
        self.host._draw_battle_hud()


class CanonicalBattleAdapter:
    """Canonical Battle Presentation driven by the session's battle log."""

    name = "canonical"

    # Session parties are "heroes" and "enemies"; mirror the legacy world layer.
    DEFAULT_PLACEMENT = {"heroes": "left", "enemies": "right"}

    def __init__(self, host, *, profile_ids=None, placement_by_side=None):
        self.host = host
        self.trace = []
        self.profile_ids = dict(profile_ids or {})
        self.placement_by_side = dict(placement_by_side or self.DEFAULT_PLACEMENT)
        self.screen = None
        self.renderer = None
        self._ui_backend = None
        self.audio_cues = []

    # -- construction -----------------------------------------------------
    def _profile(self, category):
        library = self.host.project.battle_presentation_library
        profile_id = self.profile_ids.get(category)
        if profile_id is None:
            ids = library.ids(category)
            profile_id = ids[0] if ids else None
        return None if profile_id is None else library.require(category, profile_id)

    def _theme(self):
        return self._profile("ui_theme")

    def begin(self):
        from asteria.platform.pygame_battle_ui import PygameBattleUiBackend

        self.trace.clear()
        game = self.host.game
        scene = BattlePresentationScene(
            f"battle.{game.encounter_id}", self.host.manifest["battle"].get("background", "battle.background"),
        )
        kwargs = {name: self._profile(category) for name, category in PRESENTATION_PROFILE_CATEGORIES.items()}
        kwargs = {name: value for name, value in kwargs.items() if value is not None}
        self.screen = BattleScreenRuntime(
            scene, lambda _id: None, lambda _id: None, placement_by_side=self.placement_by_side, **kwargs,
        )
        self.screen.coordinator.attach(game.battle.hooks)
        layout = self.screen.composer.layout
        scale = min(self.host.width / layout.virtual_width, self.host.height / layout.virtual_height)
        self._ui_backend = PygameBattleUiBackend(self.host.screen, scale=scale)
        self.renderer = BattleUiRenderer(self._ui_backend, self._theme())
        self.audio_cues.clear()

    # -- log translation --------------------------------------------------
    def consume(self, entries):
        coordinator = self.screen.coordinator
        for entry in entries:
            if entry.kind == "battle_started":
                coordinator.start()
            elif entry.kind == "turn":
                coordinator.push_custom("battle.turn", source_id=entry.member_id)
            elif entry.kind == "action":
                self._push_action(entry)
            elif entry.kind == "gauge":
                coordinator.push_gauge_result(entry.data)
            elif entry.kind == "battle_finished":
                data = entry.data
                outcome = BattleOutcome(True, tuple(data["winning_sides"]), tuple(data["defeated_sides"]))
                self.screen.present_result(outcome, perspective_side_ids=("heroes",))
                coordinator.finish({"winning_sides": list(data["winning_sides"])})
        events = coordinator.drain()
        self.trace.extend(self._semantics_from_events(events))
        self.screen.consume_events(events)

    def _push_action(self, entry):
        coordinator = self.screen.coordinator
        targets = tuple(entry.target_ids)
        coordinator.push_custom(
            "battle.action", source_id=entry.member_id,
            payload={"ability_id": entry.ability_id, "target_ids": list(targets)},
        )
        if targets:
            coordinator.push_target_selection(targets, primary_target_id=targets[0], source_id=entry.member_id)
        cues = [PresentationCue(f"action.{entry.ability_id}", ActionCue(
            f"{entry.member_id}.attack", 0.0, ActionCueKind.ANIMATION, {"member_id": entry.member_id, "role": "attack"},
        ))]
        cues.extend(PresentationCue(f"action.{entry.ability_id}", ActionCue(
            f"{target}.hit", 0.0, ActionCueKind.ANIMATION, {"member_id": target, "role": "hit"},
        )) for target, _ in entry.outcomes)
        coordinator.consume_timeline_cues(cues)
        for target, outcome in entry.outcomes:
            coordinator.push_resolved_value(outcome, target_id=target, source_id=entry.member_id)

    @staticmethod
    def _semantics_from_events(events):
        """Rebuild rule-relevant meaning from the presentation events actually emitted."""
        result = []
        pending = None
        for event in events:
            kind, payload = event.kind, event.payload
            if kind == BattlePresentationEventKind.SCENE_STARTED:
                result.append(("battle_started",))
            elif kind == BattlePresentationEventKind.CUSTOM and payload.get("event_id") == "battle.turn":
                result.append(("turn", event.source_id))
            elif kind == BattlePresentationEventKind.CUSTOM and payload.get("event_id") == "battle.action":
                pending = [event.source_id, payload["ability_id"], tuple(payload["target_ids"]), []]
                result.append(pending)
            elif kind == BattlePresentationEventKind.RESOLVED_VALUE and pending is not None:
                pending[3].append((payload["target_id"], round(float(payload["value"]), 6),
                                   tuple(sorted(payload["outcome_tags"]))))
            elif kind == BattlePresentationEventKind.GAUGE_THRESHOLD:
                key = ("gauge", event.source_id, payload["composition_id"])
                if result and isinstance(result[-1], tuple) and result[-1][:3] == key:
                    result[-1] = (*key, (*result[-1][3], payload["threshold_id"]))
                else:
                    result.append((*key, (payload["threshold_id"],)))
            elif kind == BattlePresentationEventKind.SCENE_FINISHED:
                result.append(("battle_finished", tuple(payload["result"]["winning_sides"])))
        return [
            ("action", item[0], item[1], item[2], tuple(item[3])) if isinstance(item, list) else item
            for item in result
        ]

    # -- frame --------------------------------------------------------------
    def update(self, dt):
        game = self.host.game
        if game.battle is not None:
            self.screen.sync_battle(game.battle, current_member_id=self.host._battle_actor())
            entries = [
                BattleActionEntry(ability_id, meta.get("label", ability_id), order=i)
                for i, (ability_id, meta) in enumerate(self.host._skills_for_actor(self.host._battle_actor()))
            ]
            self.screen.set_action_entries(entries)
        self.screen.update(dt)

    def draw(self):
        if not self.screen.scene.combatants:
            self.host._draw_battle_world(show_labels=False)
        layout = self.screen.composer.layout
        result = self.screen.render(Camera2D(width=layout.virtual_width, height=layout.virtual_height), ui_renderer=self.renderer)
        self.audio_cues.extend(result.audio_cues)
        return result


def create_battle_presentation_adapter(host):
    """Pick the adapter named by the manifest (``battle.presentation.adapter``); legacy by default."""
    settings = host.manifest.get("battle", {}).get("presentation", {})
    kind = settings.get("adapter", "legacy")
    if kind == "legacy":
        return LegacyPygameBattleAdapter(host)
    if kind == "canonical":
        return CanonicalBattleAdapter(
            host, profile_ids=settings.get("profiles"), placement_by_side=settings.get("placement_by_side"),
        )
    raise ValueError(f"unknown battle presentation adapter: {kind}")
