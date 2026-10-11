from __future__ import annotations

from pathlib import Path

from asteria.editor import EditorDocument
from asteria.events import EventContext
from asteria.project import Project
from asteria.rpg import (
    ActorAbilityState,
    ActorProgressionState,
    EquipmentGrowthRuntime,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    Inventory,
    ProgressionAllocationRuntime,
    ProgressionRuntime,
    RpgActorRuntime,
    RpgRuntimeState,
)
from asteria.runtime.game_save import GameRuntimeSave

PROFILE = {
    "early": dict(level=12, exp=11500, roster=6, inventory=10, tree_nodes=1, passives=1, growth=0, gold=3500, pos=(0,0)),
    "mid": dict(level=24, exp=8400, roster=8, inventory=11, tree_nodes=3, passives=2, growth=1, gold=8500, pos=(16,0)),
    "endgame_complex": dict(level=58, exp=74200, roster=12, inventory=16, tree_nodes=5, passives=4, growth=2, gold=88000, pos=(28,0)),
    "boss_stress": dict(level=80, exp=180000, roster=12, inventory=16, tree_nodes=6, passives=6, growth=3, gold=250000, pos=(38,0)),
}


def load_project(project_path):
    document=EditorDocument()
    return Project.load_json(project_path,document.component_registry)


def _progression(db, level):
    runtime=ProgressionRuntime(db.progression_tracks.values())
    scale=max(0,level-1)
    for track_id in db.progression_tracks:
        runtime.add(track_id,float(scale*18 + (sum(ord(ch) for ch in track_id)%17)))
    return runtime


def _allocation(db, actor_index, tree_nodes, level):
    graph_ids=sorted(db.progression_graphs)
    target=graph_ids[actor_index % len(graph_ids)]
    graph=db.progression_graphs[target]
    allocations={}
    ranks={}
    for node in graph.nodes[:tree_nodes]:
        ranks[node.node_id]=1
    allocations[target]=ranks
    return ProgressionAllocationRuntime(
        db.progression_graphs.values(),
        balances={"ap":float(max(0,level*2-tree_nodes))},
        allocations=allocations,
    )


def _loadout(db, actor_index, growth_rank):
    loadout=EquipmentLoadout((
        EquipmentSlotDefinition("weapon",capacity=1),
        EquipmentSlotDefinition("accessory",capacity=2),
    ))
    weapon=db.equipment[f"weapon_{(actor_index%12)+1:02d}"]
    growth=None
    if growth_rank:
        growth=EquipmentGrowthRuntime(
            db.equipment_growth["weapon_growth"],
            ranks={
                "temper_1":1,
                "temper_2":1 if growth_rank>=2 else 0,
                "awaken":1 if growth_rank>=3 else 0,
            },
        )
    item=EquippedItem(weapon,instance_id=f"{weapon.equipment_id}:actor:{actor_index+1}",growth=growth)
    rune=db.attachments[f"rune_{(actor_index%6)+1:02d}"]
    item.attach("rune",rune)
    loadout.equip("weapon",item,validate_requirements=False)
    for n in range(2):
        acc=db.equipment[f"accessory_{((actor_index+n)%8)+1:02d}"]
        loadout.equip("accessory",EquippedItem(acc,instance_id=f"{acc.equipment_id}:actor:{actor_index+1}:{n}"),validate_requirements=False)
    return loadout


def build_save(project, profile_name):
    cfg=PROFILE[profile_name]
    db=project.rpg_database
    actor_ids=tuple(sorted(db.actors))[:cfg["roster"]]

    inventory=Inventory()
    for i,item_id in enumerate(sorted(db.items)[:cfg["inventory"]]):
        inventory.add(item_id,1+(i%5)+(cfg["level"]//20))

    snapshots={}
    progression_allocations={}
    loadouts={}
    actor_progression={}
    all_classes=tuple(sorted(db.classes))
    all_passives=tuple(sorted(db.passives))

    for index,actor_id in enumerate(actor_ids):
        definition=db.actors[actor_id]
        runtime=RpgActorRuntime(definition,class_definitions=db.classes)
        hero_skill_sets=(
            ("strike","fire_arc","heal","meteor","guard","armor_break"),
            ("strike","ice_lance","heal","revive","party_barrier","guard"),
            ("strike","storm_chain","double_cut","haste_song","heal","guard"),
            ("strike","poison_edge","armor_break","counter_stance","heal","guard"),
            ("strike","fire_arc","summon_wisp","focus_charge","burst_release","heal"),
            ("strike","double_cut","dispel","slow_hex","heal","revive"),
        )
        learned=hero_skill_sets[index % len(hero_skill_sets)]
        active_passives=tuple(all_passives[(index+j)%len(all_passives)] for j in range(cfg["passives"]))
        runtime.ability_state=ActorAbilityState(
            learned_abilities=learned,
            active_passives=active_passives,
        )
        snapshots[actor_id]=runtime.snapshot()
        progression_allocations[actor_id]=_allocation(db,index,cfg["tree_nodes"],cfg["level"])
        loadouts[actor_id]=_loadout(db,index,cfg["growth"])

        authored=tuple(x.class_id for x in definition.class_assignments)
        unlocked=all_classes[:min(len(all_classes),2+cfg["level"]//12)]
        unlocked=tuple(dict.fromkeys(authored+unlocked))
        actor_progression[actor_id]=ActorProgressionState(
            cfg["level"]+(index%4),
            cfg["exp"]+index*375,
            points={"ap":float(max(0,cfg["level"]*2-cfg["tree_nodes"]*2)),"ability_points":4.0},
            unlocked_class_ids=unlocked,
            active_class_ids=authored,
        )

    rpg=RpgRuntimeState(
        inventory=inventory,
        progression=_progression(db,cfg["level"]),
        loadouts=loadouts,
        party_actor_ids=actor_ids,
        party_active_actor_ids=actor_ids[:(6 if profile_name=="early" else 4 if profile_name=="mid" else 6)],
        party_placements={
            actor_id:f"slot_{i+1}"
            for i,actor_id in enumerate(actor_ids[:(6 if profile_name=="early" else 4 if profile_name=="mid" else 6)])
        },
        currencies={"gold":cfg["gold"],"renown":max(0,cfg["level"]//20)},
        actor_snapshots=snapshots,
        progression_allocations=progression_allocations,
        actor_progression=actor_progression,
    )

    scene=project.scene(project.startup_scene_id)
    player=next(x for x in scene.entities() if x.name=="Player")
    ctx=EventContext()
    ctx.set_variable("chapter",1 if profile_name=="early" else 3 if profile_name=="mid" else 7)
    ctx.set_variable("reference_profile",profile_name)
    ctx.set_switch("boss_gate_unlocked",profile_name!="early")
    ctx.set_local("astral_tyrant","challenged",profile_name=="boss_stress")

    save=GameRuntimeSave(
        project.id,scene.id,player_entity_id=player.id,player_facing="right",
        player_position=cfg["pos"],rpg_state=rpg,event_context=ctx,
    )
    save.validate(project)
    return save


def write_saves(project_path, output_dir):
    project=load_project(project_path)
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    paths={}
    for name in PROFILE:
        save=build_save(project,name)
        path=output_dir/f"{name}.asteria-save.json"
        save.save_json(path); paths[name]=path
    return paths


if __name__=="__main__":
    here=Path(__file__).resolve().parent
    write_saves(here/"project.asteria.json",here/"saves")
