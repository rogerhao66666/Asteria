"""D91 on the built project: every stat defined, base stats that are only base stats, no Hero
job, and job pictures that show the job.

* Game Systems ▸ Stats: each of the demo's 38 stats with its name, short name (STR, SPD...),
  how it is written, where it is set and what it means - in English and Chinese. The editor
  lists beside each where it comes from and what reads it.
* An actor's Base Stats hold STR, DEX, INT, LUK, VIT and SPD only. The attack, defence and
  rate stats come from the stat formulas: what the actors held of them (the party's average)
  moves into the formula's own base. Speed is SPD, a base stat (no formula).
* The Hero job is gone: the job, its skill tree, its job points, its shrine in town, and the
  skills and passives nothing else uses.
* Job pictures: the job's weapon (a sword for the Brave, crossed blades for the Weapon
  Master) or its gear (a helmet, a robe), from the demo's own CC0 gear art.
* Lifesteal (a 0..1 share) reads as a percent: 0.12 is 12%.

Run: ``python reference_projects/full_verification_demo/trial_d91.py`` (safe to run again).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

ICONS = HERE / "playable_assets" / "lucifer" / "icons"
BASE = ("str", "dex", "int", "luk", "vit", "speed")
ACTOR_CLASS = ["actors", "classes"]
ELEMENTS = {
    "fire": ("Fire", "火"),
    "ice": ("Ice", "冰"),
    "lightning": ("Lightning", "雷"),
    "wind": ("Wind", "風"),
    "earth": ("Earth", "地"),
    "light": ("Light", "光"),
    "dark": ("Dark", "闇"),
}

# stat id -> (name, short, Chinese name, Chinese short, written as, set on, description,
# Chinese description); the order of this table is the stats' order
STATS = {
    "str": (
        "Strength",
        "STR",
        "力量",
        "力量",
        "number",
        ACTOR_CLASS,
        "Raises Physical Attack (+2 a point), Physical Defence (+1) and Critical Damage (+0.1%).",
        "提高物理攻擊（每點 +2）、物理防禦（+1）與暴擊傷害（+0.1%）。",
    ),
    "dex": (
        "Dexterity",
        "DEX",
        "敏捷",
        "敏捷",
        "number",
        ACTOR_CLASS,
        "Raises Accuracy (+1 a point), Physical Attack, Physical Defence and Evasion"
        " (+0.5) and Critical Rate (+0.2).",
        "提高命中（每點 +1）、物理攻擊、物理防禦與迴避（+0.5）以及暴擊率（+0.2）。",
    ),
    "int": (
        "Intelligence",
        "INT",
        "智力",
        "智力",
        "number",
        ACTOR_CLASS,
        "Raises Magic Attack (+2 a point) and Magic Defence (+1).",
        "提高魔法攻擊（每點 +2）與魔法防禦（+1）。",
    ),
    "luk": (
        "Luck",
        "LUK",
        "幸運",
        "幸運",
        "number",
        ACTOR_CLASS,
        "Raises Evasion (+1 a point), Accuracy, Critical Rate, Magic Attack and Magic"
        " Defence (+0.5) and Critical Damage (+0.3%).",
        "提高迴避（每點 +1）、命中、暴擊率、魔法攻擊與魔法防禦（+0.5）以及暴擊傷害（+0.3%）。",
    ),
    "vit": (
        "Vitality",
        "VIT",
        "體力",
        "體力",
        "number",
        ACTOR_CLASS,
        "Raises Physical Defence (+1.5 a point), Magic Defence (+1) and Status Resistance"
        " (+0.5%).",
        "提高物理防禦（每點 +1.5）、魔法防禦（+1）與異常抗性（+0.5%）。",
    ),
    "speed": (
        "Speed",
        "SPD",
        "速度",
        "速度",
        "number",
        [*ACTOR_CLASS, "enemies"],
        "Who acts first: every round the turns go from the highest SPD down (Battle"
        " Rules ▸ Turn Order Stat). A fast target also dodges more: +0.02% a point.",
        "決定出手順序：每回合由 SPD 最高的先行動（戰鬥規則 ▸ 行動順序屬性）。"
        "速度快的目標也較會閃避：每點 +0.02%。",
    ),
    "power": (
        "Physical Attack",
        "ATK",
        "物理攻擊",
        "物攻",
        "number",
        ["enemies"],
        "What physical skills hit with: a skill's damage is a multiple of its user's ATK"
        " less a multiple of the target's DEF. From STR and DEX (Stat Formulas).",
        "物理技能的威力來源：技能傷害＝使用者 ATK 的倍數－目標 DEF 的倍數。"
        "由力量與敏捷算出（屬性公式）。",
    ),
    "magic": (
        "Magic Attack",
        "MATK",
        "魔法攻擊",
        "魔攻",
        "number",
        ["enemies"],
        "What spells and healing work with: a spell's damage or healing is a multiple of"
        " its user's MATK. From INT and LUK (Stat Formulas).",
        "法術與治療的威力來源：法術的傷害或治療量＝使用者 MATK 的倍數。"
        "由智力與幸運算出（屬性公式）。",
    ),
    "defense": (
        "Physical Defence",
        "DEF",
        "物理防禦",
        "物防",
        "number",
        ["enemies"],
        "Taken off physical damage: a skill subtracts a multiple of the target's DEF."
        " Also +0.2% Block chance a point. From STR, DEX and VIT.",
        "減少受到的物理傷害：技能會扣掉目標 DEF 的倍數。每點也讓格擋機率 +0.2%。"
        "由力量、敏捷與體力算出。",
    ),
    "magic_defense": (
        "Magic Defence",
        "MDEF",
        "魔法防禦",
        "魔防",
        "number",
        ["enemies"],
        "Taken off magic damage: a spell subtracts a multiple of the target's"
        " MDEF. From INT, VIT, LUK and half the Physical Defence.",
        "減少受到的魔法傷害：法術會扣掉目標 MDEF 的倍數。由智力、體力、幸運與一半的物理防禦算出。",
    ),
    "accuracy": (
        "Accuracy",
        "ACC",
        "命中",
        "命中",
        "number",
        ["enemies"],
        "A hit lands at 95%, +0.3% a point of the attacker's ACC and -0.3% a point of"
        " the target's EVA (the Land check).",
        "攻擊命中率 95%，攻擊者每點 ACC +0.3%，目標每點 EVA −0.3%（命中判定）。",
    ),
    "evade": (
        "Evasion",
        "EVA",
        "迴避",
        "迴避",
        "number",
        ["enemies"],
        "Takes 0.3% a point off the attacker's chance to land a hit (the Land check).",
        "每點讓攻擊者的命中率 −0.3%（命中判定）。",
    ),
    "crit": (
        "Critical Rate",
        "CRI",
        "暴擊率",
        "暴擊",
        "number",
        ["enemies"],
        "A critical hit's chance: 5% and +0.3% a point (the Crit check).",
        "暴擊機率：5%，每點 +0.3%（暴擊判定）。",
    ),
    "crit_damage": (
        "Critical Damage %",
        "CDMG",
        "暴擊傷害 %",
        "暴傷",
        "percent",
        [],
        "A critical hit does x2, +1% a point.",
        "暴擊時傷害 ×2，每點再 +1%。",
    ),
    "penetration": (
        "Penetration %",
        "PEN",
        "穿透 %",
        "穿透",
        "percent",
        [],
        "Ignores this % of the target's defence in damage formulas (Battle Rules ▸"
        " Penetration Stat).",
        "計算傷害時無視目標這個百分比的防禦（戰鬥規則 ▸ 穿透屬性）。",
    ),
    "damage_bonus": (
        "Damage %",
        "DMG",
        "傷害 %",
        "傷害",
        "percent",
        [],
        "Every hit does 1% more a point.",
        "所有攻擊每點 +1% 傷害。",
    ),
    "final_damage": (
        "Final Damage %",
        "FDMG",
        "最終傷害 %",
        "最終",
        "percent",
        [],
        "Every hit does 1% more a point, after every other bonus.",
        "所有攻擊每點 +1% 傷害，在其他加成之後計算。",
    ),
    "boss_damage": (
        "Boss Damage %",
        "BOSS",
        "首領傷害 %",
        "首領",
        "percent",
        [],
        "Hits on a boss (a target tagged boss) do 1% more a point.",
        "攻擊首領（帶有 boss 標籤的目標）時每點 +1% 傷害。",
    ),
    "weakness_damage": (
        "Weakness Damage %",
        "WEAK",
        "弱點傷害 %",
        "弱點",
        "percent",
        [],
        "A hit on a weakness does x1.8, +1% a point.",
        "打中弱點時傷害 ×1.8，每點再 +1%。",
    ),
    "break_damage": (
        "Break Damage %",
        "BRK",
        "破防傷害 %",
        "破防",
        "percent",
        [],
        "Hits on a broken foe do x2.5, +1% a point.",
        "攻擊破防中的敵人時傷害 ×2.5，每點再 +1%。",
    ),
    "bp_bonus": (
        "BP Bonus %",
        "BPB",
        "BP 加成 %",
        "BP 加成",
        "percent",
        [],
        "A boosted skill gains 1% more a point for each BP spent (x2 at 1 BP, x3 at 2 BP...).",
        "強化技能時，每消耗 1 BP 再多 1%（1 BP 為 ×2、2 BP 為 ×3…）。",
    ),
    "bp_power": (
        "Skill Boost per BP %",
        "BP%",
        "每 BP 技能強化 %",
        "BP 強化",
        "percent",
        [],
        "Shown only: what each BP spent on a boost adds, 100% + BP Bonus. The boost"
        " rules read BP Bonus itself.",
        "只用於顯示：每消耗 1 BP 強化的幅度＝100%＋BP 加成。實際計算讀取的是 BP 加成。",
    ),
    "status_resist": (
        "Status Resistance %",
        "RES",
        "異常抗性 %",
        "抗性",
        "percent",
        [],
        "A bad state (poison, sleep, stun... 15 of them) lands 1% less often a point.",
        "負面狀態（中毒、睡眠、暈眩…共 15 種）每點降低 1% 的命中機率。",
    ),
    "lifesteal": (
        "Lifesteal",
        "LS",
        "吸血",
        "吸血",
        "share",
        [],
        "Heals this share of the damage dealt (0.12: 12%; Battle Extensions ▸ Lifesteal Stat).",
        "回復造成傷害的這個比例（0.12 即 12%；戰鬥擴充 ▸ 吸血屬性）。",
    ),
}
for element, (word, zh) in ELEMENTS.items():
    STATS[f"{element}_attack"] = (
        f"{word} Attack %", f"{word[:3].upper()}+", f"{zh}屬性攻擊 %", f"{zh}攻", "percent",
        ["enemies"], f"{word} hits do 1% more a point.", f"{zh}屬性攻擊每點 +1% 傷害。",
    )  # fmt: skip
    STATS[f"{element}_resist"] = (
        f"{word} Resist %", f"{word[:3].upper()}-", f"{zh}屬性抗性 %", f"{zh}抗", "percent",
        ["enemies"], f"{word} hits taken do 1% less a point.", f"受到的{zh}屬性傷害每點 −1%。",
    )  # fmt: skip

# job -> the demo's gear pictures that show it; two weapons cross
JOB_ICONS = {
    "brave": ("w_sunbrand",),
    "duelist": ("w_steel_sword", "w_dagger"),
    "weapon_master": ("w_war_axe", "w_sword"),
    "knight": ("hd_plate_helmet",),
    "guardian": ("a_warden_plate",),
    "forgemaster": ("w_bone_scepter",),
    "rogue": ("w_dagger",),
    "archmage": ("w_ash_staff",),
    "sage": ("hd_wizard_hat",),
    "mystic": ("a_moon_pendant",),
    "cleric": ("a_holy_symbol",),
    "priest": ("w_saint_staff",),
    "bishop": ("hd_royal_helmet",),
    "necromancer": ("a_phylactery",),
    "lich": ("hd_chain_helmet",),
    "death_lord": ("w_titan_cleaver",),
    "cultist": ("w_ritual_kris",),
    "heretic": ("w_demon_ring",),
    "zealot": ("a_zealot_mail",),
    "spirit": ("a_feather_charm",),
}


def patch_stats(db):
    """Game Systems ▸ Stats: one definition a stat, in the table's order."""
    definitions = []
    for order, (stat, (name, short, _zn, _zs, display, set_on, text, _zt)) in enumerate(
        STATS.items()
    ):
        definitions.append(
            {
                "schema": "asteria.rpg.stat_definition",
                "version": 1,
                "stat_id": stat,
                "display_name": name,
                "short_name": short,
                "display": display,
                "set_on": list(set_on),
                "order": order,
                "description": text,
            }
        )
    db["stat_definitions"] = definitions
    for rule in db["derived_stats"]:  # a formula describes its stat the same way
        if rule["stat_id"] in STATS:
            rule["display_name"] = STATS[rule["stat_id"]][0]
            rule["description"] = STATS[rule["stat_id"]][6]


