"""Capturing a foe (RPG-08)."""

from __future__ import annotations

from asteria.rpg.built_in_text import translated

from .support import (  # noqa: F401 - the names the moved methods use
    BESTIARY_TAG_KINDS,
    FIELD_BODY_HEIGHT,
    WALK_PATTERN_SEQUENCE,
    WALK_ROW_BY_FACING,
    _load_manifest,
    field_player_render_size,
    walking_pattern_index,
    walking_row_index,
)


class CaptureMixin:
    # --- capture (RPG-08) ----------------------------------------------------

    def _capture_input(self, events):
        targets = self.game.capture_targets()
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key in (self.pg.K_ESCAPE, self.pg.K_x, self.pg.K_BACKSPACE):
                self._capture_menu = False
                return
            if self.pg.K_1 <= event.key <= self.pg.K_9 and event.key - self.pg.K_1 < len(targets):
                self._attempt_capture(targets[event.key - self.pg.K_1][0])
                return

    def _attempt_capture(self, target_id):
        actor = self._battle_actor()
        self._capture_menu = False
        if actor is None:
            return False
        name = target_id.split(":", 1)[0].replace("_", " ").title()
        tr = self.game.tr
        try:
            captured = self.game.attempt_capture(actor, target_id)
        except Exception as exc:
            reason = translated(exc, tr)
            self._last_action_name = tr(
                "capture.failed", "Capture failed: {reason}", reason=reason
            )
            return False
        if captured:
            self._last_action_name = tr("capture.caught", "Captured {name}!", name=name)
        else:
            self._last_action_name = tr("capture.broke_free", "{name} broke free", name=name)
        self._sound(self.manifest.get("dialogue_confirm_sfx") if captured else None)
        self._after_hero_action()
        return captured

    def _draw_capture_menu(self):
        targets = self.game.capture_targets()
        height = 70 + 30 * max(1, len(targets))
        self.panel((300, 190, 360, height), fill=(12, 18, 28, 240), border=(130, 200, 255))
        tr = self.game.tr
        title = tr("capture.title", "Capture")
        self.text(title, 480, 200, size=28, color=(175, 235, 255), center=True)
        inventory = self.save.rpg_state.inventory
        for i, (member_id, chance, item_id) in enumerate(targets, 1):
            name = member_id.split(":", 1)[0].replace("_", " ").title()
            need = ""
            if item_id:
                need = "  " + tr(
                    "capture.uses",
                    "(uses {item}: {count})",
                    item=item_id,
                    count=inventory.count(item_id),
                )
            self.text(f"{i}. {name}  {chance * 100:.0f}%{need}", 320, 236 + (i - 1) * 30, size=20)
        self.text(
            tr("capture.cancel", "Esc: cancel"),
            480,
            190 + height - 24,
            size=16,
            color=(170, 210, 240),
            center=True,
        )
