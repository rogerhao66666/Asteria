"""Checks for the plain values records are built from: one copy instead of one per module."""

from __future__ import annotations

from math import isfinite


def required_id(value, label):
    """``value`` as a stripped string; ``label is required`` when it is empty."""
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def finite(value, label):
    """``value`` as a float; ``label must be finite`` for infinity and NaN."""
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def clean_text(value):
    """``value`` as a stripped string, ``""`` for None."""
    return str(value or "").strip()


def positive(value, label):
    """``value`` as a float; ``label must be finite and > 0`` otherwise."""
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and > 0")
    return value


def non_negative(value, label):
    """``value`` as a float; ``label must be finite and >= 0`` otherwise."""
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and >= 0")
    return value


def word_list(values):
    """Words in their first order without repeats or blanks; a string is split at commas."""
    if isinstance(values, str):
        values = values.split(",")
    return tuple(dict.fromkeys(t for t in (clean_text(v) for v in values or ()) if t))


def lower_id_set(values, label="tag"):
    """Required ids in lower case, sorted and without repeats."""
    return tuple(sorted({required_id(x, label).lower() for x in values}))
