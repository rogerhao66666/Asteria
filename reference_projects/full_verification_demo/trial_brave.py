"""Aldric the Brave and Archmage: his own two jobs, their trees, the Demon Ring, two new
elements and much stronger foes.

* **Brave** (main job): every weapon (sword, axe, spear, dagger, bow, staff, ring), power and
  magic grow together. Nine skills from Valiant Slash to the divine Final Hope; Arsenal Storm
  strikes once with every weapon, so it finds any weapon weakness.
* **Archmage** (sub job): every element - fire, ice, lightning, light, dark and the new wind and
  earth - each with a Bolt (one foe) and a Storm (all foes); Prismatic Cataclysm hits with all
  seven, Mana Shield and Arcane Surge guard and focus.
* **Trees**: the Brave tree has a ten-rank core, the nine skills, a mastery per weapon (that
  weapon's blows x1.25), Weapon Saint once all seven masteries reach rank 3, three exclusive
  Oaths, then (trial_trees) three specs with talents and capstones, three runes on Valiant Slash
  and a skill book. The Archmage tree has seven elemental schools (school, Bolt, Storm,
  Attunement: that element x1.25), Prismatic Cataclysm behind the schools, three exclusive
  Paths, specs, runes on Fire Bolt and a book. Attributes gain Twin Arts (power and magic).
* **Demon Ring**: a ring weapon with power and magic, seven sockets (three cards, two gems, two
  charms - six new charm attachments) whose attack strikes five times. It waits in the family
  chest in Aldric's house.
* **Foes**: every foe is far stronger (health x3, power and magic x1.8, defence x1.4).
"""

from __future__ import annotations

import dataclasses

import trial_content as tc
import trial_trees as trees_lib

from asteria.gameplay.formulas import FormulaTerm, ValueFormula
from asteria.rpg import (
    AttachmentDefinition,
    ClassAssignment,
    ClassDefinition,
    EquipmentDefinition,
    InteractionRule,
    ItemDefinition,
    ProgressionGraphDefinition,
    SocketDefinition,
)
from asteria.rpg.ability_build import PassiveDefinition

HP, SP = tc.HP, tc.SP
ability, op, healing, _hits, _state = tc.ability, tc.op, tc.healing, tc._hits, tc._state
node, mod = tc._node, tc._modifier
WEAPONS = ("sword", "axe", "spear", "dagger", "bow", "staff", "ring")
ELEMENTS = {  # element: (name, bolt, storm, fx, status the storm leaves)
    "fire": ("Fire", "Fire Bolt", "Inferno", ("fire", "explosion"), "burn"),
    "ice": ("Ice", "Ice Bolt", "Blizzard", ("ice",), "slow"),
    "lightning": ("Lightning", "Thunder Bolt", "Thunderstorm", ("thunder",), "stun"),
    "light": ("Light", "Holy Bolt", "Radiant Storm", ("spark", "spirit"), "blind"),
    "dark": ("Dark", "Shadow Bolt", "Abyss", ("spirit",), "magic_down"),
    "wind": ("Wind", "Gale Bolt", "Tempest", ("circ", "slash"), "defense_down"),
    "earth": ("Earth", "Stone Bolt", "Earthquake", ("explosion", "smoke"), "power_down"),
}
FOE_SCALE = {"stats": {"power": 1.8, "magic": 1.8, "defense": 1.4, "speed": 1.15}, HP: 3.0}
NEW_WEAKNESS = {  # foe: tags for the new elements
    "goblin_slinger": ("weak.wind",),
    "goblin_beast": ("resist.earth",),
    "skeleton_hunter": ("weak.earth",),
    "skeleton_ancient": ("weak.wind",),
    "crimson_warlord": ("weak.earth", "resist.wind"),
    "mender_wisp": ("weak.wind",),
}
CHARMS = {  # charm: (name, stat bonuses, picture tint)
    "charm_lion": ("Lion Charm", {"power": 30}, "red"),
    "charm_owl": ("Owl Charm", {"magic": 30}, "blue"),
    "charm_tortoise": ("Tortoise Charm", {"defense": 30}, "green"),
    "charm_falcon": ("Falcon Charm", {"speed": 15, "evade": 8}, "white"),
    "charm_viper": ("Viper Charm", {"crit": 15}, "purple"),
    "charm_serpent": ("Twin Serpent Charm", {"power": 18, "magic": 18}, "gold"),
}