def patch_base_stats(db):
    """Actors keep the base stats; the rest moves into the formulas' own base."""
    rules = {r["stat_id"]: r for r in db["derived_stats"]}
    actors = db["actors"]
    moved = {}
    for actor in actors:
        for stat, value in actor["base_stats"].items():
            if stat not in BASE:
                moved.setdefault(stat, []).append(float(value))
    for stat, values in moved.items():
        if stat in rules:
            rules[stat]["base"] = round(rules[stat]["base"] + sum(values) / len(actors), 1)
    for actor in actors:
        actor["base_stats"] = {s: v for s, v in actor["base_stats"].items() if s in BASE}
        actor["base_stats"].update(HERO_BASE.get(actor["actor_id"], {}))
    db["derived_stats"] = [r for r in db["derived_stats"] if r["stat_id"] != "speed"]
    for rule in db["derived_stats"]:
        rule["base"] = FORMULA_BASE.get(rule["stat_id"], rule["base"])


# Each hero's base stats, fitted so the formulas give back the attack, defence, magic and rate
# stats they held before (within a few points): what set one hero apart now comes from STR,
# DEX, INT, LUK and VIT, not from a number of their own.
HERO_BASE = {
    "hero_01": {"str": 21, "dex": 9, "int": 12, "luk": 4, "vit": 7},
    "hero_02": {"str": 1, "dex": 7, "int": 19, "luk": 8, "vit": 7},
    "hero_03": {"str": 1, "dex": 6, "int": 19, "luk": 9, "vit": 10},
    "hero_04": {"str": 16, "dex": 9, "int": 1, "luk": 17, "vit": 3},
    "spirit_knight": {"str": 19, "dex": 9, "int": 3, "luk": 1, "vit": 10},
}
FORMULA_BASE = {"power": 21.0, "defense": 20.5, "magic": 27.0, "magic_defense": 0.0}


