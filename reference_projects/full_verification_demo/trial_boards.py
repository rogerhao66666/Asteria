"""Hearthfold's quest board, guild office and Starfall Chest (U5): three event-opened screens.

* **Star stones** (``star_stones``): a second currency, paid by the board's bounties (and 300
  at the start, so the chest can be tried at once).
* **Bounty Board** (``hearthfold_board``, a scroll on the plaza): four bounties as cards -
  slingers (repeatable, back five minutes after it is handed in), an herb delivery with a ten
  minute limit, skeleton hunters, and a bounty on Vaelor that opens after the catacombs. Three can
  be taken at once.
* **Guild Office** (``hearthfold_guild``, a clerk): Mira, Vesper and Cael for gold or star
  stones, each at a level rolled in a range; a member sent away gives half the price back.
  The campaign hires them by story as before - this is another way in.
* **Starfall Chest** (``starfall``, a big chest): common / rare / mythical prizes for star
  stones, ten at once with a rare guaranteed, a mythical at the latest on pull 50 (softly
  likelier from 36), Cael at twice the weight (owned: an Elixir instead). The chests are
  Foozle's Chest and Key Pack (CC0, ``asset_library/foozle/Foozle_2DO0002_Chest_and_Key_Pack``).

``apply(project, root)`` adds what is missing and can run again; ``build_project.py`` runs it
after ``trial_crafting``.
"""

from __future__ import annotations

ICONS = "playable_assets/icons_7soul"
CHESTS = "playable_assets/chests"
PORTRAITS = "playable_assets/portraits"
STAR = "star_stones"
START_STARS = 300.0

# quest id: (name, description, (objective kind, target, required), rank, category, icon,
#            reward currencies, reward items, options)
BOUNTIES = {
    "bounty_slingers": (
        "Slinger Bounty",
        "Goblin slingers keep stoning the road carts. Three of them, and the guild pays.",
        ("defeat_enemy", "goblin_slinger", 3),
        "C",
        "Hunt",
        "W_Throw001.png",
        {"gold": 150.0, STAR: 30.0},
        (),
        {"repeatable": True},
    ),
    "bounty_herbs": (
        "Herb Delivery",
        "The apothecary is short of healing herbs. Bring three before they wilt.",
        ("item", "healing_herb", 3),
        "D",
        "Delivery",
        "I_Leaf.png",
        {STAR: 20.0},
        (("potion", 2),),
        {"repeatable": True, "time_limit": 10.0},
    ),
    "bounty_hunters": (
        "Hunter Cull",
        "Skeleton hunters shoot from the catacomb dark. Put two of them down.",
        ("defeat_enemy", "skeleton_hunter", 2),
        "B",
        "Hunt",
        "I_Crystal01.png",
        {STAR: 50.0},
        (("hi_potion", 1),),
        {},
    ),
    "bounty_warlord": (
        "Vaelor's Bounty",
        "Vaelor holds the throne. The guild's richest bounty.",
        ("defeat_enemy", "crimson_warlord", 1),
        "S",
        "Hunt",
        "W_Sword016.png",
        {"gold": 1000.0, STAR: 300.0},
        (),
        {"prerequisites": ("q_crypt",)},
    ),
}
# station-like objects on the plaza: (name, (x, y), Ninja Adventure picture or character)
OBJECTS = {
    "board": ("Bounty Board", (248.0, 200.0), ("item", "Items/Scroll/Scroll.png")),
    "guild": ("Guild Clerk", (216.0, 200.0), "OldWoman"),
    "gacha": ("Starfall Chest", (504.0, 200.0), ("item", "Items/Treasure/BigTreasureChest.png")),
}


def quests():
    from asteria.rpg.enemies import LootEntry, RewardDefinition
    from asteria.rpg.quests import QuestDefinition, QuestObjective

    out = {}
    for quest_id, value in BOUNTIES.items():
        name, about, (kind, target, required), rank, category, icon, money, loot, options = value
        options = dict(options)
        out[quest_id] = QuestDefinition(
            quest_id,
            name,
            description=about,
            objectives=(QuestObjective("goal", kind, target=target, required=required),),
            reward=RewardDefinition(
                currencies=money,
                loot=tuple(LootEntry(i, minimum=n, maximum=n) for i, n in loot),
            ),
            prerequisites=options.pop("prerequisites", ()),
            auto_complete=False,
            icon_id=f"{ICONS}/{icon}",
            card_image=f"{ICONS}/{icon}",
            rank=rank,
            category=category,
            **options,
        )
    return out


def board():
    from asteria.rpg.boards import QuestBoardDefinition

    return QuestBoardDefinition(
        "hearthfold_board",
        "Bounty Board",
        description="Hearthfold's bounties. Take up to three; report back here.",
        quest_ids=tuple(BOUNTIES),
        max_active=3,
        refresh_minutes=5.0,
    )


