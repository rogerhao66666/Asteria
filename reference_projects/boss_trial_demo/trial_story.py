"""The story of the Boss Trial campaign: who asks what, who joins when, what the doors want.

Quests chain from the Warden of Hearthfold down to the Skeleton King; the necromancer and the
cultist join after the woods and the catacombs; reputation with two factions moves with the deeds;
caches and vaults are world interactions; patrolling foes run behaviour trees; the weather of each
area changes how magic hits. Everything is project data and event programs.
"""

from __future__ import annotations

import trial_content as tc
import trial_maps as maps

from asteria.core import Transform
from asteria.events.conditions import EventCondition
from asteria.events.program import EventInstruction
from asteria.rpg.battle_lifecycle import BattleObjectiveCondition, BattleObjectiveDefinition
from asteria.rpg.behavior_tree import BehaviorNode, BehaviorTree
from asteria.rpg.enemies import RewardDefinition
from asteria.rpg.interactions import InteractionRule
from asteria.rpg.items import InventoryRules
from asteria.rpg.quests import QuestDefinition, QuestObjective
from asteria.rpg.world_interactions import WorldInteraction
from asteria.rpg.world_record import AchievementDefinition, FactionDefinition
from asteria.runtime.character_control import (
    AIController2DComponent,
    CharacterController2DComponent,
)

say, world, set_switch = maps.say, maps.world, maps.set_switch

QUESTS = (
    # id, name, text, objectives, prerequisites, gold
    (
        "q_patrol",
        "Clear the Road",
        "Goblin slingers pick off travellers on the woods road. Thin them out.",
        (("slingers", "defeat_enemy", "goblin_slinger", 4),),
        (),
        800,
    ),
    (
        "q_beast",
        "The Goblin Beast",
        "A beast drives the goblins. Kill it in its clearing at the end of the road.",
        (("beast", "defeat_enemy", "goblin_beast", 1),),
        ("q_patrol",),
        2000,
    ),
    (
        "q_crypt",
        "Into the Catacombs",
        "The dead stir below the woods. Put the Skeleton Ancient to rest.",
        (("ancient", "defeat_enemy", "skeleton_ancient", 1),),
        ("q_beast",),
        3500,
    ),
    (
        "slay_vaelor",
        "Slay Vaelor",
        "Vaelor, the Skeleton King, sits on the Ember Throne. End him; bring herbs.",
        (
            ("warlord", "defeat_enemy", "crimson_warlord", 1),
            ("herbs", "item", "healing_herb", 3),
        ),
        ("q_crypt",),
        6000,
    ),
    (
        "bone_collector",
        "Bone Collector",
        "The Warden pays for every skeleton acolyte put down.",
        (("acolytes", "defeat_enemy", "mender_wisp", 6),),
        (),
        1500,
    ),
)