def _without(data, record_id):
    """``data`` as text without ``record_id``'s own records: a skill's definition, targeting
    and motion, a passive's definition - what is left is who else uses it."""
    db, library = data["rpg_database"], data["gameplay_library"]
    motions = data["battle_presentation_library"]["categories"].get("motion_sequences", {})
    trimmed = {
        **data,
        "gameplay_library": {
            **library,
            "abilities": [a for a in library["abilities"] if a["ability_id"] != record_id],
        },
        "battle_presentation_library": "",
        "rpg_database": {
            **db,
            "passives": [x for x in db["passives"] if x["passive_id"] != record_id],
            "battle_targeting": [
                x for x in db["battle_targeting"] if x.get("ability_id") != record_id
            ],
        },
    }
    return json.dumps(trimmed) + json.dumps({k: v for k, v in motions.items() if k != record_id})


def _drop(data, record_id):
    db, library = data["rpg_database"], data["gameplay_library"]
    library["abilities"] = [a for a in library["abilities"] if a["ability_id"] != record_id]
    db["passives"] = [x for x in db["passives"] if x["passive_id"] != record_id]
    db["battle_targeting"] = [
        x for x in db["battle_targeting"] if x.get("ability_id") != record_id
    ]
    data["battle_presentation_library"]["categories"].get("motion_sequences", {}).pop(
        record_id, None
    )


