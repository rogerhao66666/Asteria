"""Real-window check of the ARPG playground (D22 A8): real assets, scripted keys posted into pygame's event queue.

    python scripts/arpg_live_check.py topdown|side OUT_DIR

Saves screenshots at fixed frames and prints a JSON summary (video driver, fps, abilities used, HP, kills, loot).
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.runtime.combat import CombatantComponent
from asteria.runtime.playable_test_runtime import PlayableTestRuntime
from asteria.validation.arpg_playground import build_playground

view = sys.argv[1]
out = Path(sys.argv[2])
root = REPO / "reference_projects" / "complex_reference_rpg"
project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
rt = PlayableTestRuntime(project, project.game_start.instantiate(project), root, width=1280, height=720)
rt.open()
game = build_playground(rt, view)
pg = rt.pg
# script: (frame, key, down/up)
K = pg
script = {}


def tap(frame, key, hold=3):
    script.setdefault(frame, []).append((pg.KEYDOWN, key))
    script.setdefault(frame + hold, []).append((pg.KEYUP, key))


if view == "topdown":
    script.setdefault(10, []).append((pg.KEYDOWN, pg.K_a))
    script.setdefault(70, []).append((pg.KEYUP, pg.K_a))
    for f in (80, 92, 104, 150, 162, 174, 220, 232, 244):
        tap(f, pg.K_j)
    tap(130, pg.K_k)
    tap(200, pg.K_1)
    tap(260, pg.K_l)
    tap(270, pg.K_1)
    tap(300, pg.K_1)
    for f in range(330, 600, 14):
        tap(f, pg.K_j)
    tap(600, pg.K_f)
    shots = {120: "combo", 205: "bolt", 280: "lock", 450: "melee", 640: "late"}
    frames = 660
else:
    script.setdefault(10, []).append((pg.KEYDOWN, pg.K_d))
    script.setdefault(80, []).append((pg.KEYUP, pg.K_d))
    tap(30, pg.K_SPACE, 10)
    for f in range(84, 130, 12):
        tap(f, pg.K_j)
    script.setdefault(130, []).append((pg.KEYDOWN, pg.K_a))
    script.setdefault(260, []).append((pg.KEYUP, pg.K_a))
    tap(150, pg.K_SPACE, 4)
    tap(200, pg.K_1)
    shots = {36: "jump", 116: "attack", 160: "short_hop", 230: "bolt", 300: "late"}
    frames = 320
log = []
fps = []
seen = []
game.combat.listeners.append(seen.append)
for frame in range(frames):
    for kind, key in script.get(frame, ()):
        pg.event.post(pg.event.Event(kind, key=key, mod=0, unicode="", scancode=0))
    dt = min(rt.clock.tick(60) / 1000.0, 0.05)
    fps.append(dt)
    rt._frame(pg.event.get(), dt)
    rt.present()
    if frame in shots:
        pg.image.save(rt.screen, str(out / f"arpg_{view}_{shots[frame]}.png"))
    log += [(frame, e.kind, e.entity_id == game.player.id, e.ability_id, e.reason) for e in game.action_combat.events]
p = game.player
state = game.combat.state(p)
life = p.get(CombatantComponent).life_resource
summary = {
    "driver": pg.display.get_driver(),
    "frames": frames,
    "mean_fps": round(len(fps) / sum(fps), 1),
    "player_uses": [x for x in log if x[2] and x[1] in ("used", "combo")][:20],
    "player_life": [state.resources.current(life), state.resources.maximum(life)],
    "enemies_left": sorted(
        (e.name, round(c.state.resources.current(c.life_resource)))
        for e, c in game.scene.query(CombatantComponent)
        if e is not p and c.state is not None
    ),
    "kills": sorted(e.target_id[:6] for e in seen if e.kind == "death"),
    "player_hits_landed": sum(1 for e in seen if e.kind == "damage" and e.attacker_id == game.player.id),
    "hits_taken": sum(1 for e in seen if e.kind == "damage" and e.target_id == game.player.id),
    "bag": len(game.save.rpg_state.equipment_bag),
    "gold": game.save.rpg_state.currencies.get("gold", 0),
    "level": game.ensure_actor_progression(game._actor_of(p)).level,
}
rt.close()
print(json.dumps(summary, indent=1, default=str))
