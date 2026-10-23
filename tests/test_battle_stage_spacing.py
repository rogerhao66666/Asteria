"""Side-view staging options (D54): the distance between columns, the party against its edge,
and feet that stay on the ground even where a staging template puts them on the wall."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from asteria.presentation import BattleSideviewTemplateProfile, BattleSideviewZone
from asteria.presentation.battle_ui import BattleUiLayoutProfile
from asteria.presentation.library import BattlePresentationLibrary
from asteria.runtime.battle_visuals import BattleVisualResolver

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
CLIPS = {role: {"frames": [0]} for role in ("idle", "attack", "hit", "ko", "weak")}
HEROES = ("h1", "h2", "h3", "h4")
PLACEMENT = {"heroes": "right", "foes": "left"}
# a frame of 60 x 48 (most of it the room an attack swings through); the stage of a 480 x 270
# side-list layout runs from x 8 to 356 and its ground from y 126.9 (47%) down to 256
FRAME = (60, 48)


def _layout(**options):
    return BattleUiLayoutProfile(
        virtual_width=480,
        virtual_height=270,
        party_hud="side_list",
        hud_panel_width=108.0,
        stage_top=0.47,
        stage_front=0.16,
        column_size=2,
        front_large_zones=("right",),
        **options,
    )


def _resolver(sizes):
    """Generated sheets, one per member of ``sizes`` (member -> frame width, height)."""
    project = SimpleNamespace(battle_presentation_library=BattlePresentationLibrary())
    resolver = BattleVisualResolver(project, lambda uri: (0, 0))
    for member, size in sizes.items():
        resolver.register_generated(f"sheet.{member}", None, size, frame_size=size, clips=CLIPS)
        resolver.register_generated_profile(member, f"sheet.{member}", 1.0)
    return resolver


def _stage(
    layout, foes=("f1", "f2", "f3"), sizes=None, template=None, resolver=None, heroes=HEROES
):
    sizes = {m: FRAME for m in (*heroes, *foes)} | dict(sizes or {})
    resolver = resolver or _resolver(sizes)
    sides = {"heroes": [m for m in sizes if m not in foes], "foes": list(foes)}
    visuals = resolver.combatant_visuals(sides, PLACEMENT, layout, template)
    return {v.member_id: v.anchor for v in visuals}


def _x(anchors):
    return {member: anchor.x for member, anchor in anchors.items()}


# --- column spacing --------------------------------------------------------------------------


def test_without_the_options_columns_stand_as_before():
    x = _x(_stage(_layout()))
    # two hero columns, each clear of the other's whole frame: 30 + 30 + 4 apart; the back one
    # would leave the stage, so both are pushed toward the foes (the front at 262, not 300)
    assert x["h1"] == x["h2"] and x["h3"] == x["h4"]
    assert x["h3"] - x["h1"] == pytest.approx(64.0)
    assert x["h3"] == pytest.approx(356.0 - 30.0)
    assert x["f1"] - x["f3"] == pytest.approx(64.0)


def test_column_spacing_sets_the_distance_on_both_sides_and_the_right_one_overrides_it():
    x = _x(_stage(_layout(column_spacing=20.0)))
    assert x["h3"] - x["h1"] == pytest.approx(20.0)
    assert x["f1"] - x["f3"] == pytest.approx(20.0)
    x = _x(_stage(_layout(column_spacing_right=30.0)))
    assert x["h3"] - x["h1"] == pytest.approx(30.0)
    assert x["f1"] - x["f3"] == pytest.approx(64.0)  # the foes keep the automatic distance
    x = _x(_stage(_layout(column_spacing=20.0, column_spacing_right=30.0)))
    assert (x["h3"] - x["h1"], x["f1"] - x["f3"]) == (pytest.approx(30.0), pytest.approx(20.0))


def test_the_party_stands_against_its_edge():
    layout = _layout(stage_front_right=0.0, column_spacing_right=30.0)
    x = _x(_stage(layout))
    # the back column's frame ends at the stage's edge, the front one 30 nearer the foes
    assert x["h3"] == pytest.approx(326.0)
    assert x["h1"] == pytest.approx(296.0)
    # one hero alone stands at that edge too
    alone = _x(_stage(layout, foes=("f1",), heroes=("h1",)))
    assert alone["h1"] == pytest.approx(326.0)


def test_a_boss_column_keeps_its_automatic_distance():
    sizes = {"boss": (160, 120)}
    x = _x(_stage(_layout(column_spacing=30.0), foes=("f1", "f2", "boss"), sizes=sizes))
    assert x["f1"] == x["f2"]
    assert x["f1"] - x["boss"] == pytest.approx(30.0 + 80.0 + 4.0)  # clear of its whole frame
    assert x["h3"] - x["h1"] == pytest.approx(30.0)


def test_a_pet_in_front_of_the_party_stands_one_spacing_ahead():
    sizes = {m: FRAME for m in (*HEROES, "pet", "f1")}
    resolver = _resolver(sizes)
    pet = resolver._generated_profiles["pet"]
    resolver._generated_profiles["pet"] = replace(pet, hud_visible=False)  # no HUD: apart
    layout = _layout(stage_front_right=0.0, column_spacing_right=30.0)
    x = _x(_stage(layout, foes=("f1",), sizes=sizes, resolver=resolver))
    assert x["h1"] - x["pet"] == pytest.approx(30.0)
    assert x["h3"] - x["h1"] == pytest.approx(30.0)
    assert x["h3"] == pytest.approx(326.0)


# --- feet on the ground ----------------------------------------------------------------------


def _template():
    return BattleSideviewTemplateProfile(
        "t",
        BattleSideviewZone("foes", 100.0, 300.0, 0.0, "right", 0.2, 0.01, -30.0),
        BattleSideviewZone("party", 300.0, 100.0, 30.0, "left", 0.2, 0.01, 10.0),
    )


def test_a_template_never_puts_feet_on_the_wall_or_under_the_stage():
    anchors = _stage(_layout(), template=_template())
    ground = 270 * 0.47
    assert anchors["h1"].y == pytest.approx(ground)  # the template says 100: the wall
    assert [anchors[m].y for m in ("h2", "h3", "h4")] == [130.0, 160.0, 190.0]
    assert anchors["h1"].depth == pytest.approx(ground + 0.2)
    assert {anchors[m].y for m in ("f1", "f2", "f3")} == {256.0}  # not under the stage's bottom
    # the template's x and facing stay as written
    assert [anchors[m].x for m in HEROES] == [300.0, 310.0, 320.0, 330.0]
    assert anchors["h1"].facing == "left" and anchors["f1"].facing == "right"


def test_turned_off_the_template_is_used_as_written():
    anchors = _stage(_layout(feet_on_ground=False), template=_template())
    assert [anchors[m].y for m in HEROES] == [100.0, 130.0, 160.0, 190.0]
    assert {anchors[m].y for m in ("f1", "f2", "f3")} == {300.0}


def test_a_sprite_offset_still_lifts_a_flyer_off_the_ground():
    sizes = {m: FRAME for m in (*HEROES, "f1", "f2", "f3")}
    resolver = _resolver(sizes)
    flyer = resolver._generated_profiles["h1"]
    lifted = replace(flyer.transform, offset_y=-40.0)
    resolver._generated_profiles["h1"] = replace(flyer, transform=lifted)
    anchors = _stage(_layout(), template=_template(), resolver=resolver)
    assert anchors["h1"].y == pytest.approx(270 * 0.47 - 40.0)


# --- data and editor -------------------------------------------------------------------------


def test_the_layout_writes_the_options_only_when_set():
    library = BattlePresentationLibrary()
    plain = BattleUiLayoutProfile()
    assert (plain.column_spacing, plain.column_spacing_right, plain.feet_on_ground) == (
        0.0,
        None,
        True,
    )
    data = library._encode("ui_layout", plain)
    assert not {"column_spacing", "column_spacing_right", "feet_on_ground"} & set(data)
    assert BattleUiLayoutProfile(**data) == plain  # data from before D54 reads the same
    chosen = BattleUiLayoutProfile(
        column_spacing=24.0, column_spacing_right=30.0, feet_on_ground=False
    )
    library.add("ui_layout", "set", chosen)
    raw = library.to_data()["categories"]["ui_layout"]["set"]
    assert (raw["column_spacing"], raw["column_spacing_right"], raw["feet_on_ground"]) == (
        24.0,
        30.0,
        False,
    )
    back = BattlePresentationLibrary.from_data(library.to_data()).require("ui_layout", "set")
    assert back == chosen
    for bad in ({"column_spacing": -1}, {"column_spacing_right": -1}):
        with pytest.raises(ValueError):
            BattleUiLayoutProfile(**bad)


def test_the_editor_shows_every_option_and_the_right_spacing_follows_until_changed():
    from asteria.editor.record_vocabulary import HELP, words

    library = BattlePresentationLibrary()
    shown = library.encode_for_editor("ui_layout", BattleUiLayoutProfile(column_spacing=24.0))
    assert (shown["column_spacing"], shown["column_spacing_right"]) == (24.0, 24.0)
    assert shown["feet_on_ground"] is True
    same = library.decode_from_editor("ui_layout", shown)
    assert same.column_spacing_right is None  # the same value: it follows Column Spacing
    shown["column_spacing_right"] = 30.0
    assert library.decode_from_editor("ui_layout", shown).column_spacing_right == 30.0
    table = json.loads(
        (REPO / "src/asteria/editor/translations/zh_TW.json").read_text(encoding="utf-8")
    )["exact"]
    keys = ("column_spacing", "column_spacing_right", "feet_on_ground", "stage_front_right")
    for text in (*(words(k) for k in keys), *(HELP[k] for k in keys)):
        assert table.get(text), text


def test_the_full_verification_party_stands_close_together_at_its_edge_on_the_floor():
    data = json.loads((DEMO / "project.asteria.json").read_text(encoding="utf-8"))
    categories = data["battle_presentation_library"]["categories"]
    layout = BattleUiLayoutProfile(**categories["ui_layout"]["adaptive"])
    assert (layout.column_spacing_right, layout.stage_front_right) == (30.0, 0.0)
    assert layout.feet_on_ground
    party = categories["sideview_templates"]["crypt_ranks"]["right_zone"]
    ground = layout.virtual_height * layout.stage_top
    bottom = layout.virtual_height - layout.margin - 6.0
    feet = [party["y_start"] + i * party["y_step"] for i in range(5)]  # four heroes and a pet
    assert all(ground <= y <= bottom for y in feet), feet