def remove_hero(data):
    """The Hero job, its tree, its shrine, its job points, and the skills and passives that
    only they used."""
    db = data["rpg_database"]
    candidates = set()
    for graph in db["progression_graphs"]:
        if graph["graph_id"] == "hero_tree":
            for node in graph["nodes"]:
                for reward in node.get("rewards", ()):
                    candidates.update(reward.get("granted_abilities", ()))
                    candidates.update(reward.get("unlocked_passives", ()))
    for job in db["classes"]:
        if job["class_id"] == "hero":
            candidates.update(job.get("granted_abilities", ()))
    runes = [e for e in db["ability_evolutions"] if e["rule_id"].startswith("hero.")]
    for rule in runes:
        candidates.update(v for k, v in rule.items() if k.endswith("ability_id"))
    candidates.update(
        x["ability_id"]
        for x in data["gameplay_library"]["abilities"]
        if x["ability_id"].startswith(("hero_", "heros_", "heroic_"))
    )
    candidates.update(
        x["passive_id"] for x in db["passives"] if x["passive_id"].startswith(("hero_", "heros_"))
    )
    db["classes"] = [c for c in db["classes"] if c["class_id"] != "hero"]
    db["progression_graphs"] = [
        g for g in db["progression_graphs"] if g["graph_id"] != "hero_tree"
    ]
    db["ability_evolutions"] = [e for e in db["ability_evolutions"] if e not in runes]
    for allocation in data["game_start"]["rpg_state"]["progression_allocations"].values():
        allocation.get("balances", {}).pop("jp.hero", None)
        allocation.get("allocations", {}).pop("hero_tree", None)
    _remove_shrine(data)
    removed = []
    for record_id in sorted(candidates):
        if f'"{record_id}"' not in _without(data, record_id):  # nobody else has it
            _drop(data, record_id)
            removed.append(record_id)
    icon = ICONS / "job_hero.png"
    if icon.exists():
        icon.unlink()
    return removed


