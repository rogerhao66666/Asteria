"""Audio buses, music and sound effects over a pluggable device (ASTERIA_SPEC §8 Audio).

``AudioMixer`` owns the policy: buses (``bgm``, ``ambient``, ``sfx`` and any
project-defined bus), per-bus and master volume, one current music track with
fade in/out and cross-fade, looping ambient layers and one-shot effects. An
``AudioDevice`` performs playback; ``platform.pygame_audio.PygameAudioDevice``
uses pygame.mixer, and ``RecordingAudioDevice`` records calls for headless
runs or machines without an output device.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

DEFAULT_BUSES = ("master", "bgm", "ambient", "sfx")


class AudioDevice(Protocol):
    def play_music(self, path: str, *, loops: int, fade_ms: int, volume: float) -> None: ...
    def stop_music(self, *, fade_ms: int) -> None: ...
    def set_music_volume(self, volume: float) -> None: ...
    def play_sound(self, path: str, *, loops: int, fade_ms: int, volume: float) -> object: ...
    def stop_sound(self, handle: object, *, fade_ms: int) -> None: ...
    def set_sound_volume(self, handle: object, volume: float) -> None: ...


@dataclass(slots=True)
class RecordingAudioDevice:
    """Records every call; used headless and when no real output device is available."""

    calls: list = field(default_factory=list)
    _next: int = 0

    def play_music(self, path, *, loops, fade_ms, volume):
        self.calls.append(("play_music", path, loops, fade_ms, round(volume, 4)))

    def stop_music(self, *, fade_ms):
        self.calls.append(("stop_music", fade_ms))

    def set_music_volume(self, volume):
        self.calls.append(("music_volume", round(volume, 4)))

    def play_sound(self, path, *, loops, fade_ms, volume):
        self._next += 1
        self.calls.append(("play_sound", path, loops, fade_ms, round(volume, 4)))
        return self._next

    def stop_sound(self, handle, *, fade_ms):
        self.calls.append(("stop_sound", handle, fade_ms))

    def set_sound_volume(self, handle, volume):
        self.calls.append(("sound_volume", handle, round(volume, 4)))


class AudioMixer:
    def __init__(self, device: AudioDevice, resolve_path):
        self.device = device
        self.resolve_path = resolve_path
        self.volumes = {bus: 1.0 for bus in DEFAULT_BUSES}
        self.music_asset_id: str | None = None
        self._music_volume = 1.0
        self._ambient: dict[str, tuple[object, float]] = {}
        self.missing: list[str] = []

    # -- volume -----------------------------------------------------------
    def _bus_volume(self, bus):
        return self.volumes.get("master", 1.0) * self.volumes.get(bus, 1.0)

    def set_volume(self, bus, volume):
        volume = max(0.0, min(1.0, float(volume)))
        self.volumes[str(bus)] = volume
        if self.music_asset_id is not None:
            self.device.set_music_volume(self._music_volume * self._bus_volume("bgm"))
        for handle, base in self._ambient.values():
            self.device.set_sound_volume(handle, base * self._bus_volume("ambient"))

    def _path(self, asset_id):
        path = self.resolve_path(asset_id)
        if path is None:
            if asset_id not in self.missing:
                self.missing.append(asset_id)
            return None
        return str(path)

    # -- music ------------------------------------------------------------
    def play_music(self, asset_id, *, fade_in=0.0, volume=1.0, restart=False):
        """Play a looping track; a different current track is replaced (cross-fade by fade_in)."""
        if asset_id == self.music_asset_id and not restart:
            return False
        path = self._path(asset_id)
        if path is None:
            return False
        if self.music_asset_id is not None:
            self.device.stop_music(fade_ms=int(fade_in * 1000))
        self._music_volume = max(0.0, min(1.0, float(volume)))
        self.device.play_music(path, loops=-1, fade_ms=int(fade_in * 1000),
                               volume=self._music_volume * self._bus_volume("bgm"))
        self.music_asset_id = asset_id
        return True

    def stop_music(self, *, fade_out=0.0):
        if self.music_asset_id is None:
            return False
        self.device.stop_music(fade_ms=int(fade_out * 1000))
        self.music_asset_id = None
        return True

    # -- ambient / effects --------------------------------------------------
    def play_ambient(self, asset_id, *, fade_in=0.0, volume=1.0):
        if asset_id in self._ambient:
            return False
        path = self._path(asset_id)
        if path is None:
            return False
        volume = max(0.0, min(1.0, float(volume)))
        handle = self.device.play_sound(path, loops=-1, fade_ms=int(fade_in * 1000),
                                        volume=volume * self._bus_volume("ambient"))
        self._ambient[asset_id] = (handle, volume)
        return True

    def stop_ambient(self, asset_id, *, fade_out=0.0):
        entry = self._ambient.pop(asset_id, None)
        if entry is None:
            return False
        self.device.stop_sound(entry[0], fade_ms=int(fade_out * 1000))
        return True

    def play_effect(self, asset_id, *, volume=1.0, bus="sfx"):
        path = self._path(asset_id)
        if path is None:
            return None
        return self.device.play_sound(path, loops=0, fade_ms=0,
                                      volume=max(0.0, min(1.0, float(volume))) * self._bus_volume(bus))

    # -- WORLD command requests from event programs ------------------------
    def handle_world_request(self, command):
        """Apply a PLAY_BGM / STOP_BGM / PLAY_SE request queued by GameSessionRuntime."""
        args = command.args
        name = command.name
        if name == "PLAY_BGM":
            return self.play_music(str(args.get("asset_id", "")), fade_in=float(args.get("fade", 0.0)),
                                   volume=float(args.get("volume", 1.0)))
        if name == "STOP_BGM":
            return self.stop_music(fade_out=float(args.get("fade", 0.0)))
        if name == "PLAY_SE":
            return self.play_effect(str(args.get("asset_id", "")), volume=float(args.get("volume", 1.0)))
        return None
