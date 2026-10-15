"""State deltas: exact round trips, small patches for small changes, and bad patches."""

from __future__ import annotations

import copy
import json
import random

import pytest

from asteria.multiplayer.delta import DeltaError, apply, diff


def _round_trip(old, new):
    patch = diff(old, new)
    snapshot = copy.deepcopy(old)
    assert apply(old, patch) == new
    assert old == snapshot  # the input is never touched
    return patch


def test_equal_states_need_no_patch():
    assert diff({"a": [1, {"b": 2}]}, {"a": [1, {"b": 2}]}) is None
    assert apply({"a": 1}, None) == {"a": 1}


def test_a_changed_leaf_is_a_tiny_patch():
    state = {"tick": 5, "boss": {"hp": 200, "x": 1.5, "name": "x" * 50}, "log": ["a"] * 30}
    new = {**state, "tick": 6, "boss": {**state["boss"], "hp": 190}}
    patch = _round_trip(state, new)
    assert patch == {"tick": {"$set": 6}, "boss": {"hp": {"$set": 190}}}
    assert len(json.dumps(patch)) < len(json.dumps(new)) / 4


def test_added_removed_and_retyped_keys():
    pad = {"padding": ["unchanged"] * 40}  # big enough that a patch beats resending everything
    old = {**pad, "a": 1, "b": {"c": 2}, "gone": True}
    new = {**pad, "a": "one", "b": {"c": 2, "d": [1]}, "fresh": None}
    patch = _round_trip(old, new)
    assert patch["$del"] == ["gone"] and "padding" not in patch
    assert patch["fresh"] == {"$set": None}


def test_a_list_that_only_grew_sends_the_new_tail():
    old = {"log": ["a", "b", "c"]}
    patch = _round_trip(old, {"log": ["a", "b", "c", "d"]})
    assert patch == {"log": {"$append": ["d"]}}


def test_lists_of_objects_with_ids_are_patched_per_object():
    old = {
        "players": [
            {"player_id": "p1", "x": 1, "hp": 100, "bag": ["a"] * 20},
            {"player_id": "p2", "x": 5, "hp": 100, "bag": ["a"] * 20},
        ]
    }
    new = {
        "players": [
            {"player_id": "p1", "x": 2, "hp": 100, "bag": ["a"] * 20},
            {"player_id": "p2", "x": 5, "hp": 90, "bag": ["a"] * 20},
        ]
    }
    patch = _round_trip(old, new)
    keyed = patch["players"]["$keyed"]
    assert keyed["key"] == "player_id" and set(keyed["changes"]) == {"p1", "p2"}
    assert keyed["changes"]["p1"] == {"x": {"$set": 2}}


def test_players_joining_leaving_and_reordering():
    one = {"players": [{"player_id": "a", "x": 1}, {"player_id": "b", "x": 2}]}
    joined = {"players": [*one["players"], {"player_id": "c", "x": 3}]}
    left = {"players": [{"player_id": "b", "x": 2}]}
    swapped = {"players": [{"player_id": "b", "x": 2}, {"player_id": "a", "x": 1}]}
    for new in (joined, left, swapped):
        _round_trip(one, new)


def test_a_patch_is_never_bigger_than_just_sending_the_new_value():
    old, new = {"a": 1}, {"a": [1, 2, 3], "b": {"deep": {"er": 1}}}
    patch = _round_trip(old, new)
    assert len(json.dumps(patch)) <= len(json.dumps({"$set": new}))
    assert _round_trip([1, 2], {"x": 1}) == {"$set": {"x": 1}}


def test_random_states_always_round_trip():
    rng = random.Random(42)

    def value(depth=0):
        kind = rng.randrange(6 if depth < 3 else 3)
        if kind == 0:
            return rng.randrange(100)
        if kind == 1:
            return rng.choice(["a", "b", None, True, 1.5])
        if kind == 2:
            return rng.choice([[], {}, ""])
        if kind == 3:
            return {rng.choice("abcde"): value(depth + 1) for _ in range(rng.randrange(4))}
        if kind == 4:
            return [value(depth + 1) for _ in range(rng.randrange(4))]
        ids = rng.sample(range(6), rng.randrange(4))
        return [{"id": i, "v": rng.randrange(3)} for i in ids]

    for _ in range(400):
        old = {"s": value()}
        new = copy.deepcopy(old) if rng.random() < 0.3 else {"s": value()}
        if rng.random() < 0.5 and isinstance(old["s"], dict):
            new["s"] = {**old["s"], rng.choice("abcde"): value()}
        _round_trip(old, new)


def test_a_patch_that_does_not_fit_is_refused():
    with pytest.raises(DeltaError):
        apply({"a": 1}, {"missing": {"x": {"$set": 1}}})
    with pytest.raises(DeltaError):
        apply({"a": 1}, {"$append": [1]})
    with pytest.raises(DeltaError):
        apply([1], {"a": {"$set": 1}})
    with pytest.raises(DeltaError):
        apply([{"id": 1}], {"$keyed": {"key": "id", "order": [9], "changes": {}}})
    with pytest.raises(DeltaError):
        apply({}, "not a patch")