# Game Systems ▸ Tags: tag or family -> (name, Chinese name, meaning, Chinese meaning)
TAGS = {
    # -- what a hit is ----------------------------------------------------------------------
    "damage.*": (
        "Element",
        "屬性",
        "The element a hit deals (damage.fire): weak.*, resist.*,"
        " immune.* and absorb.* tags of the target read it.",
        "攻擊帶的屬性（damage.fire）：目標的 weak.*、resist.*、immune.*、absorb.* 標籤會讀它。",
    ),
    "weapon.*": (
        "Weapon Type",
        "武器種類",
        "The weapon a hit is made with (weapon.sword): the"
        " target's weak.* and resist.* tags read it.",
        "攻擊使用的武器（weapon.sword）：目標的 weak.*、resist.* 標籤會讀它。",
    ),
    "physical": (
        "Physical",
        "物理",
        "A physical skill (a label for lists).",
        "物理技能（列表分類用）。",
    ),
    "magic": (
        "Magic",
        "魔法",
        "A spell: Silence blocks it, Bulwark and Reflect read it.",
        "魔法技能：沉默會封鎖它，壁壘與反射會讀它。",
    ),
    "healing": ("Healing", "治療", "A skill that restores health.", "回復生命的技能。"),
    "support": (
        "Support",
        "輔助",
        "A buff or helping skill; follow-ups and cover ignore it.",
        "增益或輔助技能；追擊與掩護不會因它觸發。",
    ),
    "divine": (
        "Divine",
        "神聖",
        "A holy skill (a label for lists).",
        "神聖系技能（列表分類用）。",
    ),
    "defense": (
        "Defensive",
        "防禦",
        "A guarding skill (a label for lists).",
        "防禦技能（列表分類用）。",
    ),
    "combo": (
        "Combo",
        "連攜",
        "A combined party attack; follow-ups and cover ignore it.",
        "隊伍連攜攻擊；追擊與掩護不會因它觸發。",
    ),
    "follow_up": (
        "Follow-up",
        "追擊",
        "A follow-up hit; it never sets off another follow-up.",
        "追擊攻擊；不會再觸發另一次追擊。",
    ),
    "finisher": (
        "Finisher",
        "終結技",
        "A finishing skill (a label for lists).",
        "終結技（列表分類用）。",
    ),
    "summon": (
        "Summon",
        "召喚",
        "A skill that calls a helper (a label).",
        "召喚幫手的技能（分類用）。",
    ),
    "pet": (
        "Pet Command",
        "寵物指令",
        "A skill that commands a pet (a label).",
        "指揮寵物的技能（分類用）。",
    ),
    "ability": (
        "Skill",
        "技能",
        "Any skill (a label every skill carries).",
        "所有技能都帶的分類標籤。",
    ),
    "outcome.*": (
        "Outcome",
        "判定結果",
        "Put on a hit by a battle check (outcome.crit, outcome.evade); gauges and rules read it.",
        "戰鬥判定加在攻擊上的結果（outcome.crit、outcome.evade）；量表與規則會讀它。",
    ),
    # -- what a battler is ------------------------------------------------------------------
    "weak.*": (
        "Weakness",
        "弱點",
        "Takes more damage from that element or weapon (a damage rule reads target weak.<x>).",
        "受該屬性或武器攻擊時傷害增加（傷害規則讀取）。",
    ),
    "resist.*": (
        "Resistance",
        "抗性",
        "Takes less damage from that element or weapon.",
        "受該屬性或武器攻擊時傷害減少。",
    ),
    "immune.*": (
        "Immunity",
        "免疫",
        "Cannot get that state or effect (immune.stun, immune.kill).",
        "不會受到該狀態或效果（immune.stun、immune.kill）。",
    ),
    "absorb.*": (
        "Absorb",
        "吸收",
        "Heals from that element instead of taking damage.",
        "受到該屬性攻擊時改為回復。",
    ),
    "reflect.*": (
        "Reflect",
        "反射",
        "Sends that kind of skill back at its user.",
        "把該類技能反彈給施放者。",
    ),
    "attune.*": (
        "Attunement",
        "屬性親和",
        "Strengthens the holder's skills of that element.",
        "強化持有者該屬性的技能。",
    ),
    "status.*": (
        "Ailment",
        "異常狀態",
        "Carried while an ailment lasts (status.poison).",
        "異常狀態持續時帶有（status.poison）。",
    ),
    "state.*": (
        "Battle State",
        "戰鬥狀態",
        "Carried while a battle state lasts (state.taunt).",
        "戰鬥狀態持續時帶有（state.taunt）。",
    ),
    "stance.*": ("Stance", "架勢", "Carried while a stance lasts.", "架勢持續時帶有。"),
    "trait.*": (
        "Trait",
        "特性",
        "A battle habit: guard, dodge, cover, follow up.",
        "戰鬥習性：防禦、閃避、掩護、追擊。",
    ),
    "boss": (
        "Boss",
        "頭目",
        "A boss enemy or fight: instant-kill skills fail, boss damage rules apply.",
        "頭目敵人或戰鬥：即死技能無效，頭目傷害規則生效。",
    ),
    "enemy": ("Enemy", "敵人", "Every enemy carries it.", "所有敵人都帶有。"),
    "class.*": (
        "Job",
        "職業",
        "Every job gives its holder class.<job>; rules can ask for it.",
        "每個職業給持有者 class.<job>；規則可以要求它。",
    ),
    "job.*": ("Job Skill", "職業技能", "A skill that belongs to that job.", "屬於該職業的技能。"),
    "capability.weapon.*": (
        "Can Wield",
        "可裝備武器",
        "Given by a job: lets the holder wield"
        " that weapon type (a weapon asks for its capability).",
        "由職業給予：可以裝備該種武器（武器會要求這個能力）。",
    ),
    "mastery.*": (
        "Mastery",
        "精通",
        "A weapon or skill mastery from the skill tree.",
        "技能樹給予的武器或技能精通。",
    ),
    "boost.*": (
        "Boost",
        "強化",
        "A skill's BP boost level or effect.",
        "技能的 BP 強化等級或效果。",
    ),
    "rune.*": (
        "Rune",
        "符文",
        "Given by a skill-tree rune node: turns a skill into its variant"
        " (Ability Evolutions read it).",
        "技能樹符文節點給予：把技能變成變化型（技能進化讀取）。",
    ),
    "school.*": (
        "School",
        "學派",
        "A spell school (the skill tree's branch).",
        "魔法學派（技能樹分支）。",
    ),
    "school": (
        "School Node",
        "學派節點",
        "A skill-tree branch node (a label).",
        "技能樹分支節點（分類用）。",
    ),
    "weather.*": ("Weather", "天氣", "The battle's weather.", "戰鬥中的天氣。"),
    # -- gear and items ---------------------------------------------------------------------
    "equip.*": (
        "Weapon Kind",
        "武器類型",
        "What weapon a piece is (equip.sword); it asks for capability.weapon.<kind>.",
        "裝備是哪種武器（equip.sword）；需要 capability.weapon.<種類>。",
    ),
    "weapon": (
        "Weapon",
        "武器",
        "Every weapon; the Weapons item tab holds them.",
        "所有武器；道具的武器分頁會收納它們。",
    ),
    "armor": (
        "Armour",
        "防具",
        "Body armour and armour pieces; the Armour tab and the armour refine rules take them.",
        "身體防具與防具部件；防具分頁與防具精煉規則會收納。",
    ),
    "armor.*": (
        "Armour Weight",
        "防具重量",
        "Light, heavy or cloth armour.",
        "輕、重或布製防具。",
    ),
    "accessory": ("Accessory", "飾品", "Rings, amulets, charms.", "戒指、護身符、飾物。"),
    "head": ("Head", "頭部", "A helmet or hat.", "頭盔或帽子。"),
    "head.*": (
        "Head Style",
        "頭部款式",
        "The helmet's style (chain, plate...).",
        "頭部裝備款式（鎖子、板甲…）。",
    ),
    "legs": ("Legs", "腿部", "Leggings.", "護腿。"),
    "legs.*": ("Legs Style", "腿部款式", "The leggings' style.", "護腿款式。"),
    "feet": ("Feet", "腳部", "Boots and shoes.", "靴子與鞋子。"),
    "feet.*": ("Feet Style", "腳部款式", "The boots' style.", "靴子款式。"),
    "form": (
        "Form",
        "形態",
        "A form piece: changes the wearer's shape and skills.",
        "形態裝備：改變穿戴者的外型與技能。",
    ),
    "form.*": ("Form Kind", "形態種類", "Which form it is.", "是哪種形態。"),
    "set.*": (
        "Set",
        "套裝",
        "Marks a piece of that equipment set (a label: the set itself, in"
        " Game Systems ▸ Equipment Sets, lists its pieces and bonuses).",
        "標示屬於該套裝的部件（分類用：套裝本身在「裝備套裝」列出部件與加成）。",
    ),
    "tier.*": (
        "Tier",
        "階級",
        "The gear's tier (stronger forged versions).",
        "裝備的階級（更強的鍛造版本）。",
    ),
    "unique": (
        "Unique",
        "唯一",
        "A one-of-a-kind piece; the Uniques filter shows it.",
        "獨一無二的裝備；唯一篩選會顯示它。",
    ),
    "gem": ("Gem", "寶石", "Fits a gem socket.", "可鑲入寶石孔。"),
    "card": ("Card", "卡片", "Fits a card socket.", "可鑲入卡片孔。"),
    "charm": ("Charm", "符咒", "Fits a charm socket.", "可鑲入符咒孔。"),
    "orb": ("Orb", "寶珠", "An element orb (a gem).", "屬性寶珠（寶石的一種）。"),
    "consumable": (
        "Consumable",
        "消耗品",
        "Used up when used; the Consumables tab holds it.",
        "使用後消失；消耗品分頁收納。",
    ),
    "potion": (
        "Potion",
        "藥水",
        "A potion; the Potions tab and filter hold it.",
        "藥水；藥水分頁與篩選收納。",
    ),
    "cure": ("Cure", "治療藥", "Removes ailments.", "解除異常狀態。"),
    "concoction": ("Concoction", "調合品", "Made at the alchemy table.", "在鍊金台調合而成。"),
    "throwable": (
        "Throwable",
        "投擲物",
        "Thrown at enemies; the Throwables tab holds it.",
        "丟向敵人；投擲物分頁收納。",
    ),
    "bomb": (
        "Bomb",
        "炸彈",
        "A forged bomb (the forge's Bombs tab).",
        "鍛造的炸彈（鍛造台炸彈分頁）。",
    ),
    "material": (
        "Material",
        "素材",
        "Crafting material; the Materials tab holds it.",
        "製作素材；素材分頁收納。",
    ),
    "fuse": (
        "Fusion",
        "融合",
        "A gem fusion recipe (the forge's tab).",
        "寶石融合配方（鍛造台分頁）。",
    ),
    "smelt": (
        "Smelting",
        "冶煉",
        "A smelting recipe (the forge's tab).",
        "冶煉配方（鍛造台分頁）。",
    ),
    "light": ("Light", "輕型", "A light pet (a label).", "輕型寵物（分類用）。"),
    # -- skill trees ------------------------------------------------------------------------
    "keystone": (
        "Keystone",
        "關鍵節點",
        "A skill-tree node that changes how a build plays.",
        "改變玩法的技能樹節點。",
    ),
    "notable": ("Notable", "重要節點", "A larger skill-tree node.", "較大的技能樹節點。"),
    "capstone": ("Capstone", "頂點節點", "The last node of a branch.", "分支的最後節點。"),
    "ultimate": ("Ultimate", "奧義", "An ultimate skill node.", "奧義技能節點。"),
    "spec": ("Specialisation", "專精", "A specialisation node.", "專精節點。"),
    "rune": (
        "Rune Node",
        "符文節點",
        "A rune node (gives a rune.* tag).",
        "符文節點（給予 rune.* 標籤）。",
    ),
    "mastery": ("Mastery Node", "精通節點", "A mastery node.", "精通節點。"),
    "book": ("Book Node", "書籍節點", "A node of the book branch.", "書籍分支的節點。"),
    "attunement": ("Attunement Node", "親和節點", "An attunement node.", "屬性親和節點。"),
    "berserk": ("Berserk Node", "狂暴節點", "The knight's berserk node.", "騎士的狂暴節點。"),
    "attributes": (
        "Attributes Board",
        "能力值盤",
        "The shared stat-point board.",
        "共用的能力點數盤。",
    ),
    "shared": ("Shared Board", "共用盤", "A board every job shares.", "所有職業共用的盤面。"),
    "gate": ("Gate", "關卡節點", "A Fate Web gate node.", "命運之網的關卡節點。"),
    "bridge": ("Bridge", "橋接節點", "A Fate Web bridge node.", "命運之網的橋接節點。"),
    # -- battles and the world --------------------------------------------------------------
    "no_escape": (
        "No Escape",
        "無法逃跑",
        "The party cannot run from this battle.",
        "隊伍無法從這場戰鬥逃跑。",
    ),
    "multi_phase": (
        "Several Phases",
        "多階段",
        "A boss fight in phases (a label).",
        "分階段的頭目戰（分類用）。",
    ),
    "stress": (
        "Stress Test",
        "壓力測試",
        "A crowded test fight (a label).",
        "大量敵人的測試戰（分類用）。",
    ),
    "scheduler:*": (
        "Turn Scheduler",
        "回合排程",
        "Runs the battle with that scheduler.",
        "用該排程進行戰鬥。",
    ),
    "objective:*": ("Objective", "戰鬥目標", "Gives the battle that objective.", "給戰鬥該目標。"),
    "rules:*": (
        "Battle Rules",
        "戰鬥規則",
        "Runs the battle with those rules.",
        "用那套規則進行戰鬥。",
    ),
    "escape:*": ("Escape Rules", "逃跑規則", "Uses those escape rules.", "使用那套逃跑規則。"),
    "stage:*": (
        "Battle Stage",
        "戰鬥舞台",
        "Lays the battle out on that stage.",
        "在該舞台佈置戰鬥。",
    ),
    "crypt": ("Crypt", "地下墓穴", "A crypt fight (a label).", "地下墓穴的戰鬥（分類用）。"),
    "woods": ("Woods", "森林", "A woods fight (a label).", "森林的戰鬥（分類用）。"),
    "throne": ("Throne", "王座", "The throne-room vigil (a label).", "王座廳守夜戰（分類用）。"),
    "vigil.*": ("Vigil", "守夜", "The vigil fight's states.", "守夜戰的狀態。"),
    "front": ("Front Row", "前排", "A front-row place of a formation.", "陣型的前排位置。"),
    "back": ("Back Row", "後排", "A back-row place of a formation.", "陣型的後排位置。"),
    "decor": ("Decoration", "裝飾", "A doodad placed for looks.", "純裝飾的擺設。"),
}
# tags the demo's data carries that the families above leave out
for _tag, _row in {
    "action.*": ("Action", "行動", "A special battle action (steal).", "特殊戰鬥行動（偷竊）。"),
    "actor.*": ("Actor Kind", "角色種類", "Who an actor is (playable).", "角色是誰（可操作）。"),
    "item.*": ("Item Kind", "道具種類", "What an item is (a key).", "道具是什麼（鑰匙）。"),
    "combatant": ("Combatant", "戰鬥者", "Anyone who fights.", "參與戰鬥的任何人。"),
    "hero": ("Party Member", "隊員", "A party member (the hero side).", "隊伍成員（我方）。"),
    "icon": ("Icon", "圖示", "A picture's role (a label).", "圖片的用途（分類用）。"),
    "particles": ("Particles", "粒子", "A particle effect (a label).", "粒子效果（分類用）。"),
    "vfx": ("Visual Effect", "視覺效果", "A visual effect (a label).", "視覺效果（分類用）。"),
    "reference.*": (
        "Reference",
        "參考",
        "A reference record (a label).",
        "參考用的資料（分類用）。",
    ),
    "roster.*": ("Roster", "名單", "A party roster (a label).", "隊伍名單（分類用）。"),
}.items():
    TAGS.setdefault(_tag, _row)


