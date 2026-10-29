"""The standalone app's helpers (AST-06): python-style command lines, the bundled game, a
writable game folder, and exports that carry the frozen player."""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

import pytest

from asteria import frozen
from asteria.project_tools import build_player_game, package_game

REF = Path(__file__).resolve().parents[1] / "reference_projects" / "party_rpg_demo"


def test_python_style_command_lines_run_modules_and_code(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    out = tmp_path / "out.txt"
    code = f"import sys; open({str(out)!r}, 'w').write(' '.join(sys.argv[1:]))"
    assert frozen.run_python_style(["-I", "-c", code, "a", "b"]) == 0
    assert out.read_text() == "a b"
    with pytest.raises(SystemExit) as exit_info:
        frozen.run_python_style(["-m", "asteria.runtime.preview", "--help"])
    assert exit_info.value.code == 0
    assert sys.argv[0] == "asteria.runtime.preview"  # as python -m sets it
    assert frozen.run_python_style(["project.asteria.json"]) is None
    assert frozen.run_python_style(["-m"]) is None


def test_source_checkout_is_not_frozen_and_has_no_bundled_player(monkeypatch):
    monkeypatch.delenv("ASTERIA_PLAYER", raising=False)
    assert not frozen.is_frozen() and frozen.engine_root() is None
    assert frozen.player_runtime() is None


def test_player_runtime_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTERIA_PLAYER", str(tmp_path / "missing"))
    assert frozen.player_runtime() is None
    monkeypatch.setenv("ASTERIA_PLAYER", str(tmp_path))
    assert frozen.player_runtime() == tmp_path


def test_bundled_game_is_found_beside_the_program(tmp_path):
    app = tmp_path / "Game.app" / "Contents"
    (app / "MacOS").mkdir(parents=True)
    (app / "Resources" / "game").mkdir(parents=True)
    assert frozen.bundled_game(app / "MacOS" / "Game") is None
    (app / "Resources" / "game" / frozen.PROJECT_FILE).write_text("{}")
    assert frozen.bundled_game(app / "MacOS" / "Game") == app / "Resources" / "game"
    folder = tmp_path / "Game"
    (folder / "game").mkdir(parents=True)
    (folder / "game" / frozen.PROJECT_FILE).write_text("{}")
    assert frozen.bundled_game(folder / "Game.exe") == folder / "game"


def test_a_game_inside_an_app_runs_from_a_writable_mirror_with_lasting_saves(tmp_path):
    game = tmp_path / "Quest.app" / "Contents" / "Resources" / "game"
    (game / "art").mkdir(parents=True)
    (game / "engine" / "asteria").mkdir(parents=True)
    (game / frozen.PROJECT_FILE).write_text('{"name": "Quest: Two"}')
    (game / "art" / "hero.png").write_bytes(b"png")
    data = tmp_path / "data"
    root = frozen.writable_game_folder(game, data)
    assert root == data / "Asteria Games" / "Quest_ Two"
    assert (root / "art" / "hero.png").read_bytes() == b"png"
    assert not (root / "engine").exists()  # the engine is imported from the game, not here
    (root / "saves" / "slot1.json").write_text("kept")
    (game / "art" / "boss.png").write_bytes(b"new")  # an updated game
    again = frozen.writable_game_folder(game, data)
    assert again == root and (root / "art" / "boss.png").exists()
    assert (root / "saves" / "slot1.json").read_text() == "kept"
    plain = tmp_path / "plain"
    plain.mkdir()
    assert frozen.writable_game_folder(plain, data) == plain  # a writable folder is used as is


def _fake_player_app(tmp_path):
    app = tmp_path / "AsteriaPlayer.app" / "Contents"
    (app / "MacOS").mkdir(parents=True)
    (app / "Resources").mkdir()
    (app / "MacOS" / "AsteriaPlayer").write_text("#!/bin/sh\n")
    info = {"CFBundleExecutable": "AsteriaPlayer", "CFBundleName": "AsteriaPlayer"}
    (app / "Info.plist").write_bytes(plistlib.dumps(info))
    return app.parent


def test_exports_carry_the_frozen_player_and_need_no_python(tmp_path, monkeypatch):
    monkeypatch.setattr("asteria.project_tools._sign_ad_hoc", lambda app: True)
    player = _fake_player_app(tmp_path)
    assert frozen.player_executable(player) == player / "Contents" / "MacOS" / "AsteriaPlayer"
    result = package_game(
        REF / "project.asteria.json", tmp_path / "out", name="Ref Game", app=True, pyz=False,
        player=player,
    )  # fmt: skip
    app = result["app"]
    assert result["standalone"] and result["pyz"] is None and app.name == "Ref Game.app"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleExecutable"] == "Ref_Game" and info["CFBundleName"] == "Ref Game"
    assert (app / "Contents" / "MacOS" / "Ref_Game").is_file()
    game = app / "Contents" / "Resources" / "game"
    assert (game / frozen.PROJECT_FILE).is_file()
    assert (game / "engine" / "asteria" / "runtime" / "preview.py").is_file()
    assert not (game / "run_game.py").exists()
    assert frozen.bundled_game(app / "Contents" / "MacOS" / "Ref_Game") == game


def test_a_player_folder_becomes_a_game_folder(tmp_path):
    player = tmp_path / "AsteriaPlayer"
    player.mkdir()
    suffix = ".exe" if os.name == "nt" else ""
    (player / f"AsteriaPlayer{suffix}").write_text("binary")
    (player / "_internal").mkdir()
    game_folder = tmp_path / "export"
    (game_folder / "engine").mkdir(parents=True)
    (game_folder / frozen.PROJECT_FILE).write_text("{}")
    (game_folder / "run_game.py").write_text("")
    target = build_player_game(game_folder, tmp_path / "out", name="My Game", player=player)
    assert target == tmp_path / "out" / "My_Game"
    assert (target / f"My_Game{suffix}").read_text() == "binary"
    assert frozen.player_executable(target) == target / f"My_Game{suffix}"  # renamed program
    assert (target / "game" / frozen.PROJECT_FILE).is_file()
    assert not (target / "game" / "run_game.py").exists()


def test_a_game_named_with_a_slash_is_one_bundle_in_the_output_folder(tmp_path, monkeypatch):
    monkeypatch.setattr("asteria.project_tools._sign_ad_hoc", lambda app: True)
    game_folder = tmp_path / "export"
    game_folder.mkdir()
    (game_folder / frozen.PROJECT_FILE).write_text("{}")
    out = tmp_path / "out"
    out.mkdir()
    app = build_player_game(game_folder, out, name="Act 1/2", player=_fake_player_app(tmp_path))
    assert app == out / "Act 1-2.app" and app.is_dir()
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleName"] == "Act 1/2"  # the name players see is kept


def test_python_style_runs_a_script_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    monkeypatch.setattr(sys, "path", list(sys.path))
    script = tmp_path / "check.py"
    script.write_text(f"import sys; open({str(tmp_path / 'r')!r}, 'w').write(sys.argv[1])")
    assert frozen.run_python_style([str(script), "ok"]) == 0
    assert (tmp_path / "r").read_text() == "ok"