def systems(c):
    """Factions, the quest chain, achievements, bag rules, world interactions, behaviour trees,
    battle objectives and weather rules."""
    db = c.db
    db.add_faction(
        FactionDefinition(
            "wardens",
            "Hearthfold Wardens",
            minimum=-100,
            maximum=100,
            initial=0,
            ranks=((-100, "Hostile"), (0, "Stranger"), (25, "Friend"), (60, "Ally")),
        )
    )
    db.add_faction(
        FactionDefinition(
            "bonewalkers",
            "Bonewalker Court",
            minimum=-100,
            maximum=100,
            initial=0,
            ranks=((-100, "Sworn Enemy"), (-30, "Hunted"), (0, "Unknown"), (40, "Tolerated")),
        )
    )
    db.quests.clear()
    for quest_id, name, text, objectives, needs, gold in QUESTS:
        db.add_quest(
            QuestDefinition(
                quest_id,
                name,
                description=text,
                objectives=tuple(
                    QuestObjective(oid, kind, target=target, required=count)
                    for oid, kind, target, count in objectives
                ),
                prerequisites=needs,
                reward=RewardDefinition(currencies={"gold": float(gold)}),
            )
        )
    db.add_quest(
        QuestDefinition(
            "q_show",
            "The Showman's Request",
            description="Pip wants three tricks for the crowd, then a bow.",
            objectives=(QuestObjective("tricks", "counter", required=3),),
            reward=RewardDefinition(currencies={"gold": 300}),
            auto_complete=False,
        )
    )
    from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
    from asteria.rpg.battle_scheduler import BattleSchedulerDefinition

    c.library.add_timeline(
        ActionTimeline(
            "pip_hop",
            [
                ActionCue("up", 0.0, "movement", {"x": 0.0, "y": -1.0, "duration": 0.2}),
                ActionCue("down", 0.2, "movement", {"x": 0.0, "y": 1.0, "duration": 0.2}),
                ActionCue("end", 0.5, "gameplay_event", {"name": "end"}),
            ],
        )
    )
    # some fights take turns in rounds instead of on the speed timeline
    db.battle_schedulers["classic_rounds"] = BattleSchedulerDefinition(
        "classic_rounds", mode="round"
    )
    db.achievements.clear()
    for achievement in (
        AchievementDefinition(
            "road_cleared",
            "Road Cleared",
            description="Finish Clear the Road.",
            kind="quest",
            target="q_patrol",
        ),
        AchievementDefinition(
            "beast_slayer",
            "Beast Slayer",
            description="Defeat the Goblin Beast.",
            kind="defeated",
            target="goblin_beast",
            value=1,
        ),
        AchievementDefinition(
            "ancient_laid_to_rest",
            "Laid to Rest",
            description="Defeat the Skeleton Ancient.",
            kind="defeated",
            target="skeleton_ancient",
            value=1,
        ),
        AchievementDefinition(
            "warlord_slayer",
            "King Slayer",
            description="Defeat Vaelor.",
            kind="defeated",
            target="crimson_warlord",
            value=1,
        ),
        AchievementDefinition(
            "warden_friend",
            "Friend of the Wardens",
            description="Reach Friend with the Wardens.",
            kind="reputation",
            target="wardens",
            value=25,
        ),
        AchievementDefinition(
            "contractor",
            "Contractor",
            description="Take two contracts.",
            kind="counter",
            target="contracts",
            value=2,
        ),
        AchievementDefinition(
            "quest_done",
            "Contract Complete",
            description="Complete Slay Vaelor.",
            kind="quest",
            target="slay_vaelor",
            hidden=True,
        ),
        AchievementDefinition(
            "bone_hunter",
            "Bone Hunter",
            description="Defeat ten skeleton acolytes.",
            kind="defeated",
            target="mender_wisp",
            value=10,
        ),
    ):
        db.add_achievement(achievement)
    db.add_inventory_rules(
        InventoryRules("trial_bag", "Traveller's bag", max_kinds=40, overflow="fill")
    )
    for interaction in (
        WorldInteraction(
            "search_cache",
            "Search the old cache",
            verb="search",
            check_stat="speed",
            difficulty=100,
            base_chance=0.5,
            chance_per_point=0.004,
            success_items={"ether_leaf": 3, "ice_crystal": 2},
            success_switch="cache.found",
            failure_switch="cache.empty",
            repeatable=True,
        ),
        WorldInteraction(
            "pick_vault",
            "Pick the sealed vault",
            verb="open",
            required_item="ancient_thread",
            cost_items={"iron_ore": 1},
            success_items={"ruby_item": 1, "onyx_item": 1},
            success_currencies={"gold": 1200},
            success_switch="vault.open",
            reputation={"bonewalkers": -5},
            repeatable=False,
        ),
        WorldInteraction(
            "talk_the_scout_down",
            "Persuade the camp scout",
            verb="persuade",
            check_stat="magic",
            difficulty=150,
            base_chance=0.4,
            chance_per_point=0.003,
            success_switch="scout.persuaded",
            reputation={"wardens": 5},
            repeatable=False,
        ),
    ):
        db.add_world_interaction(interaction)
    n = BehaviorNode
    db.add_behavior_tree(
        BehaviorTree(
            "foe_patrol",
            n(
                "selector",
                {},
                (
                    n(
                        "sequence",
                        {},
                        (n("player_within", {"radius": 56}, ()), n("chase", {"arrive": 6}, ())),
                    ),
                    n("wander", {"radius": 40}, ()),
                ),
            ),
        )
    )
    # a fight can end when its leader falls, whatever stands beside him
    for objective_id, leader in (
        ("beast_down", "goblin_beast:1"),
        ("ancient_down", "skeleton_ancient:1"),
    ):
        db.add_battle_objective(
            BattleObjectiveDefinition(
                objective_id,
                success_conditions=(
                    BattleObjectiveCondition("member_active", leader, "==", False),
                ),
                winning_sides=("heroes",),
                defeated_sides=("enemies",),
                priority=5,
            )
        )
    # weather changes how magic hits: rain feeds lightning and drowns fire
    db.interaction_rules["rain_lightning"] = InteractionRule(
        "rain_lightning", source_tags_all=("damage.lightning", "weather.rain"), multiplier=1.3
    )
    db.interaction_rules["rain_fire"] = InteractionRule(
        "rain_fire", source_tags_all=("damage.fire", "weather.rain"), multiplier=0.7
    )
    db.interaction_rules["dust_light"] = InteractionRule(
        "dust_light", source_tags_all=("damage.light", "weather.dust"), multiplier=0.8
    )


