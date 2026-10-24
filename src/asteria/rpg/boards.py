"""Quest boards and recruiting offices (U5): two kinds of project data opened by events.

**Quest board** (``OPEN_QUEST_BOARD``): the quests it offers (``quest_ids``) as cards; a quest
can be taken when its prerequisites are done (and the board's ``open_switch`` is on, when it
names one). ``max_active`` caps how many of the board's quests run at once (0: no cap). A
repeatable quest comes back on the board ``refresh_minutes`` of play after it was handed in
(0: at once). ``card_style`` lays the cards out in a ``grid`` or one ``row``; ``layout`` names
the menu layout the screen draws through.

**Recruiting office** (``OPEN_RECRUIT``): candidates, each a character of the project with a
price, an optional switch that must be on, a level rolled between ``level_min`` and
``level_max`` when hired (0: the character's own) and a ``portrait`` for its card.
``party_limit`` caps the party's size (0: no cap); ``can_dismiss`` lets the player send a
hired member away for ``dismiss_refund`` of the price.
"""

from __future__ import annotations

from dataclasses import dataclass

CARD_STYLES = ("grid", "row")


def _text(value):
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class QuestBoardDefinition:
    board_id: str
    display_name: str = ""
    description: str = ""
    quest_ids: tuple = ()
    open_switch: str = ""
    max_active: int = 0
    refresh_minutes: float = 0.0
    card_style: str = "grid"
    music: str = ""
    layout: str = ""

    def __init__(
        self,
        board_id,
        display_name="",
        *,
        description="",
        quest_ids=(),
        open_switch="",
        max_active=0,
        refresh_minutes=0.0,
        card_style="grid",
        music="",
        layout="",
    ):
        board_id = _text(board_id)
        if not board_id:
            raise ValueError("a quest board needs an id")
        quest_ids = tuple(_text(q) for q in quest_ids if _text(q))
        if len(quest_ids) != len(set(quest_ids)):
            raise ValueError(f"a quest is listed twice on board {board_id}")
        if card_style not in CARD_STYLES:
            raise ValueError(f"card_style is one of {CARD_STYLES}")
        if int(max_active) < 0 or float(refresh_minutes) < 0:
            raise ValueError("max_active and refresh_minutes are >= 0")
        object.__setattr__(self, "board_id", board_id)
        object.__setattr__(self, "display_name", _text(display_name) or board_id)
        object.__setattr__(self, "description", str(description or ""))
        object.__setattr__(self, "quest_ids", quest_ids)
        object.__setattr__(self, "open_switch", _text(open_switch))
        object.__setattr__(self, "max_active", int(max_active))
        object.__setattr__(self, "refresh_minutes", float(refresh_minutes))
        object.__setattr__(self, "card_style", card_style)
        object.__setattr__(self, "music", _text(music))
        object.__setattr__(self, "layout", _text(layout))

    def to_data(self):
        return {
            "schema": "asteria.rpg.quest_board",
            "version": 1,
            "board_id": self.board_id,
            "display_name": self.display_name,
            "description": self.description,
            "quest_ids": list(self.quest_ids),
            "open_switch": self.open_switch,
            "max_active": self.max_active,
            "refresh_minutes": self.refresh_minutes,
            "card_style": self.card_style,
            "music": self.music,
            "layout": self.layout,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema", "asteria.rpg.quest_board") != "asteria.rpg.quest_board":
            raise ValueError("unsupported quest board")
        keys = ("description", "quest_ids", "open_switch", "max_active", "refresh_minutes",
                "card_style", "music", "layout")  # fmt: skip
        return cls(
            data["board_id"],
            data.get("display_name", ""),
            **{k: data[k] for k in keys if k in data},
        )


@dataclass(frozen=True, slots=True)
class RecruitCandidate:
    actor_id: str
    currency: str = "gold"
    cost: float = 0.0
    require_switch: str = ""
    level_min: int = 0
    level_max: int = 0
    note: str = ""
    portrait: str = ""  # the picture on the office's card (empty: the character's own)

    def __init__(
        self, actor_id, currency="gold", cost=0.0, require_switch="", level_min=0, level_max=0,
        note="", portrait="",
    ):  # fmt: skip
        actor_id = _text(actor_id)
        if not actor_id:
            raise ValueError("a candidate needs a character")
        cost, level_min, level_max = float(cost), int(level_min), int(level_max)
        if cost < 0 or level_min < 0 or level_max < 0:
            raise ValueError("cost and levels are >= 0")
        if level_max and level_max < level_min:
            raise ValueError("level_max is below level_min")
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "currency", _text(currency) or "gold")
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "require_switch", _text(require_switch))
        object.__setattr__(self, "level_min", level_min)
        object.__setattr__(self, "level_max", level_max or level_min)
        object.__setattr__(self, "note", str(note or ""))
        object.__setattr__(self, "portrait", _text(portrait))

    def to_data(self):
        return {
            "actor_id": self.actor_id,
            "currency": self.currency,
            "cost": self.cost,
            "require_switch": self.require_switch,
            "level_min": self.level_min,
            "level_max": self.level_max,
            "note": self.note,
            "portrait": self.portrait,
        }

    @classmethod
    def from_data(cls, data):
        keys = ("currency", "cost", "require_switch", "level_min", "level_max", "note",
                "portrait")  # fmt: skip
        return cls(data["actor_id"], **{k: data[k] for k in keys if k in data})


