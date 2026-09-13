from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from asteria.rpg.battle import BattleOutcome
from asteria.rpg.rewards import RewardApplicationResult


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class BattleResultProfile:
    victory_label: str = "Victory"
    defeat_label: str = "Defeat"
    escape_label: str = "Escaped"
    complete_label: str = "Battle Complete"
    currency_labels: tuple[tuple[str, str], ...] = ()
    progression_labels: tuple[tuple[str, str], ...] = ()
    item_labels: tuple[tuple[str, str], ...] = ()

    def __init__(
        self, *, victory_label="Victory", defeat_label="Defeat", escape_label="Escaped",
        complete_label="Battle Complete", currency_labels=None, progression_labels=None,
        item_labels=None,
    ):
        object.__setattr__(self, "victory_label", str(victory_label))
        object.__setattr__(self, "defeat_label", str(defeat_label))
        object.__setattr__(self, "escape_label", str(escape_label))
        object.__setattr__(self, "complete_label", str(complete_label))
        object.__setattr__(self, "currency_labels", tuple(sorted((str(k), str(v)) for k, v in dict(currency_labels or {}).items())))
        object.__setattr__(self, "progression_labels", tuple(sorted((str(k), str(v)) for k, v in dict(progression_labels or {}).items())))
        object.__setattr__(self, "item_labels", tuple(sorted((str(k), str(v)) for k, v in dict(item_labels or {}).items())))

    def _label(self, pairs, key):
        return dict(pairs).get(str(key), str(key))

    def currency_label(self, key): return self._label(self.currency_labels, key)
    def progression_label(self, key): return self._label(self.progression_labels, key)
    def item_label(self, key): return self._label(self.item_labels, key)

    def to_data(self):
        return {
            "schema": "asteria.battle_result_profile", "version": 1,
            "victory_label": self.victory_label, "defeat_label": self.defeat_label,
            "escape_label": self.escape_label, "complete_label": self.complete_label,
            "currency_labels": dict(self.currency_labels),
            "progression_labels": dict(self.progression_labels),
            "item_labels": dict(self.item_labels),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.battle_result_profile" or data.get("version") != 1:
            raise ValueError("unsupported battle result profile")
        return cls(
            victory_label=data.get("victory_label", "Victory"),
            defeat_label=data.get("defeat_label", "Defeat"),
            escape_label=data.get("escape_label", "Escaped"),
            complete_label=data.get("complete_label", "Battle Complete"),
            currency_labels=data.get("currency_labels"),
            progression_labels=data.get("progression_labels"),
            item_labels=data.get("item_labels"),
        )


@dataclass(frozen=True, slots=True)
class BattleCurrencyRewardView:
    currency_id: str
    label: str
    amount: float


@dataclass(frozen=True, slots=True)
class BattleItemRewardView:
    item_id: str
    label: str
    amount: int


@dataclass(frozen=True, slots=True)
class BattleProgressionRewardView:
    track_id: str
    label: str
    old_total: float
    new_total: float
    old_rank: int
    new_rank: int
    crossed_ranks: tuple[int, ...]
    granted_abilities: tuple[str, ...]
    granted_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BattleResultView:
    finished: bool
    headline: str
    winning_sides: tuple[str, ...]
    defeated_sides: tuple[str, ...]
    escaped_sides: tuple[str, ...]
    objective_ids: tuple[str, ...]
    currencies: tuple[BattleCurrencyRewardView, ...]
    progression: tuple[BattleProgressionRewardView, ...]
    items: tuple[BattleItemRewardView, ...]
    revision: int


class BattleResultPresentationRuntime:
    """Read-only projection of canonical battle outcome and applied rewards.

    Reward rolling/application and battle-outcome resolution stay outside
    presentation. This runtime only copies already-resolved/applied values.
    """

    SCHEMA = "asteria.battle_result_presentation_runtime"
    VERSION = 1

    def __init__(self, profile=None):
        self.profile = profile or BattleResultProfile()
        if not isinstance(self.profile, BattleResultProfile):
            raise TypeError("profile must be BattleResultProfile")
        self.revision = 0
        self._view = BattleResultView(False, "", (), (), (), (), (), (), (), 0)

    @property
    def view(self):
        return self._view

    def _headline(self, outcome, *, perspective_side_ids=None, disposition=None):
        if not outcome.finished:
            return ""

        if disposition is not None:
            disposition = str(disposition).strip().lower()
            labels = {
                "victory": self.profile.victory_label,
                "defeat": self.profile.defeat_label,
                "escape": self.profile.escape_label,
                "complete": self.profile.complete_label,
            }
            if disposition not in labels:
                raise ValueError("unsupported battle result presentation disposition")
            return labels[disposition]

        if perspective_side_ids is None:
            # A canonical outcome may contain winners/defeated sides but without a
            # viewer perspective presentation cannot truthfully call that Victory
            # or Defeat. Neutral completion is the only generic default.
            return self.profile.complete_label

        perspective = {str(x) for x in perspective_side_ids}
        if perspective.intersection(map(str, outcome.winning_sides)):
            return self.profile.victory_label
        if perspective.intersection(map(str, outcome.escaped_sides)):
            return self.profile.escape_label
        if perspective.intersection(map(str, outcome.defeated_sides)):
            return self.profile.defeat_label
        return self.profile.complete_label

    def present(self, outcome, reward_result=None, *, perspective_side_ids=None, disposition=None):
        if not isinstance(outcome, BattleOutcome):
            raise TypeError("outcome must be BattleOutcome")
        if reward_result is not None and not isinstance(reward_result, RewardApplicationResult):
            raise TypeError("reward_result must be RewardApplicationResult")

        currencies = ()
        progression = ()
        items = ()
        if reward_result is not None:
            currencies = tuple(
                BattleCurrencyRewardView(str(k), self.profile.currency_label(k), _finite(v, "currency reward"))
                for k, v in sorted(reward_result.currencies.items())
            )
            items = tuple(
                BattleItemRewardView(str(k), self.profile.item_label(k), int(v))
                for k, v in sorted(reward_result.items.items())
            )
            progression_values = []
            for result in reward_result.progression_results:
                crossed = tuple(result.crossed)
                granted_abilities = tuple(dict.fromkeys(
                    ability for milestone in crossed for ability in milestone.granted_abilities
                ))
                granted_tags = tuple(sorted({
                    tag for milestone in crossed for tag in milestone.granted_tags
                }))
                progression_values.append(BattleProgressionRewardView(
                    str(result.track_id), self.profile.progression_label(result.track_id),
                    _finite(result.old_total, "old_total"), _finite(result.new_total, "new_total"),
                    int(result.old_rank), int(result.new_rank),
                    tuple(int(x.rank) for x in crossed), granted_abilities, granted_tags,
                ))
            progression = tuple(sorted(progression_values, key=lambda x: x.track_id))

        self.revision += 1
        self._view = BattleResultView(
            bool(outcome.finished), self._headline(
                outcome,
                perspective_side_ids=perspective_side_ids,
                disposition=disposition,
            ),
            tuple(str(x) for x in outcome.winning_sides),
            tuple(str(x) for x in outcome.defeated_sides),
            tuple(str(x) for x in outcome.escaped_sides),
            tuple(str(x) for x in outcome.objective_ids),
            currencies, progression, items, self.revision,
        )
        return self._view

    def snapshot(self):
        return {
            "schema": self.SCHEMA, "version": self.VERSION,
            "profile": self.profile.to_data(), "revision": self.revision,
            "view": {
                "finished": self._view.finished, "headline": self._view.headline,
                "winning_sides": list(self._view.winning_sides),
                "defeated_sides": list(self._view.defeated_sides),
                "escaped_sides": list(self._view.escaped_sides),
                "objective_ids": list(self._view.objective_ids),
                "currencies": [x.__dict__ if hasattr(x, "__dict__") else {
                    "currency_id": x.currency_id, "label": x.label, "amount": x.amount
                } for x in self._view.currencies],
                "progression": [{
                    "track_id": x.track_id, "label": x.label, "old_total": x.old_total,
                    "new_total": x.new_total, "old_rank": x.old_rank, "new_rank": x.new_rank,
                    "crossed_ranks": list(x.crossed_ranks),
                    "granted_abilities": list(x.granted_abilities),
                    "granted_tags": list(x.granted_tags),
                } for x in self._view.progression],
                "items": [{"item_id": x.item_id, "label": x.label, "amount": x.amount} for x in self._view.items],
            },
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported battle result presentation snapshot")
        self.profile = BattleResultProfile.from_data(data["profile"])
        self.revision = int(data["revision"])
        v = data["view"]
        currencies = tuple(BattleCurrencyRewardView(**x) for x in v.get("currencies", ()))
        progression = tuple(BattleProgressionRewardView(
            x["track_id"], x["label"], float(x["old_total"]), float(x["new_total"]),
            int(x["old_rank"]), int(x["new_rank"]), tuple(x.get("crossed_ranks", ())),
            tuple(x.get("granted_abilities", ())), tuple(x.get("granted_tags", ())),
        ) for x in v.get("progression", ()))
        items = tuple(BattleItemRewardView(**x) for x in v.get("items", ()))
        self._view = BattleResultView(
            bool(v["finished"]), str(v["headline"]), tuple(v.get("winning_sides", ())),
            tuple(v.get("defeated_sides", ())), tuple(v.get("escaped_sides", ())),
            tuple(v.get("objective_ids", ())), currencies, progression, items, self.revision,
        )
        return self._view