def rewrite_door(project, program_id, *, before=(), gate=None, locked=()):
    """Change what a door does: ``before`` runs first, ``gate`` (a switch) must be on to pass,
    ``locked`` is what happens while it is off."""
    from asteria.events import EventProgram

    library = project.event_programs
    old = library.get(program_id)
    body = [i for i in old.instructions if i.opcode != "END"]
    steps = [*before, *body]
    if gate:
        steps = chain([(gate, steps)], list(locked))[:-1]  # the chain ends with its own END
    library.unregister(program_id)
    library.register(program_id, EventProgram([*steps, EventInstruction("END")], name=program_id))


def chain(cases, default):
    """The first case whose switch is on runs; ``default`` otherwise."""
    out = []
    for index, (name, _steps) in enumerate(cases):
        condition = EventCondition("switch", name, "==", True, None).to_data()
        out.append(EventInstruction("JUMP_IF", {"condition": condition, "label": f"case{index}"}))
    out += [*default, EventInstruction("END")]
    for index, (_name, steps) in enumerate(cases):
        out += [
            EventInstruction("LABEL", {"name": f"case{index}"}),
            *steps,
            EventInstruction("END"),
        ]
    return out


def warden(builders, looks, places):
    town = builders["town"]
    npc = town.npc("Warden Thessaly", maps.world_xy(21, 5), looks["sorceress"])

    def rep(amount):
        return world("CHANGE_REPUTATION", faction_id="wardens", amount=amount)

    def start(quest, line):
        return [say("Warden Thessaly", line), world("START_QUEST", quest_id=quest)]

    cases = [
        ("quest.slay_vaelor.completed", [say("Warden Thessaly", "Hearthfold is in your debt.")]),
        (
            "quest.slay_vaelor.active",
            [
                say(
                    "Warden Thessaly",
                    "The Skeleton King sits on the Ember Throne, past the catacombs.",
                )
            ],
        ),
        (
            "quest.q_crypt.completed",
            [
                rep(15),
                *start(
                    "slay_vaelor",
                    "The Ancient is down. Only Vaelor is left. Bring herbs as well.",
                ),
            ],
        ),
        (
            "quest.q_crypt.active",
            [
                say(
                    "Warden Thessaly",
                    "The catacombs open behind the crypt door at the end of the woods.",
                )
            ],
        ),
        (
            "quest.q_beast.completed",
            [
                rep(15),
                *start(
                    "q_crypt",
                    "Then the dead are next. The crypt door at the end of the road leads below.",
                ),
            ],
        ),
        (
            "quest.q_beast.active",
            [
                say(
                    "Warden Thessaly",
                    "The Goblin Beast lairs in the clearing, east end of the road.",
                )
            ],
        ),
        (
            "quest.q_patrol.completed",
            [
                rep(10),
                *start("q_beast", "The road is safer. Now kill the beast that drives them."),
            ],
        ),
        ("quest.q_patrol.active", [say("Warden Thessaly", "Four slingers, then come back.")]),
    ]
    first = [
        world("SCREEN_FADE", to=1.0, duration=0.4, color=[0, 0, 0]),
        world("CAMERA_FOCUS", entity="Warden Thessaly", zoom=1.4, blend=0.4),
        world("SCREEN_FADE", to=0.0, duration=0.4, color=[0, 0, 0]),
        *start("q_patrol", "Goblins hold the woods road. Thin out four slingers and I will pay."),
        world("PLAY_SE", asset_id="confirm"),
        world("GIVE_ITEM", item_id="healing_herb", quantity=3),
        world("ADD_COUNTER", counter_id="contracts", amount=1),
        world("CAMERA_RELEASE", blend=0.4),
    ]
    town.program(npc, "story.warden", chain(cases, first))
    side = town.npc("Bounty Clerk", maps.world_xy(18, 5), looks["cultist"])
    town.program(
        side,
        "story.clerk",
        chain(
            [
                ("quest.bone_collector.completed", [say("Bounty Clerk", "Paid in full.")]),
                (
                    "quest.bone_collector.active",
                    [say("Bounty Clerk", "Six acolytes. Bones count.")],
                ),
            ],
            [
                say(
                    "Bounty Clerk", "Skeleton acolytes drag the dead back up. Six, and I pay well."
                ),
                world("START_QUEST", quest_id="bone_collector"),
                world("ADD_COUNTER", counter_id="contracts", amount=1),
            ],
        ),
    )
    inn = town.npc("Innkeeper Marla", maps.world_xy(24, 5), looks["warrior"])
    town.program(
        inn,
        "story.inn",
        maps.menu(
            "Marla",
            "A bed for the night is 100 gold.",
            [
                (
                    "Rest (100 gold)",
                    [
                        world("CHANGE_CURRENCY", currency_id="gold", amount=-100),
                        world("REST_PARTY"),
                    ],
                ),
                ("Not now", [say("Marla", "The door is always open.")]),
            ],
        ),
    )