def twin(power, magic, defense=6.0):
    """Damage from both the user's power and magic (the Brave's way of fighting)."""
    return ValueFormula(
        (
            FormulaTerm("source_stat", "power", -power),
            FormulaTerm("source_stat", "magic", -magic),
            FormulaTerm("target_stat", "defense", defense),
        ),
        maximum=-1.0,
    )


def magic(amount, defense=5.0):
    return tc.damage("magic", amount, defense)


# -- skills ---------------------------------------------------------------------------------
def brave_skills():
    """``[(id, label, targeting, definition)]`` of the Brave."""
    sword = ("weapon.sword",)
    every = tuple(f"weapon.{w}" for w in WEAPONS if w != "ring")
    return [
        (
            "valiant_slash",
            "Valiant Slash",
            "enemy",
            ability(
                "valiant_slash",
                tags=(*sword, "damage.light"),
                sp=10,
                effect=op(twin(14, 6)),
                hits=_hits(1.0, 0.8, tags=(*sword, "damage.light")),
            ),
        ),
        (
            "gigaslash",
            "Gigaslash",
            "enemies",
            ability(
                "gigaslash",
                tags=(*sword, "damage.lightning", "damage.light"),
                sp=36,
                targets=6,
                effect=op(twin(10, 10)),
                hits=_hits(1.0, 1.0, 1.4, tags=(*sword, "damage.lightning")),
            ),
        ),
        (
            "heroic_lance",
            "Heroic Lance",
            "enemy",
            ability(
                "heroic_lance",
                tags=("weapon.spear",),
                sp=18,
                effect=op(twin(20, 4)),
                hits=_hits(1.5, tags=("weapon.spear",)),
                apply_states=[_state("defense_down")],
            ),
        ),
        (
            "aegis_of_courage",
            "Aegis of Courage",
            "self",
            ability(
                "aegis_of_courage",
                tags=("support",),
                sp=14,
                apply_states=[_state("ward", "self"), _state("armor_up", "self")],
            ),
        ),
        (
            "rallying_cry",
            "Rallying Cry",
            "allies",
            ability(
                "rallying_cry",
                tags=("support",),
                sp=24,
                allies=True,
                apply_states=[_state("attack_up"), _state("magic_up")],
            ),
        ),
        (
            "arsenal_storm",
            "Arsenal Storm",
            "enemy",
            ability(
                "arsenal_storm",
                tags=every,
                sp=40,
                effect=op(twin(9, 3)),
                # one blow with every weapon: whichever the foe fears lands as a weakness
                hits=[{"tags": [t], "power": 0.8, "checks": ["crit", "land"]} for t in every],
            ),
        ),
        (
            "dragon_slayer",
            "Dragon Slayer",
            "enemy",
            ability(
                "dragon_slayer",
                tags=(*sword, "damage.fire", "finisher"),
                sp=48,
                effect=op(twin(26, 18)),
                hits=_hits(1.0, 2.2, tags=(*sword, "damage.fire")),
            ),
        ),
        (
            "lightbringer",
            "Lightbringer",
            "allies",
            ability(
                "lightbringer",
                tags=("magic", "support", "damage.light"),
                sp=32,
                allies=True,
                effect=op(healing(8.0)),
                apply_states=[_state("regen")],
            ),
        ),
        (
            "final_hope",
            "Final Hope",
            "enemies",
            ability(
                "final_hope",
                tags=(*sword, "damage.light", "divine", "finisher"),
                sp=60,
                targets=6,
                battle_costs={"bp": 3},
                effect=op(twin(22, 22)),
                hits=_hits(1.0, 1.0, 1.0, 2.5, tags=(*sword, "damage.light")),
            ),
        ),
    ]


