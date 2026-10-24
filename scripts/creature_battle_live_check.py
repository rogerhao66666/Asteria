"""Real-window check of the creature battle screen (``battle.style: "creature"``, D58).

    python scripts/creature_battle_live_check.py OUTPUT_DIR [--art DIR] [--emerald DIR]

Opens the Full Verification demo in a real (Cocoa) window at 960 x 640 (the 240 x 160 screen
four times) with the creature party laid over it in memory (``trial_creatures``) and plays,
with real frames and key presses, a wild battle (the foe appears, Go!, the commands, the moves,
a super-effective hit, the foe's turn, the bag's two pockets, a ball shaking and the catch), a
trainer battle (the challenge, the trainer's creature, no running, the party screen, a switch,
a creature fainting and the forced choice, the trainer's next creature, the win and the prize),
a legendary encounter and the same wild battle in Traditional Chinese.

Pictures: ``--art DIR`` reads ``DIR/front/<species>.png`` and ``DIR/back/<species>.png``
(any project art); without it CC0 Foozle critters from ``asset_library/`` stand in (written to
OUTPUT_DIR/art). ``--emerald DIR`` reads a private art folder made by AsteriaEmerald's
``tools/import_pokeemerald.py`` (never part of this repository): the species, trainer,
background, windows, info boxes, bars and font of that folder, with the creatures, moves and
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
FOOZLE = REPO / "asset_library" / "foozle"
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


EMERALD_SPECIES = {"cub": "treecko", "wolf": "poochyena", "titan": "rayquaza"}
EMERALD_MOVES = {
    "pet_shot": "TACKLE",
    "pet_volley": "PECK",
    "pet_bandage": "ABSORB",
    "struggle": "STRUGGLE",
}
EMERALD_ITEMS = {
    "pet_ball": ("poke_ball", "POKé BALL"),
    "great_ball": ("great_ball", "GREAT BALL"),
}
EMERALD_MUSIC = {  # the battle screen's music keys -> the game's own songs
    "wild": "mus_vs_wild",
    "trainer": "mus_vs_trainer",
    "legendary": "mus_vs_rayquaza",
    "victory_wild": "mus_victory_wild",
    "victory_trainer": "mus_victory_trainer",
}
EMERALD_WORDS = {  # the game's own words for the engine's (its English locale table)
    "creature.cmd.party": "POKéMON",
    "creature.choose": "Choose a POKéMON.",
    "creature.out_of_creatures": "{player} is out of usable POKéMON!",
    "creature.pocket.balls": "POKé BALLS",
}


def _potion_id(project):
    """The demo's first item usable in battle (shown as the bag's POTION)."""
    db = project.rpg_database
    return next(
        i for i in sorted(db.items) if db.items[i].battle_ability or db.items[i].use_effects
    )


def _emerald_art(source, out):
    """Copy the private pictures the check needs under the demo's species ids."""
    import shutil

    art = out / "art_emerald"
    for side in ("front", "back"):
        (art / side).mkdir(parents=True, exist_ok=True)
        for species, name in EMERALD_SPECIES.items():
            shutil.copyfile(source / side / f"{name}.png", art / side / f"{species}.png")
    shutil.copyfile(source / "trainers" / "youngster.png", art / "front" / "youngster.png")
    (art / "icons").mkdir(exist_ok=True)
    (art / "items").mkdir(exist_ok=True)
    for species, name in EMERALD_SPECIES.items():
        shutil.copyfile(source / "icons" / f"{name}.png", art / "icons" / f"{species}.png")
    for item_id, (name, _label) in EMERALD_ITEMS.items():
        shutil.copyfile(source / "items" / f"{name}.png", art / "items" / f"{item_id}.png")
    return art


def _emerald_potion(project, source, art):
    import shutil

    potion = _potion_id(project)
    shutil.copyfile(source / "items" / "potion.png", art / "items" / f"{potion}.png")
    item = project.rpg_database.items[potion]
    object.__setattr__(item, "display_name", "POTION")
    return potion


def _emerald_offsets(source):
    """The game's per-species picture offsets under the demo's species ids."""
    import json

    table = json.loads((source / "offsets.json").read_text(encoding="utf-8"))
    return {species: table.get(name, {}) for species, name in EMERALD_SPECIES.items()}


def _emerald_screen(source, art):
    battle = source / "battle"
    return {
        "background": str(battle / "background_tall_grass.png"),
        "window_message": str(battle / "window_message.png"),
        "window_commands": str(battle / "window_commands.png"),
        "window_moves": str(battle / "window_moves.png"),
        "healthbox_foe": str(battle / "healthbox_foe.png"),
        "healthbox_mine": str(battle / "healthbox_mine.png"),
        "hp_label": str(battle / "hp_label.png"),
        "hp_bar": {c: str(battle / f"hp_bar_{c}.png") for c in ("green", "yellow", "red")},
        "exp_bar": str(battle / "exp_bar.png"),
        "font": str(source / "font" / "latin_normal.json"),
        "font_small": str(source / "font" / "latin_small.json"),
        "sprite_offsets": _emerald_offsets(source),
        "music": {key: f"emerald.{song}" for key, song in EMERALD_MUSIC.items()},
        "currency_symbol": "¥",  # the game's money sign (its font draws it as its own glyph)
        "icon": str(art / "icons" / "{species}.png"),
        "item_icon": str(art / "items" / "{item}.png"),
        "party": {
            "background": str(source / "party" / "background.png"),
            "slot_main": {
                s: str(source / "party" / f"slot_main_{s}.png")
                for s in ("normal", "selected", "fainted", "fainted_selected")
            },
            "slot_wide": {
                s: str(source / "party" / f"slot_wide_{s}.png")
                for s in ("normal", "selected", "fainted", "fainted_selected")
            },
            "slot_wide_empty": str(source / "party" / "slot_wide_empty.png"),
            "ball_closed": str(source / "party" / "ball_closed.png"),
            "ball_open": str(source / "party" / "ball_open.png"),
            "cancel_normal": str(source / "party" / "cancel_normal.png"),
            "cancel_selected": str(source / "party" / "cancel_selected.png"),
            "message": str(source / "party" / "message.png"),
        },
        "bag": {
            "background": str(source / "bag" / "background.png"),
            "bag": str(source / "bag" / "bag_{pocket}.png"),
            "arrow": str(source / "bag" / "arrow_a.png"),
        },
    }