def woods(builders, looks, places):
    scene = builders["woods"]
    scout = scene.npc("Camp Scout", maps.world_xy(8, 13), looks["cultist"])
    scene.program(
        scout,
        "story.scout",
        chain(
            [
                (
                    "scout.persuaded",
                    [say("Scout", "Mind the east camp. The beast's howl calls the rest.")],
                )
            ],
            [
                say("Scout", "Turn back. Goblins everywhere."),
                world("INTERACT", interaction_id="talk_the_scout_down"),
            ],
        ),
    )
    cache = scene.npc("Old Cache", maps.world_xy(31, 21), looks["necromancer"], solid=False)
    scene.program(
        cache,
        "story.cache",
        [
            say("Old Cache", "A mouldy pack by the camp. Search it?"),
            world("INTERACT", interaction_id="search_cache"),
        ],
    )
    wild_companion(
        scene,
        "Vesper",
        "vesper",
        places["woods"]["camp"],
        looks["hero_necromancer"],
        met=(
            "encounter.woods_boss.defeated",
            "You broke the beast. The dead below will want you next. Find me at the guild.",
        ),
        waiting="The beast keeps the camp. Break it and we talk.",
    )


def _identity(entity, npc_id, *, hidden=False):
    from asteria.runtime.npc_state import NpcIdentity2DComponent

    component = NpcIdentity2DComponent()
    component.npc_id, component.starts_hidden = npc_id, hidden
    entity.add_component(component)
    return entity


def wild_companion(scene, name, key, xy, look, *, met, waiting):
    """A companion met in the wild: once ``met`` = (switch, line) holds, they leave for the
    adventurers' guild in Hearthfold (their guild double appears there)."""
    entity = _identity(scene.npc(name, xy, look), f"{key}_wild")
    switch, line = met
    scene.program(
        entity,
        f"story.{key}",
        chain(
            [
                (
                    switch,
                    [
                        say(name, line),
                        world("SET_NPC", npc=f"{key}_wild", key="visible", value=False),
                        world("SET_NPC", npc=f"{key}_guild", key="visible", value=True),
                        world("SHOW_POPUP", text=f"{name} heads for the guild.", kind="item"),
                    ],
                )
            ],
            [say(name, waiting)],
        ),
    )
    return entity


