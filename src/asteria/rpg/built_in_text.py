"""The engine's own words: every built-in text a game's screens draw, by translation key.

The runtime draws them through ``GameSessionRuntime.tr(key, english, **params)``, so a
project's locale tables (``rpg.localization.LocaleTable``) can give any key its own text: a
translation (``zh-TW``) or a word of the author's own in the default locale (``Fight`` for
``battle.command.attack``). A key no table has shows the English, so a project without tables
looks exactly as it always did. ``{name}`` marks a value filled in when the text is drawn.

``BUILT_IN_TEXT`` lists every key with its English (``GROUPS`` orders them by screen for the
editor's Translations page); ``ENGINE_TRANSLATIONS`` holds the engine's own translations of
them (``built_in_text/<locale>.json``), which the editor can copy into a project's table.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

FOLDER = Path(__file__).resolve().parent / "built_in_text"


def _fill(text, params):
    if not params:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        return text


class Words:
    """A message for the player still to be put in their language: ``key`` in the project's
    locale tables, else ``english``, with ``{name}`` filled from ``params``. ``str()`` gives the
    English, so code that shows ``str(error)`` reads as before; ``shown(tr)`` translates it.
    Rules that cannot reach the game session raise their errors with one."""

    __slots__ = ("english", "key", "params")

    def __init__(self, key, english, **params):
        self.key, self.english, self.params = str(key), str(english), params

    def __str__(self):
        return _fill(self.english, self.params)

    def __repr__(self):
        return f"Words({self.key!r}, {str(self)!r})"

    def shown(self, tr):
        """The message through ``tr(key, default, **params)`` (``GameSessionRuntime.tr``)."""
        return tr(self.key, self.english, **self.params)


def translated(message, tr):
    """``message`` - a ``Words``, an error raised with one, or plain text - in the player's
    language."""
    if isinstance(message, BaseException):
        message = message.args[0] if len(message.args) == 1 else str(message)
    return message.shown(tr) if isinstance(message, Words) else str(message)


def engine_translations(locale):
    """The engine's own translation of the built-in words for ``locale`` (``zh-TW``), or of its
    parent (``zh``); ``{}`` when the engine has none."""
    locale = str(locale or "").strip()
    while locale:
        found = _engine_table(locale)
        if found is not None:
            return dict(found)
        locale = locale.rsplit("-", 1)[0] if "-" in locale else ""
    return {}


@cache
def _engine_table(locale):
    path = FOLDER / f"{locale}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.get("entries", {}).items() if k in BUILT_IN_TEXT}


def engine_locales():
    """The locales the engine has translations of its own words for."""
    return tuple(sorted(p.stem for p in FOLDER.glob("*.json")))


def group_of(key):
    """The title of the editor group ``key`` belongs to ("" for a project's own key)."""
    return _GROUP_OF.get(str(key), "")


# ((group title, ((key, english), ...)), ...) in the order the editor lists them; a key a
# runtime screen draws must be here with the English it draws (tests/test_built_in_text.py)
GROUPS = (
    (
        "Title screen",
        (
            ("title.name", "ASTERIA"),
            ("title.subtitle", "Complex Reference RPG"),
            ("title.server_session", "N   Enter Server Session"),
            ("title.server_save", "L   Reload Server Save"),
            ("title.guest", "Guest: {player}"),
            ("title.new_game", "N   New Game"),
            ("title.load_game", "L   Load Game"),
            ("title.saves", "{count} save(s) found"),
            ("title.no_saves", "No saves yet"),
            ("title.no_player_save", "No player save exists yet"),
            ("title.loaded", "Loaded player save"),
            ("title.new_game_plus", "New Game+"),
        ),
    ),
    (
        "Field",
        (
            ("notice.gained", "+{count} {name}"),
            ("notice.broke", "{name} broke!"),
            ("field.skip_cutscene", "Esc: skip"),
            ("field.title", "Field Test"),
            (
                "field.controls",
                "Move: WASD / Arrows   C: Build   Q: Quests   E: Interact   F5: Save   Esc: Pause",
            ),
            ("field.interact", "E  Interact — {name}"),
            ("equip_offer.instead", "{who}: wear it instead of {old}?"),
            ("equip_offer.new", "New: {name}"),
            ("equip_offer.free", "{who} has a free {slot} place. Wear it now?"),
            ("equip_offer.keys", "1 / Enter: wear it     2 / Esc: keep it in the bag"),
            ("field.saved", "Saved: {file}"),
            ("notice.no_room", "No room for {name}"),
        ),
    ),
    (
        "Dialogue",
        (
            ("dialogue.continue", "Enter / E: continue"),
            ("dialogue.choose", "Choose"),
        ),
    ),
    (
        "Pause menu",
        (
            ("pause.resume", "Resume"),
            ("pause.status", "Status / Items / Equipment / Skills"),
            ("pause.equipment", "Equipment"),
            ("pause.enhance", "Enhance"),
            ("pause.achievements", "Achievements"),
            ("pause.bestiary", "Bestiary"),
            ("pause.title", "Return to Title"),
            ("pause.quit", "Quit"),
            ("pause.pets", "Pets"),
            ("pause.backlog", "Message Log"),
            ("pause.skill_slots", "Skill Slots"),
            ("pause.music", "Music Room"),
            ("pause.credits", "Credits"),
            ("pause.save", "Save Game"),
            ("pause.load", "Load Game"),
            ("pause.crafting", "Crafting"),
            ("pause.settings", "Settings"),
            ("pause.quests", "Quest Log"),
            ("pause.heading", "Paused"),
        ),
    ),
    (
        "Game over",
        (
            ("game_over.load", "Load Last Save"),
            ("game_over.title", "Return to Title"),
            ("game_over.heading", "Game Over"),
        ),
    ),
    (
        "Settings",
        (
            ("settings.music_volume", "Music Volume"),
            ("settings.effects_volume", "Effects Volume"),
            ("settings.show_battle_log", "Battle Messages"),
            ("settings.developer_menu", "Developer Menu"),
            ("settings.controls", "Controls…"),
            ("settings.back", "Back"),
            ("settings.language", "Language"),
            ("language.name", "English"),
            ("settings.on", "On"),
            ("settings.off", "Off"),
            ("settings.hint", "Left/Right: change   Esc: save and back"),
        ),
    ),
    (
        "Controls",
        (
            ("controls.pad_button", "Pad {button}"),
            ("controls.pad_axis", "Pad {axis}"),
            ("controls.pad_stick", "stick"),
            ("controls.pad_hat", "d-pad"),
            ("controls.reset_all", "Reset all to defaults"),
            ("controls.all_reset", "All controls reset"),
            ("controls.press", "Press a key or pad button for {action} (Esc cancels)"),
            ("controls.title", "Controls"),
            ("controls.hint", "Enter: rebind   Backspace: reset action   Esc: save and back"),
        ),
    ),
    (
        "Save and load",
        (
            ("slots.loaded", "Loaded slot {slot}"),
            ("slots.autosave", "Autosave (F5)"),
            ("slots.slot", "Slot {slot}"),
            ("slots.hint", "Enter: choose   Delete: erase   Esc: back"),
            ("slots.damaged", "damaged save ({error})"),
            ("slots.empty_slot", "— empty —"),
            ("slots.summary", "{scene} · {leader} Lv {level} · {saved_at}"),
            ("slots.is_empty", "That slot is empty"),
            ("slots.is_damaged", "That save is damaged"),
            ("slots.overwrite", "Overwrite slot {slot}? Press Enter again"),
            ("slots.saved", "Saved to slot {slot}"),
            ("slots.delete", "Delete slot {slot}? Press Delete again"),
            ("slots.deleted", "Deleted slot {slot}"),
        ),
    ),
    (
        "Status menu",
        (
            ("status.tab.status", "Status"),
            ("status.tab.items", "Items"),
            ("status.tab.equipment", "Equipment"),
            ("status.tab.skills", "Skills"),
            ("status.reason.not_in_inventory", "not_in_inventory"),
            ("status.reason.effect_rejected", "effect_rejected"),
            ("status.member", "Q / E  {name}"),
            ("status.empty", "Nothing here yet."),
            (
                "status.hint",
                "Tab: next tab   Up/Down: choose   Enter: use / equip / unequip   Esc: back",
            ),
            ("status.usable", "(use)"),
            ("status.learned", "learned"),
            ("status.active", "active"),
            ("status.used", "Used {name}"),
            ("status.cannot_use", "{name} can't be used ({reason})"),
            ("status.equipped", "Equipped {name}"),
            ("status.unequipped", "Unequipped {name}"),
            ("status.nothing_to_unequip", "Nothing to unequip"),
        ),
    ),
    (
        "Quest log",
        (
            ("quests.status.active", "active"),
            ("quests.status.completed", "completed"),
            ("quests.status.failed", "failed"),
            ("quests.none", "No quests yet."),
            ("quests.hint", "Enter / Esc: back"),
            ("quests.objective.defeat", "Defeat {name}"),
            ("quests.objective.item", "Collect {name}"),
        ),
    ),
    (
        "Shop",
        (
            ("shop.buy", "Buy"),
            ("shop.sell", "Sell"),
            ("shop.error.stock", "{shop} has only {count} {item}"),
            ("shop.error.not_now", "{shop} is not offering {item} now"),
            ("shop.error.afford", "cannot afford {count} {item}"),
            ("shop.error.no_room", "no room for {count} {item} (room for {room})"),
            ("shop.error.sell", "not enough {item} to sell"),
            ("shop.bought", "Bought {name}"),
            ("shop.sold", "Sold {name}"),
            ("shop.item", "Item"),
            ("shop.price", "Price"),
            ("shop.stock", "Stock"),
            ("shop.owned", "Owned"),
            ("shop.hint", "Up/Down: select   Left/Right: buy/sell   Enter: confirm   Esc: leave"),
        ),
    ),
    (
        "Crafting",
        (
            ("crafting.nothing", "nothing"),
            ("crafting.crafted_quality", "Crafted {items} ({quality})"),
            ("crafting.crafted", "Crafted {items}"),
            ("crafting.failed", "Crafting failed — got {items}"),
            ("crafting.none", "No known recipes here."),
            ("crafting.hidden", "??? {count} recipe(s) not yet discovered"),
            ("crafting.hint", "Up/Down: select   Enter: craft   Esc: back"),
        ),
    ),
    (
        "Achievements and bestiary",
        (
            ("bestiary.tag.weak", "weak"),
            ("bestiary.tag.resist", "resist"),
            ("bestiary.tag.immune", "immune"),
            ("bestiary.tag.absorb", "absorb"),
            ("bestiary.tag.reflect", "reflect"),
            ("bestiary.tag.trait", "trait"),
            ("achievements.hidden_name", "???"),
            ("achievements.hidden", "Hidden achievement"),
            ("bestiary.unseen", "???"),
            ("achievements.title", "Achievements  {done}/{count}"),
            ("bestiary.title", "Bestiary  {seen}/{count} seen"),
            ("list.hint", "Up/Down: scroll   Enter / Esc: back"),
            ("bestiary.counts", "seen {seen}   defeated {defeated}   captured {captured}"),
            ("bestiary.nothing_special", "nothing special"),
            ("bestiary.unknown", "Defeat one to learn its weaknesses and health."),
            ("bestiary.drops", "Drops: {items}"),
            ("bestiary.no_drops", "Drops: none seen yet"),
        ),
    ),
    (
        "Message log, music room, credits",
        (
            ("backlog.title", "Message Log"),
            ("backlog.hint", "Up / Down: scroll   Esc: back"),
            ("backlog.empty", "Nothing has been said yet."),
            ("music.title", "Music Room"),
            ("music.hint", "Up / Down: choose   Enter: play   Esc: back"),
            ("music.empty", "There are no tracks."),
            ("music.locked", "? ? ?"),
            ("music.playing", "PLAYING"),
            ("credits.title", "Credits"),
            ("credits.hint", "Left / Right: page   {page}/{pages}   Esc: back"),
        ),
    ),
    (
        "Skill slots",
        (
            ("skill_slots.title", "Skill Slots"),
            (
                "skill_slots.hint",
                "Up / Down: choose   Enter: equip / remove   Left / Right: member   Esc: back",
            ),
            ("skill_slots.no_party", "No party members."),
            ("skill_slots.count", "{name}   Slots {used}/{capacity}"),
            ("skill_slots.nothing", "Nothing learned yet."),
            ("skill_slots.equipped", "EQUIPPED"),
        ),
    ),
    (
        "Pets",
        (
            ("pets.sent_out", "{name} will be sent out"),
            ("pets.evolved", "{name} evolved!"),
            ("pets.not_ready", "Not ready to evolve"),
            ("pets.renamed", "Renamed"),
            ("pets.title", "Pets"),
            ("pets.hint", "Up / Down: choose   Enter: send this one out   R: rename   Esc: back"),
            ("pets.none", "You have no pets yet."),
            ("pets.level", "{kind}   Lv {level}"),
            ("pets.bond", "Bond {bond}"),
            ("pets.active", "ACTIVE"),
            ("pets.rename_hint", "Type a name, Enter keeps it, Esc cancels"),
        ),
    ),
    (
        "Battle commands",
        (
            ("battle.command.attack", "Attack"),
            ("battle.command.skills", "Skills"),
            ("battle.command.items", "Items"),
            ("battle.command.escape", "Escape"),
            ("battle.command.more", "More"),
            ("battle.command.back", "Back"),
            ("battle.menu.command", "Command"),
            ("battle.menu.target", "Target"),
            ("battle.menu.form", "Form"),
            ("battle.menu.filter", "Filter: {query}"),
            ("battle.workflow.ready", "Ready"),
            ("battle.hint.attack", "Choose a weapon"),
            ("battle.hint.skills", "Abilities, concoct, capture"),
            ("battle.hint.group", "Abilities"),
            ("battle.hint.items", "Use an item from the bag"),
            ("battle.hint.escape", "{chance}% to get away"),
            ("battle.hint.back", "The first commands"),
            ("battle.hint.more", "More commands"),
            ("battle.nothing_to_use", "Nothing to use"),
            ("battle.hint.concoct", "Pick ingredients"),
            ("battle.capture_row", "X  Capture ({chance}%)"),
            ("battle.boost_row", "Boost x{level}"),
            (
                "battle.hint.boost",
                "Left / Right (or Enter here) set the boost for the next action",
            ),
            ("battle.pick_count", "Pick {count}"),
            ("battle.concoct_nothing", "These ingredients make nothing"),
            ("battle.boost_key_row", "B  Boost x{level} ({points} {amount})"),
            ("battle.boost_level", "BOOST x{level}"),
        ),
    ),
    (
        "Battle: why a command cannot be used",
        (
            ("battle.reason.cooldown_one", "Ready in {turns} turn"),
            ("battle.reason.cooldown", "Ready in {turns} turns"),
            ("battle.reason.short", "Needs {amount} {resource} (has {have})"),
            ("battle.reason.form_needs", "needs {amount} {resource}"),
            ("battle.reason.form_short", "needs {amount} {resource} ({have})"),
            ("battle.reason.blocked", "Blocked by {states}"),
            ("battle.reason.no_uses", "No uses left this battle"),
            ("battle.reason.a_pet", "a pet"),
            ("battle.reason.needs_items", "Needs {what} x{count}"),
            ("battle.reason.needs_amount", "Needs {amount} {resource}"),
            ("battle.reason.needs", "Needs {what}"),
            ("battle.reason.no_ingredients", "No ingredients"),
            ("battle.reason.pet_unlearned", "{pet} has not learned this"),
            ("battle.condition.not", "no {what}"),
            ("battle.condition.or", " or "),
            ("battle.condition.state", "state {state}"),
            ("battle.condition.some", "conditions"),
        ),
    ),
    (
        "Battle",
        (
            ("battle.result.victory", "Victory"),
            ("battle.result.defeat", "Defeat"),
            ("battle.result.escape", "Escaped"),
            ("battle.result.complete", "Battle Complete"),
            ("battle.result.rank", "Rank {old} → {new}"),
            ("battle.tile.break", "BREAK"),
            ("battle.break_caption", "Damage up - loses a turn"),
            ("battle.item_none_left", "no {name} left"),
            ("battle.escape.no_rule", "The project defines no escape rule"),
            ("battle.escape.blocked", "This battle has no_escape: there is no running away"),
            ("battle.capture.needs", "capturing needs {item}"),
        ),
    ),
    (
        "Capture",
        (
            ("capture.failed", "Capture failed: {reason}"),
            ("capture.caught", "Captured {name}!"),
            ("capture.broke_free", "{name} broke free"),
            ("capture.title", "Capture"),
            ("capture.uses", "(uses {item}: {count})"),
            ("capture.cancel", "Esc: cancel"),
        ),
    ),
    (
        "Victory",
        (
            ("victory.defeated", "Defeated: {names}"),
            ("victory.title", "Victory"),
            ("victory.exp", "EXP  +{amount}"),
            ("victory.level", "Level {before} -> {after}"),
            ("victory.learned", "Learned {name}"),
            ("victory.spoils", "Spoils"),
            ("victory.overkill", "Overkill x{scale}"),
            ("victory.next", "Enter: next"),
            ("victory.close", "Enter: continue"),
        ),
    ),
    (
        "Equipment bag (action games)",
        (
            ("bag.set_tag", "tag {tag}"),
            ("bag.set_bonus", "bonus"),
            ("bag.unequipped", "Unequipped {name}"),
            ("bag.equipped", "Equipped {name}"),
            ("bag.cannot_equip", "Cannot equip: {reason}"),
            ("bag.title", "Equipment"),
            ("bag.hint", "Arrows: choose   Enter: equip / unequip   B / Esc: close"),
            ("bag.worn", "Worn"),
            ("bag.count", "Bag  ({count})"),
            ("bag.empty", "Nothing here."),
            ("bag.common", "Common"),
            ("bag.item_line", "{rarity}  ·  item level {level}  ·  {slot}"),
            ("bag.compared", "Compared with the worn piece"),
            ("bag.stats", "Stats"),
            ("bag.replaces", "(replaces {name})"),
            ("bag.affixes", "Affixes"),
        ),
    ),
    (
        "Skill tree (action games)",
        (
            ("skill_tree.status.learned", "learned"),
            ("skill_tree.status.maxed", "maxed"),
            ("skill_tree.status.available", "available"),
            ("skill_tree.status.locked", "locked"),
            ("skill_tree.max", "max {name} +{value}"),
            ("skill_tree.skill", "Skill: {name}"),
            ("skill_tree.passive", "Passive: {name}"),
            ("skill_tree.tag", "Tag: {name}"),
            ("skill_tree.unmet", "requirements not met"),
            ("skill_tree.cannot_learn", "Cannot learn {name}: {reason}"),
            ("skill_tree.learned", "Learned {name} (rank {rank}/{max})"),
            ("skill_tree.title", "Skill Tree"),
            ("skill_tree.none", "No skill tree for this character."),
            ("skill_tree.header", "{tree}   ·   {classes}   ·   Lv {level}"),
            ("skill_tree.trees", "Tree {index}/{count}  (O: next tree)"),
            (
                "skill_tree.hint",
                "Arrows: choose   Enter: learn   Wheel / + -: zoom   Drag: move   R: fit   O: "
                "next tree   C: back",
            ),
            ("skill_tree.rank", "Rank {rank}/{max}   ·   {status}"),
            ("skill_tree.free", "free"),
            ("skill_tree.cost", "Next rank costs {cost}"),
            ("skill_tree.gives", "Next rank gives:"),
            ("skill_tree.so_far", "Learned so far:"),
            ("skill_tree.needs", "Needs:"),
            ("points.ap", "AP"),
            ("points.skill_points", "SP"),
            ("points.stat_points", "Stat points"),
            ("points.jp", "{name} JP"),
            ("socket.number", "Socket {number}"),
        ),
    ),
    (
        "Action HUD",
        (
            ("action.level_up", "Level {level}!"),
            ("action.fell", "You fell — back in {seconds}s"),
            ("hud.level", "Lv {level}"),
            ("hud.skills", "Skills 1-{last}"),
            ("hud.skill", "Skill 1"),
            (
                "hud.controls",
                "Move WASD   Attack J   Dodge K   {skills}   Lock L   Pick up F   Bag B   "
                "Skill tree C   Pause Esc",
            ),
        ),
    ),
    (
        "Build menu (testing)",
        (
            ("build.title", "Character / Build Acceptance Menu"),
            ("build.keys", "Q/E Actor   C Close     Current: {actor}"),
            ("build.points", "Level {level}   EXP {exp}   AP {ap}   Ability Pts {ability_points}"),
            ("build.class", "1 Secondary Class: {value}"),
            ("build.passives", "3 Passives: {value}"),
            ("build.weapon", "4 Weapon: {value}"),
            ("build.base", "base"),
            ("build.upgrade", "5 Weapon Upgrade: {value}"),
            ("build.accessories", "6 Accessories: {value}"),
            ("build.party", "7 Party / Formation: {value}"),
            ("build.tree", "2 Skill Tree: allocate next available node"),
            (
                "build.note",
                "All changes are Runtime State and are verified again after Save/Load.",
            ),
            ("build.learned", "Learned {name}"),
            ("build.no_node", "No affordable/unlocked node"),
            ("build.upgraded", "Weapon upgraded: {name}"),
            ("build.no_upgrade", "Weapon growth maxed or blocked"),
        ),
    ),
    (
        "Equipment and enhance",
        (
            ("workshop.refined", "Refine: {outcome}"),
            ("workshop.outcome.success", "success"),
            ("workshop.outcome.failure", "failure"),
            ("workshop.outcome.protected", "failed, level kept"),
            ("workshop.took_out", "Took {name} out of {socket}"),
            ("workshop.socketed", "Socketed {name} into {socket}"),
            ("workshop.locked", "locked"),
            ("workshop.empty", "empty"),
            ("workshop.socket_row", "{socket}: {value}"),
            ("equipment.title", "Equipment"),
            ("equipment.member", "{name}  ·  Lv {level}  ·  {job}   (Q / E)"),
            (
                "equipment.hint",
                "Arrows: choose   Enter: change   X: take off   Q / E: member   Esc: back",
            ),
            ("equipment.fits", "For {slot}"),
            ("equipment.nothing_fits", "Nothing in the bag fits."),
            ("equipment.empty_slot", "Nothing worn here."),
            ("equipment.durability", "durability {now}/{most}"),
            ("equipment.sockets", "Sockets {filled}/{total}"),
            ("equipment.stats", "Stats"),
            ("enhance.title", "Enhance"),
            ("enhance.member", "{name}  ·  Gold {gold}   (Q / E)"),
            (
                "enhance.hint.refine",
                "Enter: refine   P: protection on / off   Tab: page   Q / E: member   Esc: back",
            ),
            (
                "enhance.hint.sockets",
                "Enter: choose / socket   X: take out   Tab: page   Q / E: member   Esc: back",
            ),
            (
                "enhance.hint.growth",
                "Enter: choose / unlock   Tab: page   Q / E: member   Esc: back",
            ),
            ("enhance.tab.refine", "Refine"),
            ("enhance.tab.sockets", "Sockets"),
            ("enhance.tab.cards", "Cards"),
            ("enhance.tab.growth", "Growth"),
            ("enhance.gear", "Worn gear"),
            ("enhance.sockets", "Sockets"),
            ("enhance.card_sockets", "Card sockets"),
            ("enhance.fits", "From the bag"),
            ("enhance.stages", "Growth stages"),
            ("enhance.levels", "Refine levels"),
            ("enhance.level_row", "+{level}   {chance}%   {cost} {currency}"),
            ("enhance.no_growth", "This piece does not grow."),
            ("enhance.no_sockets", "This piece has no such socket."),
            ("enhance.nothing_fits", "Nothing in the bag fits this socket."),
            ("enhance.unlocked", "{name} unlocked"),
            ("enhance.destroyed", "the piece was destroyed"),
            ("enhance.cannot_refine", "This piece cannot be refined."),
            ("enhance.max_level", "At the highest level (+{level})"),
            ("enhance.next_level", "+{level} → +{next}   chance {chance}%"),
            ("enhance.price", "Price {cost} {currency} (have {have})"),
            ("enhance.materials", "Materials"),
            ("enhance.material_row", "{name}  {have}/{need}"),
            ("enhance.fail.keep", "A failure loses nothing but the price"),
            ("enhance.fail.drop", "A failure drops one level"),
            ("enhance.fail.break", "A failure breaks the piece (repair it)"),
            ("enhance.fail.destroy", "A failure destroys the piece"),
            ("enhance.safe", "Always succeeds up to +{level}"),
            ("enhance.protect", "{name} x{have}: protection {state} (P)"),
            ("enhance.preview", "At the next level"),
            ("enhance.takes", "Takes: {tags}"),
            ("enhance.takes_any", "anything"),
            ("enhance.removal.lost", "Taking it out destroys it"),
            ("enhance.removal.kept", "Taking it out returns it to the bag"),
            ("enhance.stage_done", "Complete"),
            ("enhance.needs", "Next rank needs"),
            ("enhance.counter_row", "{name}  {now}/{need}"),
            ("enhance.gives", "Gives"),
            ("enhance.opens_sockets", "Opens {count} socket(s)"),
            ("enhance.evolves", "Evolves into {name}"),
            ("enhance.auto", "Unlocks by itself when ready"),
            ("enhance.ready", "Ready: Enter unlocks it"),
        ),
    ),
    (
        "Co-op",
        (
            ("coop.bag_title", "Co-op Inventory"),
            ("coop.experience", "Experience: {amount}"),
            ("coop.no_items", "No items yet"),
            ("coop.boss_rule", "Boss reward: full XP to contributors; loot to one contributor"),
            ("coop.close", "B / Esc: close"),
            ("coop.craft_requested", "Craft requested from server"),
            ("coop.learn_requested", "Learning requested from server"),
            ("coop.bind_requested", "Slot {slot} binding requested from server"),
            ("coop.bind_hint", "1–4: bind learned skill to slot"),
            ("coop.offline", "Co-op offline: {error}"),
            ("coop.requested", "Server {command} requested"),
            ("coop.required", "Server connection required · F3 to retry"),
            ("coop.connected_project", "Co-op connected · WASD / arrows · J attack · F pickup"),
            ("coop.connected", "Co-op connected · move with WASD / arrows · attack with F"),
            ("coop.boss_defeated", "Boss defeated · +{amount} XP"),
            ("coop.boss_loot", "Boss loot: {item}"),
            ("coop.profile_error", "Co-op profile error: {error}"),
            ("coop.start_server", "Start the local server in Multiplayer first"),
            ("coop.retry", "Co-op offline · {status} · F3 to retry"),
            ("coop.players", "Co-op · {count} players"),
            ("coop.boss", "Co-op Boss · {hp}/{max_hp}"),
            ("coop.claim", "G: claim treasure"),
            ("coop.status", "Co-op · {count} players · XP {xp} · B: bag / G: loot"),
            ("coop.player", "Player"),
            ("coop.player_hp", "{name} · {hp} HP"),
            ("coop.paused", "Server connection paused · F3 to retry"),
            ("coop.confirmed", "Server {command} confirmed"),
            ("coop.rejected", "Server rejected command"),
        ),
    ),
)
BUILT_IN_TEXT = {key: english for _, rows in GROUPS for key, english in rows}
_GROUP_OF = {key: title for title, rows in GROUPS for key, _ in rows}
