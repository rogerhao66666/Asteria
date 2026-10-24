"""Gacha banners (U5): prizes drawn by weight, pity, a guaranteed rarity per multi-pull.

A banner is project data. Its ``rarities`` run from the lowest to the highest; each carries its
own name, colour and the pictures and sound of the chest that opens for it. Its ``prizes`` are
items, equipment, characters or pets, each with a weight and a rarity; a ``featured`` prize's
weight is multiplied by ``featured_multiplier`` (a rate-up). The chance of a rarity is the sum of
its prizes' weights over all of them (``rates()``), shown on the banner's rates page, which the
game always shows.

Pity: ``hard_pity`` pulls without a prize of ``pity_rarity`` (the highest when empty) or better
make the next one that rarity; from ``soft_pity_start`` on, each pull adds ``soft_pity_step`` to
its chance (the others shrink in proportion). A multi-pull of ``multi_count`` with no prize of
``multi_guarantee`` or better turns its last pull into one of those. A character (or pet) already
owned becomes ``duplicate_item`` x ``duplicate_amount`` instead.

``GachaRuntime`` draws with the rng it is given (the game seeds one per pull from the banner and
the pull count, so a save draws the same way again and tests can fix it); ``simulate`` draws many
times to show the real spread. The presentation: the chest of the best rarity drawn appears
(``appear_seconds``, ``appear_sound``), shakes (``shake_seconds``, ``shake_sound``) and opens in
its rarity's colour (``open_seconds``, the rarity's ``open_sound``), then the prizes show in a
grid.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

PRIZE_KINDS = ("item", "equipment", "actor", "pet")


def _text(value):
    return str(value or "").strip()


def _color(value, default=(235, 235, 245)):
    if value is None or value == "":
        return default
    values = tuple(int(v) for v in value)
    if len(values) != 3 or any(not 0 <= v <= 255 for v in values):
        raise ValueError("a colour is three numbers from 0 to 255")
    return values


@dataclass(frozen=True, slots=True)
class GachaRarity:
    rarity_id: str
    display_name: str = ""
    color: tuple = (235, 235, 245)
    chest_image: str = ""  # the closed chest that appears and shakes
    open_image: str = ""  # the chest open in this rarity's light
    open_sound: str = ""

    def __init__(
        self, rarity_id, display_name="", color=None, chest_image="", open_image="", open_sound=""
    ):
        rarity_id = _text(rarity_id)
        if not rarity_id:
            raise ValueError("a rarity needs an id")
        object.__setattr__(self, "rarity_id", rarity_id)
        object.__setattr__(self, "display_name", _text(display_name) or rarity_id)
        object.__setattr__(self, "color", _color(color))
        object.__setattr__(self, "chest_image", _text(chest_image))
        object.__setattr__(self, "open_image", _text(open_image))
        object.__setattr__(self, "open_sound", _text(open_sound))

    def to_data(self):
        return {
            "rarity_id": self.rarity_id,
            "display_name": self.display_name,
            "color": list(self.color),
            "chest_image": self.chest_image,
            "open_image": self.open_image,
            "open_sound": self.open_sound,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["rarity_id"],
            data.get("display_name", ""),
            data.get("color"),
            data.get("chest_image", ""),
            data.get("open_image", ""),
            data.get("open_sound", ""),
        )


@dataclass(frozen=True, slots=True)
class GachaPrize:
    prize_id: str
    kind: str = "item"
    target_id: str = ""
    amount: int = 1
    weight: float = 1.0
    rarity: str = ""
    featured: bool = False
    duplicate_item: str = ""
    duplicate_amount: int = 0

    def __init__(
        self,
        prize_id,
        kind="item",
        target_id="",
        amount=1,
        weight=1.0,
        rarity="",
        featured=False,
        duplicate_item="",
        duplicate_amount=0,
    ):
        prize_id = _text(prize_id)
        if not prize_id:
            raise ValueError("a prize needs an id")
        if kind not in PRIZE_KINDS:
            raise ValueError(f"a prize is one of {PRIZE_KINDS}")
        weight, amount = float(weight), int(amount)
        if weight < 0 or amount < 1 or int(duplicate_amount) < 0:
            raise ValueError("weights are >= 0, amounts >= 1")
        object.__setattr__(self, "prize_id", prize_id)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "target_id", _text(target_id) or prize_id)
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "weight", weight)
        object.__setattr__(self, "rarity", _text(rarity))
        object.__setattr__(self, "featured", bool(featured))
        object.__setattr__(self, "duplicate_item", _text(duplicate_item))
        object.__setattr__(self, "duplicate_amount", int(duplicate_amount))

    def to_data(self):
        return {
            "prize_id": self.prize_id,
            "kind": self.kind,
            "target_id": self.target_id,
            "amount": self.amount,
            "weight": self.weight,
            "rarity": self.rarity,
            "featured": self.featured,
            "duplicate_item": self.duplicate_item,
            "duplicate_amount": self.duplicate_amount,
        }

    @classmethod
    def from_data(cls, data):
        keys = ("kind", "target_id", "amount", "weight", "rarity", "featured",
                "duplicate_item", "duplicate_amount")  # fmt: skip
        return cls(data["prize_id"], **{k: data[k] for k in keys if k in data})


@dataclass(frozen=True, slots=True)
class GachaBanner:
    banner_id: str
    display_name: str = ""
    description: str = ""
    banner_image: str = ""
    currency: str = "gold"
    single_cost: float = 100.0
    multi_cost: float = 1000.0
    multi_count: int = 10
    rarities: tuple = ()
    prizes: tuple = ()
    featured_multiplier: float = 1.0
    hard_pity: int = 0
    pity_rarity: str = ""
    soft_pity_start: int = 0
    soft_pity_step: float = 0.0
    multi_guarantee: str = ""
    open_switch: str = ""
    appear_seconds: float = 0.5
    shake_seconds: float = 0.8
    open_seconds: float = 0.6
    appear_sound: str = ""
    shake_sound: str = ""
    music: str = ""
    layout: str = ""

    def __init__(self, banner_id, display_name="", **values):
        banner_id = _text(banner_id)
        if not banner_id:
            raise ValueError("a banner needs an id")
        rarities = tuple(
            r if isinstance(r, GachaRarity) else GachaRarity.from_data(r)
            for r in values.pop("rarities", ())
        )
        prizes = tuple(
            p if isinstance(p, GachaPrize) else GachaPrize.from_data(p)
            for p in values.pop("prizes", ())
        )
        ids = [r.rarity_id for r in rarities]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate rarities in banner {banner_id}")
        prize_ids = [p.prize_id for p in prizes]
        if len(prize_ids) != len(set(prize_ids)):
            raise ValueError(f"duplicate prizes in banner {banner_id}")
        for prize in prizes:
            if ids and prize.rarity not in ids:
                raise ValueError(f"prize {prize.prize_id} has an unknown rarity {prize.rarity}")
        object.__setattr__(self, "banner_id", banner_id)
        object.__setattr__(self, "display_name", _text(display_name) or banner_id)
        object.__setattr__(self, "rarities", rarities)
        object.__setattr__(self, "prizes", prizes)
        texts = ("description", "banner_image", "currency", "pity_rarity", "multi_guarantee",
                 "open_switch", "appear_sound", "shake_sound", "music", "layout")  # fmt: skip
        for name in texts:
            raw = values.pop(name, None)
            default = GachaBanner.__dataclass_fields__[name].default
            value = str(raw if raw is not None else default)
            object.__setattr__(self, name, value if name == "description" else value.strip())
        numbers = ("single_cost", "multi_cost", "featured_multiplier", "soft_pity_step",
                   "appear_seconds", "shake_seconds", "open_seconds")  # fmt: skip
        for name in numbers:
            value = float(values.pop(name, GachaBanner.__dataclass_fields__[name].default))
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
            object.__setattr__(self, name, value)
        for name in ("multi_count", "hard_pity", "soft_pity_start"):
            value = int(values.pop(name, GachaBanner.__dataclass_fields__[name].default))
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
            object.__setattr__(self, name, value)
        if self.multi_count < 1:
            raise ValueError("multi_count must be at least 1")
        for name in ("pity_rarity", "multi_guarantee"):
            if getattr(self, name) and getattr(self, name) not in ids:
                raise ValueError(f"{name} names an unknown rarity")
        if values:
            raise TypeError(f"unknown banner fields: {sorted(values)}")

    # -- reading ---------------------------------------------------------------------------
    def rarity(self, rarity_id):
        return next((r for r in self.rarities if r.rarity_id == rarity_id), None)

    def rank(self, rarity_id):
        """How high a rarity is (0: the lowest)."""
        ids = [r.rarity_id for r in self.rarities]
        return ids.index(rarity_id) if rarity_id in ids else -1

    def top_rarity(self):
        return self.pity_rarity or (self.rarities[-1].rarity_id if self.rarities else "")

    def weight(self, prize):
        return prize.weight * (self.featured_multiplier if prize.featured else 1.0)

    def rates(self):
        """``[(rarity, chance, [(prize, chance)])]``: every rarity's chance and each prize's,
        from the weights (what the rates page shows)."""
        total = sum(self.weight(p) for p in self.prizes) or 1.0
        out = []
        for rarity in self.rarities or (GachaRarity("all"),):
            own = [p for p in self.prizes if not self.rarities or p.rarity == rarity.rarity_id]
            chance = sum(self.weight(p) for p in own) / total
            out.append((rarity, chance, [(p, self.weight(p) / total) for p in own]))
        return out

    def to_data(self):
        data = {"schema": "asteria.rpg.gacha_banner", "version": 1}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if name in ("rarities", "prizes"):
                value = [x.to_data() for x in value]
            data[name] = value
        return data

    @classmethod
    def from_data(cls, data):
        if data.get("schema", "asteria.rpg.gacha_banner") != "asteria.rpg.gacha_banner":
            raise ValueError("unsupported gacha banner")
        values = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        banner_id = values.pop("banner_id")
        return cls(banner_id, values.pop("display_name", ""), **values)


@dataclass(frozen=True, slots=True)
class GachaPull:
    prize: GachaPrize
    rarity: str
    pity: bool = False  # the hard pity made it
    guaranteed: bool = False  # the multi-pull's guarantee made it


@dataclass(slots=True)
class GachaState:
    """What a save keeps of one banner: pulls in all, pulls since the pity rarity, history."""

    total: int = 0
    since_top: int = 0
    history: list = field(default_factory=list)  # [[prize id, rarity], ...] newest last

    HISTORY = 100

    def to_data(self):
        return {"total": self.total, "since_top": self.since_top, "history": list(self.history)}

    @classmethod
    def from_data(cls, data):
        data = dict(data or {})
        return cls(
            int(data.get("total", 0)),
            int(data.get("since_top", 0)),
            [list(x) for x in data.get("history", ())],
        )


class GachaRuntime:
    def __init__(self, banner):
        self.banner = banner

    def _chances(self, state, floor=-1):
        """``{rarity: chance}`` for the next pull (rarities below rank ``floor`` left out)."""
        banner = self.banner
        weights = {}
        for prize in banner.prizes:
            if banner.rank(prize.rarity) >= floor:
                weights[prize.rarity] = weights.get(prize.rarity, 0.0) + banner.weight(prize)
        total = sum(weights.values())
        if total <= 0:
            return {}
        chances = {k: v / total for k, v in weights.items()}
        top = banner.top_rarity()
        start = banner.soft_pity_start
        if top in chances and start and banner.soft_pity_step and state.since_top + 1 > start:
            boosted = min(
                1.0, chances[top] + banner.soft_pity_step * (state.since_top + 1 - start)
            )
            rest = 1.0 - chances[top]
            scale = (1.0 - boosted) / rest if rest > 0 else 0.0
            chances = {k: (boosted if k == top else v * scale) for k, v in chances.items()}
        return chances

    def _pick(self, rng, chances):
        roll, last = rng.random(), None
        for rarity, chance in sorted(chances.items(), key=lambda kv: self.banner.rank(kv[0])):
            last = rarity
            roll -= chance
            if roll < 0:
                return rarity
        return last

    def _prize(self, rng, rarity):
        banner = self.banner
        own = [p for p in banner.prizes if p.rarity == rarity and banner.weight(p) > 0]
        roll = rng.random() * sum(banner.weight(p) for p in own)
        for prize in own:
            roll -= banner.weight(prize)
            if roll < 0:
                return prize
        return own[-1]

    def pull(self, rng, state, count=1):
        """``count`` pulls (``multi_count`` for a multi-pull); ``state`` moves on."""
        banner = self.banner
        if not banner.prizes:
            raise ValueError(f"banner {banner.banner_id} has no prizes")
        top = banner.top_rarity()
        top_rank = banner.rank(top)
        pulls = []
        for n in range(int(count)):
            pity = bool(banner.hard_pity) and state.since_top + 1 >= banner.hard_pity
            guaranteed = False
            floor = -1
            if pity:
                floor = top_rank
            elif (
                count > 1
                and n == count - 1
                and banner.multi_guarantee
                and all(banner.rank(p.rarity) < banner.rank(banner.multi_guarantee) for p in pulls)
            ):
                floor, guaranteed = banner.rank(banner.multi_guarantee), True
            chances = self._chances(state, floor)
            if pity and top in chances:
                rarity = top
            else:
                rarity = self._pick(rng, chances)
            pull = GachaPull(self._prize(rng, rarity), rarity, pity, guaranteed)
            pulls.append(pull)
            state.total += 1
            if banner.rank(rarity) >= top_rank:
                state.since_top = 0
            else:
                state.since_top += 1
            state.history.append([pull.prize.prize_id, rarity])
        del state.history[: -GachaState.HISTORY]
        return pulls

    def simulate(self, pulls=10000, seed=0, multi=True):
        """Draw ``pulls`` times from a fresh state (multi-pulls when ``multi``): ``{"rarity":
        {id: count}, "prize": {id: count}, "pity": n, "guaranteed": n}``."""
        rng = random.Random(seed)
        state = GachaState()
        out = {"rarity": {}, "prize": {}, "pity": 0, "guaranteed": 0, "pulls": 0}
        step = self.banner.multi_count if multi else 1
        while out["pulls"] < pulls:
            for pull in self.pull(rng, state, min(step, pulls - out["pulls"])):
                out["pulls"] += 1
                out["rarity"][pull.rarity] = out["rarity"].get(pull.rarity, 0) + 1
                out["prize"][pull.prize.prize_id] = out["prize"].get(pull.prize.prize_id, 0) + 1
                out["pity"] += pull.pity
                out["guaranteed"] += pull.guaranteed
        return out