def guild_companion(town, name, key, actor_id, xy, look, *, joined, hidden, extra=()):
    """A companion waiting at the guild: talk to them and they join the party."""
    entity = _identity(town.npc(name, xy, look), f"{key}_guild", hidden=hidden)
    town.program(
        entity,
        f"story.{key}.guild",
        chain(
            [(f"recruited.{key}", [say(name, joined)])],
            [
                say(name, "Ready when you are."),
                world("JOIN_PARTY", actor_id=actor_id),
                world("CHANGE_RELATIONSHIP", subject_id=key, amount=10),
                *extra,
                set_switch(f"recruited.{key}"),
                world("SHOW_POPUP", text=f"{name} joins the party!", kind="item"),
            ],
        ),
    )
    return entity


def guild(builders, looks, places):
    """The adventurers' guild in Hearthfold, where companions are hired: Mira waits here from
    the start, Vesper and Cael once met in the wild; the Guildmaster sends one back to wait
    (LEAVE_PARTY) and they can be hired again."""
    town = builders["town"]
    spots = places["town"]["guild"]
    guild_companion(
        town,
        "Mira",
        "mira",
        "hero_02",
        spots[0],
        looks["hero_sorceress"],
        joined="Stay close and I will keep you standing.",
        hidden=False,
    )
    guild_companion(
        town,
        "Vesper",
        "vesper",
        "hero_03",
        spots[1],
        looks["hero_necromancer"],
        joined="Lead on. The dead talk, and I listen.",
        hidden=True,
        extra=[world("SET_NPC", npc="vesper_guild", key="mood", value="loyal")],
    )
    guild_companion(
        town,
        "Cael",
        "cael",
        "hero_04",
        spots[2],
        looks["hero_cultist"],
        joined="Where you go, I follow. Mind the king's guard.",
        hidden=True,
        extra=[
            world("LEARN_RECIPE", recipe_id="storm_flask"),
            world("TIMER_STOP", timer_id="crypt_run"),
        ],
    )
    master = town.npc("Guildmaster Orla", places["town"]["guild_board"], looks["warrior"])

    def part(name, actor_id, key):
        return (
            f"{name} waits here",
            [
                world("LEAVE_PARTY", actor_id=actor_id),
                set_switch(f"recruited.{key}", False),
                say("Guildmaster Orla", f"{name} will wait at the guild until you call."),
            ],
        )

    town.program(
        master,
        "story.guildmaster",
        maps.menu(
            "Guildmaster Orla",
            "Companions wait here until you hire them. Anything else?",
            [
                part("Mira", "hero_02", "mira"),
                part("Vesper", "hero_03", "vesper"),
                part("Cael", "hero_04", "cael"),
                ("Nothing", [say("Guildmaster Orla", "Good hunting.")]),
            ],
        ),
    )


def crypt(builders, looks, places):
    scene = builders["crypt"]
    wild_companion(
        scene,
        "Cael",
        "cael",
        places["crypt"]["camp"],
        looks["hero_cultist"],
        met=(
            "encounter.crypt_boss.defeated",
            "The Ancient falls. I served it once. I will wait for you at the guild.",
        ),
        waiting="The Ancient holds the hall below. I cannot pass it alone.",
    )
    vault = scene.npc("Sealed Vault", maps.world_xy(12, 17), looks["necromancer"], solid=False)
    scene.program(
        vault,
        "story.vault",
        chain(
            [("vault.open", [say("Vault", "Empty now.")])],
            [
                say("Vault", "A bone lock. Thread of the Ancient and an iron pick."),
                world("INTERACT", interaction_id="pick_vault"),
            ],
        ),
    )
    # the throne door stays shut until the Ancient is down
    rewrite_door(
        scene.project,
        "door.crypt.throne_door",
        before=[world("CAMERA_SHAKE", intensity=2, duration=0.4)],
        gate="encounter.crypt_boss.defeated",
        locked=[say("Door", "The door is sealed with bone. The Ancient keeps the key.")],
    )
    # a run through the catacombs is timed from the crypt door to the cultist's camp
    rewrite_door(
        scene.project,
        "door.woods.crypt_door",
        before=[world("TIMER_START", timer_id="crypt_run", seconds=0, count_up=True, show=True)],
    )


