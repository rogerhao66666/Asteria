"""Quests: objectives, prerequisites, rewards and chains (ASTERIA_SPEC §26)."""

from __future__ import annotations

from dataclasses import dataclass

from .enemies import RewardDefinition

OBJECTIVE_KINDS = ("counter", "item", "defeat_enemy", "switch")
QUEST_STATUSES = ("active", "completed", "failed")
CARD_FIELDS = ("card_image", "rank", "category", "repeatable", "time_limit")


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _ids(values, label):
    out = tuple(_id(x, label) for x in values)
    if len(out) != len(set(out)):
        raise ValueError(f"duplicate {label}")
    return out


class QuestError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class QuestObjective:
    """One condition a quest needs.

    kinds: ``counter`` (advanced by events), ``item`` (hold ``required`` of
    item ``target``), ``defeat_enemy`` (defeat ``required`` enemies with id
    ``target``), ``switch`` (event switch ``target`` is on).
    """

    objective_id: str
    kind: str = "counter"
    target: str = ""
    required: int = 1
    description: str = ""

    def __init__(self, objective_id, kind="counter", *, target="", required=1, description=""):
        if kind not in OBJECTIVE_KINDS:
            raise ValueError(f"unknown objective kind: {kind}")
        required = int(required)
        if required < 1:
            raise ValueError("required must be >= 1")
        target = str(target).strip()
        if kind != "counter" and not target:
            raise ValueError(f"{kind} objective needs a target")
        object.__setattr__(self, "objective_id", _id(objective_id, "objective_id"))
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "required", required)
        object.__setattr__(self, "description", str(description))

    def to_data(self):
        return {
            "objective_id": self.objective_id,
            "kind": self.kind,
            "target": self.target,
            "required": self.required,
            "description": self.description,
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["objective_id"],
            data["kind"],
            target=data["target"],
            required=data["required"],
            description=data["description"],
        )


