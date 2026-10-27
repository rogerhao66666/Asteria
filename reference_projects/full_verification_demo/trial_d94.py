"""D94: formulas written as text, reading only the stats Game Systems ▸ Stats declares.

Two examples a beginner can copy, each giving the same numbers as the fields it replaces (so
every battle of the demo plays as before):

* **Accuracy** (Game Systems ▸ Stat Formulas): ``self.dex + 0.5 * self.luk`` - it was Read From
  DEX 1, LUK 0.5. Its Read From list is cleared, so the formula is plainly what counts.
* **Land** (Battle Rules ▸ Chance Checks): ``0.95 + 0.003 * source.accuracy - 0.003 *
  target.evade`` - it was a base chance of 0.95 with the accuracy and evasion terms (cleared
  too); the lowest (30%) and highest (100%) chance still apply.

The other stat formulas and checks keep their fields: an empty formula uses them. Run it once
over ``project.asteria.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCURACY = "self.dex + 0.5 * self.luk"
LAND = "0.95 + 0.003 * source.accuracy - 0.003 * target.evade"


def main():
    path = HERE / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    db = data["rpg_database"]
    (accuracy,) = [r for r in db["derived_stats"] if r["stat_id"] == "accuracy"]
    assert accuracy["terms"] == {"dex": 1.0, "luk": 0.5} and accuracy["base"] == 0.0
    accuracy["terms"] = {}
    accuracy["expression"] = ACCURACY
    (land,) = [c for c in db["outcome_checks"] if c["check_id"] == "land"]
    assert land["base_chance"] == 0.95
    assert land["source_stat_terms"] == {"accuracy": 0.003}
    assert land["target_stat_terms"] == {"evade": -0.003}
    land["source_stat_terms"], land["target_stat_terms"] = {}, {}
    land["chance_expression"] = LAND
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("accuracy and land are written as formulas")


if __name__ == "__main__":
    main()
