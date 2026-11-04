"""The stat formulas are one set for both sides, and they are written plainly: what a stat comes
to is read off its STR, DEX, INT, LUK and VIT, with no fixed amounts of a hero's own.

The fixed amounts move into every hero's base stats (``POINTS``: the whole numbers that come
closest). Each formula's terms are the same for each hero, so all five change alike. Enemies hold
none of those stats, so a formula adds nothing to them but half their DEF in MDEF; that half
comes off their own MDEF, which grows at DEF's rate, so the sum is what it was. Heroes come out
with about 20 more MDEF, and a skill's damage takes off a multiple of it, so a monster's MATK
rises by what buys back that damage (``_raised_magic``). ``bp_power`` keeps its 100: no stat
stands for it, and no monster has a boost skill to read it.

Run once: ``python reference_projects/full_verification_demo/trial_shared_formulas.py``.
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
POINTS = {"str": 11, "int": 12, "luk": 5, "vit": 6}
KEPT_BASE = ("bp_power",)
HERO_MAGIC_DEFENSE = 20.25  # +12 INT, +2.5 from LUK, +6 VIT, and half a DEF 20.5 -> 20 lower


def _terms(ability):
    """Every formula's terms in ``ability``."""
    found, stack = [], [ability]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("terms"), list):
                found.append(node["terms"])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found


def _raised_magic(enemy, abilities):
    """The MATK that buys back what the heroes' extra MDEF takes off this monster's spells."""
    needed = []
    for ability_id in enemy.get("abilities", ()):
        for terms in _terms(abilities.get(ability_id, {})):
            by_key = {(t.get("source"), t.get("key")): t.get("coefficient", 0) for t in terms}
            spell = by_key.get(("source_stat", "magic"), 0)
            ward = by_key.get(("target_stat", "magic_defense"), 0)
            if spell < 0 and ward > 0:
                needed.append(HERO_MAGIC_DEFENSE * ward / -spell)
    return math.ceil(sum(needed) / len(needed)) if needed else 0


def patch(data):
    db = data["rpg_database"]
    library = data["gameplay_library"]["abilities"]
    abilities = {a["ability_id"]: a for a in library} if isinstance(library, list) else library
    rules = {r["stat_id"]: r for r in db["derived_stats"]}
    assert all(r["applies_to"] == "actors" for r in rules.values())
    for stat, rule in rules.items():
        rule["applies_to"] = "all"
        if stat not in KEPT_BASE:
            rule["base"] = 0.0
    for actor in db["actors"]:
        for stat, points in POINTS.items():
            actor["base_stats"][stat] = actor["base_stats"][stat] + points
    half = rules["magic_defense"]["terms"]["defense"]
    for enemy in db["enemies"]:
        stats = enemy["stats"]
        stats["magic_defense"] = round(stats["magic_defense"] - half * stats["defense"], 4)
        assert stats["magic_defense"] >= 0, enemy["enemy_id"]
        stats["magic"] = round(stats["magic"] + _raised_magic(enemy, abilities), 4)


def main():
    path = HERE / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    patch(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
