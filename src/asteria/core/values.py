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
