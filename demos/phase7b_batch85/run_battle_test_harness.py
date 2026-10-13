"""Batch 85 developer battle harness.

Exercises real-window targeting plus combatant lifecycle/objectives. This is
intentionally a developer sandbox, not final RPG presentation.

Controls:
  1-4       choose an ability
  click     choose highlighted manual target
  Enter     execute selected manual action
  Space     execute auto-target abilities
  K         incapacitate selected/current combatant
  V         revive selected/current combatant
  S         summon a temporary ally
  T / Y     transform / revert Aria
  E         attempt hero escape
  R         restart
  Esc       quit
"""

from __future__ import annotations

import random

import pygame

from asteria.gameplay import (
    AbilityDefinition,
    AbilityEffect,
    AbilityRegistry,
    AbilityRuntime,
    AbilityTargetMode,
    Effect,
    EffectOperation,
    EffectOperationKind,
    GameplaySubject,
    ResourcePool,
    StatBlock,
    TagSet,
    TargetingRule,
)
from asteria.rpg import (
    BattleAction,
    BattleEscapeRule,
    BattleObjectiveCondition,
    BattleObjectiveDefinition,
    BattleFormationRuntime,
    BattlePlacement,
    BattleRuntime,
    BattleTargetingDefinition,
    FormationDefinition,
    FormationSlotDefinition,
    Party,
    PartyMember,
)

WIDTH, HEIGHT = 1120, 680


def make_subject(hp=100, tags=()):
    resources = ResourcePool()
    resources.define("hp", 100, current=hp)
    return GameplaySubject(StatBlock(), resources, TagSet(tags))


