"""Build a small playable starter from the shipped party template's licensed art."""

from __future__ import annotations

import copy
import json
from pathlib import Path


def simplify_basic_rpg(folder):
    """Remove advanced systems and replace the demo with a one-hero starter game."""
    folder = Path(folder)
    path = folder / "project.asteria.json"
    data = json.loads(path.read_text())
    db = data["rpg_database"]
    old = copy.deepcopy(db)
    for key, value in db.items():
        if isinstance(value, list):
            db[key] = []

    abilities = {a["ability_id"]: a for a in data["gameplay_library"]["abilities"]}
    selected = ("attack_sword", "fireball", "first_aid", "add_bite")
    for ability_id, amount in zip(selected, (-18, -30, 40, -10), strict=True):
        ability = abilities[ability_id]
        ability["tags"] = ["ability"]
        ability["conditions"] = {"type": "group", "mode": "all", "conditions": []}
        ability["effects"] = [ability["effects"][0]]
        effect = ability["effects"][0]["effect"]
        effect["required_tags"] = []
        effect["blocked_tags"] = []
        effect["operations"] = [{"kind": "resource_delta", "target": "vitality", "value": amount}]
        ability["targeting"]["maximum_targets"] = 1
        ability["targeting"]["required_tags"] = []
        ability["targeting"]["blocked_tags"] = []
        ability["costs"] = (
            [
                {
                    "resource": "technique",
                    "amount": {
                        "schema": "asteria.value_formula",
                        "version": 1,
                        "terms": [{"source": "constant", "key": "", "coefficient": 4.0}],
                        "multipliers": [],
                        "minimum": None,
                        "maximum": None,
                    },
                }
            ]
            if ability_id in ("fireball", "first_aid")
            else []
        )
    library = data["gameplay_library"]
    for key, value in library.items():
        if isinstance(value, list):
            library[key] = []
    library["abilities"] = [abilities[key] for key in selected]

    hero = old["actors"][0]
    hero["display_name"] = "Hero"
    hero["abilities"] = list(selected[:3])
    hero["tags"] = ["actor.playable"]
    hero["base_stats"] = {"power": 12, "magic": 12, "defense": 5, "speed": 12}
    hero["base_resources"] = {
        rid: {"minimum": 0.0, "maximum": amount, "current": amount}
        for rid, amount in (("vitality", 120.0), ("technique", 24.0))
    }
    assignment = hero["class_assignments"][0]
    assignment.update(class_id="adventurer", progression_track_ids=[])
    hero["class_assignments"] = [assignment]
    db["actors"] = [hero]
    job = old["classes"][0]
    job.update(
        class_id="adventurer",
        display_name="Adventurer",
        granted_abilities=[],
        granted_tags=[],
        resource_bonuses={},
        stat_bonuses={},
    )
    db["classes"] = [job]
    enemies = []
    for enemy_id, hp in (("gel_slime", 54), ("bone_wraith", 72)):
        enemy = next(e for e in old["enemies"] if e["enemy_id"] == enemy_id)
        enemy.update(
            abilities=["add_bite"],
            resources={"vitality": hp},
            stats={"power": 8, "defense": 3, "speed": 8},
            tags=["enemy"],
            reward={"currencies": {"gold": 5.0}, "experience": {}, "loot": []},
        )
        enemies.append(enemy)
    db["enemies"] = enemies
    db["encounters"] = [
        {
            **old["encounters"][0],
            "encounter_id": encounter_id,
            "tags": [],
            "members": [{"enemy_id": enemy_id, "count": 1, "weight": 1.0}],
        }
        for encounter_id, enemy_id in (("slime_pit", "gel_slime"), ("old_crypt", "bone_wraith"))
    ]
    for key in ("battle_objectives", "battle_schedulers", "escape_rules"):
        db[key] = old[key][:1]
    session = old["battle_session_rules"][0]
    session.update(
        rules_id="basic_battle", boost_resource_id="", boost_max_level=0, shield_resource_id=""
    )
    db["battle_session_rules"] = [session]
    db["battle_resources"] = [
        {
            "schema": "asteria.rpg.battle_resource",
            "version": 1,
            "resource_id": rid,
            "minimum": 0.0,
            "maximum": amount,
            "start_mode": "current",
            "start_value": None,
            "end_mode": "persist",
            "overflow_limit": None,
            "rules": [],
        }
        for rid, amount in (("vitality", 120.0), ("technique", 24.0))
    ]
    db["battle_targeting"] = [r for r in old["battle_targeting"] if r["ability_id"] in selected]
    for rule in db["battle_targeting"]:
        rule["maximum_targets"] = 1
    ai = old["enemy_ai"][0]
    ai.update(ai_id="basic_enemy", phases=[], initial_phase_id=None, actions_per_ready=1)
    rule = ai["rules"][0]
    rule.update(
        rule_id="attack",
        conditions=[],
        payload={"ability_id": "add_bite"},
        target_selector="first_opponent",
    )
    ai["rules"] = [rule]
    db["enemy_ai"] = [ai]
    db["enemy_behavior_bindings"] = [
        {**old["enemy_behavior_bindings"][0], "enemy_id": e["enemy_id"], "ai_id": "basic_enemy"}
        for e in enemies
    ]
    party = old["party_setups"][0]
    party.update(
        active_actor_ids=[hero["actor_id"]],
        roster_actor_ids=[hero["actor_id"]],
        active_capacity=1,
        placements=party["placements"][:1],
        tags=[],
    )
    db["party_setups"] = [party]
    db["formations"] = old["formations"][:1]
    party["formation_id"] = db["formations"][0]["formation_id"]

    start = data["game_start"]
    from asteria.rpg.save_state import RpgRuntimeState

    start["rpg_state"] = RpgRuntimeState(
        party_actor_ids=[hero["actor_id"]],
        party_active_actor_ids=[hero["actor_id"]],
    ).to_data()
    start["event_context"] = {
        "schema": "asteria.event_context",
        "version": 1,
        "switches": {},
        "variables": {},
        "locals": {},
    }
    for scene in data["scenes"]:
        scene["name"] = "Training Meadow"
        scene["entities"] = [
            e for e in scene["entities"] if e["name"] in ("Player", "Gel Slime", "Bone Wraith")
        ]
    data["event_programs"] = {}
    data["scene_event_bindings"] = {}
    data["lifecycle_event_bindings"] = []
    categories = data["battle_presentation_library"]["categories"]
    old_visuals = categories["combatant_visuals"]
    categories["combatant_visuals"] = {
        k: v for k, v in old_visuals.items() if k in (hero["actor_id"], "gel_slime", "bone_wraith")
    }
    for enemy in enemies:  # the one monster of the starter: the Lucifer Skeleton Ancient
        enemy["display_name"] = "Skeleton Ancient"
        categories["combatant_visuals"][enemy["enemy_id"]] = {
            **old_visuals["iron_samurai"],
            "profile_id": enemy["enemy_id"],
        }
    path.write_text(json.dumps(data, indent=2) + "\n")
    _skeleton_field_pictures(folder)
    manifest_path = folder / "playable_test_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["title"] = data["name"]
    manifest["field"]["entity_sprites"] = {
        k: v
        for k, v in manifest["field"]["entity_sprites"].items()
        if k in ("Gel Slime", "Bone Wraith")
    }
    manifest["battle"]["skills"] = {
        key: {**manifest["battle"]["skills"][key], "label": label}
        for key, label in zip(selected[:3], ("Attack", "Fire", "Heal"), strict=True)
    }
    manifest["battle"]["heroes"] = manifest["battle"]["heroes"][:1]
    manifest["progression_rewards"] = {}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (folder / "START_HERE.md").write_text(
        "# Basic RPG\n\nRun Project to explore Training Meadow. Touch a slime or wraith "
        "to start a battle. Use Attack, Fire (4 MP), or Heal (4 MP). Defeat the enemy to win.\n\n"
        "Game Data contains one hero, one Adventurer class, three player abilities "
        "and two enemies.\n"
        "Battle contains HP (vitality), MP (technique), targeting, turn order, "
        "victory and escape.\n"
        "The field is the tile-painted Diablo map. Select Map in the scene, then Tiles "
        "to edit its layers and collision.\n"
        "Enemy AI contains one attack rule shared by both enemies.\n"
        "There are no jobs to unlock, shields, boost points, pets or crafting dependencies.\n"
    )
    (folder / "README.md").write_text((folder / "START_HERE.md").read_text())


def _skeleton_field_pictures(folder):
    """Both field foes wear the Skeleton Ancient picture (the starter has one monster)."""
    from PIL import Image

    assets = folder / "playable_assets"
    source = assets / "field_iron_samurai.png"
    if not source.is_file():
        return
    picture = Image.open(source).convert("RGBA").resize((48, 48), Image.NEAREST)
    for name in ("field_gel_slime.png", "field_bone_wraith.png"):
        picture.save(assets / name)
