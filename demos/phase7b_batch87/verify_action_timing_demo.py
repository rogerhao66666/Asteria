import json
from pathlib import Path

from asteria.rpg import (
    ActionTimingDefinition,
    BattleAction,
    BattleActionTimingRuntime,
    RpgDatabase,
)

root = Path(__file__).resolve().parents[2]
project = json.loads((root / "AsteriaPhase7B_ActionTimingDemo.asteria.json").read_text())
db = RpgDatabase.from_data(project["rpg_database"])
meteor = db.action_timings["meteor"]
assert meteor.windup == 5.0
assert meteor.recovery == 2.0
assert meteor.priority == 10

runtime = BattleActionTimingRuntime(db.action_timings.values())
pending = runtime.begin(BattleAction("hero", "meteor", ("boss",)), current_time=12.0)
assert pending.resolve_at == 17.0
assert not runtime.interrupt("hero", power=4).interrupted
assert runtime.interrupt("hero", power=5).interrupted

snapshot = runtime.to_data()
restored = BattleActionTimingRuntime.from_data(snapshot)
assert restored.to_data() == snapshot
print("Batch 87 action timing demo PASS")
print("meteor: startup=1 cast=4 recovery=2 priority=10 interrupt_threshold=5")
