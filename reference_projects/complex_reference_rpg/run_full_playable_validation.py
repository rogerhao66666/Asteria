from __future__ import annotations
from pathlib import Path
import tempfile

from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime


def run():
    here=Path(__file__).resolve().parent
    document=EditorDocument()
    project=Project.load_json(here/"project.asteria.json",document.component_registry)
    save=GameRuntimeSave.load_json(here/"saves/boss_stress.asteria-save.json",project)
    game=GameSessionRuntime(project,save)

    actor=save.rpg_state.party_active_actor_ids[0]
    game.set_active_classes(actor,("arcanist","oracle"))
    game.learn_ability(actor,"meteor")
    game.equip_passive(actor,"passive_01",capacity=8)

    trigger=game.field_step({"interact":1})
    boss="astral_tyrant:1"
    game.enemy_turn(boss,"astral_tyrant_ai")

    actions=0
    for enemy_id in tuple(game.active_enemy_ids()):
        while enemy_id in game.active_enemy_ids():
            for hero_id in tuple(game.active_hero_ids()):
                if enemy_id not in game.active_enemy_ids():
                    break
                game.execute(hero_id,"strike",(enemy_id,))
                actions+=1

    gold_before=save.rpg_state.currencies["gold"]
    game.finish_victory()
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/"post_boss.asteria-save.json"
        game.sync_world_state().save_json(path)
        restored=GameRuntimeSave.load_json(path,project)
        exact=restored.to_data()==save.to_data()

    return {
        "trigger_program":trigger.event_program_id,
        "active_party":len(save.rpg_state.party_active_actor_ids),
        "battle_actions":actions,
        "boss_defeated":save.event_context.get_switch("encounter.boss_room.defeated"),
        "gold_before":gold_before,
        "gold_after":save.rpg_state.currencies["gold"],
        "save_reload_exact":exact,
    }


if __name__=="__main__":
    print(run())
