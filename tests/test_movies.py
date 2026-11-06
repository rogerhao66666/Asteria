"""D83: a movie is a zip of PNG frames shown as a picture; SET_VARIABLE can pick at random."""

import io
import os
import zipfile

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from asteria.runtime.movies import Movie, is_movie  # noqa: E402


@pytest.fixture()
def movie_file(tmp_path):
    pygame.init()
    pygame.display.set_mode((8, 8))
    path = tmp_path / "clip.ZIP"
    with zipfile.ZipFile(path, "w") as archive:
        for number, colour in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255))):
            frame = pygame.Surface((2, 2))
            frame.fill(colour)
            data = io.BytesIO()
            pygame.image.save(frame, data, "frame.png")
            archive.writestr(f"{number:04d}.png", data.getvalue())
        archive.writestr("cues.json", "{}")
    yield path
    pygame.quit()


def test_is_movie_by_the_file_name():
    assert is_movie("a/b.zip") and is_movie("B.ZIP")
    assert not is_movie("a/b.png")


def test_only_the_png_files_are_frames(movie_file):
    assert len(Movie(pygame, movie_file)) == 3


def test_frames_are_read_in_name_order(movie_file):
    movie = Movie(pygame, movie_file)
    assert movie.image(0).get_at((0, 0))[:3] == (255, 0, 0)
    assert movie.image(2).get_at((1, 1))[:3] == (0, 0, 255)


def test_a_movie_stops_on_its_last_frame_unless_it_loops(movie_file):
    movie = Movie(pygame, movie_file)
    assert movie.frame_at(0.0, 60) == 0
    assert movie.frame_at(1 / 60, 60) == 1
    assert movie.frame_at(10.0, 60) == 2
    assert movie.frame_at(4 / 60, 60, loop=True) == 1


def test_rate_zero_is_a_still_of_the_first_frame_given(movie_file):
    assert Movie(pygame, movie_file).frame_at(5.0, 0, first=1) == 1


def test_a_zip_without_frames_is_refused(tmp_path):
    path = tmp_path / "empty.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("notes.txt", "x")
    with pytest.raises(ValueError):
        Movie(pygame, path)


def test_set_variable_random_stays_under_the_number():
    from asteria.events import EventContext, EventInstruction, EventProgram, EventVM

    seen = set()
    for _ in range(60):
        context = EventContext()
        program = EventProgram([EventInstruction("SET_VARIABLE", {"name": "n", "random": 3})])
        EventVM(program, context=context).run_until_blocked()
        seen.add(context.get_variable("n"))
    assert seen == {0, 1, 2}


def _runner(*rows):
    from asteria.events import (
        EventInstruction,
        EventProgram,
        EventProgramRegistry,
        EventRunner,
    )

    registry = EventProgramRegistry()
    registry.register("it", EventProgram([EventInstruction(op, args) for op, args in rows]))
    runner = EventRunner(registry)
    runner.start("it")
    return runner


def test_a_held_line_stays_until_a_line_without_words():
    runner = _runner(
        ("DIALOGUE", {"text": "Hello", "wait": False}),
        ("WAIT", {"seconds": 1.0}),
        ("DIALOGUE", {"text": "", "wait": False}),
    )
    runner.update(0.0)
    assert runner.dialogue.held.line.text == "Hello"
    runner.update(2.0)
    assert runner.dialogue.held is None


@pytest.mark.parametrize("over", ["world", "message_window", "everything"])
def test_a_fade_says_what_it_covers(over):
    from types import SimpleNamespace

    from asteria.runtime.field_presentation import FieldEffects

    effects = FieldEffects.__new__(FieldEffects)
    effects.fade_alpha = 0.0
    command = SimpleNamespace(name="SCREEN_FADE", args={"to": 1, "duration": 0, "over": over})
    effects.handle(command, None, None)
    assert (effects.fade_alpha, effects.fade_over) == (1.0, over)


def test_a_fade_covers_the_world_unless_told():
    from types import SimpleNamespace

    from asteria.runtime.field_presentation import FieldEffects

    effects = FieldEffects.__new__(FieldEffects)
    effects.fade_alpha = 0.0
    effects.handle(SimpleNamespace(name="SCREEN_FADE", args={"to": 1}), None, None)
    assert effects.fade_over == "world"
