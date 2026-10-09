"""Shared pytest configuration."""

from pathlib import Path

import pytest

from asteria.assets.local_reference import resolve_rpg_maker_mv_root

_REPO = Path(__file__).resolve().parents[1]
_MV_REFERENCE_AVAILABLE = resolve_rpg_maker_mv_root(_REPO) is not None


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "mv_reference: needs the git-ignored local RPG Maker MV reference "
        "(local_reference/rpg_maker_mv); skipped when it is absent",
    )


def pytest_collection_modifyitems(config, items):
    if _MV_REFERENCE_AVAILABLE:
        return
    skip = pytest.mark.skip(reason="local RPG Maker MV reference unavailable")
    for item in items:
        if item.get_closest_marker("mv_reference") is not None:
            item.add_marker(skip)
