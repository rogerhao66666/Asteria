"""Real-window check of the creature battle screen (``battle.style: "creature"``, D58).

    python scripts/creature_battle_live_check.py OUTPUT_DIR [--art DIR] [--skin FILE DIR]

Opens the Full Verification demo in a real (Cocoa) window at 960 x 640 (the 240 x 160 screen
four times) with the creature party laid over it in memory (``trial_creatures``) and plays,
with real frames and key presses, a wild battle (the foe appears, Go!, the commands, the moves,
a super-effective hit, the foe's turn, the bag's two pockets, a ball shaking and the catch), a
trainer battle (the challenge, the trainer's creature, no running, the party screen, a switch,
a creature fainting and the forced choice, the trainer's next creature, the win and the prize),
a legendary encounter and the same wild battle in Traditional Chinese.

Pictures: ``--art DIR`` reads ``DIR/front/<species>.png`` and ``DIR/back/<species>.png``
(any project art); without it CC0 Foozle critters from ``asset_library/`` stand in (written to
OUTPUT_DIR/art). ``--skin FILE DIR`` loads a project's own skin file (see ``_load_skin``)
with its art folder ``DIR``: its pictures, windows, fonts, songs, and the creatures, moves and
player renamed to match. Every step is saved as
``creature_<step>.png``; ``creature_results.json`` lists what each step showed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(DEMO))
for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
    os.environ.pop(key, None)

HP = "vitality"
FOOZLE = REPO / "asset_library" / "characters"  # the critter packs
STAND_INS = {  # species -> (critter idle sheet, faces left)
    "cub": (
        "Foozle_2DC0022_RealmOfCritters_Mouse_Pixel_Art/Mouse/Spritesheet/Player Idle.png",
        False,
    ),
    "wolf": (
        "Foozle_2DC0026_Critters_EnemyPack3_Pixel_Art/Newt Slinger/PNGs/Newt Slinger Idle.png",
        True,
    ),
    "titan": (
        "Foozle_2DC0026_Critters_EnemyPack3_Pixel_Art/Turtle King/PNGs/Turtle King Idle.png",
        True,
    ),
    "youngster": (
        "Foozle_2DC0026_Critters_EnemyPack3_Pixel_Art/Weasel Fisherman/PNGs/"
        "Weasel Fisherman Idle.png",
        True,
    ),
}


def _helpers():
    spec = importlib.util.spec_from_file_location(
        "real_machine_validation", REPO / "scripts" / "real_machine_validation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stand_in_art(out):
    """64 x 64 front (facing left) and back (facing right) pictures from the critters."""
    import pygame

    art = out / "art"
    for side in ("front", "back"):
        (art / side).mkdir(parents=True, exist_ok=True)
    for species, (relative, faces_left) in STAND_INS.items():
        sheet = pygame.image.load(str(FOOZLE / relative))
        size = sheet.get_height()
        frame = sheet.subsurface((0, 0, size, size)).copy()
        box = frame.get_bounding_rect()
        frame = frame.subsurface(box).copy()
        scale = max(1, 56 // max(box.width, box.height))
        frame = pygame.transform.scale(frame, (box.width * scale, box.height * scale))
        canvas = pygame.Surface((64, 64), pygame.SRCALPHA)
        canvas.blit(frame, frame.get_rect(midbottom=(32, 62)))
        front = canvas if faces_left else pygame.transform.flip(canvas, True, False)
        pygame.image.save(front, str(art / "front" / f"{species}.png"))
        pygame.image.save(
            pygame.transform.flip(front, True, False), str(art / "back" / f"{species}.png")
        )
    return art


def _load_skin(path):
    """A skin file (``--skin FILE DIR``): ``art(source, out)``, ``apply(project, source, art)``
    (``{item_id: count}`` to carry), ``screen(source, art)`` (over ``creature_screen``),
    ``audio(source)``, ``TITLE`` and ``NICKNAME`` - all optional."""
    spec = importlib.util.spec_from_file_location("creature_check_skin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project(art):
    import trial_creatures

    from asteria.gameplay.abilities import AbilityDefinition
    from asteria.project import Project
    from asteria.rpg import InteractionRule
    from asteria.rpg.characters.pets import PetExpCurve, PetMove, PetSpeciesDefinition
    from asteria.rpg.enemies.definitions import EncounterDefinition, EncounterMember
    from asteria.runtime.component_registry import default_component_registry

    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    trial_creatures.install(project, max_moves=4, party_size=6)
    db = project.rpg_database
    library = project.gameplay_library.abilities
    for ability_id, kind, uses in (
        ("pet_shot", "normal", 3),
        ("pet_volley", "flying", 20),
        ("pet_bandage", "normal", 10),
    ):
        data = library.require(ability_id).to_data()
        data["tags"] = sorted({*data["tags"], f"type.{kind}"})
        data["max_uses"] = uses
        for entry in data["effects"]:  # the demo's numbers are for 700-HP heroes: GBA scale
            for operation in entry["effect"]["operations"]:
                value = operation.get("value")
                if isinstance(value, dict) and value.get("terms"):
                    for term in value["terms"]:
                        term["coefficient"] = round(term["coefficient"] * 0.04, 3)
        library._definitions[ability_id] = AbilityDefinition.from_data(data)
    db.add_interaction_rule(
        InteractionRule(
            "flying_beats_bug",
            source_tags_any=("type.flying",),
            target_tags_any=("type.bug",),
            multiplier=2.0,
        )
    )
    wolf = db.pet_species["wolf"]
    db.pet_species["wolf"] = PetSpeciesDefinition.from_data(
        {**wolf.to_data(), "tags": ["type.bug"]}
    )
    db.add_pet_species(
        PetSpeciesDefinition(
            "titan",
            "Titan",
            stats={"power": 40, "magic": 90, "defense": 60, "speed": 50, HP: 120},
            growth={},
            battle_unit=True,
            resources={HP: 1},
            battle_abilities=("pet_shot",),
            learnset=(PetMove("pet_volley", level=40),),
            exp_curve=PetExpCurve(cubic=(1, 0, 0, 0)),
            exp_yield=200,
            capture_rate=3,
        )
    )
    for encounter_id, members, tags in (
        ("wild_one", [EncounterMember(pet_species_id="wolf", level=5)], ()),
        (
            "trainer_youngster",
            [
                EncounterMember(pet_species_id="wolf", level=5, moves=("pet_shot",)),
                EncounterMember(pet_species_id="cub", level=6, reserve=True, moves=("pet_shot",)),
            ],
            ("no_capture", "no_escape"),
        ),
        ("legend", [EncounterMember(pet_species_id="titan", level=40)], ("legendary",)),
    ):
        db.encounters.pop(encounter_id, None)
        db.add_encounter(EncounterDefinition(encounter_id, members=members, tags=tags))
    assert db.reference_errors() == []
    return project


def main(argv=None):
    import pygame

    from asteria.events import WorldCommand
    from asteria.runtime.creature.battle import CreatureBattleScreen
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    art_dir = skin = source = None
    if "--skin" in argv:
        index = argv.index("--skin")
        skin = _load_skin(Path(argv[index + 1]).expanduser())
        source = Path(argv[index + 2]).expanduser()
        del argv[index : index + 3]
    if "--art" in argv:
        index = argv.index("--art")
        art_dir = Path(argv[index + 1]).expanduser()
        del argv[index : index + 2]
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "creature_battle")
    out.mkdir(parents=True, exist_ok=True)
    helper = _helpers()
    pump, key = helper._pump, helper._key
    pygame.init()
    if art_dir is None:
        has_art = skin is not None and hasattr(skin, "art")
        art_dir = skin.art(source, out) if has_art else _stand_in_art(out)
    art = art_dir
    project = _project(art)
    carried = skin.apply(project, source, art) if hasattr(skin, "apply") else {}
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=640
    )
    if hasattr(skin, "TITLE"):
        runtime.manifest["title"] = skin.TITLE
    runtime.open()
    runtime.manifest.setdefault("battle", {})["style"] = "creature"
    runtime.manifest["battle"]["creature_screen"] = {
        "front": str(art / "front" / "{species}.png"),
        "back": str(art / "back" / "{species}.png"),
        "trainer": str(art / "front" / "{trainer}.png"),
        **(skin.screen(source, art) if hasattr(skin, "screen") else {}),
        "trainers": {
            "trainer_youngster": {
                "title": "YOUNGSTER",
                "name": "CALVIN",
                "sprite": "youngster",
                "prize": 160,
            }
        },
    }
    if hasattr(skin, "audio"):
        runtime.manifest.setdefault("audio", {}).update(skin.audio(source))
    driver = pygame.display.get_driver()
    game = runtime.game
    steps = []

    first = game.add_pet("cub", level=7, nickname=getattr(skin, "NICKNAME", "MOCHI"))
    first.moves = ["pet_shot", "pet_volley", "pet_bandage"]
    second = game.add_pet("wolf", level=6)
    second.moves = ["pet_shot", "pet_bandage"]
    inventory = game.save.rpg_state.inventory
    inventory.add("pet_ball", 5)
    inventory.add("great_ball", 2)
    for item_id, count in carried.items():
        inventory.add(item_id, count)
    runtime._ui_mode = "title"
    pump(runtime, 0.3)
    key(pygame.K_n)
    pump(runtime, 0.1)
    key(pygame.K_n, up=True)
    pump(runtime, 0.4)

    def screen():
        return runtime._creature_battle

    def shot(name, **facts):
        pump(runtime, 0.1)
        pygame.image.save(runtime.capture(), str(out / f"creature_{name}.png"))
        current = screen()
        entry = {"step": name, **facts}
        if current is not None:
            entry.update(phase=current.phase, message=current.message)
        steps.append(entry)
        print(name, json.dumps(entry, ensure_ascii=False, default=str))
        return entry

    def press(k, seconds=0.25):
        """A key pressed and released (the input reads held keys: a key never let go would
        never be pressed again)."""
        key(k)
        pump(runtime, 0.05)
        key(k, up=True)
        pump(runtime, max(0.05, seconds - 0.05))

    def typed():
        current = screen()
        return (
            current is not None
            and current.step is not None
            and current.step.kind == "text"
            and current.shown_chars >= len(current.message)
            and not current._drain_bars(0.0)
        )

    def until(condition, seconds=10.0):
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            if condition():
                return True
            pump(runtime, 0.05)
        return bool(condition())

    def text(fragment, seconds=12.0):
        """Advance the story (confirm on every finished line) until a line with ``fragment``
        is fully shown; returns whether it was reached."""
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            current = screen()
            if current is None:
                return False
            if typed() and fragment in current.message:
                return True
            if typed():
                press(pygame.K_RETURN, 0.1)
            else:
                pump(runtime, 0.05)
        return False

    def to_phase(phase, seconds=15.0):
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            current = screen()
            if current is None or current.phase == phase:
                return current is not None
            if typed():
                press(pygame.K_RETURN, 0.1)
            else:
                pump(runtime, 0.05)
        return False

    def fight():
        """The cursor back on FIGHT (the menu remembers it, as the game's does), then open it
        with the first move chosen."""
        press(pygame.K_UP)
        press(pygame.K_LEFT)
        press(pygame.K_RETURN)
        press(pygame.K_UP)
        press(pygame.K_LEFT)

    def close_battle(limit=120):
        """Confirm the remaining lines until the battle screen closes (at most ``limit``)."""
        for _ in range(limit):
            if screen() is None:
                return True
            press(pygame.K_RETURN, 0.15)
        raise SystemExit("the battle screen did not close")

    def battle(encounter_id):
        game.start_encounter(encounter_id)
        runtime._creature_battle = CreatureBattleScreen(runtime)
        start = runtime._creature_battle.music("start") or runtime.manifest["battle"].get("bgm")
        runtime._music(start)  # as the field does when a fight starts
        pump(runtime, 0.2)

    def tracks_played():
        """The music the (silent) audio device was asked to play, in order."""
        calls = getattr(runtime.audio.device, "calls", [])
        return [Path(c[1]).stem for c in calls if c[0] == "play_music"]

    # -- a wild battle --------------------------------------------------------------------------
    battle("wild_one")
    text("appeared")
    shot("01_wild_appeared")
    text("Go!")
    shot("02_go")
    to_phase("command")
    shot("03_commands")
    press(pygame.K_RETURN)
    shot("04_moves")
    press(pygame.K_RIGHT)
    shot("05_move_selected", cursor=screen().list_cursor)
    press(pygame.K_RETURN, 0.1)
    until(lambda: screen() is not None and "used" in screen().message, 8)
    shot("06_used_move")
    text("super effective")
    shot("07_super_effective")
    wild_foe = game.stage_ids("enemies")[0]
    until(lambda: typed() and "Wild" in screen().message and "used" in screen().message, 8)
    shot("08_foe_turn")
    to_phase("command")
    press(pygame.K_RIGHT)
    press(pygame.K_RETURN)
    shot("09_bag_items")
    press(pygame.K_RIGHT)
    shot("10_bag_balls")
    game.battle.member(wild_foe).subject.resources.set_current(HP, 1.0)
    screen().shown_hp[wild_foe] = screen().target_hp[wild_foe] = 1.0
    press(pygame.K_DOWN)
    press(pygame.K_RETURN, 0.1)  # the Great Ball
    until(lambda: screen() is not None and screen().throw is not None, 4)
    pump(runtime, 1.2)
    shot("11_ball_shaking")
    text("Gotcha")
    shot("12_caught", pets=[p.instance_id for p in game.pets()])
    until(lambda: screen() is None, 15) or [press(pygame.K_RETURN, 0.2) for _ in range(12)]
    close_battle()

    # -- a trainer battle -----------------------------------------------------------------------
    game.heal_pets()
    battle("trainer_youngster")
    text("would like to battle")
    shot("13_trainer_challenge")
    text("sent out")
    shot("14_trainer_sent_out")
    to_phase("command")
    press(pygame.K_RIGHT)
    press(pygame.K_DOWN)
    press(pygame.K_RETURN, 0.1)  # RUN
    text("no running")
    shot("15_no_running")
    to_phase("command")
    press(pygame.K_LEFT)
    press(pygame.K_RETURN)  # PARTY
    shot("16_party_screen")
    press(pygame.K_DOWN)
    press(pygame.K_RETURN, 0.1)
    text("come back")
    shot("17_come_back")
    text("Go!")
    shot("18_switch_go")
    to_phase("command")
    mine = game.stage_ids("heroes")[0]
    game.battle.member(mine).subject.resources.set_current(HP, 1.0)
    screen().shown_hp[mine] = screen().target_hp[mine] = 1.0
    foe = game.stage_ids("enemies")[0]
    game.battle.member(foe).subject.resources.set_current(HP, 999.0)
    press(pygame.K_UP)
    press(pygame.K_LEFT)
    press(pygame.K_RETURN)
    press(pygame.K_RETURN, 0.1)  # FIGHT, the first move
    text("fainted")
    shot("19_mine_fainted")
    to_phase("party")
    shot("20_forced_party")
    # the party in the battle's order (the fallen one first): the first that can fight
    standing = next(
        i
        for i, pet in enumerate(screen()._party())
        if game.pet_member_id(pet) in game.bench_ids("heroes")
    )
    for _ in range(standing):
        press(pygame.K_DOWN, 0.1)
    press(pygame.K_RETURN, 0.1)
    text("Go!")
    shot("21_sent_back_in")
    to_phase("command")
    asked = []

    def advance_to(*fragments, seconds=12.0):
        """Advance the story until a fully shown line has one of ``fragments`` (which is
        returned); the trainer's "change creatures?" is answered NO (shown once)."""
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            current = screen()
            if current is None:
                return None
            if current.phase == "yesno":
                if not asked:
                    asked.append(shot("22a_change_asked"))
                press(pygame.K_DOWN, 0.1)
                press(pygame.K_RETURN, 0.1)
                continue
            if typed():
                found = next((f for f in fragments if f in current.message), None)
                if found:
                    return found
                press(pygame.K_RETURN, 0.1)
            else:
                pump(runtime, 0.05)
        return None

    for _ in range(8):  # the trainer's creatures fall one by one (a blow may miss: again)
        if screen() is None or game.battle is None or not game.stage_ids("enemies"):
            break
        foe = game.stage_ids("enemies")[0]
        game.battle.member(foe).subject.resources.set_current(HP, 1.0)
        screen().shown_hp[foe] = screen().target_hp[foe] = 1.0
        mine = game.stage_ids("heroes")[0]  # ours stands: the foe falls first, whoever is faster
        pool = game.battle.member(mine).subject.resources
        pool.set_current(HP, pool.maximum(HP))
        screen().shown_hp[mine] = screen().target_hp[mine] = pool.maximum(HP)
        game.battle.member(mine).subject.stats.set("speed", 999.0)
        fight()
        press(pygame.K_RETURN, 0.1)
        if advance_to("fainted", "do?") != "fainted":
            continue  # missed: the command menu again
        if advance_to("sent out", "defeated") == "defeated":
            break
        shot("22_trainer_next")
        to_phase("command")
    text("defeated")
    shot("23_defeated_trainer")
    text("for winning")
    shot("24_prize", gold=game.save.rpg_state.currencies.get("gold"))
    close_battle()

    # -- a legendary ----------------------------------------------------------------------------
    game.heal_pets()
    battle("legend")
    text("appeared")
    shot("25_legendary")
    to_phase("command")
    game.mode, game.battle, runtime._creature_battle = "field", None, None  # leave it there
    pump(runtime, 0.2)

    # -- no move uses left: Struggle (a hit that costs the user a quarter of its health) ------
    game.heal_pets()
    battle("wild_one")
    to_phase("command")
    mine = game.stage_ids("heroes")[0]
    for move in game.battle.member(mine).ability_ids:
        if game.pet_uses_left(game.unit_record(mine), move) is not None:
            game.unit_record(mine).pp[move] = 0
    game.battle.set_member_abilities(mine, ("pet_shot", "pet_volley"))
    pool = game.battle.member(mine).subject.resources
    before = pool.current(HP)
    fight()
    press(pygame.K_RETURN, 0.1)
    text("no moves left")
    shot("26_no_moves_left")
    press(pygame.K_RETURN, 0.1)
    until(lambda: "STRUGGLE" in screen().message or "Struggle" in screen().message, 8)
    shot("27_struggle")
    until(lambda: screen().shown_hp.get(mine, 0) <= pool.current(HP) + 0.01, 6)
    shot("28_struggle_recoil", hp_before=before, hp_after=pool.current(HP), top=pool.maximum(HP))
    to_phase("command", 20)
    game.mode, game.battle, runtime._creature_battle = "field", None, None
    pump(runtime, 0.2)

    # -- the same in Traditional Chinese ---------------------------------------------------------
    game.world_commands.dispatch(WorldCommand("SET_LOCALE", {"locale": "zh-TW"}))
    game.heal_pets()
    battle("wild_one")
    text("出現了")
    shot("29_zh_appeared")
    to_phase("command")
    shot("30_zh_commands")
    press(pygame.K_RETURN)
    shot("31_zh_moves")
    runtime.close()
    report = {
        "music_played": tracks_played(),
        "check": "D58 creature battle screen in a real window",
        "driver": driver,
        "art": str(art),
        "steps": steps,
        "pass": len(steps) == 32 and driver == "cocoa",  # 22a: the trainer asks to change
    }
    (out / "creature_results.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({"driver": driver, "steps": len(steps), "pass": report["pass"]}))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