def throne(builders, looks, places):
    scene = builders["throne"]
    banner = scene.npc("Victory Banner", maps.world_xy(6, 8), looks["warrior"], solid=False)
    scene.program(
        banner,
        "story.banner",
        chain(
            [
                (
                    "encounter.boss_room.defeated",
                    [
                        say(
                            "Hearthfold banner", "The Skeleton King is dust. The woods are quiet."
                        ),
                        world("CHANGE_REPUTATION", faction_id="wardens", amount=30),
                        world("CHANGE_REPUTATION", faction_id="bonewalkers", amount=-20),
                        set_switch("game.complete"),
                        world("SHOW_POPUP", text="The Trial is won.", kind="item"),
                    ],
                )
            ],
            [say("Banner", "A tattered banner. The king still sits his throne.")],
        ),
    )


def showman(builders, looks, places):
    """Showman Pip shows the field commands that nothing else in the campaign needs."""
    town = builders["town"]
    town.npc("Showman Pip", maps.world_xy(22, 19), looks["cultist"])
    pip = "Showman Pip"
    options = [
        ("Balloon", [world("SHOW_BALLOON", entity=pip, balloon="exclamation", duration_ms=800)]),
        ("Stroll", [world("WALK_TO", entity=pip, x=330, y=330, speed=40)]),
        ("Route", [world("MOVE_ROUTE", entity=pip, route="right 2, down 1", step=16, speed=40)]),
        (
            "Lantern",
            [world("SPAWN_ENTITY", prefab_id="spirit_lantern", x=300, y=300, name="Lantern")],
        ),
        (
            "Echo",
            [
                world("COPY_ENTITY", entity=pip, x=360, y=300, name="PipEcho"),
                world("MORPH_ENTITY", entity="PipEcho", prefab_id="bone_pile"),
            ],
        ),
        (
            "Badge",
            [
                world(
                    "SET_ENTITY_ICON",
                    entity=pip,
                    icon_id="playable_assets/lucifer/icons/w_sunbrand.png",
                )
            ],
        ),
        ("Sparks", [world("PLAY_VFX", asset_id="battle.fx.explosion", entity=pip, scale=1.0)]),
        (
            "Timer",
            [
                world("TIMER_START", timer_id="pip", seconds=30, show=False),
                world("TIMER_PAUSE", timer_id="pip"),
                world("TIMER_RESUME", timer_id="pip"),
                world("TIMER_ADD", timer_id="pip", seconds=10),
                world("TIMER_STOP", timer_id="pip"),
            ],
        ),
        (
            "Slides",
            [
                world(
                    "SHOW_PICTURE",
                    picture_id="slide",
                    asset_id=places["pictures"]["banner"],
                    x=1,
                    y=1,
                    scale=0.5,
                    opacity=0.8,
                ),
                world("MOVE_PICTURE", picture_id="slide", x=40, y=30, duration=0.3),
                world("SET_PICTURE_FRAME", picture_id="slide", frame=0),
                world("ERASE_PICTURE", picture_id="slide"),
            ],
        ),
        ("Hop", [world("PLAY_ACTION", entity=pip, timeline_id="pip_hop")]),
        ("Take the request", [world("START_QUEST", quest_id="q_show")]),
        (
            "A trick for the crowd",
            maps.needs_quest(
                "q_show",
                "active",
                [world("ADVANCE_QUEST", quest_id="q_show", objective_id="tricks", amount=1)],
                "adv",
            ),
        ),
        (
            "Take a bow",
            maps.needs_quest(
                "q_show", "active", [world("COMPLETE_QUEST", quest_id="q_show")], "bow"
            ),
        ),
        (
            "Drop the request",
            maps.needs_quest("q_show", "active", [world("FAIL_QUEST", quest_id="q_show")], "drop"),
        ),
        (
            "Hush the band",
            [world("STOP_BGM", fade=0.3), world("PLAY_BGM", asset_id="town_theme", fade=0.3)],
        ),
        ("Bow out", []),
    ]
    town.program(
        town.find_entity(pip), "story.showman", maps.menu(pip, "Care for a trick?", options)
    )


