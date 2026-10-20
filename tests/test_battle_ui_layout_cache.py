"""The battle UI composer keeps the last HUD and command menu layout while what they read is
unchanged: every composed frame equals what a composer with nothing kept would build."""

from dataclasses import replace
from pathlib import Path

from asteria.editor import EditorDocument
from asteria.presentation import (
    BattleActionEntry,
    BattleCombatantVisual,
    BattleHudGauge,
    BattleHudMember,
    BattlePresentationFrame,
    BattlePresentationScene,
    BattleUiComposer,
    BattleUiLayoutProfile,
    BattleVisualAnchor,
)
from asteria.presentation.battle_action_menu import BattleActionMenuView
from asteria.project import Project
from asteria.runtime import Camera2D

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def _cold(composer):
    """A composer like ``composer`` with nothing kept from earlier frames."""
    return BattleUiComposer(
        composer.scene, composer.layout, composer.party_layout, composer.polish
    )


def _counting(monkeypatch):
    calls = {"hud": 0, "menu": 0}
    hud, menu = BattleUiComposer._hud_layout, BattleUiComposer._action_menu_layout

    def hud_layout(self, *args):
        calls["hud"] += 1
        return hud(self, *args)

    def menu_layout(self, *args):
        calls["menu"] += 1
        return menu(self, *args)

    monkeypatch.setattr(BattleUiComposer, "_hud_layout", hud_layout)
    monkeypatch.setattr(BattleUiComposer, "_action_menu_layout", menu_layout)
    return calls


def test_a_recorded_battle_composes_the_same_frames_as_an_uncached_composer(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    import pygame

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    calls = _counting(monkeypatch)
    compose = BattleUiComposer.compose
    seen = {"frames": 0, "distinct": set()}

    def checked(self, camera, battle_frame, **kw):
        frame = compose(self, camera, battle_frame, **kw)
        cold = _cold(self)
        assert frame == compose(cold, camera, battle_frame, **kw)
        assert self.overhead_labels == cold.overhead_labels
        seen["frames"] += 1
        seen["distinct"].add((frame.panels, frame.texts, frame.gauges, frame.icons))
        return frame

    monkeypatch.setattr(BattleUiComposer, "compose", checked)
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    try:
        runtime._ui_mode = "field"
        runtime.game.start_encounter("woods_boss")  # a big boss and two slingers: three labels
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        keys = (pygame.K_RETURN, pygame.K_RETURN, pygame.K_DOWN, pygame.K_RETURN)
        for index in range(360):
            events = []
            if index % 25 == 0:  # pick commands and targets: the battle plays on
                key = keys[(index // 25) % len(keys)]
                events.append(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))
            runtime._frame(events, 1 / 60)
    finally:
        runtime.close()
    assert seen["frames"] >= 360
    assert len(seen["distinct"]) > 20  # the HUD really changed along the way
    # ... and was laid out again only for some frames (the cold composers count too)
    assert calls["hud"] < 1.7 * seen["frames"]
    assert calls["menu"] < 1.7 * seen["frames"]


def _scene(boss_x=240.0):
    return BattlePresentationScene(
        "battle.cache",
        "bg.arena",
        (
            BattleCombatantVisual(
                "hero", "hero.sheet", "hero.clips", BattleVisualAnchor(260, 120)
            ),
            BattleCombatantVisual(
                "ally", "ally.sheet", "ally.clips", BattleVisualAnchor(280, 150)
            ),
            BattleCombatantVisual(
                "boss", "boss.sheet", "boss.clips", BattleVisualAnchor(boss_x, 110)
            ),
            BattleCombatantVisual("imp", "imp.sheet", "imp.clips", BattleVisualAnchor(90, 140)),
        ),
    )


def _members(hp=75.0):
    def gauge(current):
        return BattleHudGauge("hp", "HP", current, 0, 100, 0, current / 100, False, None, 0)

    return tuple(
        BattleHudMember(member_id, (gauge(hp if member_id == "hero" else 50.0),), ())
        for member_id in ("hero", "ally", "boss", "imp")
    )


def _menu(cursor=0, revision=1):
    entries = tuple(
        BattleActionEntry(f"root:{name}", name.title(), cost_text="3")
        for name in ("attack", "skills", "items", "guard")
    )
    return BattleActionMenuView((), "", "", entries, 0, 1, len(entries), cursor, revision)


def _compose(composer, camera=None, scene=None, **kw):
    scene = scene or composer.scene
    composer.scene = scene
    frame = BattlePresentationFrame(scene.scene_id, "bg.arena", ())
    args = dict(
        hud_members=_members(),
        placement_by_member={"hero": "right", "ally": "right", "boss": "left", "imp": "left"},
        focus_member_id="hero",
        member_heights={"boss": 64.0},
        action_menu=_menu(),
    )
    args.update(kw)
    camera = camera or Camera2D(width=320, height=180)
    out = BattleUiComposer.compose(composer, camera, frame, **args)
    cold = _cold(composer)
    assert out == BattleUiComposer.compose(cold, camera, frame, **args)
    assert composer.overhead_labels == cold.overhead_labels
    return out


def test_each_input_of_the_kept_layout_lays_it_out_again(monkeypatch):
    layout = BattleUiLayoutProfile(party_hud="side_list", overhead_zones=("left",))
    composer = BattleUiComposer(_scene(), layout)
    first = _compose(composer)
    calls = _counting(monkeypatch)

    assert _compose(composer) == first  # nothing changed: nothing laid out again
    assert _compose(composer, action_menu=_menu(revision=9)) == first  # the same entries again
    assert calls == {"hud": 2, "menu": 2}  # only the cold composers

    inputs = {}

    def changed(**kw):  # one input more changed since the last frame
        inputs.update(kw)
        before = dict(calls)
        frame = _compose(composer, **inputs)
        return frame, {k: calls[k] - before[k] - 1 for k in calls}

    frame, again = changed(hud_members=_members(hp=20.0))  # a gauge moved
    assert again == {"hud": 1, "menu": 0} and frame.gauges != first.gauges
    frame, again = changed(action_menu=_menu(cursor=2))
    assert again == {"hud": 0, "menu": 1} and frame.texts != first.texts
    frame, again = changed(camera=Camera2D(x=12.0, width=320, height=180))  # the stage moved
    assert again == {"hud": 1, "menu": 1}
    frame, again = changed(scene=_scene(boss_x=200.0))  # a figure stepped forward
    assert again == {"hud": 1, "menu": 1}
    frame, again = changed(display_names={"boss": "The Crimson Warlord"})
    assert again == {"hud": 1, "menu": 0} and frame.texts != first.texts
    frame, again = changed(member_heights={"boss": 90.0})
    assert again == {"hud": 1, "menu": 1}
    frame, again = changed(focus_member_id="ally")
    assert again == {"hud": 1, "menu": 1}

    placement = {"hero": "right", "ally": "right", "boss": "left", "imp": "left"}
    frame, again = changed(placement_by_member=placement)
    assert again == {"hud": 0, "menu": 0}  # an equal dict
    placement["imp"] = "right"  # changed in place: the kept layout holds its own copy
    frame, again = changed(placement_by_member=placement)
    assert again["hud"] == 1
    composer.layout = replace(layout, overhead_bars=False)
    frame, again = changed()
    assert again == {"hud": 1, "menu": 1}
    assert not any(g.member_id == "boss" for g in frame.gauges)
