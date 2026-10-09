"""pygame.mixer implementation of runtime.audio_mixer.AudioDevice."""
from __future__ import annotations

from asteria.runtime.audio_mixer import RecordingAudioDevice


class PygameAudioDevice:
    """Music streams through ``pygame.mixer.music``; sounds play on mixer channels."""

    def __init__(self, pg):
        self.pg = pg
        self._sounds = {}

    def _sound(self, path):
        sound = self._sounds.get(path)
        if sound is None:
            sound = self._sounds[path] = self.pg.mixer.Sound(path)
        return sound

    def play_music(self, path, *, loops, fade_ms, volume):
        self.pg.mixer.music.load(path)
        self.pg.mixer.music.set_volume(volume)
        self.pg.mixer.music.play(loops=loops, fade_ms=fade_ms)

    def stop_music(self, *, fade_ms):
        if fade_ms > 0:
            self.pg.mixer.music.fadeout(fade_ms)
        else:
            self.pg.mixer.music.stop()

    def set_music_volume(self, volume):
        self.pg.mixer.music.set_volume(volume)

    def play_sound(self, path, *, loops, fade_ms, volume):
        sound = self._sound(path)
        channel = sound.play(loops=loops, fade_ms=fade_ms)
        if channel is not None:
            channel.set_volume(volume)
        return channel

    def stop_sound(self, handle, *, fade_ms):
        if handle is None:
            return
        if fade_ms > 0:
            handle.fadeout(fade_ms)
        else:
            handle.stop()

    def set_sound_volume(self, handle, volume):
        if handle is not None:
            handle.set_volume(volume)


def open_audio_device(pg):
    """A pygame device when an output device can be opened, else a recording device."""
    try:
        if not pg.mixer.get_init():
            pg.mixer.init()
        return PygameAudioDevice(pg)
    except Exception:
        return RecordingAudioDevice()