# weapon type -> the jobs that may wield it besides the Brave (who wields every one)
EXTRA_WEAPONS = {
    "book": ("archmage", "sage", "bishop", "priest", "mystic", "lich", "heretic"),
    "fist": ("weapon_master", "rogue", "zealot"),
    "throw": ("weapon_master", "rogue", "duelist"),
}
# the Hero's skills no other job has: the Brave, the Hero's heir, keeps its own; the party
# rally goes to the Guardian, the support job
BRAVE_SKILLS = ("brave_slash", "dawn_and_dusk", "twilight_judgment", "dragon_form")
INHERITED = {"guardian": ("rally_cry",)}


def patch_tags(db):
    """Game Systems ▸ Tags: every tag the demo uses, alone or by its family."""
    db["tag_definitions"] = [
        {
            "schema": "asteria.rpg.tag_definition",
            "version": 1,
            "tag_id": tag,
            "display_name": name,
            "description": meaning,
            "order": order,
        }
        for order, (tag, (name, _zh, meaning, _zh_meaning)) in enumerate(TAGS.items())
    ]


def patch_weapons(db):
    """A weapon asks for its type's capability (``equip.sword`` needs
    ``capability.weapon.sword``): the jobs' weapon lists now decide who can wield what. The
    Brave wields every type and keeps the Hero's light-and-dark skills."""
    cap = "capability.weapon."
    types = sorted(
        {t.split(".", 1)[1] for e in db["equipment"] for t in e["tags"] if t.startswith("equip.")}
    )
    jobs = {c["class_id"]: c for c in db["classes"]}
    for kind, holders in EXTRA_WEAPONS.items():
        for job in holders:
            if job in jobs:
                tags = jobs[job]["granted_tags"]
                jobs[job]["granted_tags"] = sorted({*tags, cap + kind})
    brave = jobs["brave"]
    brave["granted_tags"] = sorted({*brave["granted_tags"], *(cap + t for t in types)})
    brave["granted_abilities"] = list(dict.fromkeys([*brave["granted_abilities"], *BRAVE_SKILLS]))
    brave["granted_abilities"] = [a for a in brave["granted_abilities"] if a != "rally_cry"]
    for job, skills in INHERITED.items():
        held = jobs[job]["granted_abilities"]
        jobs[job]["granted_abilities"] = list(dict.fromkeys([*held, *skills]))
    for piece in db["equipment"]:
        kinds = [t.split(".", 1)[1] for t in piece["tags"] if t.startswith("equip.")]
        if piece["slot"] == "weapon" and kinds:
            piece["any_capabilities"] = sorted(cap + k for k in kinds)


