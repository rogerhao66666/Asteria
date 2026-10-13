"""Verify Batch 81 against one canonical Asteria Project definition set."""

from pathlib import Path
import json

from asteria.editor.model import EditorDocument
from asteria.editor.storage import load_document
from asteria.gameplay import (
    AbilityRegistry,
    AbilityRuntime,
    GameplaySubject,
    ResourcePool,
    StatBlock,
    TagSet,
)
from asteria.rpg import BattleRuntime, Party, PartyMember

root = Path(__file__).resolve().parents[2]
document = EditorDocument()
load_document(document, root / "AsteriaPhase7B_BattleResourcesDemo.asteria.json")
project = document.project
db = project.rpg_database

assert set(db.battle_resources) == {"mp", "rage", "boost", "stagger", "combo"}

hero_resources = ResourcePool()
hero_resources.define("hp", 120, current=120)
hero_resources.define("mp", 60, current=42)
hero = PartyMember(
    "aria",
    "heroes",
    GameplaySubject(StatBlock({"speed": 18}), hero_resources, TagSet()),
    initiative=18,
)

enemy_resources = ResourcePool()
enemy_resources.define("hp", 300, current=300)
enemy_resources.define("mp", 20, current=20)
enemy = PartyMember(
    "iron_beetle",
    "monsters",
    GameplaySubject(StatBlock({"speed": 6}), enemy_resources, TagSet()),
    initiative=6,
)

battle = BattleRuntime(
    [Party("heroes", [hero]), Party("monsters", [enemy])],
    AbilityRuntime(AbilityRegistry()),
    resource_definitions=db.battle_resources.values(),
)
r = battle.battle_resources

# Battle start + first round: boost starts at 1 then round rule grants +1.
assert r.current("aria", "boost") == 2
assert r.current("aria", "rage") == 0
assert r.current("aria", "stagger") == 100
assert r.current("aria", "mp") == 42

# Explicit domain events remain arbitrary strings and can be driven later by
# outcome/interaction resolution without changing the resource engine.
r.apply_trigger("demo.successful_hit", ["aria"])
r.apply_trigger("demo.weakness_hit", ["iron_beetle"])
assert r.current("aria", "combo") == 2
assert r.current("iron_beetle", "stagger") == 75

# Turn lifecycle rule: Aria gains rage after completing a turn.
assert battle.next_actor().member_id == "aria"
battle.advance_turn()
assert r.current("aria", "rage") == 10

snapshot = r.to_data()
(root / "reference_data" / "phase7b_batch81_battle_resources.snapshot.json").write_text(
    json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
)

print("PASS — Asteria Phase 7B Batch 81 Battle Resources / Gauges Demo")
print("Project:", project.name)
for member_id in ("aria", "iron_beetle"):
    values = {key: r.current(member_id, key) for key in db.battle_resources}
    print(member_id, values)
