"""Real-window check of the ARPG demo (D22 A10): the demo project in a real window, played by
scripted keys posted into pygame's event queue - a class from a trainer, the skill tree, a fight
in the field, the boss clearing, the side-view mine.

    python scripts/arpg_demo_live_check.py warrior|ranger|mage OUT_DIR

Saves screenshots at fixed moments and prints a JSON summary (video driver, frame times, class,
abilities used, kills, level, loot).
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from asteria.core import Transform
from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.runtime.character_control import CharacterController2DComponent
from asteria.runtime.combat import CombatantComponent
from asteria.runtime.playable_test_runtime import PlayableTestRuntime

cls = sys.argv[1]
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
root = REPO / "reference_projects" / "arpg_demo"
project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
rt = PlayableTestRuntime(
    project, project.game_start.instantiate(project), root, width=1280, height=720
)
rt.open()
rt._ui_mode = "field"
pg = rt.pg
game = rt.game
frame_times = []
events = []
deaths = []


def frame(n=1):
    for _ in range(n):
        dt = rt.tick(60)  # the runtime's own frame limiter (A11)
        frame_times.append(dt)
        rt._frame(pg.event.get(), dt)
        rt.present()
        events.extend(
            (e.kind, e.ability_id)
            for e in game.action_combat.events
            if e.entity_id == game.player.id
        )


def key(k, down=True):
    kind = pg.KEYDOWN if down else pg.KEYUP
    pg.event.post(pg.event.Event(kind, key=k, mod=0, unicode="", scancode=0))


def tap(k, wait=4):
    key(k)
    frame(2)
    key(k, False)
    frame(wait)


def shot(name):
    pg.image.save(rt.screen, str(out / f"arpg_demo_{cls}_{name}.png"))


def scene(prefix):
    return next(s for s in project.scenes() if s.name.startswith(prefix))


frame(20)
shot("town")
trainer = next(e for e in game.scene.entities() if e.name.lower().startswith(cls))
t = trainer.get(Transform)
game.set_player_position(t.x, t.y - 18)
game.player.get(CharacterController2DComponent).facing = "down"
tap(pg.K_e, 10)
shot("trainer")
while game.event_busy:
    tap(pg.K_RETURN, 12)
game.grant_actor_experience("hero", 3000, **game.action_progression)  # a few levels of points
tap(pg.K_c, 10)
for k in (pg.K_RETURN, pg.K_DOWN, pg.K_RETURN, pg.K_LEFT, pg.K_RETURN, pg.K_RETURN):
    tap(k, 8)
shot("skill_tree")
tap(pg.K_c, 6)

field = scene("Greenvale")
game.transfer_player(field.id, 14 * 16, 23.5 * 16, facing="right")
game.combat.listeners.append(lambda e: deaths.append(e.target_id) if e.kind == "death" else None)
frame(10)
key(pg.K_d)
for i in range(24):
    frame(4)
    tap(pg.K_j, 2)
    if i == 12:
        shot("field_walk")
key(pg.K_d, False)
for k in (pg.K_1, pg.K_j, pg.K_j, pg.K_2, pg.K_j, pg.K_k, pg.K_3, pg.K_j, pg.K_4):
    tap(k, 18)
shot("field_skills")
for _ in range(60):
    tap(pg.K_j, 3)
shot("field_late")
from asteria.runtime.loot import LootComponent  # noqa: E402

# step onto each equipment drop and press F (pick up)
for entity, loot in list(game.scene.query(LootComponent)):
    if loot.kind == "equipment" and entity.has(Transform):
        lt = entity.get(Transform)
        game.set_player_position(lt.x, lt.y)
        frame(2)
        tap(pg.K_f, 4)

boss = next(e for e in game.scene.entities() if e.name.startswith("Gorgoth"))
b = boss.get(Transform)
game.set_player_position(b.x, b.y + 60)
game.player.get(CharacterController2DComponent).facing = "up"
for _ in range(30):
    tap(pg.K_j, 3)
tap(pg.K_1, 10)
shot("boss")
for _ in range(30):
    tap(pg.K_j, 3)

mine = scene("Rustdeep")
game.transfer_player(mine.id, 4.5 * 18, 13 * 18, facing="right")
game.combat.listeners.append(lambda e: deaths.append(e.target_id) if e.kind == "death" else None)
frame(30)
shot("mine")
key(pg.K_d)
for i in range(40):
    frame(3)
    tap(pg.K_j, 2)
    if i == 10:
        tap(pg.K_SPACE, 6)
        shot("mine_jump")
key(pg.K_d, False)
shot("mine_late")
tap(pg.K_b, 10)
shot("bag")
tap(pg.K_b, 4)

player = game.player
state = game.combat.state(player)
life = player.get(CombatantComponent).life_resource
progress = game.ensure_actor_progression("hero")
used = {}
for kind, ability in events:
    if kind in ("used", "combo"):
        used[ability] = used.get(ability, 0) + 1
times = sorted(frame_times[30:])
summary = {
    "driver": pg.display.get_driver(),
    "class": progress.active_class_ids,
    "frames": len(frame_times),
    "mean_fps": round(len(times) / sum(times), 1),
    "p95_frame_ms": round(times[int(len(times) * 0.95)] * 1000, 1),
    "abilities_used": used,
    "known": sorted(game.resolve_actor_build("hero").abilities),
    "player_life": [round(state.resources.current(life)), state.resources.maximum(life)],
    "kills": len(set(deaths)),
    "level": progress.level,
    "gold": game.save.rpg_state.currencies.get("gold", 0),
    "bag": len(game.save.rpg_state.equipment_bag),
    "scene": game.scene.name,
}
rt.close()
(out / f"arpg_demo_{cls}_summary.json").write_text(
    json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8"
)
print(json.dumps(summary, indent=1, default=str))
