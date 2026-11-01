"""D100: the Crimson boss's skills get names a player understands at a glance; they were made
from their ids (``w_iron`` -> "W Iron"). The ids stay, so every rule and phase still finds
them."""

import json
from pathlib import Path

NAMES = {  # what each one does (its description) said as a name
    "w_charge": "Crushing Charge",  # axe blow: Defence Down, Power Down
    "w_cinder": "Cinder Blast",  # fire magic: Burn
    "w_combo": "Triple Slash",  # 3 sword hits: Bleed
    "w_counter": "Axe Counter",
    "w_cry": "War Cry",  # Fury stance, Attack Up
    "w_drain": "Dark Drain",  # dark magic: heals the user
    "w_eclipse": "Eclipse",  # dark + fire, 4 hits: Silence
    "w_iron": "Iron Stance",  # Bulwark stance, Ward
    "w_mark": "Doom Mark",  # dark magic: Defence Down
    "w_mend": "Mend",
    "w_poison": "Venom Stab",  # 2 dagger hits: Poison, Bleed
    "w_roar": "Thunder Roar",  # lightning, 2 hits: Stun
    "w_summon": "Summon Minions",
}

ZH = {  # the game's Traditional Chinese names (locale table zh-TW)
    "w_charge": "粉碎衝鋒",
    "w_cinder": "餘燼爆破",
    "w_combo": "三連斬",
    "w_counter": "斧擊反擊",
    "w_cry": "戰吼",
    "w_drain": "黑暗吸取",
    "w_eclipse": "日蝕",
    "w_iron": "鋼鐵架勢",
    "w_mark": "厄運印記",
    "w_mend": "治癒",  # the glossary's Mend
    "w_poison": "毒刃刺擊",
    "w_roar": "雷鳴咆哮",
    "w_summon": "召喚僕從",
}

path = Path("reference_projects/full_verification_demo/project.asteria.json")
raw = json.loads(path.read_text(encoding="utf-8"))
for ability in raw["gameplay_library"]["abilities"]:
    if ability["ability_id"] in NAMES:
        ability["display_name"] = NAMES[ability["ability_id"]]
for table in raw["rpg_database"]["locale_tables"]:
    if table.get("locale") == "zh-TW":
        for ability_id, name in ZH.items():
            table["entries"][f"data.ability.{ability_id}.name"] = name
path.write_text(json.dumps(raw, indent=2) + "\n")