def _rename_for_emerald(project):
    from asteria.gameplay.abilities import AbilityDefinition
    from asteria.rpg.pets import PetSpeciesDefinition

    db = project.rpg_database
    for species, name in EMERALD_SPECIES.items():
        data = db.pet_species[species].to_data()
        data["display_name"] = name.upper()
        db.pet_species[species] = PetSpeciesDefinition.from_data(data)
    library = project.gameplay_library.abilities
    for ability_id, name in EMERALD_MOVES.items():
        data = library.require(ability_id).to_data()
        data["display_name"] = name
        library._definitions[ability_id] = AbilityDefinition.from_data(data)
    object.__setattr__(db.actors["hero_01"], "display_name", "BRENDAN")  # in memory only
    for item_id, (_name, label) in EMERALD_ITEMS.items():
        object.__setattr__(db.items[item_id], "display_name", label)
    from asteria.rpg.localization import LocaleTable

    english = db.locale_tables.get("en")
    words = {**(dict(english.entries) if english else {}), **EMERALD_WORDS}
    db.locale_tables["en"] = LocaleTable("en", words)
    project.name = "AsteriaEmerald"  # the window's title: the demo is only the test bed


def _project(art):
    import trial_creatures

    from asteria.editor import EditorDocument
    from asteria.gameplay.abilities import AbilityDefinition
    from asteria.project import Project
    from asteria.rpg import InteractionRule
    from asteria.rpg.enemies import EncounterDefinition, EncounterMember
    from asteria.rpg.pets import PetExpCurve, PetMove, PetSpeciesDefinition

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
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
    from asteria.runtime.creature_battle import CreatureBattleScreen
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    argv = list(sys.argv[1:] if argv is None else argv)
    art_dir = emerald = None
    if "--emerald" in argv:
        index = argv.index("--emerald")
        emerald = Path(argv[index + 1]).expanduser()
        del argv[index : index + 2]
    if "--art" in argv:
        index = argv.index("--art")
        art_dir = Path(argv[index + 1]).expanduser()
        del argv[index : index + 2]
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "creature_battle")
    out.mkdir(parents=True, exist_ok=True)
    helper = _helpers()
    pump, key = helper._pump, helper._key
    pygame.init()
    art = art_dir or (_emerald_art(emerald, out) if emerald else _stand_in_art(out))
    project = _project(art)
    if emerald:
        _rename_for_emerald(project)
        potion = _emerald_potion(project, emerald, art)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=640
    )
    if emerald:
        runtime.manifest["title"] = "AsteriaEmerald"  # the demo is only the test bed
    runtime.open()
    runtime.manifest.setdefault("battle", {})["style"] = "creature"
    runtime.manifest["battle"]["creature_screen"] = {
        "front": str(art / "front" / "{species}.png"),
        "back": str(art / "back" / "{species}.png"),
        "trainer": str(art / "front" / "{trainer}.png"),
        **(_emerald_screen(emerald, art) if emerald else {}),
        "trainers": {
            "trainer_youngster": {
                "title": "YOUNGSTER",
                "name": "CALVIN",
                "sprite": "youngster",
                "prize": 160,
            }
        },
    }
    if emerald:  # the songs rendered from the game's own score (tools/render_music.py)
        music = emerald / "music"
        runtime.manifest.setdefault("audio", {}).update(
            {f"emerald.{song}": str(music / f"{song}.wav") for song in EMERALD_MUSIC.values()}
        )
    driver = pygame.display.get_driver()
    game = runtime.game
    steps = []

    first = game.add_pet("cub", level=7, nickname="" if emerald else "MOCHI")
    first.moves = ["pet_shot", "pet_volley", "pet_bandage"]
    second = game.add_pet("wolf", level=6)
    second.moves = ["pet_shot", "pet_bandage"]
    inventory = game.save.rpg_state.inventory
    inventory.add("pet_ball", 5)
    inventory.add("great_ball", 2)
    if emerald:
        inventory.add(potion, 3)
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
    for _ in range(2):  # both of the trainer's creatures fall
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
        text("fainted")
        if _ == 0:
            text("sent out")
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
        "pass": len(steps) == 31 and driver == "cocoa",
    }
    (out / "creature_results.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({"driver": driver, "steps": len(steps), "pass": report["pass"]}))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