@dataclass(frozen=True, slots=True)
class QuestDefinition:
    quest_id: str
    display_name: str
    description: str
    objectives: tuple[QuestObjective, ...]
    prerequisites: tuple[str, ...]
    reward: RewardDefinition
    next_quest_ids: tuple[str, ...]
    auto_complete: bool

    icon_id: str = ""  # a project icon shown in menus; written only when set
    # the quest board's card (U5); each written only when set
    card_image: str = ""  # the card's picture
    rank: str = ""  # shown on the card's corner ("S", "Bronze"...)
    category: str = ""  # "Hunt", "Delivery"... shown on the card
    repeatable: bool = False  # taken again from a board after it is handed in
    time_limit: float = 0.0  # minutes of play to finish it once taken (0: no limit)

    def __init__(
        self,
        quest_id,
        display_name=None,
        *,
        description="",
        objectives=(),
        prerequisites=(),
        reward=None,
        next_quest_ids=(),
        auto_complete=True,
        icon_id="",
        card_image="",
        rank="",
        category="",
        repeatable=False,
        time_limit=0.0,
    ):
        objectives = tuple(objectives)
        if any(not isinstance(x, QuestObjective) for x in objectives):
            raise TypeError("objectives must be QuestObjective values")
        _ids([x.objective_id for x in objectives], "objective id")
        reward = reward or RewardDefinition()
        if not isinstance(reward, RewardDefinition):
            raise TypeError("reward must be RewardDefinition")
        quest_id = _id(quest_id, "quest_id")
        prerequisites = _ids(prerequisites, "prerequisite quest id")
        next_quest_ids = _ids(next_quest_ids, "next quest id")
        if quest_id in prerequisites or quest_id in next_quest_ids:
            raise ValueError("a quest cannot require or chain to itself")
        object.__setattr__(self, "quest_id", quest_id)
        object.__setattr__(self, "display_name", str(display_name or quest_id))
        object.__setattr__(self, "description", str(description))
        object.__setattr__(self, "objectives", objectives)
        object.__setattr__(self, "prerequisites", prerequisites)
        object.__setattr__(self, "reward", reward)
        object.__setattr__(self, "next_quest_ids", next_quest_ids)
        object.__setattr__(self, "auto_complete", bool(auto_complete))
        object.__setattr__(self, "icon_id", str(icon_id or "").strip())
        object.__setattr__(self, "card_image", str(card_image or "").strip())
        object.__setattr__(self, "rank", str(rank or "").strip())
        object.__setattr__(self, "category", str(category or "").strip())
        object.__setattr__(self, "repeatable", bool(repeatable))
        time_limit = float(time_limit or 0.0)
        if time_limit < 0:
            raise ValueError("time_limit must be >= 0")
        object.__setattr__(self, "time_limit", time_limit)

    def to_data(self):
        return {
            "schema": "asteria.rpg.quest",
            "version": 1,
            "quest_id": self.quest_id,
            "display_name": self.display_name,
            "description": self.description,
            "objectives": [x.to_data() for x in self.objectives],
            "prerequisites": list(self.prerequisites),
            "reward": self.reward.to_data(),
            "next_quest_ids": list(self.next_quest_ids),
            "auto_complete": self.auto_complete,
            **({"icon_id": self.icon_id} if self.icon_id else {}),
            **{k: getattr(self, k) for k in CARD_FIELDS if getattr(self, k)},
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.quest" or data.get("version") != 1:
            raise ValueError("unsupported quest")
        return cls(
            data["quest_id"],
            data["display_name"],
            description=data["description"],
            objectives=[QuestObjective.from_data(x) for x in data["objectives"]],
            prerequisites=data["prerequisites"],
            reward=RewardDefinition.from_data(data["reward"]),
            next_quest_ids=data["next_quest_ids"],
            auto_complete=data["auto_complete"],
            icon_id=data.get("icon_id", ""),
            **{k: data[k] for k in CARD_FIELDS if k in data},
        )


@dataclass(slots=True)
class QuestProgress:
    status: str = "active"
    counts: dict = None

    def __post_init__(self):
        if self.status not in QUEST_STATUSES:
            raise ValueError(f"unknown quest status: {self.status}")
        self.counts = {str(k): int(v) for k, v in dict(self.counts or {}).items()}

    def to_data(self):
        return {"status": self.status, "counts": dict(sorted(self.counts.items()))}

    @classmethod
    def from_data(cls, data):
        return cls(data["status"], data["counts"])


class QuestLog:
    """Tracks quest progress in a save and pays rewards on completion.

    ``progress`` is the caller-owned ``{quest_id: QuestProgress}`` mapping kept
    in the save. ``inventory`` and ``switches`` (a callable ``switch_id ->
    bool``) let item and switch objectives be evaluated; ``grant_reward`` is
    called with a quest's :class:`RewardDefinition` when it completes.
    """

    def __init__(self, quests, progress, *, inventory=None, switches=None, grant_reward=None):
        self.quests = quests
        self.progress = progress
        self.inventory = inventory
        self.switches = switches or (lambda switch_id: False)
        self.grant_reward = grant_reward or (lambda reward: None)
        self.completed_log = []

    def _definition(self, quest_id):
        try:
            return self.quests[str(quest_id)]
        except KeyError:
            raise QuestError(f"unknown quest: {quest_id}") from None

    def status(self, quest_id):
        progress = self.progress.get(str(quest_id))
        return "inactive" if progress is None else progress.status

    def can_start(self, quest_id):
        quest = self._definition(quest_id)
        return self.status(quest.quest_id) == "inactive" and all(
            self.status(x) == "completed" for x in quest.prerequisites
        )

    def start(self, quest_id):
        quest = self._definition(quest_id)
        if not self.can_start(quest.quest_id):
            raise QuestError(f"quest {quest.quest_id} cannot start")
        self.progress[quest.quest_id] = QuestProgress("active", {})
        self.refresh()
        return self.status(quest.quest_id)

    def objective_value(self, quest_id, objective):
        if objective.kind == "item":
            return 0 if self.inventory is None else self.inventory.count(objective.target)
        if objective.kind == "switch":
            return 1 if self.switches(objective.target) else 0
        return self.progress[quest_id].counts.get(objective.objective_id, 0)

    def objective_done(self, quest_id, objective):
        return self.objective_value(quest_id, objective) >= (
            1 if objective.kind == "switch" else objective.required
        )

    def is_ready(self, quest_id):
        quest = self._definition(quest_id)
        return self.status(quest.quest_id) == "active" and all(
            self.objective_done(quest.quest_id, x) for x in quest.objectives
        )

    def advance(self, quest_id, objective_id, amount=1):
        quest = self._definition(quest_id)
        if self.status(quest.quest_id) != "active":
            raise QuestError(f"quest {quest.quest_id} is not active")
        objective = next((x for x in quest.objectives if x.objective_id == objective_id), None)
        if objective is None or objective.kind != "counter":
            raise QuestError(f"{quest.quest_id} has no counter objective {objective_id}")
        counts = self.progress[quest.quest_id].counts
        counts[objective.objective_id] = min(
            objective.required, counts.get(objective.objective_id, 0) + int(amount)
        )
        self.refresh()
        return counts[objective.objective_id]

    def record_defeat(self, enemy_id, amount=1):
        """Count a defeated enemy toward every active ``defeat_enemy`` objective that names it."""
        for quest_id, progress in list(self.progress.items()):
            if progress.status != "active":
                continue
            for objective in self._definition(quest_id).objectives:
                if objective.kind == "defeat_enemy" and objective.target == enemy_id:
                    progress.counts[objective.objective_id] = min(
                        objective.required,
                        progress.counts.get(objective.objective_id, 0) + int(amount),
                    )
        self.refresh()

    def complete(self, quest_id):
        reward = self._complete(quest_id)
        self.refresh()
        return reward

    def _complete(self, quest_id):
        quest = self._definition(quest_id)
        if not self.is_ready(quest.quest_id):
            raise QuestError(f"quest {quest.quest_id} objectives are not met")
        self.grant_reward(quest.reward)
        self.progress[quest.quest_id].status = "completed"
        self.completed_log.append(quest.quest_id)
        for next_id in quest.next_quest_ids:
            if self.can_start(next_id):
                self.progress[next_id] = QuestProgress("active", {})
        return quest.reward

    def fail(self, quest_id):
        quest = self._definition(quest_id)
        if self.status(quest.quest_id) != "active":
            raise QuestError(f"quest {quest.quest_id} is not active")
        self.progress[quest.quest_id].status = "failed"

    def refresh(self):
        """Complete every ready ``auto_complete`` quest (and quests their chains start)."""
        changed = True
        while changed:
            changed = False
            for quest_id in sorted(self.progress):
                quest = self._definition(quest_id)
                if quest.auto_complete and self.is_ready(quest_id):
                    self._complete(quest_id)
                    changed = True
                    break

    def active(self):
        return tuple(k for k in sorted(self.progress) if self.progress[k].status == "active")