def _remove_shrine(data):
    program = "town.heros_shrine"
    data["event_programs"].pop(program, None)
    for bindings in data["scene_event_bindings"].values():
        bindings["bindings"] = [b for b in bindings["bindings"] if b.get("program_id") != program]
    for scene in data["scenes"]:
        scene["entities"] = [e for e in scene["entities"] if program not in json.dumps(e)]


def job_icons(db):
    """Each job's picture from the demo's gear art (``JOB_ICONS``)."""
    from PIL import Image

    def diagonal(path):
        image = Image.open(path).convert("RGBA")
        if image.width == image.height:
            return image  # a helmet, a robe: as drawn
        turned = image.rotate(45, resample=Image.NEAREST, expand=True)
        return turned.crop(turned.getbbox())

    for job, sources in JOB_ICONS.items():
        pictures = [diagonal(ICONS / f"{name}.png") for name in sources]
        if len(pictures) == 2:  # two blades: one turned the other way, both over each other
            pictures[1] = pictures[1].transpose(Image.FLIP_LEFT_RIGHT)
        canvas = Image.new("RGBA", (32, 32))
        for picture in pictures:
            scale = 30 / max(picture.size)
            size = (max(1, round(picture.width * scale)), max(1, round(picture.height * scale)))
            picture = picture.resize(size, Image.NEAREST)
            canvas.alpha_composite(picture, ((32 - size[0]) // 2, (32 - size[1]) // 2))
        canvas.save(ICONS / f"job_{job}.png")
        for record in db["classes"]:
            if record["class_id"] == job:
                record["icon_id"] = f"playable_assets/lucifer/icons/job_{job}.png"


def patch_menu(db):
    for rules in db["menu_rules"]:
        for line in rules.get("stat_lines", ()):
            if line["stat_id"] == "lifesteal":
                line["format"] = "share"  # 0.12 reads 12%


def patch_words(data):
    db = data["rpg_database"]
    tables = {t["locale"]: t["entries"] for t in db["locale_tables"]}
    screens = data["battle_presentation_library"]["categories"]["rpg_character_screen"]
    for screen in screens.values():  # the screen's labels: the stats' own names (Stats)
        labels = {**screen["stat_labels"], **{s: v[0] for s, v in STATS.items()}}
        screen["stat_labels"] = dict(sorted(labels.items()))
    for stat, (_n, _s, zh, zh_short, _d, _o, _t, zh_text) in STATS.items():
        tables["zh-TW"][f"data.stat.{stat}.name"] = zh
        tables["zh-TW"][f"data.stat.{stat}.short"] = zh_short
        tables["zh-TW"][f"data.stat.{stat}.description"] = zh_text
    from asteria.rpg.built_in_text import engine_translations

    for word, chinese in engine_translations("zh-TW").items():  # the engine's new words (D91)
        tables["zh-TW"].setdefault(word, chinese)
    for tag, (_n, zh, _m, zh_meaning) in TAGS.items():
        tables["zh-TW"][f"data.tag.{tag}.name"] = zh
        tables["zh-TW"][f"data.tag.{tag}.description"] = zh_meaning
    for locale in tables:
        for key in [k for k in tables[locale] if k.startswith("data.class.hero.")]:
            tables[locale].pop(key)


def main():
    path = HERE / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    db = data["rpg_database"]
    patch_stats(db)
    patch_base_stats(db)
    removed = remove_hero(data)
    print("removed with the Hero job:", ", ".join(removed) or "nothing else")
    job_icons(db)
    patch_weapons(db)
    patch_tags(db)
    patch_menu(db)
    patch_words(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("stats defined, base stats only, the Hero job gone, job pictures drawn")


if __name__ == "__main__":
    main()