def make_ability_runtime():
    registry = AbilityRegistry()
    for ability_id, name, amount, max_targets in (
        ("strike", "Strike", -14, 1),
        ("sweep", "Sweep All", -7, 8),
        ("backshot", "Back-row Shot", -11, 1),
        ("chaos", "Random Two", -9, 2),
    ):
        registry.register(
            AbilityDefinition(
                ability_id,
                targeting=TargetingRule(
                    minimum_targets=1,
                    maximum_targets=max_targets,
                    allow_self=False,
                ),
                effects=[
                    AbilityEffect(
                        AbilityTargetMode.SELECTED,
                        Effect(
                            name,
                            [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", amount)],
                        ),
                    )
                ],
                tags=("ability.attack",),
            )
        )
    return AbilityRuntime(registry)


def side_formation(prefix):
    return FormationDefinition(
        f"{prefix}.formation",
        [
            FormationSlotDefinition(
                "front.a", x=0, y=0, tags=("row.front",), adjacent_to=("front.b", "back.a")
            ),
            FormationSlotDefinition(
                "front.b", x=1, y=0, tags=("row.front",), adjacent_to=("front.a", "back.b")
            ),
            FormationSlotDefinition(
                "back.a", x=0, y=1, tags=("row.back",), adjacent_to=("front.a", "back.b")
            ),
            FormationSlotDefinition(
                "back.b", x=1, y=1, tags=("row.back",), adjacent_to=("front.b", "back.a")
            ),
        ],
    )


def make_battle():
    abilities = ("strike", "sweep", "backshot", "chaos")
    heroes = [
        PartyMember(
            "Aria",
            "heroes",
            make_subject(100, ("actor.hero",)),
            ability_ids=abilities,
            initiative=20,
        ),
        PartyMember(
            "Bram",
            "heroes",
            make_subject(82, ("actor.hero",)),
            ability_ids=abilities,
            initiative=12,
        ),
    ]
    enemies = [
        PartyMember(
            "Beetle",
            "enemies",
            make_subject(100, ("enemy",)),
            ability_ids=abilities,
            initiative=16,
        ),
        PartyMember(
            "Mage", "enemies", make_subject(72, ("enemy",)), ability_ids=abilities, initiative=10
        ),
        PartyMember(
            "Core",
            "enemies",
            make_subject(90, ("enemy", "boss.part")),
            ability_ids=abilities,
            initiative=8,
        ),
    ]
    hf = BattleFormationRuntime(
        side_formation("heroes"),
        [BattlePlacement("Aria", "front.a"), BattlePlacement("Bram", "back.a")],
    )
    ef = BattleFormationRuntime(
        side_formation("enemies"),
        [
            BattlePlacement("Beetle", "front.a"),
            BattlePlacement("Mage", "back.a"),
            BattlePlacement("Core", "back.b"),
        ],
    )
    active = lambda m: m.subject.resources.current("hp") > 0
    targeting = [
        BattleTargetingDefinition("strike", relation="opponent", selection_mode="manual"),
        BattleTargetingDefinition(
            "sweep",
            relation="opponent",
            selection_mode="all",
            minimum_targets=1,
            maximum_targets=8,
        ),
        BattleTargetingDefinition(
            "backshot",
            relation="opponent",
            selection_mode="manual",
            required_slot_tags=("row.back",),
        ),
        BattleTargetingDefinition(
            "chaos",
            relation="opponent",
            selection_mode="random_n",
            minimum_targets=2,
            maximum_targets=2,
            selection_count=2,
        ),
    ]
    objective = BattleObjectiveDefinition(
        "defeat.enemies",
        success_conditions=(BattleObjectiveCondition("side_active_count", "enemies", "==", 0),),
        winning_sides=("heroes",),
        defeated_sides=("enemies",),
    )
    escape = BattleEscapeRule("retreat", "heroes", base_chance=0.65)
    battle = BattleRuntime(
        [Party("heroes", heroes), Party("enemies", enemies)],
        make_ability_runtime(),
        is_active=active,
        targeting_definitions=targeting,
        formations={"heroes": hf, "enemies": ef},
        objective_definitions=(objective,),
        escape_rules=(escape,),
    )
    return battle


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Asteria Batch 85 Battle Test Harness")
    font = pygame.font.Font(None, 28)
    small = pygame.font.Font(None, 22)
    clock = pygame.time.Clock()
    battle = make_battle()
    selected_ability = "strike"
    selected_targets = []
    log = ["Batch 85 harness: targeting + KO/revive/summon/transform/objective/escape."]
    summon_counter = 0
    rng = random.Random(8401)

    def current_actor():
        actor = battle.next_actor()
        if actor is None:
            battle.start_next_round()
            actor = battle.next_actor()
        return actor

    def advance():
        battle.advance_turn()
        if battle.turn_queue.exhausted():
            battle.start_next_round()

    def execute_now(actor, target_ids):
        nonlocal selected_targets
        try:
            result = battle.execute(
                BattleAction(actor.member_id, selected_ability, target_ids), rng=rng
            )
            log.append(
                f"{actor.member_id}: {selected_ability} -> {', '.join(result.action.target_ids)}"
            )
            for target_id in result.action.target_ids:
                target = battle.member(target_id)
                if target.subject.resources.current("hp") <= 0 and battle.combatants.is_active(
                    target_id
                ):
                    battle.incapacitate(target_id, state_id="ko", reason="hp.empty")
                    log.append(f"{target_id} -> KO")
            selected_targets = []
            outcome = battle.resolve_outcome()
            if outcome.finished:
                log.append(
                    f"BATTLE FINISHED winners={outcome.winning_sides} "
                    f"escaped={outcome.escaped_sides}"
                )
            else:
                advance()
        except Exception as exc:
            log.append(f"REJECTED: {exc}")

    running = True
    while running:
        actor = current_actor()
        resolution = battle.resolve_targets(
            actor.member_id, selected_ability, selected_targets, rng=random.Random(8401)
        )
        candidate_ids = set(resolution.candidate_ids)

        member_rects = {}
        for side, base_x in (("heroes", 130), ("enemies", 700)):
            formation = battle.formations[side]
            placed = set()
            for placement in formation.placements():
                slot = formation.definition.slot(placement.slot_id)
                x = base_x + slot.x * 180
                y = 230 + slot.y * 190
                member_rects[placement.member_id] = pygame.Rect(int(x), int(y), 145, 100)
                placed.add(placement.member_id)
            extras = [
                m.member_id
                for m in battle.parties[side].members
                if m.member_id not in placed and battle.combatants.state(m.member_id).present
            ]
            for i, member_id in enumerate(extras):
                member_rects[member_id] = pygame.Rect(base_x + i * 155, 440, 145, 82)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_k:
                    target_id = selected_targets[0] if selected_targets else actor.member_id
                    battle.incapacitate(target_id, state_id="ko", reason="harness")
                    log.append(f"{target_id} -> KO")
                    selected_targets = []
                elif event.key == pygame.K_v:
                    target_id = selected_targets[0] if selected_targets else actor.member_id
                    state = battle.combatants.state(target_id)
                    if state.present and state.defeated:
                        target = battle.member(target_id)
                        if target.subject.resources.current("hp") <= 0:
                            target.subject.resources.set_current("hp", 25)
                        battle.revive(target_id, reason="harness")
                        log.append(f"{target_id} revived")
                    else:
                        log.append(f"{target_id} is not revivable")
                    selected_targets = []
                elif event.key == pygame.K_s:
                    summon_counter += 1
                    summon_id = f"Sprite{summon_counter}"
                    try:
                        battle.summon(
                            PartyMember(
                                summon_id,
                                "heroes",
                                make_subject(55, ("summon",)),
                                ability_ids=("strike",),
                                initiative=14,
                            ),
                            owner_id="Aria",
                            join_current_round=False,
                        )
                        log.append(f"Summoned {summon_id}; joins next round")
                    except Exception as exc:
                        log.append(f"SUMMON REJECTED: {exc}")
                elif event.key == pygame.K_t:
                    if battle.combatants.state("Aria").form_id is None:
                        transformed = PartyMember(
                            "Aria",
                            "heroes",
                            make_subject(100, ("actor.hero", "form.dragon")),
                            ability_ids=("strike", "sweep", "backshot", "chaos"),
                            initiative=35,
                        )
                        battle.transform("Aria", transformed, form_id="dragon", reason="harness")
                        log.append("Aria transformed -> dragon")
                elif event.key == pygame.K_y:
                    if battle.combatants.state("Aria").form_id is not None:
                        battle.revert_transform("Aria", reason="harness")
                        log.append("Aria reverted form")
                elif event.key == pygame.K_e:
                    result = battle.attempt_escape("retreat", rng=rng)
                    log.append(
                        f"Escape roll {result.roll:.2f} / {result.chance:.2f}: "
                        f"{'SUCCESS' if result.succeeded else 'FAIL'}"
                    )
                elif event.key == pygame.K_r:
                    battle = make_battle()
                    selected_targets = []
                    summon_counter = 0
                    log.append("Restarted battle.")
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    selected_ability = {
                        pygame.K_1: "strike",
                        pygame.K_2: "sweep",
                        pygame.K_3: "backshot",
                        pygame.K_4: "chaos",
                    }[event.key]
                    selected_targets = []
                elif event.key == pygame.K_SPACE:
                    definition = battle.targeting.definition_for(selected_ability)
                    if definition and definition.selection_mode.value != "manual":
                        execute_now(actor, ())
                elif event.key == pygame.K_RETURN:
                    execute_now(actor, tuple(selected_targets))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for member_id, rect in member_rects.items():
                    if rect.collidepoint(event.pos) and member_id in candidate_ids:
                        selected_targets = [member_id]
                        break

        screen.fill((24, 27, 34))
        title = font.render(
            f"Current actor: {actor.member_id} | Round {battle.turn_queue.round_index}",
            True,
            (240, 240, 240),
        )
        screen.blit(title, (35, 25))
        ability_text = "1 Strike   2 Sweep All [Space]   3 Back-row Shot   4 Random Two [Space]"
        screen.blit(small.render(ability_text, True, (210, 210, 210)), (35, 62))
        screen.blit(
            small.render(
                f"Selected: {selected_ability} | candidates: {', '.join(sorted(candidate_ids))}",
                True,
                (210, 210, 210),
            ),
            (35, 90),
        )
        screen.blit(
            small.render(
                "Click/Enter attack | K KO | V revive | S summon | T/Y form | E escape | R "
                "restart",
                True,
                (180, 180, 180),
            ),
            (35, 116),
        )

        for member_id, rect in member_rects.items():
            m = battle.member(member_id)
            hp = m.subject.resources.current("hp")
            base = (65, 90, 145) if m.side == "heroes" else (135, 70, 65)
            if member_id in candidate_ids:
                base = tuple(min(255, c + 55) for c in base)
            if member_id in selected_targets:
                pygame.draw.rect(screen, (245, 220, 90), rect.inflate(8, 8), 4)
            pygame.draw.rect(screen, base, rect, border_radius=8)
            if member_id == actor.member_id:
                pygame.draw.rect(screen, (110, 220, 255), rect.inflate(4, 4), 3, border_radius=8)
            screen.blit(font.render(member_id, True, (255, 255, 255)), (rect.x + 10, rect.y + 10))
            lifecycle = battle.combatants.state(member_id)
            form = f" form={lifecycle.form_id}" if lifecycle.form_id else ""
            screen.blit(
                small.render(
                    f"HP {int(hp)}/100 | {lifecycle.state_id}{form}", True, (255, 255, 255)
                ),
                (rect.x + 10, rect.y + 48),
            )
            slot = battle.formations[m.side].slot_for(member_id)
            if slot is not None:
                screen.blit(
                    small.render(" / ".join(slot.tags), True, (215, 215, 215)),
                    (rect.x + 10, rect.y + 72),
                )

        y = 535
        screen.blit(small.render("Battle log", True, (235, 235, 235)), (35, y))
        for line in log[-5:]:
            y += 24
            screen.blit(small.render(line, True, (190, 190, 190)), (35, y))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
