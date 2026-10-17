"""Presentation timing validation (CB13): authored motion beats vs what the screen actually shows.

``measure_action_timing(frame_times)`` runs the canonical battle screen
headlessly on the reference project, plays one skill and records — on the
presentation clock — when the source's attack pose, the effect, the
target's hit pose, the damage number and the hit sound appear. Each is
compared with ``start + beat.at`` from the ability's motion sequence.
A beat may only appear at the first frame boundary at or after its authored
time, so the allowed error is ``0 <= observed - authored <= frame length``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TimingSample:
    cue: str
    authored: float
    observed: float | None
    frame: float

    @property
    def error(self):
        return None if self.observed is None else self.observed - self.authored

    @property
    def ok(self):
        return self.error is not None and -1e-6 <= self.error <= self.frame + 1e-6


def measure_action_timing(repo, frame_times, *, ability_id="fire_arc", target="astral_tyrant:1"):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    root = Path(repo) / "reference_projects" / "complex_reference_rpg"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), root)
    runtime.open()
    try:
        runtime._battle_presentation = adapter = CanonicalBattleAdapter(runtime)
        game = runtime.game
        game.start_encounter("boss_room")
        adapter.begin()
        runtime._advance_to_hero_turn()
        runtime._present_battle(0.0)
        while adapter.busy():
            runtime._present_battle(1 / 60)
        hero = runtime._battle_actor()
        skills = [s for s, _ in runtime._skills_for_actor(hero)]
        sequence = adapter.resolver.motion_sequence(ability_id)
        adapter.audio_cues.clear()  # cues from the opening enemy turns are not part of this action
        start = adapter._clock
        runtime._use_skill(skills.index(ability_id))
        runtime._present_battle(0.0)  # consumes the action at the current presentation time
        screen = adapter.screen
        authored = {
            "attack_pose": next(
                b.at
                for b in sequence.beats
                if b.channel == "animation" and b.cue in ("attack", "attack2", "attack3")
            ),
            "effect": next(b.at for b in sequence.beats if b.channel == "vfx"),
            "hit_pose": next(
                b.at for b in sequence.beats if b.channel == "animation" and b.cue == "hit"
            ),
            "damage_number": next(
                b.at for b in sequence.beats if b.channel == "animation" and b.cue == "hit"
            ),
            "hit_sound": next(b.at for b in sequence.beats if b.channel == "audio"),
        }
        observed = {}

        def role(member):
            animator = screen.animation.combatant(member)
            return str(getattr(animator.role, "value", animator.role))

        def look():
            now = adapter._clock - start
            seen = {
                "attack_pose": role(hero) in ("attack", "attack2", "attack3"),
                "effect": any(v.payload.get("asset_id") for v in screen.feedback.vfx),
                "hit_pose": role(target) == "hit",
                "damage_number": any(v.target_id == target for v in screen.feedback.values),
                "hit_sound": any(
                    dict(c.payload).get("asset_id") == "hit" for c in adapter.audio_cues
                ),
            }
            for key, value in seen.items():
                if value and key not in observed:
                    observed[key] = now

        look()
        largest = max(frame_times)
        for dt in frame_times:
            adapter.audio_cues.clear()
            runtime._present_battle(dt)
            look()
        return [TimingSample(k, authored[k], observed.get(k), largest) for k in authored]
    finally:
        runtime.close()
