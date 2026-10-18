"""Map areas, New Game Plus, translations and the music room of the Full Verification demo: the
last four Game Systems categories, each designed and used by the game.

* **Map Areas**: a poison bog in the woods (it hurts while you wade, fights there happen in a
  bog), the warden's glade (foes cannot follow you in; the party rests), the catacombs' shadowed
  halls (patrols see you from half as far) and the throne hall's ember floor (it burns while
  Vaelor lives: a switch gates it).
* **New Game Plus**: after the win the Victory Banner offers to start again keeping levels,
  skills, gear, the bag, pets and the bestiary; half the gold; levels capped at 40.
* **Translations**: English and Traditional Chinese tables; Scholar Lin in Hearthfold (or
  Settings > Language) switches; area messages, the plaque, the banner and the scholar speak
  through ``\\T[key]``.
* **Music Room**: the five themes, each opened by hearing it in the game (the battle theme by
  beating the Goblin Beast), each with a picture.
"""

from __future__ import annotations

from asteria.events.program import EventInstruction, EventProgram
from asteria.rpg.extras import MusicTrack
from asteria.rpg.localization import LocaleTable
from asteria.rpg.map_rules import AreaRule, MapRuleSet
from asteria.rpg.new_game_plus import NewGamePlusRules

BACKDROPS = {  # area -> battle backdrop (painted from the area's own tileset)
    "bog": "playable_assets/battle_bog.png",
    "crypt": "playable_assets/battle_crypt.png",
    "throne": "playable_assets/battle_throne.png",
}
ICONS = "playable_assets/lucifer/icons"
TEXT = {  # key: (English, 繁體中文)
    "language.name": ("English", "繁體中文"),
    "scholar.ask": ("Which tongue shall I tell the tales in?", "要用哪種語言講述故事？"),
    "scholar.done": ("So be it.", "就這麼辦。"),
    "area.bog": ("The bog's poison seeps into your boots!", "沼澤的毒滲進了靴子！"),
    "area.glade": (
        "The warden's glade. No foe follows you here; the party rests.",
        "守林人的空地。敵人追不進來，隊伍在此休息。",
    ),
    "area.shadow": (
        "Shadows swallow your steps: patrols will not see you so easily.",
        "陰影吞沒了腳步聲，巡邏的骷髏比較難發現你。",
    ),
    "area.embers": (
        "The floor round the pool smoulders while the king still lives.",
        "國王還活著，熔池周圍的地板仍在悶燒。",
    ),
    "plaque.empty": (
        "The Hall of Heroes: no name is carved here yet.",
        "英雄之廳：牌匾上還沒有刻任何名字。",
    ),
    "plaque.cleared": (
        "The Hall of Heroes: Aldric's name is carved here. The Trial begins anew.",
        "英雄之廳：這裡刻著 Aldric 的名字。試煉再次開始。",
    ),
    "banner.won": (
        "The Skeleton King is dust. The woods are quiet.",
        "骷髏王化為塵土，森林恢復了寧靜。",
    ),
    "banner.again": (
        "Begin the Trial again with all your strength? (New Game+)",
        "要帶著現在的力量重新挑戰試煉嗎？（二周目）",
    ),
}
TRACKS = (  # id (the manifest's music name), title, icon, opened by
    ("town_theme", "Hearthfold", "a_warden_charm", ""),
    ("woods_theme", "Whispering Woods", "card_beast", ""),
    ("crypt_theme", "Catacombs", "card_ancient", ""),
    ("throne_theme", "Ember Throne", "card_vaelor", ""),
    ("battle_theme", "Under Pressure", "item_boss_emblem", "encounter.woods_boss.defeated"),
)


def say(text_key, speaker=""):
    """A line spoken in the player's language (``\\T[key]`` reads the translation tables)."""
    return EventInstruction("DIALOGUE", {"speaker": speaker, "text": f"\\T[{text_key}]"})


def world(command, **args):
    return EventInstruction("WORLD", {"command": command, "args": args})