def archmage_skills():
    rows = []
    for element, (name, bolt, storm, _fx, status) in ELEMENTS.items():
        tags = ("magic", f"damage.{element}")
        rows.append(
            (
                f"{element}_bolt",
                bolt,
                "enemy",
                ability(
                    f"{element}_bolt",
                    tags=tags,
                    sp=12,
                    effect=op(magic(16)),
                    hits=_hits(1.0, tags=(f"damage.{element}",)),
                ),
            )
        )
        rows.append(
            (
                f"{element}_storm",
                storm,
                "enemies",
                ability(
                    f"{element}_storm",
                    tags=tags,
                    sp=30,
                    targets=6,
                    effect=op(magic(11)),
                    hits=_hits(1.0, 1.0, tags=(f"damage.{element}",)),
                    apply_states=[_state(status)],
                ),
            )
        )
    every = [f"damage.{e}" for e in ELEMENTS]
    rows += [
        (
            "prismatic_cataclysm",
            "Prismatic Cataclysm",
            "enemies",
            ability(
                "prismatic_cataclysm",
                tags=("magic", "divine", "finisher", *every),
                sp=90,
                targets=6,
                battle_costs={"bp": 3},
                effect=op(magic(14)),
                hits=[{"tags": [t], "power": 0.9, "checks": ["crit"]} for t in every],
            ),
        ),
        (
            "mana_shield",
            "Mana Shield",
            "self",
            ability(
                "mana_shield",
                tags=("magic", "support"),
                sp=16,
                apply_states=[_state("ward", "self"), _state("stoneskin", "self")],
            ),
        ),
        (
            "arcane_surge",
            "Arcane Surge",
            "self",
            ability(
                "arcane_surge",
                tags=("magic", "support"),
                sp=20,
                apply_states=[_state("magic_up", "self"), _state("haste", "self")],
            ),
        ),
    ]
    return rows


FX = {
    "valiant_slash": ("slash2", "spark"),
    "gigaslash": ("thunder", "slash2", "cutx"),
    "heroic_lance": ("cut", "cutx"),
    "aegis_of_courage": ("shield",),
    "rallying_cry": ("circ",),
    "arsenal_storm": ("slash", "cut", "claw", "slash2", "cutx", "spark"),
    "dragon_slayer": ("fire", "slash2", "explosion"),
    "lightbringer": ("spirit",),
    "final_hope": ("spark", "thunder", "explosion"),
    "prismatic_cataclysm": ("fire", "ice", "thunder", "spark", "spirit", "circ", "explosion"),
    "mana_shield": ("shield",),
    "arcane_surge": ("aura",),
}


# -- jobs ----------------------------------------------------------------------------------
def jobs(c):
    """The Brave and the Archmage, their skills, passives and trees; Aldric becomes both."""
    db = c.db
    for rows in (brave_skills(), archmage_skills()):
        for ability_id, label, target, definition in rows:
            c.add(definition, target)
            c.skill_names[ability_id] = label
    tc.FX_BY_ABILITY.update(FX)
    for element, (_n, _b, _s, fx, _st) in ELEMENTS.items():
        tc.FX_BY_ABILITY[f"{element}_bolt"] = fx
        tc.FX_BY_ABILITY[f"{element}_storm"] = (*fx, "explosion")
    for ability_id in ("aegis_of_courage", "mana_shield", "arcane_surge"):
        tc.SELF_TARGETED.add(ability_id)
    cap = "capability.weapon."
    db.add_class(
        ClassDefinition(
            "brave",
            "Brave",
            stat_bonuses={"power": 30, "magic": 20, "defense": 16, "speed": 10, "crit": 8},
            resource_bonuses={HP: 800, SP: 120},
            granted_tags=("class.brave", *(cap + w for w in WEAPONS)),
            granted_abilities=("valiant_slash",),
            level_growth={"power": 3.6, "magic": 2.6, "defense": 2.0, "speed": 0.8, "crit": 0.2},
        )
    )
    db.add_class(
        ClassDefinition(
            "archmage",
            "Archmage",
            stat_bonuses={"magic": 32, "power": 6},
            resource_bonuses={SP: 260},
            granted_tags=("class.archmage", cap + "staff", cap + "ring"),
            granted_abilities=("fire_bolt",),
            level_growth={"magic": 3.8, "power": 1.0, "speed": 0.4},
        )
    )
    passives(c)
    mastery_rules(c)
    db.add_progression_graph(brave_tree())
    db.add_progression_graph(archmage_tree())
    trees_lib.SPECS["brave"] = (
        ("paladin", "Paladin", "defense", "hp"),
        ("warlord", "Warlord", "power", "crit"),
        ("spellblade", "Spellblade", "magic", "power"),
    )
    trees_lib.SPECS["archmage"] = (
        ("destruction", "Destruction", "magic", "crit"),
        ("arcane", "Arcane", "sp", "magic"),
        ("elementalist", "Elementalist", "magic", "speed"),
    )
    twin_arts(c)
    actor = db.actors["hero_01"]
    db.actors["hero_01"] = dataclasses.replace(
        actor,
        class_assignments=(
            ClassAssignment("brave", assignment_id="hero_01.main", role="main", priority=10),
            ClassAssignment(
                "archmage", assignment_id="hero_01.sub", role="secondary", priority=5
            ),
        ),
    )


