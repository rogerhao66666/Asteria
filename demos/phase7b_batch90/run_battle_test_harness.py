"""Batch 90 developer reaction harness.

Controls:
  Space  Aria attacks Beetle -> Beetle counter reaction
  C      pre-action cover/intercept query (if another enemy ally exists)
  R      restart
  Esc    quit

Developer sandbox only; final battle presentation comes after Battle Core closure.
"""
import pygame
from verify_reaction_demo import *  # reusable tiny deterministic fixture

WIDTH, HEIGHT = 900, 480

def build():
    hero = PartyMember("Aria", "heroes", subject(), ability_ids=("hit", "counter"), initiative=20)
    ally = PartyMember("Bram", "heroes", subject(), ability_ids=("counter",), initiative=15)
    enemy = PartyMember("Iron Beetle", "enemies", subject(), ability_ids=("counter",), initiative=10)
    guard = PartyMember("Beetle Guard", "enemies", subject(), ability_ids=("counter",), initiative=8)
    return BattleRuntime(
        [Party("heroes", [hero, ally]), Party("enemies", [enemy, guard])], AbilityRuntime(registry),
        reaction_definitions=(
            ReactionDefinition("counter", "rpg.battle.after_action", "event_targets", target_selector="event_source", ability_id="counter", blocked_tags=("reaction",), priority=10),
            ReactionDefinition("cover", "rpg.battle.before_action", "allies_of_targets_except_targets", action_target_policy="replace_event_targets_with_reactor", priority=20),
        ),
    )

def main():
    pygame.init(); screen=pygame.display.set_mode((WIDTH, HEIGHT)); pygame.display.set_caption("Asteria Batch 90 Reaction Harness")
    font=pygame.font.Font(None, 28); small=pygame.font.Font(None, 22); clock=pygame.time.Clock(); b=build(); log=[]
    running=True
    while running:
        for e in pygame.event.get():
            if e.type==pygame.QUIT: running=False
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: running=False
                elif e.key==pygame.K_r: b=build(); log=["restart"]
                elif e.key==pygame.K_SPACE:
                    _, chain=b.execute_with_reactions(BattleAction("Aria","hit",("Iron Beetle",)))
                    log.append("attack -> "+", ".join(x.reaction_id for x in chain.requests))
                elif e.key==pygame.K_c:
                    chain=b.resolve_reactions("rpg.battle.before_action","Aria",("Iron Beetle",))
                    log.append("cover target -> "+str(chain.final_target_ids))
        screen.fill((25,25,30))
        lines=["Batch 90 Reaction Harness  | Space=attack/counter C=cover R=restart",
               f"Aria HP {b.member('Aria').subject.resources.current('hp'):.0f}",
               f"Iron Beetle HP {b.member('Iron Beetle').subject.resources.current('hp'):.0f}",
               f"Beetle Guard HP {b.member('Beetle Guard').subject.resources.current('hp'):.0f}"]+log[-8:]
        for i,text in enumerate(lines): screen.blit((font if i==0 else small).render(text,True,(235,235,235)),(30,30+i*38))
        pygame.display.flip(); clock.tick(60)
    pygame.quit()

if __name__ == '__main__': main()
