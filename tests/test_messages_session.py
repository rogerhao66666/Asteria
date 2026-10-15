"""Message codes, translation, the message log, the music room and credits in a session."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.events.dialogue import DialogueLine
from asteria.project import Project
from asteria.rpg.extras import CreditsPage, MusicTrack
from asteria.rpg.localization import LocaleTable, Localizer, MessageSettings
from asteria.runtime.backlog import MessageBacklog
from asteria.runtime.game_session import GameSessionError, GameSessionRuntime

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"


def _session(**database):
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    for add, value in database.items():
        for item in value if isinstance(value, list) else [value]:
            getattr(project.rpg_database, add)(item)
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def _settings(**extra):
    return MessageSettings(
        "msg", macros={"hello": r"Hail, \N[hero_01]!"}, currency_label="leaves", **extra
    )


def test_localizer_falls_back_from_region_to_language_to_default():
    tables = (
        LocaleTable("en", {"hi": "Hello", "bye": "Bye", "n": "{who} left"}),
        LocaleTable("fr", {"hi": "Bonjour"}),
        LocaleTable("fr-CA", {"hi": "Allo"}),
    )
    loc = Localizer(tables, default_locale="en", locale="fr-CA")
    assert loc.tr("hi") == "Allo"
    loc.locale = "fr"
    assert loc.tr("hi") == "Bonjour" and loc.tr("bye") == "Bye"  # missing in fr: default
    assert loc.tr("missing") == "missing" and loc.tr("missing", "dflt") == "dflt"
    assert loc.tr("n", who="Ann") == "Ann left" and loc.tr("n", nope=1) == "{who} left"
    assert loc.locales() == ("en", "fr", "fr-CA")


def test_session_expands_codes_from_its_own_state():
    game = _session(add_message_settings=_settings())
    game.save.event_context.set_variable("kills", 12)
    hero = game.project.rpg_database.actors["hero_01"].display_name
    text = game.expand_message(r"\M[hello] \V[kills] \G \$")
    gold = game.save.rpg_state.currencies["gold"]
    assert text == f"Hail, {hero}! 12 leaves {gold:g}"
    assert game.expand_message(r"\C[2]Hi\C[0] \P[1]", plain=True) == f"Hi {hero}"


def test_translation_follows_the_players_locale_and_is_saved():
    tables = [LocaleTable("en", {"greet": "Hello"}), LocaleTable("zh-TW", {"greet": "你好"})]
    game = _session(add_locale_table=tables, add_message_settings=_settings(default_locale="en"))
    assert game.tr("greet") == "Hello" and game.expand_message(r"\T[greet]") == "Hello"
    game.set_locale("zh-TW")
    assert game.tr("greet") == "你好" and game.expand_message(r"\T[greet]") == "你好"
    other = GameSessionRuntime(game.project, game.save)  # a reloaded session
    assert other.tr("greet") == "你好"
    with pytest.raises(GameSessionError):
        game.set_locale("xx")


def test_backlog_keeps_the_newest_lines_up_to_its_limit():
    game = _session(add_message_settings=_settings(backlog_limit=3))
    backlog = game.backlog
    assert backlog.limit == 3 and len(backlog) == 0
    for number in range(5):
        backlog.add("Ann", f"line {number}")
    assert [e.text for e in backlog.entries()] == ["line 2", "line 3", "line 4"]
    assert not backlog.add("Ann", "line 4")  # a repeat in a row collapses
    backlog.clear()
    assert len(backlog) == 0 and not MessageBacklog(0).add("a", "b")


def test_dialogue_lines_reach_the_backlog_through_pending_dialogue():
    game = _session(add_message_settings=_settings(backlog_limit=10))
    from types import SimpleNamespace

    line = DialogueLine(r"\C[3]Greetings\C[0], \N[hero_01]", speaker=r"\N[hero_01]")
    request = SimpleNamespace(line=line)
    runner = SimpleNamespace(dialogue=SimpleNamespace(dialogue=request, choice=None))
    game._dialogue_runner = lambda: runner
    assert game.pending_dialogue is request and game.pending_dialogue is request
    hero = game.project.rpg_database.actors["hero_01"].display_name
    assert game.backlog.entries() == (
        game.backlog.entries()[0].__class__(hero, f"Greetings, {hero}"),
    )


def test_music_heard_unlocks_tracks_by_asset():
    track = MusicTrack("theme", "Main Theme", "bgm_main", unlock_switch="music.unlock.theme")
    game = _session(add_music_track=track)
    game.note_music_heard("other")
    assert not game.save.event_context.get_switch("music.heard.theme")
    game.note_music_heard("bgm_main")
    assert game.save.event_context.get_switch("music.heard.theme")


def _runtime(monkeypatch, **database):
    pytest.importorskip("pygame")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    for add, value in database.items():
        for item in value if isinstance(value, list) else [value]:
            getattr(project.rpg_database, add)(item)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    return runtime


def test_pause_menu_lists_the_extras_only_when_the_project_has_them(monkeypatch):
    plain = _runtime(monkeypatch)
    try:
        assert not {"backlog", "music", "credits"} & {o[0] for o in plain._pause_menu.options}
    finally:
        plain.close()
    full = _runtime(
        monkeypatch,
        add_message_settings=_settings(backlog_limit=20),
        add_music_track=MusicTrack("t", "Theme", "bgm"),
        add_credits_page=CreditsPage("c", "Credits", ("A", "B")),
    )
    try:
        names = [o[0] for o in full._pause_menu.options]
        assert names.index("backlog") < names.index("music") < names.index("credits")
        assert names.index("credits") < names.index("settings")
    finally:
        full.close()


def test_extra_screens_draw_and_close(monkeypatch):
    from asteria.runtime import extras_screens

    runtime = _runtime(
        monkeypatch,
        add_message_settings=_settings(backlog_limit=20),
        add_music_track=[
            MusicTrack("a", "Open Track", "bgm_a"),
            MusicTrack("b", "Locked Track", "bgm_b", unlock_switch="never"),
        ],
        add_credits_page=[
            CreditsPage("1", "Team", ("Ann", "Bob")),
            CreditsPage("2", "Art", ("Cy",)),
        ],
    )
    try:
        runtime.game.backlog.add("Ann", "Hello there")
        for screen_class in (
            extras_screens.BacklogScreen,
            extras_screens.MusicRoomScreen,
            extras_screens.CreditsScreen,
        ):
            screen = screen_class(runtime)
            runtime.screen.fill((0, 0, 0))
            screen.draw()
            assert runtime.pg.image.tobytes(runtime.screen, "RGB").count(b"\xff") > 0
        music = extras_screens.MusicRoomScreen(runtime)
        flags = {t.track_id: music.unlocked(t) for t, _ in music.tracks()}
        assert flags == {"a": True, "b": False}
        runtime.game.save.event_context.set_switch("music.heard.b", True)
        assert music.unlocked(runtime.project.rpg_database.music_tracks["b"])
        credits = extras_screens.CreditsScreen(runtime)
        assert [p.page_id for p in credits.pages()] == ["1", "2"]
    finally:
        runtime.close()


def test_a_message_with_codes_draws_coloured_text(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        runtime.screen.fill((0, 0, 0))
        runtime._draw_message(r"\C[2]RED\C[0] plain\nsecond", 20, 20)
        pixels = runtime.pg.image.tobytes(runtime.screen, "RGB")
        assert bytes((255, 120, 76)) in pixels  # the red span's colour
        assert pixels.count(bytes((255, 255, 255))) > 0
    finally:
        runtime.close()


def test_message_icons_map_numbers_to_project_icons_and_round_trip():
    settings = MessageSettings("msg", icons={"12": "icon_potion"})
    assert MessageSettings.from_data(settings.to_data()) == settings
    game = _session(add_message_settings=settings)
    assert game.message_icon(12) == "icon_potion" and game.message_icon(99) == ""
    assert _session().message_icon(12) == ""
    assert "icons" not in MessageSettings("plain").to_data()  # old projects stay unchanged
