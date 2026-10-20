"""Battle pictures decoded ahead in the field (runtime/image_preloader.py): the first battle frame
no longer decodes every sheet, and what it draws is unchanged."""

import random
import time

import pytest

pygame = pytest.importorskip("pygame")

from test_playable_battle_loop import _boss_runtime  # noqa: E402

from asteria.runtime.image_preloader import ImagePreloader  # noqa: E402


@pytest.fixture
def screen(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    yield pygame.display.set_mode((64, 64))
    pygame.display.quit()


def _picture(path, size, colour):
    image = pygame.Surface(size, pygame.SRCALPHA)
    image.fill(colour)
    pygame.draw.circle(image, (255, 255, 255, 128), (size[0] // 2, size[1] // 2), 3)
    pygame.image.save(image, str(path))
    return path.name


def _settle(preloader, rels, limit=2.0):
    deadline = time.perf_counter() + limit
    while time.perf_counter() < deadline:
        preloader.step()
        if all(preloader.ready(rel) for rel in rels):
            return
        time.sleep(0.002)
    raise AssertionError("pictures were never decoded")


def test_preloaded_pictures_match_a_direct_load(screen, tmp_path):
    rels = [_picture(tmp_path / f"p{i}.png", (40, 20), (30 * i, 90, 200, 255)) for i in range(3)]
    preloader = ImagePreloader(pygame, lambda rel: tmp_path / rel)
    preloader.want(rels)
    _settle(preloader, rels)
    for rel in rels:
        ready = preloader.take(rel)
        direct = pygame.image.load(tmp_path / rel).convert_alpha()
        assert ready.get_size() == direct.get_size()
        assert pygame.image.tobytes(ready, "RGBA") == pygame.image.tobytes(direct, "RGBA")
        assert preloader.take(rel) is None  # handed over once
    preloader.close()


def test_the_budget_caps_what_is_held_and_loaded_pictures_are_skipped(screen, tmp_path):
    rels = [_picture(tmp_path / f"p{i}.png", (32, 32), (200, 40, 40, 255)) for i in range(4)]
    one = 32 * 32 * 4
    preloader = ImagePreloader(pygame, lambda rel: tmp_path / rel, {rels[0]: object()})
    preloader.budget_bytes = 2 * one
    preloader.want(rels)
    _settle(preloader, rels[1:3])
    for _ in range(20):
        preloader.step()
        time.sleep(0.002)
    assert not preloader.ready(rels[0])  # the host already has it
    assert not preloader.ready(rels[3])  # over the budget
    assert preloader.held_bytes == 2 * one
    preloader.want(rels[2:])  # no longer wanted: let go
    assert not preloader.ready(rels[1]) and preloader.ready(rels[2])
    image = pygame.image.load(tmp_path / rels[1]).convert_alpha()
    assert not preloader.keep(rels[1], image)  # not wanted
    preloader.close()


def test_a_missing_picture_is_left_to_the_host(screen, tmp_path):
    good = _picture(tmp_path / "good.png", (8, 8), (10, 200, 10, 255))
    preloader = ImagePreloader(pygame, lambda rel: tmp_path / rel)
    preloader.want(["missing.png", good])
    _settle(preloader, [good])
    assert preloader.take("missing.png") is None
    preloader.close()


def _battle_frame(resource_root, *, preload):
    random.seed(11)
    runtime = _boss_runtime(resource_root)
    runtime.preload_battle_images = preload
    runtime._ui_mode = "field"
    wanted = runtime._battle_presentation.upcoming_images()
    deadline = time.perf_counter() + 5.0
    while preload and time.perf_counter() < deadline:
        runtime._frame([], 1 / 60)
        if all(runtime._preloader.ready(rel) or rel in runtime._loaded for rel in wanted):
            break
        time.sleep(0.002)
    held = dict(runtime._preloader._ready) if preload else {}
    runtime.game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    for _ in range(3):
        runtime._present_battle(1 / 60)
    return runtime, wanted, held, pygame.image.tobytes(runtime.screen, "RGB")


def test_the_battle_takes_its_pictures_from_the_field_and_draws_the_same(
    resource_root, monkeypatch
):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    runtime, wanted, held, frame = _battle_frame(resource_root, preload=True)
    try:
        assert held and wanted, "the field decoded the next fight's pictures"
        taken = [rel for rel in held if runtime._loaded.get(rel) is held[rel]]
        assert any("battle/" in rel for rel in taken)  # the sheets were not decoded again
        game = runtime.game
        for enemy in game.active_enemy_ids():
            game.battle.member(enemy).subject.resources.set_current(
                game.rules.knockout_resource_id, 0
            )
        game.finish_victory()
        runtime._victory = False
        runtime._ui_mode = "field"
        runtime._frame([], 1 / 60)
        assert all(rel not in runtime._loaded for rel in taken)  # ENG-10: released
        assert all(runtime._preloader.ready(rel) for rel in taken)  # kept for the next fight
    finally:
        runtime.close()
    plain, _wanted, _held, expected = _battle_frame(resource_root, preload=False)
    plain.close()
    assert plain._preloader is None
    assert frame == expected