@dataclass(frozen=True, slots=True)
class RecruitOfficeDefinition:
    office_id: str
    display_name: str = ""
    description: str = ""
    candidates: tuple = ()
    party_limit: int = 0
    can_dismiss: bool = True
    dismiss_refund: float = 0.0
    experience_per_level: float = 1000.0  # how a rolled level is given (the battles' threshold)
    music: str = ""
    layout: str = ""

    def __init__(
        self,
        office_id,
        display_name="",
        *,
        description="",
        candidates=(),
        party_limit=0,
        can_dismiss=True,
        dismiss_refund=0.0,
        experience_per_level=1000.0,
        music="",
        layout="",
    ):
        office_id = _text(office_id)
        if not office_id:
            raise ValueError("a recruiting office needs an id")
        candidates = tuple(
            c if isinstance(c, RecruitCandidate) else RecruitCandidate.from_data(c)
            for c in candidates
        )
        ids = [c.actor_id for c in candidates]
        if len(ids) != len(set(ids)):
            raise ValueError(f"a character is a candidate twice in {office_id}")
        refund = float(dismiss_refund)
        if not 0.0 <= refund <= 1.0 or int(party_limit) < 0:
            raise ValueError("dismiss_refund is 0-1, party_limit >= 0")
        object.__setattr__(self, "office_id", office_id)
        object.__setattr__(self, "display_name", _text(display_name) or office_id)
        object.__setattr__(self, "description", str(description or ""))
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "party_limit", int(party_limit))
        object.__setattr__(self, "can_dismiss", bool(can_dismiss))
        object.__setattr__(self, "dismiss_refund", refund)
        if float(experience_per_level) <= 0:
            raise ValueError("experience_per_level must be > 0")
        object.__setattr__(self, "experience_per_level", float(experience_per_level))
        object.__setattr__(self, "music", _text(music))
        object.__setattr__(self, "layout", _text(layout))

    def candidate(self, actor_id):
        return next((c for c in self.candidates if c.actor_id == actor_id), None)

    def to_data(self):
        return {
            "schema": "asteria.rpg.recruit_office",
            "version": 1,
            "office_id": self.office_id,
            "display_name": self.display_name,
            "description": self.description,
            "candidates": [c.to_data() for c in self.candidates],
            "party_limit": self.party_limit,
            "can_dismiss": self.can_dismiss,
            "dismiss_refund": self.dismiss_refund,
            "experience_per_level": self.experience_per_level,
            "music": self.music,
            "layout": self.layout,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema", "asteria.rpg.recruit_office") != "asteria.rpg.recruit_office":
            raise ValueError("unsupported recruiting office")
        keys = ("description", "candidates", "party_limit", "can_dismiss", "dismiss_refund",
                "experience_per_level", "music", "layout")  # fmt: skip
        return cls(
            data["office_id"],
            data.get("display_name", ""),
            **{k: data[k] for k in keys if k in data},
        )
