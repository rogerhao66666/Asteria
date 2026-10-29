from __future__ import annotations

import json
import random
from pathlib import Path

from asteria.gameplay import (
    GameplaySubject,
    ResourcePool,
    StatBlock,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    TagSet,
)
from asteria.rpg import BattleStateRuntime, PartyMember, RpgDatabase

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "reference_projects" / "legacy" / "AsteriaPhase7B_BattleStatesDemo.asteria.json"


def make_subject(state_defs, *, stats=None, tags=()):
    sb = StatBlock(
        stats or {"status_power": 0, "status_resist": 0, "control_resist": 0, "speed": 10}
    )
    rp = ResourcePool()
    rp.define("hp", 100, current=100)
    ts = TagSet(tags)
    sr = StateRuntime(StateRegistry(state_defs), sb, rp, ts)
    return GameplaySubject(sb, rp, ts, sr)


def main():
    raw = json.loads(PROJECT.read_text())
    db = RpgDatabase.from_data(raw["rpg_database"])
    defs = [StateDefinition.from_data(x) for x in raw["gameplay_library"]["states"]]
    states = BattleStateRuntime(db.battle_state_policies.values())
    hero = make_subject(
        defs, stats={"status_power": 20, "status_resist": 0, "control_resist": 0, "speed": 12}
    )
    boss = make_subject(
        defs,
        stats={"status_power": 0, "status_resist": 10, "control_resist": 30, "speed": 8},
        tags=("immune.control",),
    )
    poison = states.apply("poison", "hero", hero, "boss", boss, rng=random.Random(1))
    assert poison.applied and poison.chance == 0.85
    assert boss.states.get("poison").source_id == "hero"
    stun = states.apply("stun", "hero", hero, "boss", boss, rng=random.Random(1))
    assert stun.immune and not stun.applied
    hero.states.apply("silence", source_id="boss")
    assert not states.ability_availability(hero, ("ability.magic",)).allowed
    assert states.ability_availability(hero, ("ability.physical",)).allowed
    hero.states.apply("sleep", source_id="boss")
    member = PartyMember("hero", "heroes", hero)
    states.apply_trigger("rpg.battle.damage_received", (member,))
    assert hero.states.get("sleep") is None
    boss_member = PartyMember("boss", "enemies", boss)
    states.apply_trigger("rpg.battle.turn_ended", (boss_member,))
    assert boss.resources.current("hp") == 94
    hero.states.apply("doom", source_id="boss")
    for _ in range(3):
        states.apply_trigger("rpg.battle.turn_ended", (member,))
    assert hero.resources.current("hp") == 0
    snap = boss.states.snapshot()
    restored = make_subject(defs)
    restored.states.restore(snap)
    assert restored.states.get("poison").source_id == "hero"
    print("Batch 83 battle states demo PASS")
    print("poison_chance=", poison.chance)
    print("boss_stun_immune=", stun.immune)
    print("boss_hp_after_poison_tick=", boss.resources.current("hp"))
    print("hero_hp_after_doom=", hero.resources.current("hp"))


if __name__ == "__main__":
    main()
