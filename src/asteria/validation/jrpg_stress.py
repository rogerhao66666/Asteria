"""JRPG stress test (STR-01, ASTERIA_SPEC §35) on the complex reference project's real game session.

One new game of the reference project, played through ``GameSessionRuntime`` (the same session the
playable game and its editor use): build edits, an NPC interaction, then the multi-phase boss fought
turn by turn under the battle scheduler. Every §35 item is recorded with the evidence that showed it.

Two pieces of content the reference project does not author yet are added the way a designer would,
through the canonical database API, before the run: a capture rule (Mender Wisp joins as a companion)
and a "talk" world interaction. No engine code is special-cased for this scenario.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from asteria.rpg.capture import CaptureRule
from asteria.rpg.world_interactions import WorldInteraction

ITEMS = (
    "four_character_party",
    "jobs_secondary_jobs",
    "weaknesses",
    "multi_hit",
    "guard_shield_resource",
    "break_mechanic",
    "boost_resource",
    "passives",
    "turn_order_manipulation",
    "equipment_interactions",
    "npc_interactions",
    "capture_companion",
    "multi_phase_boss",
)


@dataclass
class StressReport:
    evidence: dict = field(default_factory=dict)  # item -> detail (str) when demonstrated
    log_kinds: dict = field(default_factory=dict)
    turns: int = 0
    outcome: str = ""

    @property
    def missing(self):
        return [item for item in ITEMS if item not in self.evidence]


def _resource(battle, member, name):
    try:
        return battle.battle_resources.current(member, name)
    except (KeyError, ValueError):
        return None


def _queue(battle):
    """Upcoming turns as ``(member, ready_time)`` from the battle scheduler."""
    return [(t.member_id, round(t.ready_time, 3)) for t in battle.scheduler.pending()]


def run_jrpg_stress(project, *, seed=7, max_turns=400):
    from asteria.runtime.game_session import GameSessionRuntime

    report = StressReport()
    ev = report.evidence
    db = project.rpg_database
    if "mender_wisp" not in db.capture_rules:
        companion = next(
            a for a in db.actors if a not in project.game_start.instantiate(project).rpg_state.party_actor_ids
        )
        db.add_capture_rule(CaptureRule("mender_wisp", companion, base_chance=0.6, low_health_bonus=0.4))
    if "stress_talk" not in db.world_interactions:
        db.add_world_interaction(
            WorldInteraction(
                "stress_talk", "Talk to the guide", "talk", base_chance=1.0, success_switch="stress_talked"
            )
        )

    save = project.game_start.instantiate(project)
    game = GameSessionRuntime(project, save)
    state = save.rpg_state

    # -- party, jobs, passives, equipment (field, before the battle) ------------------------------
    party = state.party_actor_ids[:4]
    game.set_active_party(party, {actor: f"slot_{i + 1}" for i, actor in enumerate(party)})
    if len(state.party_active_actor_ids) == 4:
        ev["four_character_party"] = f"active party {state.party_active_actor_ids}"
    lead = party[0]
    progress = state.actor_progression[lead]
    before = set(game.resolve_actor_build(lead).abilities)
    alternate = next(x for x in progress.unlocked_class_ids if x not in progress.active_class_ids)
    game.set_secondary_class(lead, alternate)
    gained = set(game.resolve_actor_build(lead).abilities) - before
    if state.actor_progression[lead].active_class_ids[-1] == alternate:
        ev["jobs_secondary_jobs"] = f"{lead} secondary job {alternate}: +{sorted(gained) or 'class bonuses'}"
    game.set_passives(lead, ("passive_01", "passive_02"), capacity=4)
    if game.resolve_actor_build(lead).active_passives:
        ev["passives"] = f"{lead} passives {game.resolve_actor_build(lead).active_passives}"
    before_build = game.resolve_actor_build(lead)
    weapon = game.equip_definition(lead, "weapon_12")
    after_build = game.resolve_actor_build(lead)
    granted = sorted(set(after_build.abilities) - set(before_build.abilities))
    if weapon is not None and weapon.instance_id in after_build.equipment_instance_ids and granted:
        ev["equipment_interactions"] = f"weapon_12 equipped on {lead}: grants {granted}"

    # -- NPC interaction ---------------------------------------------------------------------------
    outcome, _detail = game.perform_interaction("stress_talk")
    if outcome == "success" and save.event_context.get_switch("stress_talked"):
        ev["npc_interactions"] = "talk interaction succeeded and set its switch"

    # -- the boss, turn by turn under the battle scheduler -------------------------------------------
    battle = game.start_encounter("boss_room")
    boss = next(x for x in game.active_enemy_ids() if x.startswith("astral_tyrant"))
    rules = game.rules
    phases_seen = []
    stagger_start = _resource(battle, boss, "stagger")
    done = set()

    def note_phase():
        phase = battle.enemy_ai.phases.get(boss)
        if phase and (not phases_seen or phases_seen[-1] != phase):
            phases_seen.append(phase)

    for _ in range(max_turns):
        if not game.active_enemy_ids() or not game.active_hero_ids():
            break
        actor, _enemy_log = game.run_enemy_turns()
        note_phase()
        if actor is None:
            break
        report.turns += 1
        abilities = set(game.resolve_actor_build(actor).abilities)
        enemies = game.active_enemy_ids()
        boss_alive = boss in enemies
        wisp = next((e for e in enemies if e.startswith("mender_wisp")), None)
        if "capture" not in done and wisp is not None:
            done.add("capture")
            if game.attempt_capture(actor, wisp, rng=random.Random(seed)):
                joined = db.capture_rules["mender_wisp"].actor_id
                ev["capture_companion"] = f"{wisp} captured in battle; {joined} joined the roster"
        elif "haste" not in done and "haste_song" in abilities:
            done.add("haste")
            ally = next(h for h in game.active_hero_ids() if h != actor)
            before = dict(_queue(battle))
            game.use_ability(actor, "haste_song")
            after = dict(_queue(battle))
            moved = {m: (before[m], after[m]) for m in after if m in before and after[m] < before[m]}
            if moved:
                ev["turn_order_manipulation"] = f"haste_song brought turns forward: {moved}"
            del ally
        elif "slow" not in done and "slow_hex" in abilities and boss_alive:
            done.add("slow")
            before = dict(_queue(battle)).get(boss)
            game.use_ability(actor, "slow_hex", (boss,))
            after = dict(_queue(battle)).get(boss)
            if before is not None and after is not None and after > before:
                ev.setdefault("turn_order_manipulation", f"slow_hex pushed {boss} back: {before} -> {after}")
        elif boss_alive and "fire_arc" in abilities and _resource(battle, boss, "stagger"):
            level = game.max_boost_level(actor) if "boost" not in done else 0
            stagger_before = _resource(battle, boss, "stagger")
            boss_ready = dict(_queue(battle)).get(boss)
            results = game.use_ability(actor, "fire_arc", (boss,), boost_level=level)  # failures must surface
            if level >= 1 and len(results) >= 2:
                done.add("boost")
                ev["boost_resource"] = f"{actor} boost {level} ({rules.boost_resource_id}): {len(results)} actions"
                ev["multi_hit"] = f"fire_arc landed {len(results)} hits from one command"
            stagger_after = _resource(battle, boss, "stagger")
            if results and stagger_after is not None and stagger_before is not None and stagger_after < stagger_before:
                ev.setdefault(
                    "weaknesses", f"fire_arc hit the boss's fire weakness: stagger {stagger_before} -> {stagger_after}"
                )
                ev["guard_shield_resource"] = f"boss stagger shield {stagger_start} -> {stagger_after}"
            if stagger_after == 0 or (stagger_before == 1 and results and stagger_after == stagger_start):
                broken = battle.member(boss).subject.states.get("broken") is not None
                ev.setdefault(
                    "break_mechanic", f"boss stagger shield broken after {report.turns} turns (broken={broken})"
                )
                delayed = dict(_queue(battle)).get(boss)
                if boss_ready is not None and delayed is not None and delayed > boss_ready:
                    ev["turn_order_manipulation"] = (
                        f"the break pushed the boss's next turn back {boss_ready} -> {delayed}"
                    )
        elif enemies:
            target = boss if boss_alive else enemies[0]
            game.use_ability(actor, "strike", (target,))
        note_phase()
        game.end_turn()
    for entry in game.drain_battle_log():
        report.log_kinds[entry.kind] = report.log_kinds.get(entry.kind, 0) + 1
    if len(phases_seen) >= 2:
        ev["multi_phase_boss"] = f"boss phases {phases_seen}"
    if not game.active_enemy_ids():
        report.outcome = "victory"
    elif not game.active_hero_ids():
        report.outcome = "defeat"
    else:
        report.outcome = "unfinished"
    return report, game
