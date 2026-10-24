"""Capturing a foe (RPG-08), and the creature party's prompts: which item to throw, which
creature to send out when a slot empties, which move to forget for a new one."""

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

_PANEL_FILL, _PANEL_BORDER, _TITLE = (12, 18, 28, 240), (130, 200, 255), (175, 235, 255)


def _number_key(pg, event, count):
    """The 0-based index a 1-9 key names, or None."""
    if event.type != pg.KEYDOWN or not (pg.K_1 <= event.key <= pg.K_9):
        return None
    index = event.key - pg.K_1
    return index if index < count else None


class CaptureMixin:
    # --- capture (RPG-08) ----------------------------------------------------

    def _capture_input(self, events):
        targets = self.game.capture_targets()
        pg = self.pg
        for event in events:
            if event.type != pg.KEYDOWN:
                continue
            if event.key in (pg.K_ESCAPE, pg.K_x, pg.K_BACKSPACE):
                if self._capture_item_menu is not None:
                    self._capture_item_menu = None  # back to the targets
                else:
                    self._capture_menu = False
                return
            if self._capture_item_menu is not None:
                items = self.game.capture_items(self._capture_item_menu)
                index = _number_key(pg, event, len(items))
                if index is not None:
                    self._attempt_capture(self._capture_item_menu, items[index][0])
                return
            index = _number_key(pg, event, len(targets))
            if index is not None:
                target_id = targets[index][0]
                items = self.game.capture_items(target_id)
                if len(items) > 1:  # several throwable items: the player picks one
                    self._capture_item_menu = target_id
                    return
                self._attempt_capture(target_id, items[0][0] if items else None)
                return

    def _attempt_capture(self, target_id, item_id=None):
        actor = self._battle_actor()
        self._capture_menu, self._capture_item_menu = False, None
        if actor is None:
            return False
        name = self.battle_commands.display_name(target_id)
        tr = self.game.tr
        try:
            captured = self.game.attempt_capture(actor, target_id, item_id=item_id)
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

    def _prompt_panel(self, title, rows, hint, *, row_size=20):
        """A centred prompt: a title, numbered rows and a hint line."""
        height = 70 + 30 * max(1, len(rows))
        width = 420
        x, y = self.width / 2 - width / 2, 190
        self.panel((x, y, width, height), fill=_PANEL_FILL, border=_PANEL_BORDER)
        self.text(title, self.width / 2, y + 10, size=28, color=_TITLE, center=True)
        for i, row in enumerate(rows, 1):
            self.text(f"{i}. {row}", x + 20, y + 46 + (i - 1) * 30, size=row_size)
        self.text(
            hint, self.width / 2, y + height - 24, size=16, color=(170, 210, 240), center=True
        )

    def _draw_capture_menu(self):
        tr = self.game.tr
        inventory = self.save.rpg_state.inventory
        names = {k: self.game.name_of(v) for k, v in self.game.project.rpg_database.items.items()}
        if self._capture_item_menu is not None:
            rows = [
                tr(
                    "capture.item_row",
                    "{item} x{count}   {chance}%",
                    item=names.get(item_id, item_id),
                    count=inventory.count(item_id),
                    chance=f"{chance * 100:.0f}",
                )
                for item_id, chance in self.game.capture_items(self._capture_item_menu)
            ]
            title = self.battle_commands.display_name(self._capture_item_menu)
            self._prompt_panel(
                title, rows, tr("capture.ball", "Throw which? 1-9: an item   Esc: cancel")
            )
            return
        rows = []
        for member_id, chance, item_id in self.game.capture_targets():
            name = self.battle_commands.display_name(member_id)
            need = ""
            if item_id:
                need = "  " + tr(
                    "capture.uses",
                    "(uses {item}: {count})",
                    item=names.get(item_id, item_id),
                    count=inventory.count(item_id),
                )
            rows.append(f"{name}  {chance * 100:.0f}%{need}")
        self._prompt_panel(
            tr("capture.title", "Capture"), rows, tr("capture.cancel", "Esc: cancel")
        )

    # --- the bench: who comes in when a slot empties -----------------------

    def _switch_rows(self):
        game, tr = self.game, self.game.tr
        rows = []
        for member_id in game.bench_ids("heroes"):
            member = game.battle.member(member_id)
            record = game.unit_record(member_id)
            pool = member.subject.resources
            hp = game.rules.knockout_resource_id
            rows.append(
                tr(
                    "switch.row",
                    "{name}   Lv {level}   HP {current}/{maximum}",
                    name=self.battle_commands.display_name(member_id),
                    level=record.level if record is not None else "",
                    current=f"{pool.current(hp):g}" if pool.contains(hp) else "",
                    maximum=f"{pool.maximum(hp):g}" if pool.contains(hp) else "",
                )
            )
        return rows

    def _switch_input(self, events):
        """A creature fell and the bench can fill its place: 1-9 sends one out."""
        game = self.game
        if game.battle is None or not game.switch_needed("heroes"):
            self._switch_menu = False
            return
        bench = game.bench_ids("heroes")
        for event in events:
            index = _number_key(self.pg, event, len(bench))
            if index is None:
                continue
            try:
                game.send_in_pet(bench[index])
            except Exception as exc:
                self._last_action_name = translated(exc, game.tr)
                return
            self._switch_menu = False
            self._advance_to_hero_turn()
            return

    def _draw_switch_menu(self):
        tr = self.game.tr
        self._prompt_panel(
            tr("switch.title", "Send out which?"),
            self._switch_rows(),
            tr("switch.hint", "1-9: choose"),
        )

    # --- a move learned past the limit --------------------------------------

    def _learn_pending(self):
        pending = self.game.pending_pet_moves()
        return pending[0] if pending else None

    def _learn_names(self):
        library = self.game.project.gameplay_library.abilities
        return lambda ability_id: (
            getattr(library.get(ability_id), "display_name", "") or ability_id
        )

    def _learn_input(self, events):
        game, tr = self.game, self.game.tr
        pending = self._learn_pending()
        if pending is None:
            self._ui_mode = "field"
            return
        instance_id, ability_id = pending
        pet = game._pet(instance_id)
        moves = game.pet_moves(pet)
        name_of = self._learn_names()
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key in (self.pg.K_ESCAPE, self.pg.K_BACKSPACE):
                game.learn_pet_move(instance_id, ability_id, "")
                game.notify(
                    tr(
                        "pets.not_learned",
                        "{name} did not learn {move}",
                        name=game.pet_display(pet),
                        move=name_of(ability_id),
                    )
                )
            index = _number_key(self.pg, event, len(moves))
            if index is not None:
                game.learn_pet_move(instance_id, ability_id, moves[index])
                game.notify(
                    tr(
                        "pets.learned",
                        "{name} learned {move}",
                        name=game.pet_display(pet),
                        move=name_of(ability_id),
                    )
                )
        if self._learn_pending() is None:
            self._ui_mode = "field"

    def _draw_learn_prompt(self):
        game, tr = self.game, self.game.tr
        pending = self._learn_pending()
        if pending is None:
            return
        instance_id, ability_id = pending
        pet = game._pet(instance_id)
        name_of = self._learn_names()
        title = tr(
            "pets.learn_title",
            "{name} wants to learn {move}",
            name=game.pet_display(pet),
            move=name_of(ability_id),
        )
        rows = [name_of(m) for m in game.pet_moves(pet)]
        hint = tr("pets.learn_hint", "1-9: forget that move and learn it   Esc: do not learn")
        self._prompt_panel(title, rows, hint)