def foes_ai(builders):
    """Foes in view roam and chase through the foe_patrol tree; bosses stand their ground."""
    for key in ("woods", "crypt"):
        for entity in builders[key].scene.entities():
            if not entity.name.startswith(
                ("Goblin Slinger", "Goblin Berserker", "Skeleton Grunt", "Skeleton Hunter")
            ):
                continue
            controller = entity.add_component(CharacterController2DComponent())
            controller.mode, controller.speed = "topdown", 22.0
            controller.half_width, controller.half_height, controller.facing = 5.0, 6.0, "down"
            ai = entity.add_component(AIController2DComponent())
            ai.driver, ai.tree_id = "behavior_tree", "foe_patrol"


SW = "w_sunbrand:hero_01"
HERO = "hero_01"


def needs(source, name, operator, value, *, then, otherwise):
    """``then`` when the ``rpg`` condition holds, else ``otherwise``; both end the event."""
    condition = EventCondition("rpg", name, operator, value, None).to_data()
    return [
        EventInstruction("JUMP_IF", {"condition": condition, "label": "ok"}),
        *otherwise,
        EventInstruction("END"),
        EventInstruction("LABEL", {"name": "ok"}),
        *then,
        EventInstruction("END"),
    ][: -1 if source else None]


def trainer(name, line, job, level):
    """A job teacher: the job needs a level (and the jobs the class record names)."""
    return needs(
        None,
        f"level:{HERO}",
        ">=",
        level,
        then=[
            world("SET_CLASSES", actor_id=HERO, class_ids=f"knight,{job}"),
            world("SHOW_POPUP", text=f"Job: {job.replace('_', ' ').title()}", kind="item"),
        ],
        otherwise=[say(name, f"Come back at level {level}.")],
    )


TRAINERS = (
    ("Mystic Teacher", "Walk the mystic path with me.", "mystic", 1),
    ("Duelist Teacher", "Speed is a blade.", "duelist", 1),
    ("Weapon Master Dojo", "Every weapon, one hand.", "weapon_master", 3),
    ("Sage's Tower", "Wisdom of every element.", "sage", 4),
    ("Hero's Shrine", "Only the brave may stand here.", "hero", 8),
    ("Forgemaster's Smithy", "Temper the steel.", "forgemaster", 3),
    ("Rogue Guild", "Take what is not nailed down.", "rogue", 3),
    ("Guardian Post", "Hold the line.", "guardian", 5),
)


