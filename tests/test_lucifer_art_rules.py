"""How the Lucifer art is used: the party fights facing left with the pack's Left strips (not
mirrored Right ones), the three attack strips go to the right kind of skill, effects turn to the
attacker, status names sit on the head."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def _project():
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    return Project.load_json(ROOT / "project.asteria.json", default_component_registry())


def test_the_party_uses_left_strips_and_the_foes_right_ones():
    project = _project()
    meta = lambda name: dict(project.assets.resolve(f"battle.combatant.{name}").metadata)  # noqa: E731
    for hero in ("hero_01", "hero_02", "hero_03", "hero_04"):
        assert meta(hero).get("facing") == "left", hero
    for foe in ("crimson_warlord", "skeleton_hunter", "goblin_beast"):
        assert "facing" not in meta(foe), foe


def test_art_that_already_faces_left_is_not_turned_round():
    from asteria.presentation.battle.runtime import _mirrored
    from asteria.presentation.battle.scene import BattleCombatantVisual, BattleVisualAnchor

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
    # over the head: above the foe's name and bar, which sit right on it
    assert caption is not None and 0 < top - caption[2] < 60
    runtime.close()


def test_every_facing_uses_the_packs_own_strips():
    import sys

    sys.path.insert(0, str(ROOT))
    import trial_lucifer as lucifer
    from PIL import ImageChops

    for facing in ("Left", "Right", "Up", "Down"):
        path = lucifer._find("warrior", "Attack01", facing)
        own = lucifer._strip_frames(path)
        used = lucifer._facing_strip("warrior", facing, "Attack01")
        assert len(own) == len(used) > 0
        for a, b in zip(own, used, strict=True):  # nothing patched, nothing reordered
            assert ImageChops.difference(a, b).getbbox() is None


def test_stable_ids_make_a_build_repeatable():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import stable_ids

    from asteria.core import Entity, ids

    original = ids.uuid4
    try:
        stable_ids.install("test-build")
        first = [Entity("A").id, Entity("B").id]
        stable_ids.install("test-build")
        again = [Entity("A").id, Entity("B").id]
    finally:
        ids.uuid4 = original
    assert first == again and first[0] != first[1]


@pytest.mark.parametrize(
    "folder",
    [
        "reference_projects/full_verification_demo",
        "reference_projects/party_rpg_demo",
        "reference_projects/complex_reference_rpg",
        "src/asteria/templates/party_rpg",
    ],
)
def test_every_turn_based_demo_uses_the_break_battle_ui(folder):
    import json

    path = Path(__file__).resolve().parents[1] / folder / "project.asteria.json"
    data = json.loads(path.read_text())["battle_presentation_library"]["categories"]
    layout = data["ui_layout"]["adaptive"]
    assert layout["party_hud"] == "side_list"  # a panel per hero down the right edge
    assert layout["action_menu_placement"] == "actor_bottom_right"  # touching who acts
    assert layout["overhead_bars"] is False  # foe health stays hidden (the bestiary tells it)
    assert layout["overhead_zones"] == ["left"] and not layout["hidden_zones"]
    assert all(
        v["hud_visible"]
        for k, v in data["combatant_visuals"].items()
        if k not in ("pet", "spirit_knight")
    )  # summons have no panel


ACTION_ROOTS = (
    Path(__file__).resolve().parents[1] / "src" / "asteria" / "templates" / "action_rpg",
    ROOT.parent / "arpg_demo",
    ROOT.parent / "arpg_multiplayer_demo",
)


def _art_source(root):
    """The lucifer_art.py that built ``root`` (the offline demo's code builds both demos)."""
    own = root / "lucifer_art.py"
    return (own if own.is_file() else ROOT.parent / "arpg_demo" / "lucifer_art.py").read_text(
        "utf-8"
    )


@pytest.mark.parametrize("root", ACTION_ROOTS, ids=lambda r: r.name)
@pytest.mark.parametrize("name", ("hero", "smith", "trainer_warrior"))
def test_the_warrior_cuts_from_above_whichever_way_it_faces(root, name):
    import json

    clips = json.loads((root / "playable_assets" / f"{name}_clips.json").read_text("utf-8"))
    clips = clips["clips"]
    cells = {
        facing: [key["frame_index"] for key in clips[f"attack_{facing}"]["keyframes"]]
        for facing in ("left", "down", "right", "up")
    }
    for facing in ("left", "down"):  # these strips come down as drawn
        assert cells[facing] == sorted(cells[facing])
    for facing in ("right", "up"):  # these swing up as drawn: played from the raised sword
        first = min(cells[facing])
        assert cells[facing] == [first + i for i in (4, 3, 2, 1, 0, 5)]
    # the slash (a strip's frame 2) is on the same beat in all four
    for facing, played in cells.items():
        assert played[2] == min(played) + 2, facing


def _swing_order(root):
    import ast
    import sys

    sys.path.insert(0, str(ROOT))
    import trial_lucifer

    source = _art_source(root)
    keep = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == "swing_order":
            keep.append(node)
        elif isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in (
            "FOLDERS",
            "ACTIONS",
            "SHORT_WINDUP",
        ):
            keep.append(node)
    space = {"lucifer": trial_lucifer}
    exec(compile(ast.Module(keep, []), str(root), "exec"), space)  # noqa: S102
    return space["swing_order"]


@pytest.mark.parametrize("root", ACTION_ROOTS, ids=lambda r: r.name)
def test_only_the_swings_drawn_from_below_are_played_the_other_way(root):
    order = _swing_order(root)
    strip = [10, 11, 12, 13, 14, 15]
    assert order("warrior", "attack", "right", strip) == [14, 13, 12, 11, 10, 15]
    assert order("warrior", "attack", "up", strip) == [14, 13, 12, 11, 10, 15]
    assert order("warrior", "attack", "left", strip) == strip
    assert order("warrior", "attack", "down", strip) == strip
    # its slam and spin already come down: only the slow start goes
    assert order("warrior", "attack2", "right", strip) == strip[1:]
    assert order("warrior", "attack3", "right", strip) == strip[1:]
    assert order("sorceress", "attack", "right", strip) == strip
    grunt = list(range(8))
    # the only swing it has: every attack plays it, the raised sword just before the slash
    for role in ("attack", "attack2", "attack3"):
        assert order("skeleton_grunt", role, "right", grunt) == [0, 1, 2, 3, 4, 7, 6, 5]
        assert order("skeleton_grunt", role, "left", grunt) == grunt
    assert order("goblin_berserker", "attack", "right", grunt) == grunt  # comes down as drawn


@pytest.mark.parametrize("root", ACTION_ROOTS, ids=lambda r: r.name)
@pytest.mark.parametrize(
    ("name", "facing", "role", "steps"),
    (
        ("skull", "right", "attack", (0, 1, 2, 3, 4, 7, 6, 5)),
        ("skull", "up", "attack3", (0, 1, 2, 3, 4, 7, 6, 5)),
        ("cyclops", "right", "attack", (5, 6, 7, 8, 9, 0, 1, 2)),
        ("cyclops", "left", "attack", (0, 1, 2, 3, 4, 5, 6, 7)),
        ("cyclops", "up", "attack", (9, 9, 9, 8, 7, 6, 5, 4, 3, 2)),
    ),
)
def test_the_monsters_cut_from_above_too(root, name, facing, role, steps):
    import json

    clips = json.loads((root / "playable_assets" / f"{name}_clips.json").read_text("utf-8"))
    cells = [k["frame_index"] for k in clips["clips"][f"{role}_{facing}"]["keyframes"]]
    assert cells == [cells[0] - steps[0] + step for step in steps]


@pytest.mark.parametrize("root", ACTION_ROOTS, ids=lambda r: r.name)
@pytest.mark.parametrize(
    ("timeline_id", "look", "strike"), (("skull_slash", "skull", 6), ("slime_bite", "slime", 7))
)
def test_a_monsters_blow_lands_with_its_slash(root, timeline_id, look, strike):
    import json

    project = json.loads((root / "project.asteria.json").read_text("utf-8"))
    timelines = project["gameplay_library"]["timelines"]
    if isinstance(timelines, dict):
        timelines = timelines.values()
    cues = next(t["cues"] for t in timelines if t["timeline_id"] == timeline_id)
    at = next(c["time"] for c in cues if c["kind"] == "hitbox")
    clips = json.loads((root / "playable_assets" / f"{look}_clips.json").read_text("utf-8"))
    frames = clips["clips"]["attack_right"]["keyframes"]
    start = sum(k["duration"] for k in frames[:strike])
    assert start <= at <= start + frames[strike]["duration"]


BATTLE_ROOTS = (
    ROOT,
    ROOT.parent / "party_rpg_demo",
    ROOT.parent / "complex_reference_rpg",
    Path(__file__).resolve().parents[1] / "src" / "asteria" / "templates" / "party_rpg",
)


def _battlers(root):
    import json

    data = json.loads((root / "project.asteria.json").read_text("utf-8"))
    for asset in data["assets"]["canonical_assets"]:
        if asset["asset_id"].startswith("battle.combatant."):
            yield (
                asset["asset_id"].rsplit(".")[-1],
                root / asset["source"]["uri"],
                dict(asset["metadata"])["clips"],
            )


@pytest.mark.parametrize("root", BATTLE_ROOTS, ids=lambda r: r.name)
def test_every_battle_marker_sits_on_the_slash_and_the_impact_falls_on_it(root):
    import sys

    from PIL import Image

    sys.path.insert(0, str(ROOT))
    import trial_lucifer as lucifer

    seconds = {"attack": (0.24,), "attack2": (0.24, 0.3), "attack3": (0.24,)}
    for name, path, clips in _battlers(root):
        image = Image.open(path).convert("RGBA")
        width = image.width // (max(max(c["frames"]) for c in clips.values()) + 1)
        for role, times in seconds.items():
            clip = clips[role]
            marker = int(next(iter(clip["events"])))
            white = [
                lucifer._white_pixels(image.crop((f * width, 0, (f + 1) * width, image.height)))
                for f in clip["frames"]
            ]
            if max(white) < 200:  # no large white blow to be on (a flame, a small flash)
                continue
            assert white[marker] >= max(white) * 0.55, (name, role)
            if marker:  # (a spin is moving from its first frame)
                start = marker * clip["frame_duration"]
                for at in times:
                    assert start <= at <= start + clip["frame_duration"] + 1e-9, (name, role, at)


@pytest.mark.parametrize("root", BATTLE_ROOTS, ids=lambda r: r.name)
def test_every_impact_is_on_a_beat_the_swings_are_timed_for(root):
    import json

    data = json.loads((root / "project.asteria.json").read_text("utf-8"))
    motions = data["battle_presentation_library"]["categories"]["motion_sequences"]
    rows = motions.values() if isinstance(motions, dict) else motions
    for sequence in rows:
        beats = sequence["beats"]
        hit = next((b for b in beats if b["channel"] == "animation" and b["cue"] == "hit"), None)
        if hit is not None:
            assert hit["at"] in (0.24, 0.3), hit
            # the flash, the shake and the sound stay with it
            for beat in beats:
                if beat["channel"] in ("camera", "audio", "screen_fx"):
                    assert beat["at"] == hit["at"], beat


def test_the_swings_drawn_from_below_cut_from_above_in_battle_too():
    import sys

    sys.path.insert(0, str(ROOT))
    import trial_lucifer as lucifer

    _sheet, _size, grunt, _body = lucifer.character_sheet("skeleton_grunt", facing="Right")
    start = grunt["idle"]["frames"][-1] + 1
    # the sword up (frame 7), the slash (6), the sword down (5), then back on its feet
    played = [start + i for i in (4, 7, 6, 5)]
    assert grunt["attack"]["frames"] == [*played, grunt["idle"]["frames"][0]]
    assert grunt["attack"]["events"] == {"2": ["hit"]}
    # a strip that comes down as drawn plays as drawn
    _sheet, _size, warrior, _body = lucifer.character_sheet("warrior", facing="Left")
    first = warrior["attack"]["frames"][0]
    assert warrior["attack"]["frames"][:6] == list(range(first, first + 6))
    assert warrior["attack"]["events"] == {"2": ["hit"]}


def _action_space(root):
    import ast
    import sys

    sys.path.insert(0, str(ROOT))
    import trial_lucifer

    keep = [
        node
        for node in ast.parse(_art_source(root)).body
        if isinstance(node, ast.Assign)
        and getattr(node.targets[0], "id", "") in ("ACTIONS", "SHORT_WINDUP")
    ]
    space = {}
    exec(compile(ast.Module(keep, []), str(root), "exec"), space)  # noqa: S102
    return trial_lucifer, space["ACTIONS"], space["SHORT_WINDUP"]


def _strike_seconds(root, key, role):
    """When a strip's blow shows, from the start of the clip that plays it."""
    lucifer, actions, windup = _action_space(root)
    names, seconds = actions[role]
    name = next(n for n in names if lucifer._facing_strip(key, "Left", n))
    frames = lucifer._facing_strip(key, "Left", name)
    strike = lucifer.COLOURED_STRIKE.get((key, name))
    strike = lucifer.strike_frame(frames) if strike is None else strike
    if strike is None:
        return None
    order = lucifer.CUT_FROM_ABOVE.get((key, "Left", name))
    at = strike if order is None else order.index(strike)
    at -= windup.get((key, name), 0)
    each = seconds / len(frames)
    return at * each, (at + 1) * each


def _timelines(root):
    import json

    timelines = json.loads((root / "project.asteria.json").read_text("utf-8"))["gameplay_library"][
        "timelines"
    ]
    return {
        t["timeline_id"]: t
        for t in (timelines.values() if isinstance(timelines, dict) else timelines)
    }


def _first_blow(timeline):
    return min(
        (c["time"] for c in timeline["cues"] if c["kind"] in ("hitbox", "projectile")),
        default=None,
    )


def _swing(timeline):
    return next(
        (
            (c["time"], dict(c["payload"])["clip"])
            for c in timeline["cues"]
            if c["kind"] == "animation"
        ),
        (0.0, "attack"),
    )


@pytest.mark.parametrize("root", ACTION_ROOTS, ids=lambda r: r.name)
def test_every_class_skills_blow_lands_on_what_its_strip_draws(root):
    looks = {"w": "warrior", "r": "cultist", "m": "sorceress"}
    checked = 0
    for timeline_id, timeline in _timelines(root).items():
        blow = _first_blow(timeline)
        if timeline_id[1:2] != "_" or timeline_id[0] not in looks or blow is None:
            continue
        swing_at, role = _swing(timeline)
        window = _strike_seconds(root, looks[timeline_id[0]], role)
        if window is None:  # the jump draws no blow
            continue
        assert swing_at + window[0] - 1e-3 <= blow <= swing_at + window[1] + 1e-3, timeline_id
        checked += 1
    assert checked > 25


@pytest.mark.parametrize("root", ACTION_ROOTS, ids=lambda r: r.name)
@pytest.mark.parametrize(
    ("timeline_id", "key"),
    (
        ("slime_bite", "goblin_berserker"),
        ("eye_shot", "necromancer"),
        ("skull_slash", "skeleton_grunt"),
        ("cyclops_smash", "skeleton_king"),
        ("cyclops_throw", "skeleton_king"),
        ("walker_bump", "goblin_slinger"),
        ("walker_bump", "goblin_rider"),
        ("drone_shot", "skeleton_ancient"),
        ("golem_slam", "goblin_beast"),
        ("golem_volley", "goblin_beast"),
    ),
)
def test_every_monsters_blow_lands_on_what_its_strip_draws(root, timeline_id, key):
    timeline = _timelines(root)[timeline_id]
    swing_at, role = _swing(timeline)
    start, end = _strike_seconds(root, key, role)
    assert swing_at + start - 1e-3 <= _first_blow(timeline) <= swing_at + end + 1e-3


def test_the_bat_strikes_at_the_same_moment_whichever_way_it_faces():
    import json
    import sys

    sys.path.insert(0, str(ROOT))
    import trial_lucifer as lucifer

    clips = json.loads(
        (ROOT.parent / "arpg_demo" / "playable_assets" / "bat_clips.json").read_text("utf-8")
    )["clips"]
    moments = set()
    for direction, facing in (
        ("right", "Right"),
        ("up", "Up"),
        ("left", "Left"),
        ("down", "Down"),
    ):
        frames = lucifer._facing_strip("goblin_rider", facing, "Attack01")
        keys = clips[f"attack_{direction}"]["keyframes"]
        cells = [k["frame_index"] for k in keys]
        strike = cells[-1] - len(frames) + 1 + lucifer.strike_frame(frames)
        moments.add(cells.index(strike))
    assert moments == {2}


def test_no_strip_left_swinging_upward_keeps_the_blow_it_draws():
    import sys

    sys.path.insert(0, str(ROOT))
    import trial_lucifer as lucifer

    # the king's blade comes down and stays down whichever side it faces
    assert lucifer.CUT_FROM_ABOVE[("skeleton_king", "Right", "Attack01")][-1] == 2
    assert lucifer.CUT_FROM_ABOVE[("skeleton_king", "Left", "Attack01")][-1] == 7
    # the ancient's flurry is cut down to its one blow from above
    for facing in ("Right", "Left"):
        assert lucifer.CUT_FROM_ABOVE[("skeleton_ancient", facing, "Attack02")] == (4, 5, 6, 7, 8)
    _sheet, _size, ancient, _body = lucifer.character_sheet("skeleton_ancient", facing="Right")
    assert ancient["attack2"]["events"] == {"2": ["hit"]}


def test_a_spell_with_a_coloured_blow_is_timed_by_it():
    import sys

    sys.path.insert(0, str(ROOT))
    import trial_lucifer as lucifer

    _sheet, _size, sorceress, _body = lucifer.character_sheet("sorceress", facing="Left")
    start = sorceress["attack3"]["frames"][0]
    # the flame pillar (frame 3 of the strip), not the small white flash at its end
    assert sorceress["attack3"]["events"] == {"2": ["hit"]}
    assert sorceress["attack3"]["frames"][2] - start == 2


def test_on_the_beat_thins_or_holds_what_comes_before_the_blow():
    import sys

    sys.path.insert(0, str(ROOT))
    import trial_lucifer as lucifer

    frames = list(range(10))
    assert lucifer.on_the_beat(frames, 7, 2) == [5, 6, 7, 8, 9]
    assert lucifer.on_the_beat(frames, 1, 3) == [0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert lucifer.on_the_beat(frames, 2, 2) == frames
    assert lucifer.on_the_beat(frames, 0, 3) == frames  # already moving from its first frame
    assert lucifer.on_the_beat(frames, None, 3) == frames  # draws no blow


def test_the_fox_knight_swings_at_the_foes():
    from PIL import Image

    name, path, clips = next(row for row in _battlers(ROOT) if row[0] == "spirit_knight")
    image = Image.open(path).convert("RGBA")
    count = max(max(c["frames"]) for c in clips.values()) + 1
    width = image.width // count
    # the frame after the slash: the blade out in front, and the party fights facing left
    cell = clips["attack"]["frames"][int(next(iter(clips["attack"]["events"]))) + 1]
    box = image.crop((cell * width, 0, (cell + 1) * width, image.height)).getbbox()
    assert width / 2 - box[0] > box[2] - width / 2, name


@pytest.mark.parametrize("root", ACTION_ROOTS, ids=lambda r: r.name)
def test_a_sword_blow_lands_with_the_slash(root):
    import json

    project = json.loads((root / "project.asteria.json").read_text("utf-8"))
    timelines = project["gameplay_library"]["timelines"]
    if isinstance(timelines, dict):
        timelines = timelines.values()
    by_id = {timeline["timeline_id"]: timeline for timeline in timelines}
    clips = json.loads((root / "playable_assets" / "hero_clips.json").read_text("utf-8"))
    frames = clips["clips"]["attack_right"]["keyframes"]
    slash_at = sum(key["duration"] for key in frames[:2])
    for timeline_id in ("w_slash1", "w_slash2", "w_slash3", "w_rend", "punch"):
        cues = by_id[timeline_id]["cues"]
        animation = next(c for c in cues if c["kind"] == "animation")
        assert animation["payload"]["clip"] == "attack", timeline_id
        hitbox = next(c for c in cues if c["kind"] == "hitbox")
        assert hitbox["time"] == pytest.approx(slash_at), timeline_id
