"""How the Lucifer art is used: the party fights facing left with the pack's Left strips (not
mirrored Right ones), the three attack strips go to the right kind of skill, effects turn to the
attacker, status names sit on the head."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "boss_trial_demo"


def _project():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    return Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)


def test_the_party_uses_left_strips_and_the_foes_right_ones():
    project = _project()
    meta = lambda name: dict(project.assets.resolve(f"battle.combatant.{name}").metadata)  # noqa: E731
    for hero in ("hero_01", "hero_02", "hero_03", "hero_04"):
        assert meta(hero).get("facing") == "left", hero
    for foe in ("crimson_warlord", "skeleton_grunt", "goblin_beast"):
        assert "facing" not in meta(foe), foe


def test_art_that_already_faces_left_is_not_turned_round():
    from asteria.presentation.battle import BattleCombatantVisual, BattleVisualAnchor
    from asteria.presentation.battle_runtime import _mirrored

    def visual(facing, art="right"):
        return BattleCombatantVisual(
            "m", "s", "c", BattleVisualAnchor(0, 0, facing), art_facing=art
        )

    assert _mirrored(visual("left")) and not _mirrored(visual("right"))  # right-looking art
    assert not _mirrored(visual("left", "left")) and _mirrored(visual("right", "left"))
    data = visual("left", "left").to_data()
    assert BattleCombatantVisual.from_data(data).art_facing == "left"
    assert "art_facing" not in visual("left").to_data()  # the default is not written


def test_a_skill_plays_the_strip_that_fits_it():
    import sys

    sys.path.insert(0, str(ROOT))
    from trial_content import _attack_clip

    class Skill:
        def __init__(self, tags=(), hits=()):
            self.tags, self.hits = tuple(tags), tuple(hits)

    assert _attack_clip("attack_sword", Skill()) == "attack"  # a plain blow
    assert _attack_clip("w_cinder", Skill(("magic",))) == "attack2"  # a spell is cast
    assert _attack_clip("w_ward", Skill()) in ("attack", "attack2")
    assert _attack_clip("w_eclipse", Skill(("divine",))) == "attack3"  # a finisher
    assert _attack_clip("w_flurry", Skill(hits=(1, 2, 3))) == "attack3"
    assert _attack_clip("w_slam", Skill()) == "attack3"  # a heavy blow


def test_slashes_turn_to_the_attacker_and_other_effects_do_not():
    project = _project()
    for key, expected in (("slash", True), ("claw", True), ("explosion", False), ("ice", False)):
        meta = dict(project.assets.resolve(f"battle.fx.{key}").metadata)
        assert meta.get("face_attacker", False) is expected, key


def test_a_swing_goes_back_to_standing_and_a_jump_lands():
    project = _project()
    clips = dict(project.assets.resolve("battle.combatant.crimson_warlord").metadata)["clips"]
    stand = clips["idle"]["frames"][0]
    for role in ("attack", "attack2", "attack3", "cast", "hit", "transform"):
        assert clips[role]["frames"][-1] == stand, role  # not left in the air or mid-blow


@pytest.mark.parametrize("encounter", ["boss_room"])
def test_status_names_stand_on_the_head_and_effects_on_the_body(monkeypatch, encounter):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = _project()
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    runtime._ui_mode = "field"
    runtime.game.start_encounter(encounter)
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    for _ in range(300):
        runtime._frame([], 1 / 60)
    adapter = runtime._battle_presentation
    boss = next(v.member_id for v in adapter.screen.scene.combatants if "crimson" in v.member_id)
    _x, top, feet = adapter.member_screen_box(boss)
    assert top < feet and feet - top == pytest.approx(
        adapter._body_height(adapter.screen.scene.visual_for(boss)) * adapter.textures.scale
    )  # the box is the figure, not the whole frame
    caption = next(b.caption for b in runtime.battle_extras_blocks if b.member_id == boss)
    assert caption is not None and 0 < top - caption[2] < 30  # right over the head
    runtime.close()


def test_looking_right_uses_the_left_strips_turned_round():
    import sys

    sys.path.insert(0, str(ROOT))
    import trial_lucifer as lucifer
    from PIL import ImageChops, ImageOps

    left = lucifer._facing_strip("warrior", "Left", "Attack01")
    right = lucifer._facing_strip("warrior", "Right", "Attack01")
    assert len(left) == len(right) > 0
    for a, b in zip(left, right, strict=True):  # every blow comes down, whichever way it faces
        assert ImageChops.difference(ImageOps.mirror(a), b).getbbox() is None
