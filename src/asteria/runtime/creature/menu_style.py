"""What the creature start menu's parts share: where the summary and card words go, the play
time counter, which phases draw over the field, and the taught-move and fanfare helpers."""

from __future__ import annotations

from asteria.events.world_commands import WorldCommand
from asteria.runtime.session.pets import taught_ability as taught

OVERLAY_PHASES = ("start", "save")  # drawn over the field


PLAY_SECONDS = "play.seconds"  # the world counter of the time played (the card, the save)


SUMMARY_PLACES = {  # the summary pages' words: (x, y) in the screen's own pixels
    "title": (8, 1),
    "number": (4, 19),
    "name": (40, 19),
    "level": (4, 112),
    "picture": (40, 72),
    "info.ot": (96, 34),
    "info.id": (184, 34),
    "info.type": (96, 50),
    "info.item": (96, 66),
    "info.memo": (96, 114),
    "skills.labels": (88, 58),
    "skills.values": (184, 58),
    "skills.exp": (88, 114),
    "moves.list": (128, 34),
}


CARD_PLACES = {  # the trainer card's words (pokeemerald's Hoenn card)
    "name": (24, 41),
    "id": (176, 17),
    "money": (24, 65),
    "money_value": (136, 65),
    "dex": (24, 81),
    "dex_value": (136, 81),
    "time": (24, 97),
    "time_value": (136, 97),
}


def taught_ability(item):
    return taught(item)


def _me(asset_id):
    return WorldCommand("PLAY_ME", {"asset_id": str(asset_id)})
