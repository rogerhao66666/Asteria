from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Iterable

from asteria.core.lifecycle import LifecycleEvent, LifecycleHookBus
from asteria.gameplay.action_timeline import PresentationCue


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _number(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


class BattlePresentationEventKind(str, Enum):
    SCENE_STARTED = "scene_started"
    SCENE_FINISHED = "scene_finished"
    TIMELINE_CUE = "timeline_cue"
    COMBATANT_STATE = "combatant_state"
    TURN_READY = "turn_ready"
    TURN_ENDED = "turn_ended"
    SEQUENCE_STARTED = "sequence_started"
    SEQUENCE_STEP = "sequence_step"
    SEQUENCE_FINISHED = "sequence_finished"
    BATTLE_RESULT = "battle_result"
    RESOLVED_VALUE = "resolved_value"
    GAUGE_THRESHOLD = "gauge_threshold"
    TARGET_SELECTION = "target_selection"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class BattleVisualAnchor:
    x: float
    y: float
    facing: str = "right"
    depth: float = 0.0

    def __init__(self, x, y, facing="right", depth=0.0):
        facing = _id(facing, "facing")
        object.__setattr__(self, "x", _number(x, "x"))
        object.__setattr__(self, "y", _number(y, "y"))
        object.__setattr__(self, "facing", facing)
        object.__setattr__(self, "depth", _number(depth, "depth"))

    def to_data(self):
        return {"x": self.x, "y": self.y, "facing": self.facing, "depth": self.depth}

    @classmethod
    def from_data(cls, data):
        return cls(data["x"], data["y"], data.get("facing", "right"), data.get("depth", 0.0))


@dataclass(frozen=True, slots=True)
class BattleCombatantVisual:
    member_id: str
    sprite_sheet_asset_id: str
    clip_set_id: str
    anchor: BattleVisualAnchor
    animation_roles: tuple[tuple[str, str], ...]
    aura_sprite_sheet_asset_id: str | None = None
    source_pixels_per_logical_pixel: float = 1.0

    def __init__(
        self,
        member_id,
        sprite_sheet_asset_id,
        clip_set_id,
        anchor,
        animation_roles=None,
        aura_sprite_sheet_asset_id=None,
        source_pixels_per_logical_pixel=1.0,
    ):
        if not isinstance(anchor, BattleVisualAnchor):
            raise TypeError("anchor must be BattleVisualAnchor")
        roles = dict(animation_roles or {"idle": "idle", "attack": "attack", "hit": "hit", "ko": "ko"})
        normalized = tuple(sorted((_id(k, "animation role"), _id(v, "animation clip")) for k, v in roles.items()))
        object.__setattr__(self, "member_id", _id(member_id, "member_id"))
        object.__setattr__(self, "sprite_sheet_asset_id", _id(sprite_sheet_asset_id, "sprite_sheet_asset_id"))
        object.__setattr__(self, "clip_set_id", _id(clip_set_id, "clip_set_id"))
        object.__setattr__(self, "anchor", anchor)
        object.__setattr__(self, "animation_roles", normalized)
        aura_asset_id = (
            None
            if aura_sprite_sheet_asset_id is None
            or not str(aura_sprite_sheet_asset_id).strip()
            else _id(aura_sprite_sheet_asset_id, "aura_sprite_sheet_asset_id")
        )
        object.__setattr__(self, "aura_sprite_sheet_asset_id", aura_asset_id)
        source_ratio = float(source_pixels_per_logical_pixel)
        if not isfinite(source_ratio) or source_ratio <= 0:
            raise ValueError("source_pixels_per_logical_pixel must be finite and positive")
        object.__setattr__(self, "source_pixels_per_logical_pixel", source_ratio)

    def clip_for(self, role):
        return dict(self.animation_roles).get(str(role))

    def to_data(self):
        data = {
            "member_id": self.member_id,
            "sprite_sheet_asset_id": self.sprite_sheet_asset_id,
            "clip_set_id": self.clip_set_id,
            "anchor": self.anchor.to_data(),
            "animation_roles": dict(self.animation_roles),
        }
        if self.aura_sprite_sheet_asset_id is not None:
            data["aura_sprite_sheet_asset_id"] = self.aura_sprite_sheet_asset_id
        if self.source_pixels_per_logical_pixel != 1.0:
            data["source_pixels_per_logical_pixel"] = self.source_pixels_per_logical_pixel
        return data

    @classmethod
    def from_data(cls, data):
        return cls(data["member_id"], data["sprite_sheet_asset_id"], data["clip_set_id"],
                   BattleVisualAnchor.from_data(data["anchor"]), data.get("animation_roles"),
                   data.get("aura_sprite_sheet_asset_id"),
                   data.get("source_pixels_per_logical_pixel", 1.0))


@dataclass(frozen=True, slots=True)
class BattlePresentationScene:
    scene_id: str
    background_asset_id: str
    combatants: tuple[BattleCombatantVisual, ...]
    camera_preset_id: str = "battle.default"

    def __init__(self, scene_id, background_asset_id, combatants=(), camera_preset_id="battle.default"):
        combatants = tuple(combatants)
        if any(not isinstance(x, BattleCombatantVisual) for x in combatants):
            raise TypeError("combatants must be BattleCombatantVisual")
        ids = [x.member_id for x in combatants]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate combatant visual member_id")
        object.__setattr__(self, "scene_id", _id(scene_id, "scene_id"))
        object.__setattr__(self, "background_asset_id", _id(background_asset_id, "background_asset_id"))
        object.__setattr__(self, "combatants", combatants)
        object.__setattr__(self, "camera_preset_id", _id(camera_preset_id, "camera_preset_id"))

    def visual_for(self, member_id):
        member_id = str(member_id)
        for visual in self.combatants:
            if visual.member_id == member_id:
                return visual
        raise KeyError(member_id)

    def to_data(self):
        return {
            "schema": "asteria.battle_presentation_scene",
            "version": 1,
            "scene_id": self.scene_id,
            "background_asset_id": self.background_asset_id,
            "camera_preset_id": self.camera_preset_id,
            "combatants": [x.to_data() for x in self.combatants],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.battle_presentation_scene" or data.get("version") != 1:
            raise ValueError("unsupported battle presentation scene")
        return cls(data["scene_id"], data["background_asset_id"],
                   [BattleCombatantVisual.from_data(x) for x in data["combatants"]],
                   data.get("camera_preset_id", "battle.default"))


@dataclass(frozen=True, slots=True)
class BattlePresentationEvent:
    sequence: int
    kind: BattlePresentationEventKind
    source_id: str
    payload: dict


class BattlePresentationCoordinator:
    """Backend-neutral bridge from frozen Battle Core/timelines to visual adapters.

    It owns ordering and presentation state only. It never computes damage, target
    legality, costs, turn order, status meaning, weakness rules, or battle outcome.
    """

    def __init__(self, scene: BattlePresentationScene):
        if not isinstance(scene, BattlePresentationScene):
            raise TypeError("scene must be BattlePresentationScene")
        self.scene = scene
        self._sequence = 0
        self._pending: list[BattlePresentationEvent] = []
        self._hooks: LifecycleHookBus | None = None
        self._active = False

    @property
    def active(self):
        return self._active

    def _emit(self, kind, source_id="", payload=None):
        self._sequence += 1
        event = BattlePresentationEvent(self._sequence, BattlePresentationEventKind(kind), str(source_id), dict(payload or {}))
        self._pending.append(event)
        return event

    def start(self):
        if self._active:
            return None
        self._active = True
        return self._emit(BattlePresentationEventKind.SCENE_STARTED, payload={"scene_id": self.scene.scene_id})

    def finish(self, result=None):
        if not self._active:
            return None
        self._active = False
        return self._emit(BattlePresentationEventKind.SCENE_FINISHED, payload={"result": result})

    def consume_timeline_cues(self, cues: Iterable[PresentationCue]):
        emitted = []
        for item in cues:
            if not isinstance(item, PresentationCue):
                raise TypeError("cues must contain PresentationCue")
            emitted.append(self._emit(
                BattlePresentationEventKind.TIMELINE_CUE,
                payload={"timeline_id": item.timeline_id, "cue": item.cue.to_data()},
            ))
        return tuple(emitted)

    def attach(self, hooks: LifecycleHookBus):
        if not isinstance(hooks, LifecycleHookBus):
            raise TypeError("hooks must be LifecycleHookBus")
        if self._hooks is hooks:
            return self
        if self._hooks is not None:
            self.detach()
        self._hooks = hooks
        hooks.subscribe("*", self._on_lifecycle_event)
        return self

    def detach(self):
        if self._hooks is not None:
            self._hooks.unsubscribe("*", self._on_lifecycle_event)
            self._hooks = None
        return self

    def _on_lifecycle_event(self, event: LifecycleEvent):
        mapping = {
            "rpg.battle.combatant_state_changed": BattlePresentationEventKind.COMBATANT_STATE,
            "rpg.battle.combatant_incapacitated": BattlePresentationEventKind.COMBATANT_STATE,
            "rpg.battle.combatant_revived": BattlePresentationEventKind.COMBATANT_STATE,
            "rpg.battle.combatant_removed": BattlePresentationEventKind.COMBATANT_STATE,
            "rpg.battle.combatant_transformed": BattlePresentationEventKind.COMBATANT_STATE,
            "rpg.battle.combatant_form_reverted": BattlePresentationEventKind.COMBATANT_STATE,
            "rpg.battle.turn_ready": BattlePresentationEventKind.TURN_READY,
            "rpg.battle.turn_ended": BattlePresentationEventKind.TURN_ENDED,
            "rpg.battle.sequence_started": BattlePresentationEventKind.SEQUENCE_STARTED,
            "rpg.battle.sequence_step_resolved": BattlePresentationEventKind.SEQUENCE_STEP,
            "rpg.battle.sequence_finished": BattlePresentationEventKind.SEQUENCE_FINISHED,
            "rpg.battle.finished": BattlePresentationEventKind.BATTLE_RESULT,
        }
        kind = mapping.get(event.name)
        if kind is not None:
            self._emit(kind, event.source, {"hook": event.name, "data": dict(event.data)})


    def push_resolved_value(self, result, *, target_id, source_id="", value_kind="damage", duration=None):
        from .battle_feedback import resolved_value_payload
        payload = resolved_value_payload(
            result, target_id=target_id, source_id=source_id, value_kind=value_kind, duration=duration
        )
        return self._emit(BattlePresentationEventKind.RESOLVED_VALUE, source_id, payload)

    def push_gauge_result(self, result):
        from .battle_feedback import gauge_threshold_payloads
        return tuple(
            self._emit(BattlePresentationEventKind.GAUGE_THRESHOLD, payload["member_id"], payload)
            for payload in gauge_threshold_payloads(result)
        )

    def push_target_selection(self, target_ids=(), *, primary_target_id=None, source_id=""):
        """Publish already-selected targets for presentation only.

        This intentionally performs no target validation or Battle Core lookup.
        The caller owns canonical selection/legality; presentation only mirrors it.
        """
        targets = tuple(_id(x, "target_id") for x in target_ids)
        if len(targets) != len(set(targets)):
            raise ValueError("duplicate target_ids")
        primary = None if primary_target_id is None else _id(primary_target_id, "primary_target_id")
        if primary is not None and primary not in targets:
            raise ValueError("primary_target_id must be present in target_ids")
        return self._emit(
            BattlePresentationEventKind.TARGET_SELECTION,
            source_id,
            {"target_ids": list(targets), "primary_target_id": primary},
        )

    def push_custom(self, event_id, *, source_id="", payload=None):
        return self._emit(BattlePresentationEventKind.CUSTOM, source_id,
                          {"event_id": _id(event_id, "event_id"), **dict(payload or {})})

    def drain(self):
        result = tuple(self._pending)
        self._pending.clear()
        return result