def passives(c):
    db = c.db

    def passive(pid, name, **stats):
        db.add_passive(
            PassiveDefinition(
                pid, name, modifiers=tuple(mod(k, v, f"{pid}.{k}") for k, v in stats.items())
            )
        )

    passive("heros_resolve", "Hero's Resolve", power=40, magic=30, defense=20)
    passive("weapon_saint", "Weapon Saint", power=30, crit=20, speed=10)
    passive("archmages_insight", "Archmage's Insight", magic=60, crit=10)
    passive("oath_legend", "Oath of the Legend", power=80, magic=80, defense=-40)
    passive("oath_shield", "Oath of the Shield", defense=60, speed=-15)
    passive("oath_wanderer", "Oath of the Wanderer", speed=30, evade=20, crit=15)
    passive("path_overload", "Path of Overload", magic=100, defense=-30)
    passive("path_echo", "Path of Echoes", magic=40, crit=25)
    passive("path_font", "Path of the Font", magic=20, defense=20)
    for weapon in WEAPONS:
        passive(f"{weapon}_mastery", f"{weapon.title()} Mastery", power=12, crit=3)
    for element, (name, *_rest) in ELEMENTS.items():
        passive(f"{element}_attunement", f"{name} Attunement", magic=14)


def mastery_rules(c):
    """A mastered weapon or attuned element hits harder; wind and earth meet weaknesses."""
    db = c.db
    for weapon in WEAPONS:
        db.interaction_rules[f"mastery_{weapon}"] = InteractionRule(
            f"mastery_{weapon}",
            source_tags_all=(f"mastery.{weapon}", f"weapon.{weapon}"),
            multiplier=1.25,
            priority=3,
        )
    for element in ELEMENTS:
        db.interaction_rules[f"attune_{element}"] = InteractionRule(
            f"attune_{element}",
            source_tags_all=(f"attune.{element}", f"damage.{element}"),
            multiplier=1.25,
            priority=3,
        )
    for element in ("wind", "earth"):  # the two new elements meet weakness and resistance
        db.interaction_rules[f"weak_{element}"] = dataclasses.replace(
            db.interaction_rules["weak_fire"],
            rule_id=f"weak_{element}",
            source_tags_all=(f"damage.{element}",),
            target_tags_all=(f"weak.{element}",),
        )
        db.interaction_rules[f"resist_{element}"] = dataclasses.replace(
            db.interaction_rules["resist_fire"],
            rule_id=f"resist_{element}",
            source_tags_all=(f"damage.{element}",),
            target_tags_all=(f"resist.{element}",),
        )


def _bonus(**stats):
    out = {}
    for key, value in stats.items():
        bucket = "resource_bonuses" if key in (HP, SP) else "stat_bonuses"
        out.setdefault(bucket, {})[key] = value
    return out