def office():
    from asteria.rpg.boards import RecruitCandidate, RecruitOfficeDefinition

    def hire(actor_id, cost, low, high, note, currency="gold"):
        return RecruitCandidate(
            actor_id, currency, cost, level_min=low, level_max=high, note=note,
            portrait=f"{PORTRAITS}/{actor_id}.png",
        )  # fmt: skip

    return RecruitOfficeDefinition(
        "hearthfold_guild",
        "Guild Office",
        description="Adventurers looking for a party.",
        candidates=(
            hire("hero_02", 500.0, 1, 3, "A cleric who heals before you ask."),
            hire("hero_03", 1500.0, 3, 5, "Raises the dead, and their bones fight for you."),
            hire("hero_04", 300.0, 4, 6, "Pays in blood for power. Asks star stones.", STAR),
        ),
        party_limit=4,
        can_dismiss=True,
        dismiss_refund=0.5,
    )


def banner():
    from asteria.rpg.gacha import GachaBanner, GachaPrize, GachaRarity

    def prize(prize_id, rarity, weight, kind="item", target="", amount=1, **more):
        return GachaPrize(prize_id, kind, target or prize_id, amount, weight, rarity, **more)

    return GachaBanner(
        "starfall",
        "Starfall Chest",
        description="Star stones buy a chest. Most hold supplies; some hold legends.",
        banner_image=f"{CHESTS}/mythicalwithgems_yellow_glow.png",
        currency=STAR,
        single_cost=30.0,
        multi_cost=270.0,
        multi_count=10,
        rarities=(
            GachaRarity(
                "common",
                "Common",
                (205, 205, 215),
                f"{CHESTS}/common_no_glow.png",
                f"{CHESTS}/common_empty_yellow_glow.png",
                "confirm",
            ),
            GachaRarity(
                "rare",
                "Rare",
                (120, 175, 255),
                f"{CHESTS}/rare_no_glow.png",
                f"{CHESTS}/rare_empty_purple_glow.png",
                "heal",
            ),
            GachaRarity(
                "mythical",
                "Mythical",
                (255, 205, 90),
                f"{CHESTS}/mythical_no_glow.png",
                f"{CHESTS}/mythicalwithgems_yellow_glow.png",
                "victory",
            ),
        ),  # fmt: skip
        prizes=(
            prize("potion", "common", 24.0, amount=2),
            prize("healing_herb", "common", 20.0, amount=3),
            prize("iron_ore", "common", 18.0, amount=3),
            prize("ether_leaf", "common", 18.0, amount=2),
            prize("hi_potion", "rare", 6.0),
            prize("ruby_item", "rare", 4.0),
            prize("sapphire_item", "rare", 4.0),
            prize("gold_ingot", "rare", 3.0),
            prize("elixir", "mythical", 1.0),
            prize("bloodreaver", "mythical", 0.5, "equipment", "w_bloodreaver"),
            prize(
                "cael",
                "mythical",
                0.75,
                "actor",
                "hero_04",
                featured=True,
                duplicate_item="elixir",
                duplicate_amount=1,
            ),
        ),  # fmt: skip
        featured_multiplier=2.0,
        hard_pity=50,
        pity_rarity="mythical",
        soft_pity_start=35,
        soft_pity_step=0.06,
        multi_guarantee="rare",
        appear_sound="confirm",
        shake_sound="hit",
    )


def apply(project, root):
    """Add the bounties, board, office, banner, star stones and their plaza objects; returns how
    many of the three were added. An object already on the plaza is left as it is."""
    import trial_maps as maps
    import trial_people as people
    import trial_shops as shops

    db = project.rpg_database
    for quest_id, quest in quests().items():
        db.quests[quest_id] = quest
    added = 0
    for store, record, key in (
        (db.quest_boards, board(), "board_id"),
        (db.recruit_offices, office(), "office_id"),
        (db.gacha_banners, banner(), "banner_id"),
    ):
        added += getattr(record, key) not in store
        store[getattr(record, key)] = record
    state = project.game_start.rpg_state_data
    if state is not None and STAR not in state.get("currencies", {}):
        state["currencies"] = {**state.get("currencies", {}), STAR: START_STARS}
    town = shops._town(project)
    standing = {e.name for e in town.scene.entities()}
    opens = {
        "board": maps.world("OPEN_QUEST_BOARD", board_id="hearthfold_board"),
        "guild": maps.world("OPEN_RECRUIT", office_id="hearthfold_guild"),
        "gacha": maps.world("OPEN_GACHA", banner_id="starfall"),
    }
    for kind, (name, xy, picture) in OBJECTS.items():
        if name in standing:
            continue
        key = "look_object_" + name.lower().replace(" ", "_")
        look = people.look(maps.Assets(project, root), key, picture, name)
        entity = town.npc(name, xy, look)
        town.program(entity, f"town.{kind}", [opens[kind]])
    return added
