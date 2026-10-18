"""The Boss Trial's remaining editor sections, each one used by the game, not only filled in.

* Battle presentation: camera choreography (a pause on a Break, a hold on the result), animation
  timing (heavy finishers play slower and hold, hits snap) and the effect / sound channels.
* Message settings: text macros (``\\M[GUILD]``, ``\\M[BOSS]``), the gold label and a message log.
* Credits pages, battle options (the auto-battle key, a low-health pose), a pause-menu entry
  ("Make Camp" outside town), doodads (graves and bushes placed around Hearthfold).
* Common events: the camp (called by the menu entry) and the Ember Throne's heat (parallel while
  the party is in the throne hall). Battle events: Vaelor and the Ancient speak when wounded, and
  every finished fight is counted.
"""

from __future__ import annotations

import trial_maps as maps

from asteria.events import EventInstruction, EventProgram, LifecycleEventBinding
from asteria.events.common import CommonEvent

say, world, set_switch = maps.say, maps.world, maps.set_switch

MACROS = {"GUILD": "the Adventurers' Guild", "BOSS": "Vaelor", "TOWN": "Hearthfold"}


def fill(c):
    presentation(c)
    messages_and_extras(c)
    doodads(c)
    events(c)


# -- battle presentation --------------------------------------------------------------------------
def presentation(c):
    from asteria.presentation.battle_animation_timing import (
        BattleAnimationTimingProfile,
        BattleAnimationTimingRule,
    )
    from asteria.presentation.battle_presentation_director import (
        BattlePresentationDirection,
        BattlePresentationDirectorProfile,
        BattlePresentationDirectorRule,
    )
    from asteria.presentation.battle_presentation_layering import (
        BattlePresentationChannelPolicy,
        BattlePresentationLayeringProfile,
    )

    library = c.project.battle_presentation_library
    library.set(
        "director",
        "adaptive",
        BattlePresentationDirectorProfile(
            rules=(
                BattlePresentationDirectorRule(  # a Break or a full gauge: a beat to take it in
                    "gauge_threshold", "*", BattlePresentationDirection("break", hold=0.25)
                ),
                BattlePresentationDirectorRule(
                    "battle_result", "*", BattlePresentationDirection("result", delay=0.3)
                ),
                BattlePresentationDirectorRule(
                    "turn_ready", "*", BattlePresentationDirection("turn", delay=0.05)
                ),
            )
        ),
    )
    library.set(
        "animation_timing",
        "adaptive",
        BattleAnimationTimingProfile(
            rules=(
                BattleAnimationTimingRule("attack3", 0.9, 0.06, "ease_out", 0.12),  # heavy
                BattleAnimationTimingRule("attack2", 1.0, 0.05, "ease_out", 0.05),
                BattleAnimationTimingRule("cast", 1.0, 0.08, "smoothstep", 0.08),
                BattleAnimationTimingRule("hit", 1.2, 0.0, "linear", 0.0),  # hits snap
                BattleAnimationTimingRule("ko", 0.9, 0.05, "ease_in", 0.25),
            ),
            default_transition_duration=0.04,
            default_transition_easing="ease_out",
        ),
    )
    library.set(
        "layering",
        "adaptive",
        BattlePresentationLayeringProfile(
            channels=(
                BattlePresentationChannelPolicy("animation", layer=0),
                BattlePresentationChannelPolicy("camera", layer=1),
                BattlePresentationChannelPolicy("vfx", layer=2),
                BattlePresentationChannelPolicy("screen_fx", layer=3),
                BattlePresentationChannelPolicy("audio", layer=0, gain=0.85, bus="sfx"),
            )
        ),
    )


# -- message settings, credits, battle options, a pause-menu entry ------------------------------
def messages_and_extras(c):
    from asteria.rpg.extras import BattleOptions, CreditsPage, MenuEntry
    from asteria.rpg.localization import MessageSettings

    db = c.db
    icon = next((i.icon_id for i in db.items.values() if getattr(i, "icon_id", "")), "")
    db.message_settings["default"] = MessageSettings(
        "default",
        macros=MACROS,
        currency_label="G",
        backlog_limit=40,  # the pause menu gets a Message Log
        icons={"1": icon} if icon else None,
    )
    pages = (
        ("title", "Asteria Boss Trial", ("A stress test of the turn-based engine.",)),
        (
            "art",
            "Art",
            (
                "Characters, foes, tiles, equipment and UI: Foozle Lucifer packs (CC0).",
                "Skill effects: Foozle Pixel Magic Effects (CC0).",
            ),
        ),
        ("thanks", "Thank You", ("Hearthfold stands. The Ember Throne is empty.",)),
    )
    for order, (page_id, title, lines) in enumerate(pages):
        db.credits_pages[page_id] = CreditsPage(page_id, title, lines, order=order)
    db.battle_options["default"] = BattleOptions("default", auto_key=True, weak_below=0.25)
    db.menu_entries["camp"] = MenuEntry(
        "camp",
        "Make Camp",
        "common.camp",
        enabled_switch="camp.allowed",  # outside town only (the doors set it)
        order=0,
    )


