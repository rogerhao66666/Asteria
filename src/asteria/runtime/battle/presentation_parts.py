"""Pieces the battle adapter's parts share: the world-then-UI draw order and the side and
channel names."""

from __future__ import annotations

from asteria.gameplay import ActionCueKind

CHANNEL_KINDS = {
    "animation": ActionCueKind.ANIMATION,
    "vfx": ActionCueKind.VFX,
    "audio": ActionCueKind.AUDIO,
    "camera": ActionCueKind.CAMERA,
    "screen_fx": ActionCueKind.SCREEN_FX,
}


# the session's player side: a Portrait Party Layout keeps it in the HUD
PARTY_SIDES = ("heroes",)


class _WorldThenUi:
    """Texture pass of the battle screen; afterwards the host switches drawing to its UI layer
    (VFX-02)."""

    def __init__(self, adapter, textures):
        self.adapter, self.textures, self.done = adapter, textures, False

    def render(self, draws):
        if self.textures is not None:
            self.textures.render(draws)
        self.finish()

    def finish(self):
        self.done = True
        host = self.adapter.host
        if hasattr(host, "world_done"):
            host.world_done("battle")
            self.adapter._ui_backend.screen = host.screen