def brave_tree():
    jp = "jp.brave"
    core = "brave_core"
    nodes = [node(core, "Brave's Training", 10, {jp: 1}, _bonus(power=4, magic=3, defense=2))]

    def skill(skill_id, name, cost, needs=(), any_=(), ap=0):
        price = {jp: cost, **({"ap": ap} if ap else {})}
        nodes.append(
            node(
                f"brave_{skill_id}",
                name,
                1,
                price,
                {"granted_abilities": (skill_id,)},
                needs=list(needs),
                any=list(any_),
            )
        )

    skill("valiant_slash", "Valiant Slash", 1, [core])
    skill("aegis_of_courage", "Aegis of Courage", 2, [(core, 2)])
    skill("heroic_lance", "Heroic Lance", 3, ["brave_valiant_slash"])
    skill("gigaslash", "Gigaslash", 4, [(core, 3), "brave_valiant_slash"])
    skill("rallying_cry", "Rallying Cry", 3, ["brave_aegis_of_courage"])
    skill("lightbringer", "Lightbringer", 5, [(core, 5), "brave_rallying_cry"])
    skill("dragon_slayer", "Dragon Slayer", 6, [(core, 6), "brave_gigaslash"])
    masteries = []
    for weapon in WEAPONS:
        node_id = f"brave_mastery_{weapon}"
        masteries.append(node_id)
        nodes.append(
            node(
                node_id,
                f"{weapon.title()} Mastery",
                5,
                {jp: 1},
                {
                    **_bonus(power=3, crit=0.5),
                    "granted_tags": (f"mastery.{weapon}",),  # that weapon's blows x1.25
                },
                needs=[(core, 2)],
                tags=("mastery",),
            )
        )
    skill("arsenal_storm", "Arsenal Storm", 5, [(core, 4)], any_=[(m, 3) for m in masteries])
    nodes.append(
        node(
            "brave_weapon_saint",
            "Weapon Saint",
            1,
            {jp: 8, "ap": 2},
            {"unlocked_passives": ("weapon_saint",)},
            needs=[(m, 3) for m in masteries],  # every weapon, mastered
            tags=("notable",),
        )
    )
    for oath, name in (
        ("oath_legend", "Oath of the Legend"),
        ("oath_shield", "Oath of the Shield"),
        ("oath_wanderer", "Oath of the Wanderer"),
    ):
        reward = {"unlocked_passives": (oath,)}
        if oath == "oath_shield":
            reward["resource_bonuses"] = {HP: 4000}
        nodes.append(
            node(
                f"brave_{oath}",
                name,
                1,
                {jp: 6, "ap": 2},
                reward,
                needs=[(core, 5)],
                group="brave_oath",
                tags=("keystone",),
            )
        )
    nodes.append(
        node(
            "brave_resolve",
            "Hero's Resolve",
            1,
            {jp: 10},
            {"unlocked_passives": ("heros_resolve",)},
            needs=[(core, 10)],
        )
    )
    skill(
        "final_hope",
        "Final Hope",
        12,
        [(core, 8), "brave_dragon_slayer", "brave_lightbringer"],
        any_=[f"brave_{o}" for o in ("oath_legend", "oath_shield", "oath_wanderer")],
        ap=3,
    )
    return ProgressionGraphDefinition(
        "brave_tree", "Brave", nodes=tuple(nodes), tags=("job.brave",)
    )