def data(c):
    """The rule set, the New Game Plus rules, both translation tables and the music room."""
    import trial_maps as maps

    db = c.db
    db.map_rule_sets["trial_areas"] = MapRuleSet(
        "trial_areas",
        (
            AreaRule(
                f"region:{maps.BOG}",
                damage_resource="vitality",
                damage_per_second=40.0,  # never kills: a hero is left on the last point
                footstep_cue="confirm",
                step_distance=24.0,
                on_enter="area.bog",
                battle_background=BACKDROPS["bog"],
            ),
            AreaRule(f"region:{maps.GLADE}", blocks=("npc",), on_enter="area.glade"),
            AreaRule(
                f"region:{maps.SHADOW}",
                visibility=0.5,
                on_enter="area.shadow",
                battle_background=BACKDROPS["crypt"],
            ),
            AreaRule(
                f"region:{maps.EMBERS}",
                damage_resource="vitality",
                damage_per_second=60.0,
                switch="vaelor.awake",  # out once the king falls
                on_enter="area.embers",
                battle_background=BACKDROPS["throne"],
            ),
        ),
        region_layer="Regions",
    )
    db.new_game_plus_rules["trial_again"] = NewGamePlusRules(
        "trial_again",
        carry=("levels", "abilities", "equipment", "inventory", "currencies", "pets", "world"),
        carry_switches=("ngplus.", "music.heard."),  # the plaque and the music room remember
        level_cap=40,
        keep_currency_share=0.5,
    )
    for index, locale in enumerate(("en", "zh-TW")):
        db.locale_tables[locale] = LocaleTable(
            locale, {key: texts[index] for key, texts in TEXT.items()}
        )
    db.music_tracks.clear()
    for track_id, name, icon, opened_by in TRACKS:
        db.music_tracks[track_id] = MusicTrack(
            track_id,
            name,
            track_id,
            unlock_switch=opened_by or f"music.heard.{track_id}",  # heard in the game
            note="Foozle, CC0",
            icon_id=f"{ICONS}/{icon}.png",
        )
    programs = c.project.event_programs
    steps = {
        "area.bog": [say("area.bog")],
        "area.glade": [say("area.glade"), world("REST_PARTY")],
        "area.shadow": [say("area.shadow")],
        "area.embers": [say("area.embers")],
    }
    for program_id, instructions in steps.items():
        programs.register(
            program_id,
            EventProgram((*instructions, EventInstruction("END")), name=program_id),
        )


def backdrops(c):
    """Battle backdrops of the bog, the catacombs and the throne hall (their own tiles)."""
    import lucifer_reskin

    for key, kind, dim in (("bog", "exterior", 0.6), ("crypt", "dungeon", 0.35)):
        lucifer_reskin.paint_background(kind, (960, 540), road=False, dim=dim).save(
            c.root / BACKDROPS[key]
        )
    lucifer_reskin.paint_background("lava", (960, 540), road=True, dim=0.25).save(
        c.root / BACKDROPS["throne"]
    )


def people(builders, looks, maps):
    """Scholar Lin (the language), the Hall of Heroes plaque (New Game Plus remembers)."""
    town = builders["town"]
    scholar = town.npc("Scholar Lin", maps.world_xy(30, 19), looks["sorceress"])
    town.program(
        scholar,
        "story.scholar",
        [
            say("scholar.ask", "Scholar Lin"),
            *maps.menu(
                "Scholar Lin",
                "Language / 語言",
                [
                    ("English", [world("SET_LOCALE", locale="en"), say("scholar.done")]),
                    ("繁體中文", [world("SET_LOCALE", locale="zh-TW"), say("scholar.done")]),
                ],
            ),
        ],
    )
    plaque = town.npc("Hall of Heroes", maps.world_xy(26, 21), looks["warrior"], solid=False)
    town.program(
        plaque,
        "story.plaque",
        maps.when(
            "ngplus.cleared",
            [say("plaque.cleared", "Hall of Heroes")],
            [say("plaque.empty", "Hall of Heroes")],
        ),
    )


def banner_steps(maps):
    """The Victory Banner: the first time it tells the win; every time it offers New Game+."""
    again = maps.menu(
        "Victory Banner",
        "New Game+?",
        [
            (
                "Begin New Game+",
                [
                    maps.set_switch("ngplus.cleared"),
                    world("NEW_GAME_PLUS", rules_id="trial_again"),
                ],
            ),
            ("Not yet", []),
        ],
    )
    return [say("banner.again", "Victory Banner"), *again]
