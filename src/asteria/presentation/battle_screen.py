from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from asteria.runtime import Camera2D
from asteria.graphics.mv_weapon_visual import WeaponVisual, weapon_visual_for_type

from .battle import BattlePresentationCoordinator, BattlePresentationScene
from .battle_camera_feedback import BattleCameraFeedbackRuntime
from .battle_feedback import BattleFeedbackProfile, BattleFeedbackRuntime
from .battle_hud import BattleHudProfile, BattleHudRuntime
from .battle_result import BattleResultPresentationRuntime, BattleResultProfile
from .battle_runtime import BattlePresentationRuntime
from .battle_turn_timeline import BattleTurnTimelineRuntime
from .battle_ui import BattleUiComposer, BattleUiLayoutProfile
from .battle_ui_renderer import BattleUiRenderer
from .battle_action_menu import BattleActionMenuPolicy, BattleActionMenuRuntime
from .battle_action_workflow import BattleActionWorkflowRuntime
from .battle_presentation_director import BattlePresentationDirector, BattlePresentationDirectorProfile
from .battle_animation_timing import BattleAnimationTimingProfile
from .battle_ui_polish import BattleUiPolishProfile
from .battle_presentation_layering import BattlePresentationLayeringProfile, BattlePresentationLayeringRuntime


def _dt(value):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError("dt must be finite and >= 0")
    return value


@dataclass(frozen=True, slots=True)
class BattleScreenRenderResult:
    frame: object
    audio_cues: tuple


