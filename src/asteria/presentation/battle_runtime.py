from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite

from asteria.gameplay.action_timeline import ActionCueKind
from asteria.runtime import AnimatorState, TextureDraw

from .battle_animation_timing import BattleAnimationTimingProfile, easing_value

from .battle import (
    BattleCombatantVisual,
    BattlePresentationEvent,
    BattlePresentationEventKind,
    BattlePresentationScene,
)


class BattleAnimationRole(str, Enum):
    IDLE = "idle"
    ATTACK = "attack"
    HIT = "hit"
    KO = "ko"


_TRANSIENT_ROLE_NAMES = {"attack", "hit"}


def _role_name(role):
    if isinstance(role, BattleAnimationRole):
        return role.value
    value = str(role).strip()
    if not value:
        raise ValueError("animation role is required")
    return value


def _normalize_role(role):
    name = _role_name(role)
    try:
        return BattleAnimationRole(name)
    except ValueError:
        return name


def _finite_dt(value):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError("dt must be finite and >= 0")
    return value


@dataclass(frozen=True, slots=True)
class BattlePresentationFrame:
    """Backend-neutral battle frame ready for a texture renderer adapter."""

    scene_id: str
    background_asset_id: str
    combatant_draws: tuple[TextureDraw, ...]


@dataclass(slots=True)
class BattleCombatantAnimator:
    """Presentation-only animation state for one canonical battle member."""

    visual: BattleCombatantVisual
    clip_set: object
    animator: AnimatorState
    role: object = BattleAnimationRole.IDLE
    visible: bool = True
    defeated: bool = False
    timing_profile: BattleAnimationTimingProfile | None = None
    transition_from_frame: int | None = None
    transition_age: float = 0.0
    transition_duration: float = 0.0
    transition_easing: str = "linear"
    recovery_remaining: float = 0.0
    timing_cache: dict[str, object] = field(default_factory=dict, repr=False)

    @classmethod
    def create(cls, visual: BattleCombatantVisual, clip_set, timing_profile=None):
        idle_name = visual.clip_for(BattleAnimationRole.IDLE.value)
        if not idle_name:
            raise ValueError(f"combatant {visual.member_id} requires an idle animation role")
        idle = clip_set.get(idle_name)
        if idle is None:
            raise ValueError(f"missing idle clip {idle_name!r} for {visual.member_id}")
        timing_profile = timing_profile or BattleAnimationTimingProfile()
        if not isinstance(timing_profile, BattleAnimationTimingProfile):
            raise TypeError("timing_profile must be BattleAnimationTimingProfile")
        return cls(visual, clip_set, AnimatorState(idle), timing_profile=timing_profile)

    @property
    def clip_name(self):
        return self.animator.clip.name

    @property
    def frame_index(self):
        return self.animator.frame_index

    def _clip_for_role(self, role):
        clip_name = self.visual.clip_for(_role_name(role))
        return None if not clip_name else self.clip_set.get(clip_name)

    def _timing_rule(self, role):
        name = _role_name(role)
        rule = self.timing_cache.get(name)
        if rule is None:
            rule = self.timing_profile.rule_for(name)
            self.timing_cache[name] = rule
        return rule

    def _begin_transition(self, old_frame, rule):
        duration = float(rule.transition_duration)
        if duration <= 0:
            self.transition_from_frame = None
            self.transition_age = 0.0
            self.transition_duration = 0.0
            self.transition_easing = rule.transition_easing
            return
        self.transition_from_frame = int(old_frame)
        self.transition_age = 0.0
        self.transition_duration = duration
        self.transition_easing = rule.transition_easing

    def transition_mix(self):
        if self.transition_from_frame is None or self.transition_duration <= 0:
            return 1.0
        return easing_value(
            self.transition_easing,
            self.transition_age / self.transition_duration,
        )

    def set_role(self, role, *, restart=True, allow_idle_fallback=True):
        role = _normalize_role(role)
        if self.defeated and _role_name(role) != BattleAnimationRole.KO.value:
            return False
        clip = self._clip_for_role(role)
        selected_role = role
        if clip is None and allow_idle_fallback:
            selected_role = BattleAnimationRole.IDLE
            clip = self._clip_for_role(selected_role)
        if clip is None:
            return False
        old_frame = self.frame_index
        rule = self._timing_rule(selected_role)
        self.role = selected_role
        self.animator.set_clip(clip, restart=restart)
        self.recovery_remaining = 0.0
        self._begin_transition(old_frame, rule)
        return _role_name(selected_role) == _role_name(role)

    def set_clip_name(self, clip_name, *, role=None, restart=True):
        clip = self.clip_set.get(str(clip_name))
        if clip is None or self.defeated:
            return False
        old_frame = self.frame_index
        selected_role = self.role if role is None else _normalize_role(role)
        rule = self._timing_rule(selected_role)
        self.animator.set_clip(clip, restart=restart)
        if role is not None:
            self.role = selected_role
        self.recovery_remaining = 0.0
        self._begin_transition(old_frame, rule)
        return True

    def mark_defeated(self):
        self.defeated = True
        self.visible = True
        self.set_role(BattleAnimationRole.KO, restart=True, allow_idle_fallback=True)

    def revive(self):
        self.defeated = False
        self.visible = True
        self.set_role(BattleAnimationRole.IDLE, restart=True)

    def update(self, dt):
        dt = _finite_dt(dt)
        if self.transition_from_frame is not None:
            self.transition_age += dt
            if self.transition_age >= self.transition_duration:
                self.transition_from_frame = None
                self.transition_age = self.transition_duration

        rule = self._timing_rule(self.role)
        if self.animator.playing:
            self.animator.update(dt * rule.playback_rate)

        if _role_name(self.role) in _TRANSIENT_ROLE_NAMES and not self.animator.playing:
            if self.recovery_remaining <= 0.0:
                self.recovery_remaining = rule.recovery_hold
            if self.recovery_remaining > 0.0:
                self.recovery_remaining = max(0.0, self.recovery_remaining - dt)
            if self.recovery_remaining <= 0.0:
                self.set_role(BattleAnimationRole.IDLE, restart=True)

    def snapshot(self):
        return {
            "member_id": self.visual.member_id,
            "role": _role_name(self.role),
            "clip_name": self.clip_name,
            "time": self.animator.time,
            "frame_cursor": self.animator.frame_cursor,
            "playing": self.animator.playing,
            "visible": self.visible,
            "defeated": self.defeated,
            "transition_from_frame": self.transition_from_frame,
            "transition_age": self.transition_age,
            "transition_duration": self.transition_duration,
            "transition_easing": self.transition_easing,
            "recovery_remaining": self.recovery_remaining,
        }

    def restore(self, data):
        if data.get("member_id") != self.visual.member_id:
            raise ValueError("combatant presentation member mismatch")
        clip = self.clip_set.get(str(data["clip_name"]))
        if clip is None:
            raise ValueError("missing presentation clip during restore")
        frame_cursor = int(data["frame_cursor"])
        time = float(data["time"])
        if not isfinite(time) or time < 0 or frame_cursor < 0 or frame_cursor >= len(clip.keyframes):
            raise ValueError("invalid combatant animation snapshot")
        self.role = _normalize_role(data["role"])
        self.animator.clip = clip
        self.animator.time = time
        self.animator.frame_cursor = frame_cursor
        self.animator.playing = bool(data["playing"])
        self.visible = bool(data["visible"])
        self.defeated = bool(data["defeated"])
        transition_from = data.get("transition_from_frame")
        self.transition_from_frame = None if transition_from is None else int(transition_from)
        self.transition_age = _finite_dt(data.get("transition_age", 0.0))
        self.transition_duration = _finite_dt(data.get("transition_duration", 0.0))
        self.transition_easing = str(data.get("transition_easing", "linear"))
        easing_value(self.transition_easing, 0.5)
        self.recovery_remaining = _finite_dt(data.get("recovery_remaining", 0.0))


