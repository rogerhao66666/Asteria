"""D89 on the built project: a stat window in the manner of MapleStory's, with every stat the
demo's battles use.

* Ability points: STR, DEX, INT, LUK, VIT (vitality: defence, magic defence and status
  resistance), and HP (+100 a point) and MP (+30 a point) of their own.
* New stats, each doing something in battle (Battle Rules):
  ``penetration`` (the share of the foe's defence a blow ignores: ``penetration_stat``),
  ``bp_bonus`` (what each BP spent on a boost adds to a skill, on top of 100%: the boost
  rules), ``weakness_damage`` and ``break_damage`` (on a weakness hit / a broken foe),
  ``boss_damage`` (against a boss), ``damage_bonus`` and ``final_damage`` (every hit), and
  ``status_resist`` (a bad state's chance to land on the member). Damage rolls 10% either way
  (``final_damage_expression``), so attack is a range.
* Gear carries them: weapons penetration, damage and weakness damage; accessories BP bonus,
  boss and break damage, status resistance; armour VIT and status resistance.
* Menu Pages' detail table: Attack, Defence, Battle, Element Attack and Element Resistance,
  a line a stat - attack as a range, rates as battle chances, the rest as percents.

Run: ``python reference_projects/full_verification_demo/trial_d89.py`` (safe to run again).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

SPREAD = 10.0  # damage rolls this percent either way
FINAL_DAMAGE = "value * (0.9 + random() * 0.2)"
BASE_VIT = {"hero_01": 8.0, "hero_02": 6.0, "hero_03": 10.0, "hero_04": 5.0, "spirit_knight": 9.0}
AILMENTS = ("bleed", "blind", "burn", "charm", "confuse", "doom", "freeze", "poison", "silence")
AILMENTS += ("sleep", "slow", "stun", "defense_down", "magic_down", "power_down")

# stat id -> (English, Chinese, English description, Chinese description)
STATS = {
    "vit": (
        "VIT",
        "體力",
        "Defence, magic defence and status resistance",
        "提高防禦、魔防與異常抗性",
    ),
    "penetration": (
        "Penetration %",
        "穿透 %",
        "The share of the foe's defence a blow ignores",
        "攻擊時無視敵人防禦的比例",
    ),
    "bp_bonus": (
        "BP Bonus %",
        "BP 加成 %",
        "Added to what each BP spent on a boost adds to a skill",
        "每消耗 1 BP 強化技能時，額外提升的效果",
    ),
    "bp_power": (
        "Skill Boost per BP %",
        "每 BP 技能強化 %",
        "What each BP spent on a boost adds to a skill (100% + BP bonus)",
        "每消耗 1 BP 強化技能時提升的效果（100% + BP 加成）",
    ),
    "weakness_damage": (
        "Weakness Damage %",
        "弱點傷害 %",
        "More damage on a weakness hit",
        "打中弱點時的額外傷害",
    ),
    "break_damage": (
        "Break Damage %",
        "破防傷害 %",
        "More damage to a broken foe",
        "對破防敵人的額外傷害",
    ),
    "boss_damage": ("Boss Damage %", "首領傷害 %", "More damage to bosses", "對首領的額外傷害"),
    "damage_bonus": ("Damage %", "傷害 %", "More damage with every hit", "所有攻擊的傷害提升"),
    "final_damage": (
        "Final Damage %",
        "最終傷害 %",
        "Every hit's damage, after everything else",
        "最後再乘上的傷害提升",
    ),
    "status_resist": (
        "Status Resistance %",
        "異常抗性 %",
        "Lowers a bad state's chance to land",
        "降低異常狀態命中自己的機率",
    ),
    "speed": ("Action Speed", "行動速度", "Acts sooner and more often", "更早、更頻繁地行動"),
}

NODES = (  # new or changed nodes of the attributes graph: id, name, reward, max rank
    ("attr_vit", "VIT (Vitality)", {"stat_bonuses": {"vit": 1.0}}, 30),
    ("attr_hp", "HP", {"resource_bonuses": {"vitality": 100.0}}, 50),
    ("attr_mp", "MP", {"resource_bonuses": {"technique": 30.0}}, 50),
)
NODE_ZH = {"attr_vit": "體力（VIT）", "attr_hp": "HP", "attr_mp": "MP"}

FORMULAS = (  # (stat, terms, base): stat formulas the new stats need
    ("bp_power", {"bp_bonus": 1.0}, 100.0),
    ("status_resist", {"vit": 0.5}, 0.0),
)
VIT_TERMS = {"defense": 1.5, "magic_defense": 1.0}  # VIT in the defence formulas

# the detail table: (group id, English, Chinese, [(stat, format, check)])
GROUPS = (
    (
        "attack",
        "Attack",
        "攻擊",
        [
            ("power", "range", ""),
            ("magic", "range", ""),
            ("damage_bonus", "percent", ""),
            ("final_damage", "percent", ""),
            ("boss_damage", "percent", ""),
            ("penetration", "percent", ""),
            ("crit", "chance", "crit"),
            ("crit_damage", "percent", ""),
            ("lifesteal", "percent", ""),
        ],
    ),
    (
        "defence",
        "Defence",
        "防禦",
        [
            ("defense", "number", ""),
            ("magic_defense", "number", ""),
            ("evade", "chance", "land"),
            ("status_resist", "percent", ""),
        ],
    ),
    (
        "battle",
        "Battle",
        "戰鬥",
        [
            ("speed", "number", ""),
            ("accuracy", "chance", "land"),
            ("bp_power", "percent", ""),
            ("weakness_damage", "percent", ""),
            ("break_damage", "percent", ""),
        ],
    ),
    (
        "element_attack",
        "Element Attack",
        "屬性攻擊",
        [(f"{e}_attack", "percent", "") for e in ("fire", "ice", "lightning", "wind", "earth")]
        + [(f"{e}_attack", "percent", "") for e in ("light", "dark")],
    ),
    (
        "element_resist",
        "Element Resistance",
        "屬性抗性",
        [(f"{e}_resist", "percent", "") for e in ("fire", "ice", "lightning", "wind", "earth")]
        + [(f"{e}_resist", "percent", "") for e in ("light", "dark")],
    ),
)

# gear: slot -> [(stat, values by the piece's place in its slot, cycling)]
GEAR = {
    "weapon": [
        ("penetration", (5, 8, 12, 15)),
        ("damage_bonus", (3, 5, 8)),
        ("weakness_damage", (10, 15, 20)),
    ],
    "accessory": [
        ("bp_bonus", (10, 15, 20, 25)),
        ("boss_damage", (5, 10, 15)),
        ("break_damage", (10, 20)),
        ("status_resist", (5, 10, 15)),
    ],
    "armor": [("vit", (2, 3, 4, 6)), ("status_resist", (5, 8, 10))],
    "head": [("vit", (1, 2, 3)), ("final_damage", (2, 3))],
    "legs": [("vit", (2, 3))],
    "feet": [("vit", (1, 2)), ("status_resist", (5,))],
}


def _modifier(owner, stat, value):
    return {
        "blocked_tags": [],
        "modifier_id": f"{owner}.{stat}",
        "operation": "add",
        "priority": 0,
        "required_tags": [],
        "stat": stat,
        "value": float(value),
    }


def patch_actors(db):
    for actor in db["actors"]:
        stats = actor["base_stats"]
        stats["vit"] = BASE_VIT.get(actor["actor_id"], 6.0)
        actor["base_stats"] = dict(sorted(stats.items()))


def patch_graph(db):
    graph = next(g for g in db["progression_graphs"] if g["graph_id"] == "attributes")
    template = graph["nodes"][0]
    nodes = {n["node_id"]: n for n in graph["nodes"]}
    for node_id, name, reward, max_rank in NODES:
        node = nodes.get(node_id) or json.loads(json.dumps(template))
        node.update(node_id=node_id, display_name=name, max_rank=max_rank)
        node["icon_id"] = nodes.get(node_id, {}).get("icon_id") or template["icon_id"]
        node["rank_costs"] = [{"stat_points": 1.0}] * max_rank
        one = {
            "granted_abilities": [],
            "granted_capabilities": [],
            "granted_tags": [],
            "resource_bonuses": reward.get("resource_bonuses", {}),
            "stat_bonuses": reward.get("stat_bonuses", {}),
            "unlocked_passives": [],
        }
        node["rewards"] = [dict(one) for _ in range(max_rank)]
        if node_id not in nodes:
            graph["nodes"].append(node)
        nodes[node_id] = node


def patch_formulas(db):
    rules = {r["stat_id"]: r for r in db["derived_stats"]}
    for stat, terms in (
        ("defense", VIT_TERMS["defense"]),
        ("magic_defense", VIT_TERMS["magic_defense"]),
    ):
        rules[stat]["terms"] = dict(sorted({**rules[stat]["terms"], "vit": terms}.items()))
    for stat, terms, base in FORMULAS:
        rule = rules.get(stat) or {
            "applies_to": "actors",
            "maximum": 0.0,
            "minimum": 0.0,
            "order": 2,
            "schema": "asteria.rpg.derived_stat",
            "version": 1,
            "stat_id": stat,
        }
        rule.update(terms=terms, base=base)
        if stat not in rules:
            db["derived_stats"].append(rule)
            rules[stat] = rule
    for stat, (name, _zh, text, _zh_text) in STATS.items():  # a formula's stat: its name too
        if stat in rules:
            rules[stat].update(display_name=name, description=text)
    db["derived_stats"].sort(key=lambda r: r["stat_id"])


def _rule(rule_id, terms, **fields):
    data = {
        "blocked_source_tags": [],
        "blocked_target_tags": [],
        "disposition": "normal",
        "flat_delta": 0.0,
        "multiplier": 1.0,
        "multiplier_source_terms": terms,
        "outcome_tags": [],
        "priority": 0,
        "rule_id": rule_id,
        "schema": "asteria.rpg.interaction_rule",
        "source_stat_terms": {},
        "source_tags_all": [],
        "source_tags_any": [],
        "target_stat_terms": {},
        "target_tags_all": [],
        "target_tags_any": [],
        "version": 1,
    }
    data.update(fields)
    return data


def patch_rules(db):
    rules = db["interaction_rules"]
    by_id = {r["rule_id"]: r for r in rules}
    for level in (1, 2, 3):
        by_id[f"boost_power_{level}"]["multiplier_source_terms"] = {"bp_bonus": 0.01 * level}
    for rule in rules:
        if "outcome.weak" in rule.get("outcome_tags", ()):
            rule["multiplier_source_terms"] = {"weakness_damage": 0.01}
    by_id["broken"]["multiplier_source_terms"] = {"break_damage": 0.01}
    added = (
        _rule("damage_bonus", {"damage_bonus": 0.01}),
        _rule("final_damage", {"final_damage": 0.01}, priority=-5),
        _rule("boss_damage", {"boss_damage": 0.01}, target_tags_all=["boss"]),
    )
    for rule in added:
        if rule["rule_id"] in by_id:
            by_id[rule["rule_id"]].update(rule)
        else:
            rules.append(rule)
    rules.sort(key=lambda r: r["rule_id"])
    for session in db["battle_session_rules"]:
        session["penetration_stat"] = "penetration"
        session["final_damage_expression"] = FINAL_DAMAGE
    for policy in db["battle_state_policies"]:
        if policy["state_id"] in AILMENTS:
            policy["target_stat_terms"] = {"status_resist": -0.01}


def patch_gear(db):
    places = {}
    for piece in sorted(db["equipment"], key=lambda e: e["equipment_id"]):
        bonuses = GEAR.get(piece["slot"])
        if not bonuses:
            continue
        index = places.get(piece["slot"], 0)
        places[piece["slot"]] = index + 1
        stat, values = bonuses[index % len(bonuses)]
        value = values[(index // len(bonuses)) % len(values)]
        new = [m for m in piece["modifiers"] if not m["modifier_id"].endswith(".d89")]
        new.append(
            {
                **_modifier(piece["equipment_id"], stat, value),
                "modifier_id": f"{piece['equipment_id']}.{stat}.d89",
            }
        )
        piece["modifiers"] = new


def chinese():
    """``(names, descriptions)``: English -> Chinese of D89's words (the glossary reads them)."""
    names = {en: zh for en, zh, _e, _z in STATS.values()}
    for stat, (en, zh, _e, _z) in STATS.items():
        bare, word = en.removesuffix(" %"), zh.removesuffix(" %")
        names[bare] = word
        names[stat.replace("_", " ").capitalize()] = word  # a stat's name made from its id
    names.update({en: zh for _g, en, zh, _lines in GROUPS})
    names.update({name: NODE_ZH[node_id] for node_id, name, _r, _m in NODES})
    descriptions = {e: z for _en, _zh, e, z in STATS.values()}
    return names, descriptions


