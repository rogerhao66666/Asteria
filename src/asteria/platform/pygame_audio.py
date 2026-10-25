"""pygame.mixer implementation of runtime.audio_mixer.AudioDevice."""

from __future__ import annotations

import time

from asteria.runtime.audio_mixer import RecordingAudioDevice


class PygameAudioDevice:
    """Music streams through ``pygame.mixer.music``; sounds play on mixer channels."""

    def __init__(self, pg, clock=time.monotonic):
        self.pg = pg
        self._sounds = {}
        self._clock = clock
        self._fading_until = 0.0  # when the music fading out now falls silent
        self._queued = False  # a track waits for that fade to end

    def _sound(self, path):
        sound = self._sounds.get(path)
        if sound is None:
            sound = self._sounds[path] = self.pg.mixer.Sound(path)
        return sound

    def play_music(self, path, *, loops, fade_ms, volume):
        music = self.pg.mixer.music
        if self._clock() < self._fading_until and music.get_busy():
            # loading now would wait for the old track to fade out: the game froze for the
            # whole fade (half a second on every scene change). The new track waits its turn
            # instead and starts the moment the old one falls silent.
            try:
                music.queue(path, loops=loops)
            except TypeError:  # an older pygame without loops: load and wait, as before
                pass
            else:
                music.set_volume(volume)
                self._queued = True
                return
        self._fading_until = 0.0
        self._queued = False
        music.load(path)
        music.set_volume(volume)
        music.play(loops=loops, fade_ms=fade_ms)

    def stop_music(self, *, fade_ms):
        if fade_ms > 0 and not self._queued:
            self.pg.mixer.music.fadeout(fade_ms)
            self._fading_until = self._clock() + fade_ms / 1000.0
        else:  # no fade, or a track queued behind the fade (stopping must cancel it too)
            self.pg.mixer.music.stop()
            self._fading_until = 0.0
            self._queued = False

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

    def pause_music(self):
        self.pg.mixer.music.pause()

    def resume_music(self):
        self.pg.mixer.music.unpause()

    def sound_busy(self, handle):
        return handle is not None and bool(handle.get_busy())


def open_audio_device(pg):
    """A pygame device when an output device can be opened, else a recording device.
    ``ASTERIA_MUTE=1`` always gives the silent recording device: automated real-window runs
    and browser checks on a developer's machine make no sound."""
    import os

    if os.environ.get("ASTERIA_MUTE", "").strip() not in ("", "0"):
        return RecordingAudioDevice()
    try:
        if not pg.mixer.get_init():
            pg.mixer.init()
        return PygameAudioDevice(pg)
    except Exception:
        return RecordingAudioDevice()
