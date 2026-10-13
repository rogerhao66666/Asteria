"""ENG-21: save slots — summaries, overwrite / delete confirmation, in-game save and load
screens."""

import pygame

from asteria.runtime.save_slots import SaveSlots, SlotMenu


def _key(rt, k):
    rt._frame([pygame.event.Event(pygame.KEYDOWN, key=k, mod=0)], 0.016)
    rt._frame([pygame.event.Event(pygame.KEYUP, key=k, mod=0)], 0.016)


def test_slots_summarise_save_and_report_damaged_files(runtime, tmp_path):
    slots = SaveSlots(tmp_path, runtime.project)
    assert [s.exists for s in map(slots.info, slots.slots())] == [False, False, False, False]
    slots.save("2", runtime.game)
    info = slots.info("2")
    assert (
        info.exists and info.scene == runtime.game.scene.name and info.level >= 1 and info.leader
    )
    assert "Lv" in info.summary
    slots.path("3").write_text("{not json")
    assert slots.info("3").error and "damaged" in slots.info("3").summary


def test_overwrite_and_delete_ask_twice(runtime, tmp_path):
    slots = SaveSlots(tmp_path, runtime.project)
    menu = SlotMenu(slots, "save")
    assert menu.slot == "1" and menu.activate(runtime.game)[0] == "saved"
    assert menu.activate(runtime.game)[0] == "confirm"  # slot 1 now exists
    assert menu.activate(runtime.game)[0] == "saved"
    assert not menu.delete() and slots.info("1").exists
    assert menu.delete() and not slots.info("1").exists
    load = SlotMenu(slots, "load")
    load.row = 1
    assert load.activate()[0] == "refused"


def test_save_to_a_slot_in_game_then_load_it_from_the_title(runtime, resource_root):
    game = runtime.game
    runtime._ui_mode = "field"
    game.set_player_position(12.0, -4.0)
    runtime.open_slots("save", back="pause")
    _key(runtime, pygame.K_DOWN)  # slot 2
    _key(runtime, pygame.K_RETURN)
    assert (resource_root / "saves" / "slot2.asteria-save.json").is_file()
    game.set_player_position(90.0, 30.0)
    runtime._ui_mode = "title"
    _key(runtime, pygame.K_l)
    assert runtime._ui_mode == "slots" and runtime.slot_menu.mode == "load"
    _key(runtime, pygame.K_DOWN)
    _key(runtime, pygame.K_DOWN)  # autosave -> slot 1 -> slot 2
    _key(runtime, pygame.K_RETURN)
    assert runtime._ui_mode == "field" and runtime.game.save.player_position == (12.0, -4.0)
    assert runtime.game is not game  # a fresh session from the slot
