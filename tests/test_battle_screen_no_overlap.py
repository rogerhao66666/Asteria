"""Every drawn text, panel, gauge, sprite and shield block on the Octopath demo's battle screen
stays clear of the others, in every menu state, while the camera settles."""

import itertools
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"
ENCOUNTERS = ["boss_room", "slime_pit", "old_crypt", "gazer_nest", "samurai_duel"]


def _hit(a, b, margin=1):
    return (
        a[0] + margin < b[0] + b[2]
        and b[0] + margin < a[0] + a[2]
        and a[1] + margin < b[1] + b[3]
        and b[1] + margin < a[1] + a[3]
    )


def _inside(a, b):
    return (
        a[0] >= b[0] - 1
        and a[1] >= b[1] - 1
        and a[0] + a[2] <= b[0] + b[2] + 1
        and (a[1] + a[3] <= b[1] + b[3] + 1)
    )


@pytest.fixture
def recorder(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.platform import pygame_battle_ui as pb

    cls = next(c for c in vars(pb).values() if isinstance(c, type) and hasattr(c, "draw_text"))
    rec = {"text": [], "panel": [], "gauge": []}
    draw_text, draw_panel, draw_gauge = cls.draw_text, cls.draw_panel, cls.draw_gauge

    def text(self, value, *, color, size):
        font = self._font(size)
        image = font.render(self._renderable(font, value.text), True, (0, 0, 0))
        x, y = self._s(value.x), self._s(value.y)
        if value.align == "center":
            x -= image.get_width() // 2
        elif value.align == "right":
            x -= image.get_width()
        rec["text"].append(
            (x, y, image.get_width(), image.get_height(), value.text, value.member_id, value.role)
        )
        return draw_text(self, value, color=color, size=size)

    def panel(self, value, **kwargs):
        r = self._rect(value.x, value.y, value.width, value.height)
        rec["panel"].append((r.x, r.y, r.width, r.height, value.panel_id))
        return draw_panel(self, value, **kwargs)

    def gauge(self, value, **kwargs):
        r = self._rect(value.x, value.y, value.width, value.height)
        rec["gauge"].append((r.x, r.y, r.width, r.height, value.member_id, value.label))
        return draw_gauge(self, value, **kwargs)

    monkeypatch.setattr(cls, "draw_text", text)
    monkeypatch.setattr(cls, "draw_panel", panel)
    monkeypatch.setattr(cls, "draw_gauge", gauge)
    return rec


def _problems(runtime, rec):
    for key in rec:
        rec[key].clear()
    adapter = runtime._battle_presentation
    adapter.draw()
    runtime._draw_battle_extras()
    texts = [t for t in rec["text"] if not t[6].startswith(("value", "feedback"))]
    panels = [p for p in rec["panel"] if not p[4].startswith("turn:")]
    sprites = {}
    for member in runtime.game.battle.members.values():
        if runtime.game.battle.is_active(member):
            box = adapter.member_screen_box(member.member_id)
            ally = adapter.screen.composer._stands_right(member.member_id)
            if box and (not ally or member.member_id == runtime._turn_actor):
                sprites[member.member_id] = (box[0] - 18, box[1], 36, box[2] - box[1])
    blocks = {b.member_id: b.rect() for b in runtime.battle_extras_blocks if b.rect()}
    found = set()
    for a, b in itertools.combinations(texts, 2):
        if _hit(a, b):
            found.add(("text/text", a[4], b[4]))
    for t in texts:
        for p in panels:
            if _hit(t, p) and not _inside(t, p):
                found.add(("text straddles panel", t[4], p[4]))
        for mid, s in sprites.items():
            if t[5] != mid and _hit(t, s):
                found.add(("text/sprite", t[4], mid))
        for mid, b in blocks.items():
            if _hit(t, b):
                found.add(("text/block", t[4], mid))
    for a, b in itertools.combinations(panels, 2):
        if "action_menu" in (a[4], b[4]) and "button:" in a[4] + b[4]:
            continue  # a menu button is drawn inside its own menu panel
        if _hit(a, b):
            found.add(("panel/panel", a[4], b[4]))
    for p in panels:
        for mid, s in sprites.items():
            if _hit(p, s):
                found.add(("panel/sprite", p[4], mid))
        for mid, b in blocks.items():
            if _hit(p, b):
                found.add(("panel/block", p[4], mid))
    for g in rec["gauge"]:
        for t in texts:
            if t[5] != g[4] and _hit(g, t, 2):
                found.add(("gauge/text", g[5], t[4]))
    return found


@pytest.mark.parametrize("encounter", ENCOUNTERS)
def test_nothing_on_the_battle_screen_covers_anything_else(recorder, encounter):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    runtime._ui_mode = "field"
    runtime.game.start_encounter(encounter)
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    hero, commands = runtime._turn_actor, runtime.battle_commands
    steps = ["", "confirm", "cancel", "down", "confirm", "cancel", "down", "confirm", "cancel"]
    for frame in range(520):
        runtime._frame([], 1 / 60)
        index = (frame - 260) // 25
        if frame >= 260 and (frame - 260) % 25 == 0 and index < len(steps) and steps[index]:
            commands.press(steps[index], hero)
        if frame >= 250 and frame % 5 == 0:
            problems = _problems(runtime, recorder)
            assert not problems, (encounter, frame, commands.mode, sorted(problems))
