"""Versioned project-owned presets for common multiplayer reward policies."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

RULE_SCHEMA = "asteria.multiplayer.rules"
RULE_VERSION = 1


def default_rules() -> dict[str, Any]:
    """Return the game-agnostic starting template with the user's Boss demo defaults."""
    return {
        "schema": RULE_SCHEMA,
        "version": RULE_VERSION,
        "rewards": {
            "boss": {
                "eligibility": "positive_damage",
                "experience": {
                    "policy": "full_amount_per_eligible_player",
                    "amount": 100,
                },
                "drops": {
                    "assignment": "random_eligible_player",
                    "items": ["ancient_shard"],
                },
            }
        },
        "world_pickup": {"policy": "first_valid_claim"},
    }


def validate_rules(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate built-in fields while retaining adapter-specific extension sections."""
    if not isinstance(value, Mapping):
        raise ValueError("multiplayer rules must be a JSON object")
    try:
        rules = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"multiplayer rules must be strict JSON: {exc}") from exc
    if rules.get("schema") != RULE_SCHEMA or rules.get("version") != RULE_VERSION:
        raise ValueError("unsupported multiplayer rules schema or version")
    rewards = rules.get("rewards")
    boss = rewards.get("boss") if isinstance(rewards, dict) else None
    if not isinstance(boss, dict):
        raise ValueError("rewards.boss must be an object")
    eligibility = boss.get("eligibility")
    if not isinstance(eligibility, str) or eligibility not in {
        "positive_damage",
        "any_session_participant",
    }:
        raise ValueError("boss eligibility policy is unsupported")
    experience = boss.get("experience")
    if not isinstance(experience, dict):
        raise ValueError("boss experience must be an object")
    if experience.get("policy") != "full_amount_per_eligible_player":
        raise ValueError("boss experience policy is unsupported")
    amount = experience.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ValueError("boss experience amount must be a non-negative integer")
    drops = boss.get("drops")
    if not isinstance(drops, dict):
        raise ValueError("boss drops must be an object")
    assignment = drops.get("assignment")
    if not isinstance(assignment, str) or assignment not in {
        "random_eligible_player",
        "highest_damage_player",
        "every_eligible_player",
    }:
        raise ValueError("boss drop assignment is unsupported")
    items = drops.get("items")
    if not isinstance(items, list) or any(
        not isinstance(item, str) or not item.strip() or len(item) > 160 for item in items
    ):
        raise ValueError("boss drop items must be a list of non-empty item IDs")
    pickup = rules.get("world_pickup")
    policy = pickup.get("policy") if isinstance(pickup, dict) else None
    if not isinstance(policy, str) or policy not in {
        "first_valid_claim",
        "owner_only",
        "personal",
        "round_robin",
        "random_eligible_player",
    }:
        raise ValueError("world pickup policy is unsupported")
    return rules


def load_rules(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return default_rules()
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON value: {constant}")
            ),
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"could not read multiplayer rules JSON: {exc}") from exc
    return validate_rules(value)


def save_rules(path: str | Path, value: Mapping[str, Any]) -> None:
    path = Path(path)
    rules = validate_rules(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(rules, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise
