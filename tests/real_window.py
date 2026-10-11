"""Real-window replay of session-level integration tests (D19, ``scripts/real_machine_validation.py``
check ``b_items_replay``).

With ``ASTERIA_REAL_WINDOW=1`` the ``runtime`` fixture and ``test_session_events._session`` open the
playable runtime in a real window (no dummy SDL driver), and every public ``GameSessionRuntime`` call
presents one real frame of that game afterwards. The tests and their assertions are unchanged: the same
scenarios run against the real playable window and renderer instead of a headless one.

The run is summarised in ``$ASTERIA_REAL_WINDOW_REPORT`` (JSON): video driver, frames presented and the
frames per test, so the evidence shows that each test really drove a presented window.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path

STATE = {
    "stage": None,
    "frames": 0,
    "per_test": {},
    "test": None,
    "driver": None,
    "shots": [],
    "last": 0.0,
    "depth": 0,
    "in_frame": False,
}
FRAME = 1 / 240  # throttle: at most one presented frame per 1/240 s of wall time


def enabled():
    return os.environ.get("ASTERIA_REAL_WINDOW") == "1"


def set_stage(runtime):
    """Make ``runtime`` (an opened PlayableTestRuntime in a real window) the window that presents frames."""
    STATE["stage"] = runtime
    try:
        import pygame

        STATE["driver"] = pygame.display.get_driver()
    except Exception:  # pragma: no cover - reported as missing driver
        STATE["driver"] = None


def _alive(stage):
    """The stage window is still open (a test may close its own runtime before teardown)."""
    try:
        import pygame

        return stage is not None and pygame.display.get_init() and getattr(stage, "screen", None) is not None
    except Exception:
        return False


def present(force=False):
    import time

    stage = STATE["stage"]
    if not _alive(stage) or not getattr(stage, "running", True):
        return
    now = time.perf_counter()
    if not force and now - STATE["last"] < FRAME:
        return
    STATE["last"] = now
    import pygame

    STATE["in_frame"] = True
    try:
        # Window events only (no input): a presented frame must not answer a dialogue or press a key.
        pygame.event.pump()
        _draw(stage)
        stage.present()
    except Exception:  # a frame must never change the test's outcome; the frame is just not counted
        return
    finally:
        STATE["in_frame"] = False
    STATE["frames"] += 1
    test = STATE["test"]
    if test:
        STATE["per_test"][test] = STATE["per_test"].get(test, 0) + 1


def _draw(stage):
    """Draw the game as it is now, without advancing it (no input, no time, no event programs) and without
    loading images the game has not loaded itself (image scopes stay exactly as the test left them)."""
    game = stage.game
    adapter = stage._battle_presentation
    in_battle = game.mode == "battle" or stage._victory or stage._defeat
    if in_battle and getattr(adapter, "visuals_enabled", False) and adapter.screen is not None:
        adapter.draw()  # its images are already loaded (battle scope)
        return
    if not in_battle:
        stage._draw_field(False)
        return
    # a battle driven through the session API: show who is fighting and their HP
    stage.screen.fill((14, 16, 24))
    font = stage.pg.font.Font(None, 26)
    lines = ["Battle (session API)"]
    battle = game.battle
    for side in ("heroes", "enemies"):
        party = battle.parties.get(side) if battle is not None and hasattr(battle, "parties") else None
        for member_id in party.ids() if party is not None else ():
            member = battle.member(member_id)
            lines.append(f"{side[:-1]} {member_id}: {getattr(member, 'hp', '?')}")
    for i, line in enumerate(lines):
        stage.screen.blit(font.render(line, True, (230, 232, 240)), (32, 28 + 24 * i))


def save_screenshot(name):
    present(force=True)  # the test's final state is on screen
    stage = STATE["stage"]
    folder = os.environ.get("ASTERIA_REAL_WINDOW_SHOTS")
    if not _alive(stage) or not folder:
        return
    import pygame

    path = Path(folder) / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(stage.capture(), str(path))
    STATE["shots"].append(path.name)


def session_runtime(project, save, root):
    """An opened real-window PlayableTestRuntime around ``save``; its ``game`` is the test's session."""
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
        os.environ.pop(key, None)
    previous = STATE["stage"]
    if previous is not None:
        previous.close()
    runtime = PlayableTestRuntime(project, save, root, width=960, height=540)
    runtime.open()
    set_stage(runtime)
    return runtime


def install():
    """Present a frame after every public GameSessionRuntime method call (once per process)."""
    from asteria.runtime.game_session import GameSessionRuntime

    if getattr(GameSessionRuntime, "_real_window_wrapped", False):
        return
    for name, value in list(vars(GameSessionRuntime).items()):
        if name.startswith("_") or not callable(value) or isinstance(value, (staticmethod, classmethod, property)):
            continue

        def wrap(method):
            @functools.wraps(method)
            def call(self, *args, **kwargs):
                STATE["depth"] += 1
                try:
                    return method(self, *args, **kwargs)
                finally:
                    STATE["depth"] -= 1
                    stage = STATE["stage"]
                    outermost = STATE["depth"] == 0 and not STATE["in_frame"]
                    if outermost and stage is not None and getattr(stage, "game", None) is self:
                        present()

            return call

        setattr(GameSessionRuntime, name, wrap(value))
    GameSessionRuntime._real_window_wrapped = True

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    frame = PlayableTestRuntime._frame

    @functools.wraps(frame)
    def guarded_frame(self, *args, **kwargs):  # the test's own frames: no extra presents inside them
        outer = STATE["in_frame"]
        STATE["in_frame"] = True
        try:
            return frame(self, *args, **kwargs)
        finally:
            STATE["in_frame"] = outer
            if not outer and STATE["stage"] is self:
                present()  # the test's own frame is shown too

    PlayableTestRuntime._frame = guarded_frame


def write_report(results):
    path = os.environ.get("ASTERIA_REAL_WINDOW_REPORT")
    if not path:
        return
    Path(path).write_text(
        json.dumps(
            {
                "driver": STATE["driver"],
                "frames": STATE["frames"],
                "per_test": STATE["per_test"],
                "results": results,
                "screenshots": STATE["shots"],
            },
            indent=2,
        )
        + "\n"
    )