class BattleScreenRuntime:
    """Orchestrates the complete Battle Presentation execution path.

    This object coordinates presentation runtimes only. It can mirror canonical
    battle runtime state through `sync_battle`, but never advances Battle Core,
    resolves actions/targets, mutates resources/states, applies rewards, or
    determines battle outcomes.
    """

    def __init__(
        self,
        scene: BattlePresentationScene,
        resolve_clip_set,
        resolve_sprite_sheet,
        *,
        coordinator=None,
        feedback_profile=None,
        hud_profile=None,
        result_profile=None,
        layout=None,
        party_layout=None,
        placement_by_side=None,
        action_menu_policy=None,
        director_profile=None,
        animation_timing_profile=None,
        layering_profile=None,
        ui_polish_profile=None,
        max_turns=8,
    ):
        if not isinstance(scene, BattlePresentationScene):
            raise TypeError("scene must be BattlePresentationScene")
        self.scene = scene
        self.coordinator = coordinator or BattlePresentationCoordinator(scene)
        if not isinstance(self.coordinator, BattlePresentationCoordinator):
            raise TypeError("coordinator must be BattlePresentationCoordinator")
        if self.coordinator.scene.scene_id != scene.scene_id:
            raise ValueError("coordinator scene mismatch")

        self.animation = BattlePresentationRuntime(
            scene,
            resolve_clip_set,
            resolve_sprite_sheet,
            timing_profile=animation_timing_profile or BattleAnimationTimingProfile(),
        )
        self.feedback = BattleFeedbackRuntime(feedback_profile or BattleFeedbackProfile())
        self.camera_feedback = BattleCameraFeedbackRuntime(scene)
        self.hud = BattleHudRuntime(hud_profile or BattleHudProfile.default())
        self.timeline = BattleTurnTimelineRuntime(max_turns=max_turns)
        self.result = BattleResultPresentationRuntime(result_profile or BattleResultProfile())
        self.action_menu = BattleActionMenuRuntime(action_menu_policy or BattleActionMenuPolicy())
        self.action_workflow = BattleActionWorkflowRuntime()
        self.director = BattlePresentationDirector(
            director_profile or BattlePresentationDirectorProfile()
        )
        self.layering = BattlePresentationLayeringRuntime(
            layering_profile or BattlePresentationLayeringProfile()
        )
        self.composer = BattleUiComposer(
            scene,
            layout or BattleUiLayoutProfile(),
            party_layout=party_layout,
            polish=ui_polish_profile or BattleUiPolishProfile(),
        )

        self.side_by_member: dict[str, str] = {}
        self.placement_by_side = {
            str(k): str(v) for k, v in dict(placement_by_side or {}).items()
        }
        self.placement_by_member: dict[str, str] = {}
        self.current_member_id: str | None = None
        self.time = 0.0

    def _dispatch_presentation_events(self, values):
        values = tuple(values)
        if not values:
            return ()
        layered = self.layering.process(values)
        self.animation.apply_events(layered)
        self.feedback.apply_events(layered)
        self.camera_feedback.apply_events(layered)
        return layered

    def consume_events(self, events=None):
        """Route already-resolved events through presentation choreography.

        Events with no authored Director delay preserve the pre-Batch-108 immediate
        fan-out behavior. Delayed events remain presentation-only pending work.
        """
        values = tuple(self.coordinator.drain() if events is None else events)
        if not values:
            return ()
        released = self.director.ingest(values)
        self._dispatch_presentation_events(released)
        return values

    def update(self, dt):
        dt = _dt(dt)
        self.time += dt

        advance = self.director.update(dt)
        visual_dt = advance.presentation_dt
        self.animation.update(visual_dt)
        self.feedback.update(visual_dt)
        self.camera_feedback.update(visual_dt)
        # Events whose authored delay matures at this update boundary begin now;
        # they are not retroactively aged by this frame's preceding visual time.
        self._dispatch_presentation_events(advance.released_events)
        return self.time

    def sync_battle(self, battle_runtime, *, current_member_id=None):
        """Mirror canonical battle HUD/scheduler state without advancing it."""
        self.current_member_id = None if current_member_id is None else str(current_member_id)
        members = self.hud.sync_battle(battle_runtime)
        timing = getattr(battle_runtime, "action_timing", None)
        if timing is None:
            timing = getattr(battle_runtime, "action_timing_runtime", None)
        self.timeline.sync(
            battle_runtime.scheduler,
            timing,
            current_member_id=self.current_member_id,
        )
        self.side_by_member = {
            str(member_id): str(member.side)
            for member_id, member in sorted(battle_runtime.battle_resources.members.items())
        }

        # Presentation placement is explicit when configured. Otherwise sides are
        # assigned to visual zones deterministically without interpreting side names.
        side_ids = tuple(sorted(set(self.side_by_member.values())))
        auto_zone = {
            side_id: ("left" if index % 2 == 0 else "right")
            for index, side_id in enumerate(side_ids)
        }
        self.placement_by_member = {
            member_id: self.placement_by_side.get(side_id, auto_zone[side_id])
            for member_id, side_id in self.side_by_member.items()
        }
        return members

    def sync_weapon_loadouts(self, loadouts, system_data, asset_id_for_sheet) -> None:
        """Read equipped weapon types; armor is intentionally visually inert."""
        names = {str(name).casefold(): str(name) for name in system_data.get("weaponTypes", ())}
        for member_id in self.animation._member_order:
            loadout = loadouts.get(member_id)
            equipped = () if loadout is None else loadout.equipped("weapon")
            tags = () if not equipped else equipped[0].equipment.tags
            selected = next((tag.split(":", 1)[1] for tag in tags
                             if tag.startswith("mv-weapon-type:")), "")
            visual = weapon_visual_for_type(names.get(selected.casefold(), ""), system_data)
            asset_id = asset_id_for_sheet(visual.sheet_name) if visual.sheet_name else ""
            self.animation.set_weapon_visual(member_id, visual, asset_id)

    def present_result(self, outcome, reward_result=None, *, perspective_side_ids=None, disposition=None):
        return self.result.present(
            outcome,
            reward_result,
            perspective_side_ids=perspective_side_ids,
            disposition=disposition,
        )

    def set_action_entries(self, entries):
        """Replace presentation action entries supplied by the canonical controller."""
        return self.action_menu.set_entries(entries)

    def begin_action_workflow(self, definition, options=()):
        return self.action_workflow.begin(definition, options)

    def cancel_action_workflow(self):
        return self.action_workflow.cancel()

    def build_frame(self, base_camera: Camera2D):
        if not isinstance(base_camera, Camera2D):
            raise TypeError("base_camera must be Camera2D")
        view_camera = self.camera_feedback.camera_view(base_camera)
        battle_frame = self.animation.build_frame(view_camera)
        camera_frame = self.camera_feedback.build_frame(base_camera)
        return self.composer.compose(
            view_camera,
            battle_frame,
            hud_members=self.hud.members,
            timeline=self.timeline.view,
            feedback=self.feedback,
            camera_feedback=camera_frame,
            result=self.result.view,
            action_menu=self.action_menu.view if self.action_menu.view.total_count else None,
            action_workflow=self.action_workflow.view,
            side_by_member=self.side_by_member,
            placement_by_member=self.placement_by_member,
            focus_member_id=self.current_member_id,
        )

    def render(self, base_camera, *, ui_renderer: BattleUiRenderer, texture_renderer=None):
        """Render one presentation frame and return one-shot audio cues.

        World combatant texture draws are optional here so headless/UI-only tests
        can use the same orchestration path. A production runtime supplies the
        existing `TextureRenderer`.
        """
        if not isinstance(ui_renderer, BattleUiRenderer):
            raise TypeError("ui_renderer must be BattleUiRenderer")
        frame = self.build_frame(base_camera)
        if texture_renderer is not None:
            texture_renderer.render(frame.combatant_draws)
        ui_renderer.render(frame)
        return BattleScreenRenderResult(frame, self.feedback.drain_audio())

    def snapshot(self):
        return {
            "schema": "asteria.battle_screen_runtime",
            "version": 1,
            "scene_id": self.scene.scene_id,
            "time": self.time,
            "side_by_member": dict(sorted(self.side_by_member.items())),
            "placement_by_side": dict(sorted(self.placement_by_side.items())),
            "placement_by_member": dict(sorted(self.placement_by_member.items())),
            "current_member_id": self.current_member_id,
            "animation": self.animation.snapshot(),
            "feedback": self.feedback.snapshot(),
            "camera_feedback": self.camera_feedback.snapshot(),
            "hud": self.hud.snapshot(),
            "timeline": self.timeline.snapshot(),
            "result": self.result.snapshot(),
            "action_menu": self.action_menu.snapshot(),
            "action_workflow": self.action_workflow.snapshot(),
            "director": self.director.snapshot(),
            "layering": self.layering.snapshot(),
        }

    def restore(self, data):
        if data.get("schema") != "asteria.battle_screen_runtime" or data.get("version") != 1:
            raise ValueError("unsupported battle screen runtime snapshot")
        if data.get("scene_id") != self.scene.scene_id:
            raise ValueError("battle screen scene mismatch")
        self.time = _dt(data["time"])
        self.side_by_member = {str(k): str(v) for k, v in dict(data.get("side_by_member", {})).items()}
        self.placement_by_side = {
            str(k): str(v) for k, v in dict(data.get("placement_by_side", self.placement_by_side)).items()
        }
        self.placement_by_member = {
            str(k): str(v) for k, v in dict(data.get("placement_by_member", {})).items()
        }
        current = data.get("current_member_id")
        self.current_member_id = None if current is None else str(current)
        self.animation.restore(data["animation"])
        self.feedback.restore(data["feedback"])
        self.camera_feedback.restore(data["camera_feedback"])
        self.hud.restore(data["hud"])
        self.timeline.restore(data["timeline"])
        self.result.restore(data["result"])
        self.action_menu.restore(data["action_menu"])
        self.action_workflow.restore(data["action_workflow"])
        self.director.restore(data["director"])
        self.layering.restore(data["layering"])
        return self