def archmage_tree():
    jp = "jp.archmage"
    core = "arch_core"
    nodes = [node(core, "Arcane Study", 10, {jp: 1}, _bonus(magic=5, **{SP: 20}))]
    attunements = []
    for element, (name, bolt, storm, _fx, _st) in ELEMENTS.items():
        school = f"arch_school_{element}"
        nodes.append(
            node(
                school,
                f"School of {name}",
                5,
                {jp: 1},
                {**_bonus(magic=3), "granted_tags": (f"school.{element}",)},
                needs=[(core, 2)],
                tags=("school",),
            )
        )
        nodes.append(
            node(
                f"arch_{element}_bolt",
                bolt,
                1,
                {jp: 2},
                {"granted_abilities": (f"{element}_bolt",)},
                needs=[school],
            )
        )
        nodes.append(
            node(
                f"arch_{element}_storm",
                storm,
                1,
                {jp: 4},
                {"granted_abilities": (f"{element}_storm",)},
                needs=[(school, 3), f"arch_{element}_bolt"],
            )
        )
        attune = f"arch_{element}_attune"
        attunements.append(attune)
        nodes.append(
            node(
                attune,
                f"{name} Attunement",
                1,
                {jp: 5},
                {
                    "unlocked_passives": (f"{element}_attunement",),
                    "granted_tags": (f"attune.{element}",),  # that element x1.25
                },
                needs=[(school, 5), f"arch_{element}_storm"],
                tags=("attunement",),
            )
        )
    nodes.append(
        node(
            "arch_mana_shield",
            "Mana Shield",
            1,
            {jp: 2},
            {"granted_abilities": ("mana_shield",)},
            needs=[core],
        )
    )
    nodes.append(
        node(
            "arch_arcane_surge",
            "Arcane Surge",
            1,
            {jp: 3},
            {"granted_abilities": ("arcane_surge",)},
            needs=[(core, 4)],
        )
    )
    for path, name in (
        ("path_overload", "Path of Overload"),
        ("path_echo", "Path of Echoes"),
        ("path_font", "Path of the Font"),
    ):
        reward = {"unlocked_passives": (path,)}
        if path == "path_font":
            reward["resource_bonuses"] = {SP: 600}
        nodes.append(
            node(
                f"arch_{path}",
                name,
                1,
                {jp: 6, "ap": 2},
                reward,
                needs=[(core, 5)],
                group="arch_path",
                tags=("keystone",),
            )
        )
    nodes.append(
        node(
            "arch_insight",
            "Archmage's Insight",
            1,
            {jp: 10},
            {"unlocked_passives": ("archmages_insight",)},
            needs=[(core, 10)],
        )
    )
    nodes.append(
        node(
            "arch_prismatic",
            "Prismatic Cataclysm",
            1,
            {jp: 14, "ap": 3},
            {"granted_abilities": ("prismatic_cataclysm",)},
            # three attunements of the classic elements, and any one of the others
            needs=[(core, 8), *attunements[:3]],
            any=attunements[3:],
            tags=("ultimate",),
        )
    )
    return ProgressionGraphDefinition(
        "archmage_tree", "Archmage", nodes=tuple(nodes), tags=("job.archmage",)
    )


def twin_arts(c):
    """Attributes gain Twin Arts: power and magic from one point (the Brave fights with both)."""
    graph = c.db.progression_graphs["attributes"]
    twin_node = node("attr_twin", "Twin Arts", 30, {"stat_points": 1}, _bonus(power=1, magic=1))
    c.db.progression_graphs["attributes"] = dataclasses.replace(
        graph, nodes=(*graph.nodes, twin_node)
    )


# -- the Demon Ring --------------------------------------------------------------------------
def ring(c):
    """The Demon Ring, its five-strike attack, the six charms and the family chest's gift."""
    db = c.db
    tags = ("weapon.ring", "boost.repeat")
    c.add(
        ability(
            "attack_ring",
            tags=tags,
            effect=op(twin(5, 5)),
            # five strikes in one attack
            hits=[{"tags": ["weapon.ring"], "power": 0.6, "checks": ["crit", "land"]}] * 5,
        ),
        "enemy",
    )
    c.skill_names["attack_ring"] = "Attack (ring)"
    tc.FX_BY_ABILITY["attack_ring"] = ("spark", "cut", "spark", "cut", "cutx")
    db.add_equipment(
        EquipmentDefinition(
            "w_demon_ring",
            "Demon Ring",
            slot="weapon",
            tags=("weapon", "equip.ring", "unique"),
            modifiers=tuple(
                mod(k, v, f"demon_ring.{k}")
                for k, v in {"power": 45, "magic": 45, "crit": 10, "speed": 10}.items()
            ),
            granted_abilities=("attack_ring",),
            sockets=(
                SocketDefinition("c1", accepted_tags=("card",)),
                SocketDefinition("c2", accepted_tags=("card",)),
                SocketDefinition("c3", accepted_tags=("card",)),
                SocketDefinition("g1", accepted_tags=("gem",)),
                SocketDefinition("g2", accepted_tags=("gem",)),
                SocketDefinition("h1", accepted_tags=("charm",)),
                SocketDefinition("h2", accepted_tags=("charm",)),
            ),
        )
    )
    for charm, (name, stats, _tint) in CHARMS.items():
        db.add_attachment(
            AttachmentDefinition(
                charm,
                name,
                tags=("charm",),
                modifiers=tuple(mod(k, v, f"{charm}.{k}") for k, v in stats.items()),
            )
        )
        db.add_item(
            ItemDefinition(f"{charm}_item", name, stack_limit=9, attachment_id=charm)
        )


