"""The ``--quick`` run leaves out the editor, multiplayer and batch tests."""

import os

import quick_tests


def _module(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_the_quick_run_leaves_out_qt_multiplayer_and_batch_tests(tmp_path):
    left_out = quick_tests.left_out
    assert left_out(_module(tmp_path, "test_editor_x.py", "from PySide6 import QtWidgets\n"))
    assert left_out(_module(tmp_path, "test_form.py", "def test_a(qt_app):\n    pass\n"))
    assert left_out(_module(tmp_path, "test_page.py", "import asteria.editor.pages\n"))
    assert left_out(_module(tmp_path, "test_multiplayer_netsim.py", "def test_a():\n    pass\n"))
    assert left_out(_module(tmp_path, "test_batch67.py", "def test_a():\n    pass\n"))
    # The engine's own tests stay, and so does every file that is not a test module.
    assert not left_out(_module(tmp_path, "test_battle.py", "import asteria.rpg\n"))
    assert not left_out(_module(tmp_path, "helper.py", "from PySide6 import QtCore\n"))


def test_a_quick_run_is_headless_and_silent(monkeypatch):
    for name in quick_tests.QUIET:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SDL_VIDEODRIVER", "cocoa")  # a choice the caller made is kept
    quick_tests.quiet()
    assert os.environ["ASTERIA_MUTE"] == "1"
    assert os.environ["SDL_AUDIODRIVER"] == "dummy"
    assert os.environ["SDL_VIDEODRIVER"] == "cocoa"