def town_people(builders, looks, places):
    """The craftsmen and teachers of Hearthfold, each a menu of what they do."""
    town = builders["town"]
    plaza = list(places["town"]["plaza"])
    faces = ("warrior", "sorceress", "necromancer", "cultist")
    index = 0

    def place(name):
        nonlocal index
        entity = town.npc(name, plaza[index % len(plaza)], looks[faces[index % len(faces)]])
        index += 1
        return entity

    def program(name, steps):
        town.program(
            place(name), f"town.{name.lower().replace(' ', '_').replace(chr(39), '')}", steps
        )

    program(
        "Smith",
        maps.menu(
            "Smith",
            "What shall I do to Sunbrand?",
            [
                ("Refine it", [world("REFINE_EQUIPMENT", actor_id=HERO, instance_id=SW)]),
                (
                    "Awaken it",
                    [world("UPGRADE_EQUIPMENT", actor_id=HERO, instance_id=SW, node_id="awaken")],
                ),
                (
                    "Sharpen the edge",
                    [world("UPGRADE_EQUIPMENT", actor_id=HERO, instance_id=SW, node_id="edge")],
                ),
                (
                    "Kindle the ember",
                    [world("UPGRADE_EQUIPMENT", actor_id=HERO, instance_id=SW, node_id="ember")],
                ),
                ("Never mind", [say("Smith", "Mind the fire.")]),
            ],
        ),
    )
    program(
        "Jeweler",
        maps.menu(
            "Jeweler",
            "Gems for the blade?",
            [
                (
                    "Set a ruby (socket 1)",
                    [
                        world(
                            "SOCKET_ITEM",
                            actor_id=HERO,
                            instance_id=SW,
                            socket_id="s1",
                            item_id="ruby_item",
                        )
                    ],
                ),
                (
                    "Set an onyx (socket 2)",
                    [
                        world(
                            "SOCKET_ITEM",
                            actor_id=HERO,
                            instance_id=SW,
                            socket_id="s2",
                            item_id="onyx_item",
                        )
                    ],
                ),
                (
                    "Take out socket 1",
                    [world("UNSOCKET_ITEM", actor_id=HERO, instance_id=SW, socket_id="s1")],
                ),
                ("Never mind", [say("Jeweler", "They keep their shine.")]),
            ],
        ),
    )
    program(
        "Card Dealer",
        maps.menu(
            "Card Dealer",
            "A card for the third socket?",
            [
                (
                    "Vampire card",
                    [
                        world(
                            "SOCKET_ITEM",
                            actor_id=HERO,
                            instance_id=SW,
                            socket_id="s3",
                            item_id="card_vampire_item",
                        )
                    ],
                ),
                (
                    "Slayer card",
                    [
                        world(
                            "SOCKET_ITEM",
                            actor_id=HERO,
                            instance_id=SW,
                            socket_id="s3",
                            item_id="card_slayer_item",
                        )
                    ],
                ),
                ("Never mind", [say("Card Dealer", "Fortune favours the patient.")]),
            ],
        ),
    )
    program(
        "Alchemist",
        [say("Alchemist", "Combine what you carry."), world("OPEN_CRAFTING", station="alchemy")],
    )
    program(
        "Merchant", [say("Merchant", "Take a look."), world("OPEN_SHOP", shop_id="trial_shop")]
    )
    program(
        "Breaker",
        maps.menu(
            "Breaker",
            "I take things apart.",
            [
                ("Ruby", [world("DISASSEMBLE", item_id="ruby_item")]),
                ("Sapphire", [world("DISASSEMBLE", item_id="sapphire_item")]),
                ("Onyx", [world("DISASSEMBLE", item_id="onyx_item")]),
                ("Never mind", []),
            ],
        ),
    )
    program(
        "Armory",
        maps.menu(
            "Armory",
            "Which off-hand weapon?",
            [
                (label, [world("EQUIP_ITEM", actor_id=HERO, equipment_id=weapon, index=1)])
                for label, weapon in (
                    ("Bow", "w_bow"),
                    ("Dagger", "w_dagger"),
                    ("Spear", "w_spear"),
                    ("Axe", "w_axe"),
                )
            ]
            + [("Never mind", [])],
        ),
    )
    shrine_cost = 500
    program(
        "Shrine",
        maps.menu(
            "Shrine",
            f"A blessing costs {shrine_cost} gold.",
            [
                (
                    "Pray",
                    needs(
                        None,
                        "gold",
                        ">=",
                        shrine_cost,
                        then=[
                            world("CHANGE_CURRENCY", currency_id="gold", amount=-shrine_cost),
                            world(
                                "GRANT_EXPERIENCE",
                                actor_id=HERO,
                                amount=3000,
                                level_track="level_curve",
                                points="stat_points=2,skill_points=1",
                            ),
                            say("Shrine", "Power flows into you."),
                        ],
                        otherwise=[say("Shrine", "The offering is too small.")],
                    ),
                ),
                ("Leave", []),
            ],
        ),
    )
    for name, line, job, level in TRAINERS:
        program(name, [say(name, line), *trainer(name, line, job, level)])


def programs(c, builders, looks, places):
    """Hook for ``trial_maps.build_world``: the people and doors of the story."""
    town_people(builders, looks, places)
    guild(builders, looks, places)
    warden(builders, looks, places)
    woods(builders, looks, places)
    crypt(builders, looks, places)
    throne(builders, looks, places)
    showman(builders, looks, places)
    foes_ai(builders)
    _ = Transform, tc
