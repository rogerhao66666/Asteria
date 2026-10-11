"""D19 / CB15 A9: the canonical battle screen fully replaces the retired legacy screen, including projects
that have no battle art (no combatant visuals, no motion sequences - only manifest images and skill fx / sfx)."""

import pytest

pygame = pytest.importorskip("pygame")

from test_playable_battle_loop import _boss_runtime  # noqa: E402


@pytest.fixture
def bare(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    import shutil
    from pathlib import Path

    from asteria.runtime.audio_mixer import RecordingAudioDevice

    reference = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"
    shutil.copytree(reference / "playable_assets" / "audio", resource_root / "playable_assets" / "audio")
    runtime = _boss_runtime(resource_root)
    library = runtime.game.project.battle_presentation_library
    for category in ("combatant_visuals", "motion_sequences"):
        for profile_id in list(library.ids(category)):
            library.remove(category, profile_id)
    runtime.audio.device = device = RecordingAudioDevice()
    yield runtime, device
    runtime.close()


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0)


def test_a_project_without_battle_art_plays_a_full_battle_on_the_canonical_screen(bare, tmp_path):
    runtime, device = bare
    runtime._ui_mode = "field"
    game = runtime.game
    game.start_encounter("boss_room")
    adapter = runtime._battle_presentation
    adapter.begin()
    runtime._advance_to_hero_turn()
    runtime._frame([], 0.016)
    # every combatant is a generated canonical visual (manifest picture, or a silhouette)
    ids = {v.member_id: v.sprite_sheet_asset_id for v in adapter.screen.scene.combatants}
    assert adapter.visuals_enabled and set(ids) == {m for p in game.battle.parties.values() for m in p.ids()}
    assert all(sheet.startswith("generated.combatant.") for sheet in ids.values())
    for _ in range(400):  # the opening enemy turns play before the hero's commands appear
        if not adapter.busy():
            break
        runtime._frame([], 0.05)
    runtime._frame([], 0.016)
    entries = [e.action_id for e in adapter.screen.action_menu.view.entries]
    assert "boost" in entries  # the legacy HUD's boost readout lives in the action menu now
    vfx_seen = sounds_before = 0
    sounds_before = sum(1 for call in device.calls if call[0] == "play_sound")
    for _ in range(4000):
        if runtime._victory or runtime._defeat:
            break
        waiting = not adapter.busy() and game.mode == "battle"
        runtime._frame([_key(pygame.K_1)] if waiting else [], 0.05)
        vfx_seen = max(vfx_seen, adapter.particle_count())
    assert runtime._victory and game.battle is None
    assert vfx_seen >= 1  # manifest skill fx played as canonical VFX
    assert sum(1 for call in device.calls if call[0] == "play_sound") > sounds_before  # manifest sfx
    for _ in range(400):
        if not adapter.busy():
            break
        runtime._frame([], 0.05)
    runtime._frame([_key(pygame.K_RETURN)], 0.016)
    assert game.mode == "field" and not runtime._victory  # battle exit
    out = tmp_path / "after.json"  # save / load after the battle
    game.sync_world_state()
    game.save.save_json(out)
    from asteria.runtime.game_save import GameRuntimeSave

    again = GameRuntimeSave.load_json(out, game.project)
    assert again.scene_id == game.save.scene_id and again.rpg_state.to_data() == game.save.rpg_state.to_data()


def test_generated_combatants_animate_get_hit_and_fall(bare):
    runtime, _ = bare
    game = runtime.game
    game.start_encounter("boss_room")
    adapter = runtime._battle_presentation
    adapter.begin()
    sheet = next(v.sprite_sheet_asset_id for v in adapter.screen.scene.combatants)
    clips = adapter.resolver.clip_set(sheet).clips
    assert [k.frame_index for k in clips["attack"].keyframes] == [1, 1, 0]
    assert [k.frame_index for k in clips["hit"].keyframes] == [2, 2, 0]
    assert len(adapter.resolver.sprite_sheet(sheet).frames) == 4
    image = adapter.resolver.generated_image(sheet)
    fw = adapter.resolver.sprite_sheet(sheet).frames[0].width

    # the hit frame is brighter than the idle frame (flash), the KO frame darker
    def brightness(index):
        frame = image.subsurface((index * fw, 0, fw, image.get_height()))
        return pygame.transform.average_color(frame, consider_alpha=True)[:3]

    assert sum(brightness(2)) > sum(brightness(0)) > sum(brightness(3))


def test_projects_without_any_images_get_silhouettes_and_a_plain_backdrop(bare):
    runtime, _ = bare
    runtime.manifest["battle"]["heroes"] = []
    runtime.manifest["battle"]["enemy_sprites"] = {}
    runtime.manifest["battle"]["background"] = "missing/background.png"
    game = runtime.game
    game.start_encounter("boss_room")
    adapter = runtime._battle_presentation
    adapter.begin()
    runtime._advance_to_hero_turn()
    runtime._present_battle(0.016)
    assert adapter.visuals_enabled and adapter.screen.scene.combatants
    assert runtime.screen.get_at((runtime.width // 2, 4))[:3] != (0, 0, 0)  # generated backdrop drawn
