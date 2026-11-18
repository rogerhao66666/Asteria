"""The ``--quick`` test run: the fast core of the suite, headless and silent.

``python -m pytest --quick`` leaves out three groups that make up most of the
suite's time and need more than the engine itself:

- the Qt editor tests (any test module that uses Qt or the editor);
- the multiplayer network simulations (``test_multiplayer*``);
- the large batch stress tests (``test_batch*``).

What is left (about 2,100 tests, under a minute) is what an automated check
runs after every change. A quick run sets ``ASTERIA_MUTE=1`` and the SDL dummy
drivers, so it opens no window and plays no sound. The full suite is still
``python -m pytest``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

SKIPPED_NAMES = ("test_multiplayer", "test_batch")
_USES_QT = re.compile(r"PySide6|QApplication|qt_app|qtbot|asteria\.editor")
QUIET = {"ASTERIA_MUTE": "1", "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}


def left_out(path: Path) -> bool:
    """Whether a quick run leaves the test module at ``path`` out."""
    if path.suffix != ".py" or not path.name.startswith("test_"):
        return False
    if path.name.startswith(SKIPPED_NAMES):
        return True
    return _USES_QT.search(path.read_text(encoding="utf-8")) is not None


def quiet():
    """Headless and silent, unless the caller already chose otherwise."""
    for name, value in QUIET.items():
        os.environ.setdefault(name, value)
