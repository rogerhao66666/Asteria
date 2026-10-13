"""Batch 89 developer battle harness for generic gauge composition.

Controls:
  Space  weak hit (-25 stagger)
  H      heavy hit (-10 stagger)
  B      weak + heavy in one logical impact (-35, one threshold evaluation)
  R      restart
  Esc    quit

This is a developer sandbox, not final battle presentation.
"""

from __future__ import annotations

import random

import pygame

from asteria.gameplay import (
    AbilityRegistry,
    AbilityRuntime,
    GameplaySubject,
    ResourcePool,
    StatBlock,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    TagSet,
)
from asteria.rpg import (
    BattleResourceDefinition,
    BattleRuntime,
    BattleSchedulerDefinition,
    BattleStatePolicy,
    GaugeCompositionDefinition,
    GaugeImpactRule,
    GaugeThresholdRule,
    Party,
    PartyMember,
)

WIDTH, HEIGHT = 920, 520


def make_subject():
    stats = StatBlock({"speed": 10})
    resources = ResourcePool()
    resources.define("hp", 100, current=100)
    tags = TagSet()
    registry = StateRegistry([StateDefinition("broken", 2)])
    states = StateRuntime(registry, stats, resources, tags)
    return GameplaySubject(stats, resources, tags, states)


def make_battle():
    hero = PartyMember("Aria", "heroes", make_subject(), initiative=20)
    enemy = PartyMember("Iron Beetle", "enemies", make_subject(), initiative=10)
    composition = GaugeCompositionDefinition(
        "stagger_break",
        impacts=(
            GaugeImpactRule(
                "weakness_pressure",
                "stagger",
                "battle.hit",
                delta=-25,
                required_outcome_tags_all=("outcome.weak",),
            ),
            GaugeImpactRule(
                "heavy_pressure",
                "stagger",
                "battle.hit",
                delta=-10,
                required_outcome_tags_all=("attack.heavy",),
            ),
        ),
        thresholds=(
            GaugeThresholdRule(
                "broken",
                "stagger",
                "at_or_below",
                0,
                state_id="broken",
                timeline_shift=20,
                reset_to=100,
                emit_trigger="battle.break.triggered",
            ),
        ),
    )
    return BattleRuntime(
        [Party("heroes", [hero]), Party("enemies", [enemy])],
        AbilityRuntime(AbilityRegistry()),
        resource_definitions=(
            BattleResourceDefinition("stagger", minimum=0, maximum=100, start_mode="maximum"),
        ),
        state_policies=(
            BattleStatePolicy("broken", prevent_action=True, tick_trigger="rpg.battle.turn_ended"),
        ),
        scheduler_definition=BattleSchedulerDefinition(
            "demo.timeline", mode="continuous", timeline_scale=100
        ),
        gauge_composition_definitions=(composition,),
    )


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Asteria Batch 89 Gauge Composition Harness")
    font = pygame.font.Font(None, 30)
    small = pygame.font.Font(None, 22)
    clock = pygame.time.Clock()
    rng = random.Random(89)
    battle = make_battle()
    log = ["Space=weak, H=heavy, B=both. Break is data composition."]

    def impact(tags):
        before = battle.battle_resources.current("Iron Beetle", "stagger")
        result = battle.apply_gauge_impact(
            "stagger_break",
            "Aria",
            "Iron Beetle",
            trigger="battle.hit",
            outcome_tags=tags,
            rng=rng,
        )
        after = battle.battle_resources.current("Iron Beetle", "stagger")
        if result.thresholds:
            log.append(f"BREAK threshold crossed {before:.0f}->0; reset={after:.0f}; timeline +20")
        else:
            log.append(f"Impact {','.join(tags)}: stagger {before:.0f}->{after:.0f}")

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    impact(("outcome.weak",))
                elif event.key == pygame.K_h:
                    impact(("attack.heavy",))
                elif event.key == pygame.K_b:
                    impact(("outcome.weak", "attack.heavy"))
                elif event.key == pygame.K_r:
                    battle = make_battle()
                    log.append("Restarted")

        screen.fill((25, 28, 36))
        screen.blit(
            font.render("Batch 89 — Generic Gauge Composition", True, (240, 240, 240)), (35, 25)
        )
        screen.blit(
            small.render(
                "No BreakSystem: outcome tags -> gauge -> threshold -> State + Timeline",
                True,
                (195, 195, 195),
            ),
            (35, 62),
        )

        enemy = battle.member("Iron Beetle")
        stagger = battle.battle_resources.current("Iron Beetle", "stagger")
        state = enemy.subject.states.get("broken")
        pending = [x for x in battle.scheduler.pending() if x.member_id == "Iron Beetle"]
        ready = pending[0].ready_time if pending else 0.0

        rect = pygame.Rect(500, 160, 270, 150)
        pygame.draw.rect(screen, (115, 80, 55), rect, border_radius=10)
        screen.blit(font.render("Iron Beetle", True, (255, 255, 255)), (rect.x + 20, rect.y + 18))
        screen.blit(
            small.render(f"State: {'broken' if state else 'normal'}", True, (255, 255, 255)),
            (rect.x + 20, rect.y + 58),
        )
        screen.blit(
            small.render(f"Next ready: t={ready:.1f}", True, (255, 255, 255)),
            (rect.x + 20, rect.y + 86),
        )
        bar = pygame.Rect(rect.x + 20, rect.y + 116, 220, 18)
        pygame.draw.rect(screen, (55, 55, 60), bar)
        fill = pygame.Rect(bar.x, bar.y, int(bar.width * stagger / 100.0), bar.height)
        pygame.draw.rect(screen, (205, 180, 85), fill)
        screen.blit(
            small.render(f"Stagger {stagger:.0f}/100", True, (230, 230, 230)),
            (rect.x + 20, rect.y + 138),
        )

        screen.blit(
            small.render(
                "Space weak -25   H heavy -10   B both -35   R restart", True, (215, 215, 215)
            ),
            (35, 350),
        )
        y = 390
        for line in log[-4:]:
            screen.blit(small.render(line, True, (185, 185, 185)), (35, y))
            y += 25
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
