"""How a trained creature foe picks its move: every move starts at 100, the rules an encounter
names move the scores, the best wins and ties go by the dice (as the handheld games' AI does).

The rules are Properties of the encounter:

``move_ai.avoid_useless``
    A move that can do nothing now loses 10: no effect on this target, an ailment it has or is
    immune to, a stat at its limit, healing at full health, the weather it is already.
``move_ai.finish``
    A move that knocks the target out gains 4 (6 with priority); a damaging move that is not the
    strongest loses 1; a move four times as effective gains 2, one time in three.
``move_ai.weigh``
    Situational sense: heal when hurt, do not raise stats when low on health, do not repeat what
    only needs doing once.
"""

from __future__ import annotations

PREFIX = "move_ai."
RULES = ("avoid_useless", "finish", "weigh")
START = 100


def move_rules_of(tags):
    """The rules an encounter's tags name, in the order they run."""
    tags = set(tags or ())
    return tuple(rule for rule in RULES if PREFIX + rule in tags)


def _damage(game, member_id, definition, target_id):
    """What this move would take from the target now, its hit tags on (types count)."""
    tags = game.battle.member(member_id).subject.tags
    added = []
    for hit in getattr(definition, "hits", ()) or ():
        for tag in hit.get("tags", ()):
            if not tags.contains(tag):
                tags.add(tag)
                added.append(tag)
    try:
        preview = game.preview(member_id, definition.ability_id, (target_id,))
    finally:
        for tag in added:
            tags.remove(tag)
    resource = game.rules.knockout_resource_id
    changes = dict(preview.resource_deltas or {}).get(target_id, {})
    return max(0.0, -float(dict(changes).get(resource, 0.0)))


def _operations(definition, mode):
    for entry in getattr(definition, "effects", ()) or ():
        if entry.mode.value == mode:
            yield from entry.effect.operations


def _deals_damage(definition):
    return any("fixed_damage" in hit.get("tags", ()) for hit in definition.hits or ()) or (
        "status" not in definition.tags and any(_operations(definition, "selected"))
    )


def _at_limit(subject, operation, up):
    """A stat counter that cannot move further this way."""
    pool = subject.resources
    if not pool.contains(operation.target):
        return False
    value = pool.to_data()["values"][operation.target]
    return value["current"] >= value["maximum"] if up else value["current"] <= value["minimum"]


def _state_is_useless(game, state_id, source_id, target_id):
    battle = game.battle
    subject = battle.member(target_id).subject
    policy = battle.battle_states.policies.get(state_id)
    states = subject.states
    if states is None or states.get(state_id) is not None:
        return True
    if policy is None:
        return False
    if any(subject.tags.contains(tag) for tag in policy.immune_target_tags):
        return True
    group = policy.exclusive_group
    return bool(group) and any(
        getattr(battle.battle_states.policies.get(a.state_id), "exclusive_group", "") == group
        for a in states.active_states()
    )


def _sign(operation):
    """Which way a stat counter's constant amount moves it."""
    terms = operation.value.to_data().get("terms") or ()
    return float(terms[0].get("coefficient", 0.0)) if terms else 0.0


def _useless(game, member_id, definition, target_id, damage):
    battle = game.battle
    user = battle.member(member_id).subject
    target = battle.member(target_id).subject
    if "effect.none" in definition.tags:
        return True
    if _deals_damage(definition):
        return damage <= 0
    for entry in definition.apply_states or ():
        if entry.get("remove"):
            continue
        aimed = member_id if entry.get("to") == "self" else target_id
        if _state_is_useless(game, entry["state"], member_id, aimed):
            return True
    weather = game.battle_weather()
    for command in definition.commands or ():
        if command.get("command") == "SET_BATTLE_WEATHER" and weather is not None:
            if weather[0] == command["args"].get("kind"):
                return True
    moved = False
    for mode, subject in (("selected", target), ("self", user)):
        for operation in _operations(definition, mode):
            if not operation.target.startswith("stage_"):
                continue
            moved = True
            if not _at_limit(subject, operation, _sign(operation) > 0):
                return False
    return moved


def _health_share(subject, resource):
    top = subject.resources.maximum(resource)
    return subject.resources.current(resource) / top if top else 0.0


def _heals(definition, resource):
    return "status" in definition.tags and any(
        operation.target == resource for operation in _operations(definition, "self")
    )


def _raises_stats(definition):
    return any(
        operation.target.startswith("stage_") for operation in _operations(definition, "self")
    )


def _strength(game, member_id, definition, target_id, damage, rule, best, dice):
    target = game.battle.member(target_id).subject
    resource = game.rules.knockout_resource_id
    if rule == "avoid_useless":
        return -10 if _useless(game, member_id, definition, target_id, damage) else 0
    user = game.battle.member(member_id).subject
    if rule == "finish":
        if damage <= 0:
            return 0
        if damage >= target.resources.current(resource):
            return 6 if getattr(definition, "priority", 0) > 0 else 4
        return -1 if damage < best else 0
    share = _health_share(user, resource)
    if _heals(definition, resource):
        return -3 if share >= 1.0 else 2 if share <= 0.4 else 0
    if _raises_stats(definition):
        return -2 if share < 0.7 else 0
    if definition.apply_states and share < 0.3:
        return -1
    return 0


def score_moves(game, member_id, usable, target_id, rules):
    """``{ability id: score}`` of ``usable`` against ``target_id``."""
    registry = game.battle.ability_runtime.registry
    scores = {}
    damage = {}
    for ability_id in usable:
        scores[ability_id] = START
        definition = registry.get(ability_id)
        relation_self = "status" in definition.tags
        damage[ability_id] = (
            0.0 if relation_self else _damage(game, member_id, definition, target_id)
        )
    best = max(damage.values(), default=0.0)
    dice = game.battle.rng
    for rule in rules:
        for ability_id in usable:
            scores[ability_id] += _strength(
                game, member_id, registry.get(ability_id), target_id, damage[ability_id], rule,
                best, dice,
            )  # fmt: skip
    return scores


def choose_move(game, member_id, usable, target_id, rules):
    """The move with the best score (ties by the battle's dice)."""
    usable = tuple(usable)
    if target_id is None or not usable:
        return game.battle.rng.choice(usable) if usable else None
    scores = score_moves(game, member_id, usable, target_id, rules)
    top = max(scores.values())
    return game.battle.rng.choice([a for a in usable if scores[a] == top])


__all__ = ["RULES", "choose_move", "move_rules_of", "score_moves"]
