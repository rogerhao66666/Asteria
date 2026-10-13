from asteria.gameplay import GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.rpg import BattleScheduler, BattleSchedulerDefinition, PartyMember, RpgDatabase
import json
from pathlib import Path


def s():
    return GameplaySubject(StatBlock(), ResourcePool(), TagSet())


root = Path(__file__).resolve().parents[2]
project = json.loads((root / "AsteriaPhase7B_BattleSchedulerDemo.asteria.json").read_text())
db = RpgDatabase.from_data(project["rpg_database"])
definition = db.battle_schedulers["continuous.demo"]
members = [
    PartyMember("fast_hero", "heroes", s(), initiative=100),
    PartyMember("normal_enemy", "enemies", s(), initiative=50),
    PartyMember("slow_enemy", "enemies", s(), initiative=25),
]
scheduler = BattleScheduler(members, definition)
order = [scheduler.pop().member_id for _ in range(6)]
assert order == [
    "fast_hero",
    "fast_hero",
    "normal_enemy",
    "fast_hero",
    "fast_hero",
    "normal_enemy",
], order
snap = scheduler.to_data()
restored = BattleScheduler.from_data(snap, members)
assert restored.to_data() == snap
print("Batch 86 scheduler demo PASS")
print("order:", " -> ".join(order))
print("timeline:", scheduler.current_time, "round:", scheduler.round_index)
