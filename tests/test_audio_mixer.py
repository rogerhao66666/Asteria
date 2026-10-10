"""CB6: audio buses, music, ambient, effects and runtime integration (ASTERIA_SPEC §8 Audio)."""

import shutil
from pathlib import Path

import pytest

from asteria.events import WorldCommand
from asteria.runtime.audio_mixer import AudioMixer, RecordingAudioDevice

REF = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"
AUDIO = REF / "playable_assets" / "audio"


def _mixer():
    device = RecordingAudioDevice()
    paths = {"town": "town.ogg", "boss": "boss.ogg", "hit": "hit.wav", "rain": "rain.wav"}
    return device, AudioMixer(device, paths.get)


def test_music_cross_fades_and_ignores_repeat_requests():
    device, mixer = _mixer()
    assert mixer.play_music("town", fade_in=0.5)
    assert not mixer.play_music("town")
    mixer.play_music("boss", fade_in=1.0)
    assert device.calls == [
        ("play_music", "town.ogg", -1, 500, 1.0),
        ("stop_music", 1000),
        ("play_music", "boss.ogg", -1, 1000, 1.0),
    ]
    assert mixer.stop_music(fade_out=0.25) and device.calls[-1] == ("stop_music", 250)
    assert not mixer.stop_music()


def test_bus_and_master_volumes_scale_playback():
    device, mixer = _mixer()
    mixer.set_volume("master", 0.5)
    mixer.set_volume("sfx", 0.5)
    mixer.play_effect("hit", volume=0.8)
    assert device.calls[-1] == ("play_sound", "hit.wav", 0, 0, 0.2)
    mixer.play_music("town")
    mixer.set_volume("bgm", 0.4)
    assert ("music_volume", 0.2) in device.calls


def test_ambient_layers_loop_and_stop_and_missing_assets_are_reported():
    device, mixer = _mixer()
    assert mixer.play_ambient("rain", volume=0.5)
    assert not mixer.play_ambient("rain")
    assert device.calls[-1][:3] == ("play_sound", "rain.wav", -1)
    assert mixer.stop_ambient("rain", fade_out=1.0) and device.calls[-1] == ("stop_sound", 1, 1000)
    assert mixer.play_effect("nope") is None and mixer.missing == ["nope"]


def test_world_requests_from_event_programs_drive_the_mixer():
    device, mixer = _mixer()
    mixer.handle_world_request(WorldCommand("PLAY_BGM", {"asset_id": "boss", "fade": 2}))
    mixer.handle_world_request(WorldCommand("PLAY_SE", {"asset_id": "hit"}))
    mixer.handle_world_request(WorldCommand("STOP_BGM", {"fade": 1}))
    assert [c[0] for c in device.calls] == ["play_music", "play_sound", "stop_music"]


def test_pygame_device_plays_the_committed_files(monkeypatch):
    pygame = pytest.importorskip("pygame")
    from asteria.platform.pygame_audio import PygameAudioDevice, open_audio_device

    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    try:
        device = open_audio_device(pygame)
        assert isinstance(device, PygameAudioDevice)
        mixer = AudioMixer(device, lambda name: AUDIO / name)
        assert mixer.play_music("field_theme.ogg", fade_in=0.1)
        assert mixer.play_effect("hit.wav") is not None or pygame.mixer.get_num_channels() > 0
        mixer.stop_music()
    finally:
        pygame.mixer.quit()


def test_playable_runtime_plays_field_battle_and_victory_audio(monkeypatch, tmp_path):
    pygame = pytest.importorskip("pygame")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_save import GameRuntimeSave
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    shutil.copy(REF / "playable_test_manifest.json", tmp_path / "playable_test_manifest.json")
    shutil.copytree(REF / "playable_assets", tmp_path / "playable_assets")
    project = Project.load_json(REF / "project.asteria.json", EditorDocument().component_registry)
    save = GameRuntimeSave.load_json(REF / "saves" / "boss_stress.asteria-save.json", project)
    runtime = PlayableTestRuntime(project, save, tmp_path)
    runtime.open()
    device = RecordingAudioDevice()
    runtime.audio.device = device
    monkeypatch.setattr(runtime, "_play_fx", lambda *a, **k: None)
    key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k)  # noqa: E731
    try:
        runtime._ui_mode = "field"
        runtime._frame([], 0.016)
        assert runtime.audio.music_asset_id == "field_theme"
        runtime._frame([key(pygame.K_e)], 0.016)
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        assert runtime.audio.music_asset_id == "battle_theme"
        for _ in range(3000):                   # actions play their choreography before the next input
            if runtime._victory or runtime._defeat:
                break
            runtime._frame([key(pygame.K_1)], 0.05)
        for _ in range(400):                    # the jingle waits until the final blows have been shown
            if not runtime._presentation_busy():
                break
            runtime._frame([], 0.05)
        runtime._frame([], 0.016)
        played = [Path(c[1]).name for c in device.calls if c[0] == "play_sound"]
        assert "confirm.wav" in played and "hit.wav" in played
        assert runtime._victory and played[-1] == "victory.wav", played[-4:]
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        runtime._frame([], 0.016)
        assert runtime.audio.music_asset_id == "field_theme"
        assert runtime.audio.missing == []
    finally:
        runtime.close()