class BattlePresentationRuntime:
    """Consumes presentation events and produces deterministic visual state.

    This runtime never calls Battle Core resolvers. It can only consume already
    resolved presentation/lifecycle events, advance animation clocks, and emit
    texture draw commands through the existing runtime/render abstraction.
    """

    def __init__(self, scene: BattlePresentationScene, resolve_clip_set, resolve_sprite_sheet, timing_profile=None):
        if not isinstance(scene, BattlePresentationScene):
            raise TypeError("scene must be BattlePresentationScene")
        self.scene = scene
        self.timing_profile = timing_profile or BattleAnimationTimingProfile()
        if not isinstance(self.timing_profile, BattleAnimationTimingProfile):
            raise TypeError("timing_profile must be BattleAnimationTimingProfile")
        self._resolve_sprite_sheet = resolve_sprite_sheet
        self._combatants: dict[str, BattleCombatantAnimator] = {}
        self._sprite_sheets = {}
        self._member_order = tuple(x.member_id for x in scene.combatants)
        for visual in scene.combatants:
            clip_set = resolve_clip_set(visual.clip_set_id)
            if clip_set is None:
                raise ValueError(f"missing animation clip set: {visual.clip_set_id}")
            sheet = resolve_sprite_sheet(visual.sprite_sheet_asset_id)
            if sheet is None:
                raise ValueError(f"missing sprite sheet: {visual.sprite_sheet_asset_id}")
            clip_set.validate(sheet)
            self._sprite_sheets[visual.member_id] = sheet
            self._combatants[visual.member_id] = BattleCombatantAnimator.create(
                visual, clip_set, self.timing_profile
            )
        self.time = 0.0
        self.last_sequence = 0

    def combatant(self, member_id):
        return self._combatants[str(member_id)]

    def _member_from_animation_payload(self, payload):
        for key in ("member_id", "combatant_id", "source_id", "target_id"):
            value = str(payload.get(key, "")).strip()
            if value:
                return value
        return ""

    def _apply_timeline_event(self, event):
        cue = dict(event.payload.get("cue", {}))
        if cue.get("kind") != ActionCueKind.ANIMATION.value:
            return False
        payload = dict(cue.get("payload", {}))
        member_id = self._member_from_animation_payload(payload)
        state = self._combatants.get(member_id)
        if state is None:
            return False
        role = payload.get("role")
        clip = payload.get("clip")
        if role:
            try:
                return state.set_role(role, restart=bool(payload.get("restart", True)))
            except ValueError:
                return False
        if clip:
            return state.set_clip_name(clip, restart=bool(payload.get("restart", True)))
        return False

    @staticmethod
    def _hook_name(event):
        return str(event.payload.get("hook", ""))

    def _apply_combatant_state_event(self, event):
        state = self._combatants.get(event.source_id)
        if state is None:
            return False
        hook = self._hook_name(event)
        data = event.payload.get("data", {})
        lifecycle = data.get("state") or data.get("current")
        defeated = getattr(lifecycle, "defeated", None)
        present = getattr(lifecycle, "present", None)
        if hook == "rpg.battle.combatant_revived" or defeated is False:
            state.revive()
            return True
        if hook == "rpg.battle.combatant_removed" or present is False:
            state.mark_defeated()
            state.visible = False
            return True
        if hook == "rpg.battle.combatant_incapacitated" or defeated is True:
            state.mark_defeated()
            return True
        return False

    def apply_event(self, event: BattlePresentationEvent):
        if not isinstance(event, BattlePresentationEvent):
            raise TypeError("event must be BattlePresentationEvent")
        if event.sequence <= self.last_sequence:
            raise ValueError("presentation events must be applied in increasing sequence order")
        self.last_sequence = event.sequence
        if event.kind == BattlePresentationEventKind.TIMELINE_CUE:
            return self._apply_timeline_event(event)
        if event.kind == BattlePresentationEventKind.COMBATANT_STATE:
            return self._apply_combatant_state_event(event)
        return False

    def apply_events(self, events):
        return tuple(self.apply_event(event) for event in events)

    def update(self, dt):
        dt = _finite_dt(dt)
        self.time += dt
        for member_id in self._member_order:
            self._combatants[member_id].update(dt)

    def build_frame(self, camera):
        draws = []
        for visual in self.scene.combatants:
            state = self._combatants[visual.member_id]
            if not state.visible:
                continue
            sheet = self._sprite_sheets[visual.member_id]
            frame = sheet.frames[state.frame_index]
            mix = state.transition_mix()

            if state.transition_from_frame is not None and 0 <= state.transition_from_frame < len(sheet.frames):
                previous = sheet.frames[state.transition_from_frame]
                px = visual.anchor.x - previous.width * previous.pivot_x
                py = visual.anchor.y - previous.height * previous.pivot_y
                psx, psy = camera.world_to_screen(px, py)
                draws.append(
                    TextureDraw(
                        sheet.texture.asset_id,
                        (previous.x, previous.y, previous.width, previous.height),
                        psx,
                        psy,
                        previous.width * camera.zoom,
                        previous.height * camera.zoom,
                        layer=0,
                        depth=visual.anchor.depth,
                        opacity=max(0.0, min(1.0, 1.0 - mix)),
                        flip_x=visual.anchor.facing.lower() == "left",
                    )
                )

            draw_x = visual.anchor.x - frame.width * frame.pivot_x
            draw_y = visual.anchor.y - frame.height * frame.pivot_y
            sx, sy = camera.world_to_screen(draw_x, draw_y)
            draws.append(
                TextureDraw(
                    sheet.texture.asset_id,
                    (frame.x, frame.y, frame.width, frame.height),
                    sx,
                    sy,
                    frame.width * camera.zoom,
                    frame.height * camera.zoom,
                    layer=0,
                    depth=visual.anchor.depth,
                    opacity=max(0.0, min(1.0, mix)),
                    flip_x=visual.anchor.facing.lower() == "left",
                )
            )
        draws.sort(key=lambda d: (d.layer, d.depth, d.screen_y, d.screen_x))
        return BattlePresentationFrame(self.scene.scene_id, self.scene.background_asset_id, tuple(draws))

    def snapshot(self):
        return {
            "schema": "asteria.battle_presentation_runtime",
            "version": 1,
            "scene_id": self.scene.scene_id,
            "time": self.time,
            "last_sequence": self.last_sequence,
            "timing_profile": self.timing_profile.to_data(),
            "combatants": [self._combatants[k].snapshot() for k in sorted(self._combatants)],
        }

    def restore(self, data):
        if data.get("schema") != "asteria.battle_presentation_runtime" or data.get("version") != 1:
            raise ValueError("unsupported battle presentation runtime snapshot")
        if data.get("scene_id") != self.scene.scene_id:
            raise ValueError("battle presentation scene mismatch")
        if "timing_profile" in data:
            restored_profile = BattleAnimationTimingProfile.from_data(data["timing_profile"])
            if restored_profile != self.timing_profile:
                raise ValueError("battle animation timing profile mismatch")
        time = float(data["time"])
        last_sequence = int(data["last_sequence"])
        if not isfinite(time) or time < 0 or last_sequence < 0:
            raise ValueError("invalid battle presentation runtime snapshot")
        raw = list(data["combatants"])
        if {x.get("member_id") for x in raw} != set(self._combatants):
            raise ValueError("battle presentation combatant set mismatch")
        for item in raw:
            self._combatants[item["member_id"]].restore(item)
        self.time = time
        self.last_sequence = last_sequence