# -- doodads ------------------------------------------------------------------------------------
DOODADS = {  # id: (exterior prop, solid footprint w, h)
    "grave": ("grave", 18.0, 8.0),
    "grave_cross": ("grave_cross", 14.0, 8.0),
    "bush": ("bush", 0.0, 0.0),
}
TOWN_DOODADS = (("grave", 40.0, 380.0), ("grave_cross", 72.0, 380.0), ("bush", 640.0, 60.0))


def doodads(c):
    import trial_lucifer as lucifer
    from PIL import Image

    from asteria.editor.doodads import make_doodad_entity
    from asteria.rpg.doodads import DoodadDefinition

    sheet = Image.open(
        lucifer.FREE_ASSETS
        / "Foozle_2DT0002_Lucifer_Exterior_Tileset_Pixel_Art"
        / "Png"
        / "OuterTileset.png"
    ).convert("RGBA")
    assets = maps.Assets(c.project, c.root)
    for doodad_id, (prop, solid_w, solid_h) in DOODADS.items():
        col, row, w, h, _solid = maps.EXTERIOR_PROPS[prop]
        image = sheet.crop((col * 16, row * 16, (col + w) * 16, (row + h) * 16))
        sheet_id = assets.sheet(
            f"doodad_{doodad_id}", image, [(0, 0, image.width, image.height)], doodad_id
        )
        c.db.doodads[doodad_id] = DoodadDefinition(
            doodad_id,
            sheet_id,
            solid_width=solid_w,
            solid_height=solid_h,
            layer=1,
            snap=8.0,
            tags=("decor",),
        )
    town = next(s for s in c.project.scenes() if s.name == "Hearthfold")
    for index, (doodad_id, x, y) in enumerate(TOWN_DOODADS, 1):
        town.add_entity(
            make_doodad_entity(c.db.doodads[doodad_id], x, y, name=f"doodad:{doodad_id}.{index}")
        )


# -- common events and battle events ---------------------------------------------------------
def _program(project, program_id, steps):
    project.event_programs.register(
        program_id, EventProgram([*steps, EventInstruction("END")], name=program_id)
    )


def events(c):
    import trial_story as story

    from asteria.editor.event_flow_authoring import battle_condition

    project = c.project
    _program(
        project,
        "common.camp",
        [
            say("Aldric", "We camp here tonight."),
            world("REST_PARTY"),
            world("ADD_COUNTER", counter_id="camps", amount=1),
            world("SHOW_POPUP", text="The party is rested.", kind="item"),
        ],
    )
    _program(
        project,
        "common.ember_heat",
        [
            EventInstruction("WAIT", {"seconds": 2.0}),
            world("ADD_COUNTER", counter_id="ember_heat", amount=1),
        ],
    )
    project.common_events.extend(
        (
            CommonEvent("common.camp", "call"),
            CommonEvent("common.ember_heat", "parallel", "throne.hot"),
        )
    )
    # doors: camping is allowed outside town; the throne hall is hot while the party is in it
    for door, steps in (
        ("door.town.road_east", (set_switch("camp.allowed"),)),
        ("door.woods.road_west", (set_switch("camp.allowed", False),)),
        ("door.crypt.throne_door", (set_switch("throne.hot"),)),
        ("door.throne.stairs_down", (set_switch("throne.hot", False),)),
    ):
        story.rewrite_door(project, door, before=steps)
    _program(
        project,
        "battle.vaelor_wounded",
        [say("Vaelor", "You bleed me? Then burn with me!")],
    )
    _program(
        project,
        "battle.ancient_wounded",
        [say("Skeleton Ancient", "The dead do not stay down...")],
    )
    _program(
        project,
        "battle.tally",
        [world("ADD_COUNTER", counter_id="battles_fought", amount=1)],
    )
    project.lifecycle_event_bindings.extend(
        (
            LifecycleEventBinding(
                "rpg.battle.round_started",
                "battle.vaelor_wounded",
                conditions=(battle_condition("hp_ratio:crimson_warlord", "<=", 0.5),),
                once=True,
            ),
            LifecycleEventBinding(
                "rpg.battle.round_started",
                "battle.ancient_wounded",
                conditions=(battle_condition("hp_ratio:skeleton_ancient", "<=", 0.4),),
                once=True,
            ),
            LifecycleEventBinding("rpg.battle.finished", "battle.tally"),
        )
    )