def patch_menu(db):
    rules = next(r for r in db["menu_rules"] if r["rules_id"] == "trial_menu")
    rules["stat_columns"] = ["total", "base", "points", "gear", "gain"]  # no rank (D89)
    rules["stat_groups"] = [{"group_id": g, "display_name": en} for g, en, _zh, _l in GROUPS]
    rules["stat_lines"] = [
        {
            "stat_id": stat,
            "group": g,
            **({"format": fmt} if fmt != "number" else {}),
            **({"spread": SPREAD} if fmt == "range" else {}),
            **({"check": check} if check else {}),
        }
        for g, _en, _zh, lines in GROUPS
        for stat, fmt, check in lines
    ]


def patch_words(data):
    """English names on the character screen's stat labels; Chinese in the zh-TW table."""
    from asteria.rpg.built_in_text import engine_translations

    db = data["rpg_database"]
    screens = data["battle_presentation_library"]["categories"]["rpg_character_screen"]
    for screen in screens.values():
        labels = {**screen["stat_labels"], **{s: en for s, (en, *_rest) in STATS.items()}}
        screen["stat_labels"] = dict(sorted(labels.items()))
    tables = {t["locale"]: t["entries"] for t in db["locale_tables"]}
    formulas = {r["stat_id"] for r in db["derived_stats"]}
    for stat, (_en, zh, _en_text, zh_text) in STATS.items():
        for locale in ("en", "zh-TW"):  # D89's first build wrote these: the labels hold them
            tables[locale].pop(f"data.stat.{stat}.description", None)
        tables["en"].pop(f"data.stat.{stat}.name", None)
        tables["zh-TW"][f"data.stat.{stat}.name"] = zh
        if stat in formulas:  # a stat formula's description is a data text
            tables["zh-TW"][f"data.stat.{stat}.description"] = zh_text
    for group, _en, zh, _lines in GROUPS:
        tables["zh-TW"][f"data.stat_group.{group}.name"] = zh
    for node_id, zh in NODE_ZH.items():
        tables["zh-TW"][f"data.skill_tree_node.{node_id}.name"] = zh
    for key, word in engine_translations("zh-TW").items():
        tables["zh-TW"].setdefault(key, word)


def main():
    path = HERE / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    db = data["rpg_database"]
    patch_actors(db)
    patch_graph(db)
    patch_formulas(db)
    patch_rules(db)
    patch_gear(db)
    patch_menu(db)
    patch_words(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("stats, points, rules, gear and the detail table set")


if __name__ == "__main__":
    main()
