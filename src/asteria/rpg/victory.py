"""Victory aftermath: what a won battle gave, as pages a results screen can show one by one.

Pure data - it records money, items, each hero's experience and level change (with the stats that
rose), and the abilities newly available. The screen that draws it lives in ``runtime``.
"""

from __future__ import annotations

from dataclasses import dataclass


def _round(value):
    return round(float(value), 4)


@dataclass(frozen=True, slots=True)
class ActorAftermath:
    actor_id: str
    name: str = ""
    experience_gained: float = 0.0
    level_before: int = 1
    level_after: int = 1
    stat_changes: tuple[tuple[str, float, float], ...] = ()  # (stat, before, after) that changed
    new_abilities: tuple[str, ...] = ()

    @property
    def leveled_up(self):
        return self.level_after > self.level_before

    def to_data(self):
        return {
            "actor_id": self.actor_id,
            "name": self.name,
            "experience_gained": self.experience_gained,
            "level_before": self.level_before,
            "level_after": self.level_after,
            "stat_changes": [list(x) for x in self.stat_changes],
            "new_abilities": list(self.new_abilities),
        }


@dataclass(frozen=True, slots=True)
class AftermathPage:
    kind: str  # "rewards", "actor" or "drops"
    title: str
    lines: tuple[str, ...] = ()
    actor_id: str = ""


@dataclass(frozen=True, slots=True)
class VictoryAftermath:
    currencies: tuple[tuple[str, float], ...] = ()
    items: tuple[tuple[str, int], ...] = ()
    actors: tuple[ActorAftermath, ...] = ()
    defeated: tuple[str, ...] = ()
    bonus_notes: tuple[str, ...] = ()  # e.g. "Overkill x1.5"

    def pages(self, *, item_names=None, currency_names=None, stat_names=None):
        """Pages in display order: rewards, one per hero that gained experience, then drops."""
        item_names = item_names or {}
        currency_names = currency_names or {}
        stat_names = stat_names or {}
        pages = []
        lines = [f"{currency_names.get(k, k)}  +{v:g}" for k, v in self.currencies if v]
        lines += list(self.bonus_notes)
        if self.defeated:
            lines.insert(0, "Defeated: " + ", ".join(self.defeated))
        pages.append(AftermathPage("rewards", "Victory", tuple(lines)))
        for actor in self.actors:
            if not (actor.experience_gained or actor.leveled_up):
                continue
            lines = [f"EXP  +{actor.experience_gained:g}"]
            if actor.leveled_up:
                lines.append(f"Level {actor.level_before} -> {actor.level_after}")
                for stat, before, after in actor.stat_changes:
                    label = stat_names.get(stat, stat)
                    lines.append(f"{label}  {before:g} -> {after:g}")
                lines += [f"Learned {a}" for a in actor.new_abilities]
            pages.append(
                AftermathPage("actor", actor.name or actor.actor_id, tuple(lines), actor.actor_id)
            )
        if self.items:
            lines = tuple(f"{item_names.get(k, k)}  x{n}" for k, n in self.items)
            pages.append(AftermathPage("drops", "Spoils", lines))
        return tuple(pages)

    def to_data(self):
        return {
            "currencies": dict(self.currencies),
            "items": dict(self.items),
            "actors": [x.to_data() for x in self.actors],
            "defeated": list(self.defeated),
            "bonus_notes": list(self.bonus_notes),
        }


def build_aftermath(
    applied,
    before,
    after,
    *,
    defeated=(),
    names=None,
    experience=None,
    bonus_notes=(),
):
    """Assemble a ``VictoryAftermath``.

    ``applied``: the ``RewardApplicationResult`` values of the battle (money and items are summed).
    ``before`` / ``after``: ``{actor_id: {"level": n, "stats": {...}, "abilities": [...]}}``
    captured around the reward step. ``experience``: ``{actor_id: amount}`` gained.
    """
    names = names or {}
    experience = experience or {}
    currencies, items = {}, {}
    for result in applied:
        for key, value in result.currencies.items():
            currencies[key] = currencies.get(key, 0.0) + float(value)
        for key, value in result.items.items():
            items[key] = items.get(key, 0) + int(value)
    actors = []
    for actor_id in sorted(after):
        was = before.get(
            actor_id, {"level": after[actor_id]["level"], "stats": {}, "abilities": ()}
        )
        now = after[actor_id]
        changes = tuple(
            (stat, _round(was["stats"].get(stat, value)), _round(value))
            for stat, value in sorted(now["stats"].items())
            if _round(was["stats"].get(stat, value)) != _round(value)
        )
        learned = tuple(a for a in now["abilities"] if a not in set(was["abilities"]))
        actors.append(
            ActorAftermath(
                actor_id,
                names.get(actor_id, actor_id),
                float(experience.get(actor_id, 0.0)),
                int(was["level"]),
                int(now["level"]),
                changes,
                learned,
            )
        )
    return VictoryAftermath(
        tuple(sorted(currencies.items())),
        tuple(sorted(items.items())),
        tuple(actors),
        tuple(defeated),
        tuple(bonus_notes),
    )
