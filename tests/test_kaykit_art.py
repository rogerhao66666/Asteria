"""The KayKit art build: Blender's frames become smooth battle and walking sheets, with the
metadata the battle reads (frame grid, feet pivot, clips, ``scaling: smooth``), and the demo
reads them back without Blender."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def art(tmp_path, monkeypatch):
    module = _load("build_kaykit_art", REPO / "scripts" / "build_kaykit_art.py")
    monkeypatch.setattr(module, "RAW", tmp_path / "raw")
    monkeypatch.setattr(module, "RENDERED", tmp_path / "rendered")
    return module


def _fake_frames(folder, art, key):
    """A figure 160 px tall in a 384 canvas, its arm reaching further in attack frames."""
    folder.mkdir(parents=True)
    style = art.STYLES[art.CAST[key][2]]
    for clip, (_, count, _) in {**style, **art.FIELD_CLIPS}.items():
        views = ["battle"] if clip in style else [f"field_{f}" for f, _ in art.FIELD_VIEWS]
        for view in views:
            for index in range(count):
                image = Image.new("RGBA", (384, 384), (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.rectangle((150, 120, 230, 280), fill=(200, 60, 60, 255))  # body
                draw.ellipse((160, 60, 220, 125), fill=(240, 200, 160, 255))  # head
                if clip.startswith("attack"):
                    draw.rectangle((60, 180, 150, 200), fill=(180, 180, 200, 255))  # the swing
                image.save(folder / f"{view}_{clip}_{index:02d}.png")


def test_the_job_shoots_battle_clips_from_the_side_and_walks_from_above(art):
    job = art.job("knight")
    assert Path(job["character"]).name == "Knight.glb" and len(job["props"]) == 2
    assert [v["name"] for v in job["views"]] == [
        "battle",
        "field_down",
        "field_left",
        "field_right",
        "field_up",
    ]
    assert set(job["views"][0]["clips"]) == set(art.STYLES["sword_shield"])
    assert (
        job["views"][1]["clips"] == ["walk"]
        and job["views"][1]["pitch"] > job["views"][0]["pitch"]
    )
    assert all(Path(p).is_file() for p in job["animations"])
    assert Path(job["character"]).is_file()


def test_frames_become_a_smooth_grid_sheet_and_a_walking_sheet(art):
    _fake_frames(art.RAW / "knight", art, "knight")
    art.build("knight")
    meta = json.loads((art.RENDERED / "knight_battle.json").read_text())
    sheet = Image.open(art.RENDERED / "knight_battle.png")
    width, height = meta["frame_size"]
    count = sum(frames for _, frames, _ in art.STYLES["sword_shield"].values())
    assert sheet.size == (width * 10, height * -(-count // 10))  # ten frames a row
    assert meta["scaling"] == "smooth" and meta["scale"] == pytest.approx(1 / 3)
    body = sheet.crop((0, 0, width, height)).getchannel("A").getbbox()
    assert body[3] - body[1] == pytest.approx(art.BODY_UNITS * art.VIRTUAL_PIXEL, abs=2)
    assert meta["body_height"] == pytest.approx(body[3] - body[1], abs=2)
    assert meta["pivot"][1] == pytest.approx(body[3] / height, abs=0.01)
    clips = meta["clips"]
    assert clips["idle"]["loop"] and clips["idle"]["frames"] == list(range(8))
    assert clips["attack"]["frames"][-1] == 0 and clips["attack"]["events"] == {"6": ["hit"]}
    assert clips["revive"]["frames"] == clips["ko"]["frames"][::-1]
    assert {"guard", "cast", "hit", "transform", "status", "victory"} <= set(clips)
    field = Image.open(art.RENDERED / "knight_field.png")
    assert field.size == (3 * art.FIELD_CELL, 4 * art.FIELD_CELL)
    field_meta = json.loads((art.RENDERED / "knight_field.json").read_text())
    size = art.FIELD_CELL
    assert field_meta == {
        "frame_size": [size, size],
        "scaling": "smooth",
        "rows": ["down", "left", "right", "up"],
    }
    cell = field.crop((0, 0, size, size)).getchannel("A").getbbox()
    assert cell[3] == size - 2 and cell[3] - cell[1] == pytest.approx(art.FIELD_BODY, abs=1)


def test_the_demo_reads_the_sheets_back_without_blender(art, monkeypatch):
    _fake_frames(art.RAW / "knight", art, "knight")
    art.build("knight")
    demo = REPO / "reference_projects" / "full_verification_demo"
    kaykit = _load("trial_kaykit", demo / "trial_kaykit.py")
    monkeypatch.setattr(kaykit, "RENDERED", art.RENDERED)
    monkeypatch.setenv("ASTERIA_FV_PARTY", "kaykit")
    assert not kaykit.available()  # three of the four are not built
    for key in ("mage", "rogue_hooded", "rogue"):
        for kind in ("battle", "field"):
            for suffix in (".png", ".json"):
                src = art.RENDERED / f"knight_{kind}{suffix}"
                (art.RENDERED / f"{key}_{kind}{suffix}").write_bytes(src.read_bytes())
    assert kaykit.available()
    monkeypatch.delenv("ASTERIA_FV_PARTY")
    assert kaykit.built() and not kaykit.available()  # the Lucifer party unless asked
    image, frame, clips, scale, body = kaykit.battle_sheet("knight")
    assert image.size[0] == frame[0] * 10 and "attack3" in clips and scale == pytest.approx(1 / 3)
    assert body > 100
    out = art.RENDERED.parent / "assets"
    out.mkdir()
    size = art.FIELD_CELL
    assert kaykit.field_sheet(out) == {
        "player_frame_size": [size, size],
        "player_scaling": "smooth",
    }
    assert (out / "player_field_sheet.png").is_file()
    assert "Kay Lousberg" in kaykit.credits_rows()[0]
    # the field look of a party member: the same (sheet, clips) pair trial_maps.character gives
    calls = []

    class Assets:
        def sheet(self, key, image, frames, name, pivot=(0.5, 1.0), scaling=None):
            calls.append(("sheet", key, image.size, len(frames), scaling))
            return f"{key}-sheet"

        def clips(self, key, clips, name):
            calls.append(("clips", key, clips))
            return f"{key}-clips"

    assert kaykit.field_character(Assets(), "look_hero_warrior", "warrior", "Warrior") == (
        "look_hero_warrior-sheet",
        "look_hero_warrior-clips",
    )
    size = art.FIELD_CELL
    assert calls[0] == ("sheet", "look_hero_warrior", (3 * size, 4 * size), 12, "smooth")
    clips = calls[1][2]
    assert clips["idle_down"] == ([1], 0.2, True) and clips["walk_up"][0] == [9, 10, 11, 10]
    assert set(clips) == {
        f"{k}_{f}" for k in ("idle", "walk") for f in ("down", "left", "right", "up")
    }


def test_without_blender_the_message_says_where_to_get_it(art, monkeypatch):
    monkeypatch.delenv("ASTERIA_BLENDER", raising=False)
    monkeypatch.setattr(art.shutil, "which", lambda name: None)
    monkeypatch.setattr(art.Path, "is_file", lambda self: False)
    with pytest.raises(SystemExit, match="blender.org"):
        art.blender_path()
    assert art.main(["--list"]) == 0
    with pytest.raises(SystemExit, match="unknown cast keys"):
        art.main(["--keys", "paladin"])