def family_chest(assets, home, maps):
    """The chest in Aldric's house: the Demon Ring (worn in his second hand) and the charms."""
    import trial_people as people
    from asteria.runtime.collision import Collider2DComponent

    chest = home.entity("Family Chest", 9 * 16.0 + 8.0, 4 * 16.0)
    picture = ("item", "Items/Treasure/LittleTreasureChest.png")
    home.look(chest, *people.look(assets, "home_chest", picture, "Family Chest"))
    chest.add_component(maps._set(Collider2DComponent(), width=26, height=10, offset_y=-5))
    gifts = [
        maps.world("EQUIP_ITEM", actor_id="hero_01", equipment_id="w_demon_ring", index=1),
        *(maps.world("GIVE_ITEM", item_id=f"{charm}_item", quantity=1) for charm in CHARMS),
        maps.world("SHOW_POPUP", text="The Demon Ring and six charms!", kind="item"),
    ]
    home.program(
        chest,
        "home.chest",
        maps.when(
            "home.chest.open",
            [maps.say("Family Chest", "Empty. The ring is on your hand.")],
            [maps.set_switch("home.chest.open"), *gifts],
        ),
        radius=28.0,
    )
    return chest


# -- the foes ------------------------------------------------------------------------------
def foes(c):
    """Every foe far stronger; wind and earth weaknesses on some."""
    db = c.db
    for enemy_id, enemy in list(db.enemies.items()):
        stats = {
            k: v * FOE_SCALE["stats"].get(k, 1.0) for k, v in dict(enemy.stats).items()
        }
        resources = dict(enemy.resources)
        if HP in resources and enemy_id != "vigil_acolyte":  # the vigil is held, not won
            resources[HP] = resources[HP] * FOE_SCALE[HP]
        tags = (*enemy.tags, *NEW_WEAKNESS.get(enemy_id, ()))
        db.enemies[enemy_id] = dataclasses.replace(
            enemy, stats=stats, resources=resources, tags=tuple(dict.fromkeys(tags))
        )


# -- pictures ------------------------------------------------------------------------------
def icons(c):
    """The Demon Ring and the charms wear Lucifer pictures (tinted)."""
    import trial_icons as icons_lib
    import trial_lucifer as lucifer

    folder = c.root / "playable_assets" / "lucifer" / "icons"
    misc = lucifer.FREE_ASSETS / "Foozle_2DS0005_Lucifer_Equipment_Pixel_Art" / "Equipment"
    db = c.db

    def save(source, tint, name):
        image = icons_lib._tint(lucifer.first_frame(misc / source), tint)
        image.save(folder / name)
        return f"playable_assets/lucifer/icons/{name}"

    icon = save("Misc/Png/Wizards Sparkle Ring.png", "purple", "w_demon_ring.png")
    db.equipment["w_demon_ring"] = dataclasses.replace(db.equipment["w_demon_ring"], icon_id=icon)
    for charm, (_name, _stats, tint) in CHARMS.items():
        icon = save("Misc/Png/Wizards Amulet.png", tint, f"{charm}.png")
        db.attachments[charm] = dataclasses.replace(db.attachments[charm], icon_id=icon)
        item = db.items[f"{charm}_item"]
        db.items[f"{charm}_item"] = dataclasses.replace(item, icon_id=icon)
