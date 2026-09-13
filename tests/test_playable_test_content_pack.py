from pathlib import Path
import json

from PIL import Image

from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime


REF=Path(__file__).parents[1]/"reference_projects/complex_reference_rpg"


def load():
    d=EditorDocument()
    p=Project.load_json(REF/"project.asteria.json",d.component_registry)
    s=GameRuntimeSave.load_json(REF/"saves/boss_stress.asteria-save.json",p)
    return p,s


def test_playable_manifest_has_all_visual_categories_and_existing_files():
    data=json.loads((REF/"playable_test_manifest.json").read_text())
    assert data["schema"]=="asteria.playable_test_content"
    assert data["version"]==1

    paths=[
        data["field"]["background"],
        data["field"]["player_sheet"],
        data["field"]["boss_sprite"],
        data["battle"]["background"],
        *data["battle"]["heroes"],
        *data["battle"]["enemy_sprites"].values(),
        *(x["fx"] for x in data["battle"]["skills"].values()),
    ]
    assert len(paths)>=15
    for rel in paths:
        path=REF/rel
        assert path.exists(),rel
        with Image.open(path) as image:
            assert image.width>0 and image.height>0


def test_field_sprite_sheet_has_four_directions_and_three_frames():
    data=json.loads((REF/"playable_test_manifest.json").read_text())
    fw,fh=data["field"]["player_frame_size"]
    with Image.open(REF/data["field"]["player_sheet"]) as image:
        assert image.size==(fw*3,fh*4)


def test_skill_vfx_assets_are_16_frame_four_by_four_sheets():
    data=json.loads((REF/"playable_test_manifest.json").read_text())
    for ability_id,meta in data["battle"]["skills"].items():
        assert meta["frames"]==16
        with Image.open(REF/meta["fx"]) as image:
            assert image.width%4==0
            assert image.height%4==0
            assert image.width//4==image.height//4


def test_boss_stress_save_is_human_playable_not_one_hit_party_death():
    p,s=load()
    g=GameSessionRuntime(p,s)
    g.field_step({"interact":1})
    hero=g.active_hero_ids()[0]
    boss="astral_tyrant:1"
    hp_before=g.battle.member(hero).subject.resources.current("vitality")
    assert hp_before>=1500
    result=g.enemy_turn(boss,"astral_tyrant_ai")
    assert result is not None
    hp_after=g.battle.member(hero).subject.resources.current("vitality")
    assert hp_after>0
    assert hp_after<hp_before


def test_visible_action_menu_skills_are_in_first_saved_actor_build():
    p,s=load()
    g=GameSessionRuntime(p,s)
    actor=s.rpg_state.party_active_actor_ids[0]
    build=g.resolve_actor_build(actor)
    for ability_id in ("strike","fire_arc","heal","meteor"):
        assert ability_id in build.abilities


def test_reference_battle_can_be_won_in_reasonable_manual_action_count():
    p,s=load()
    g=GameSessionRuntime(p,s)
    g.field_step({"interact":1})
    actions=0
    for enemy_id in tuple(g.active_enemy_ids()):
        while enemy_id in g.active_enemy_ids():
            for hero_id in tuple(g.active_hero_ids()):
                if enemy_id not in g.active_enemy_ids():
                    break
                g.execute(hero_id,"strike",(enemy_id,))
                actions+=1
                assert actions<80
    assert actions<40
    assert not g.active_enemy_ids()


def test_runtime_preview_has_playable_manifest_route():
    text=(Path(__file__).parents[1]/"src/asteria/runtime/preview.py").read_text()
    assert 'playable_test_manifest.json' in text
    assert 'run_playable_test_runtime' in text
