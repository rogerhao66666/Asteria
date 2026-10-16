"""Original code-drawn icons: every kind draws, ids map to kinds, projects get working icon_ids."""

import json
import os
from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")

from asteria.graphics.forged_icons import (  # noqa: E402
    ABILITY_RULES,
    DRAWINGS,
    PET_RULES,
    STATE_RULES,
    apply_to_project_file,
    forge,
    kind_for,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _dummy_video(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", os.environ.get("SDL_VIDEODRIVER", "dummy"))


@pytest.mark.parametrize("kind", sorted(DRAWINGS))
def test_every_kind_draws_something_visible(kind):
    image = forge(kind, 32)
    assert image.get_size() == (32, 32)
    opaque = sum(1 for x in range(32) for y in range(32) if image.get_at((x, y)).a > 0)
    assert 60 < opaque < 32 * 32  # a pictogram: not empty, not a filled square


def test_unknown_kinds_are_rejected():
    with pytest.raises(KeyError):
        forge("no_such_icon")


def test_ids_map_to_sensible_kinds():
    assert kind_for("fireball", ABILITY_RULES) == "fire"
    assert kind_for("attack_sword", ABILITY_RULES) == "sword"
    assert kind_for("rain_of_arrows", ABILITY_RULES) == "arrows"
    assert kind_for("life_drain", ABILITY_RULES) == "drain"
    assert kind_for("zzz_unknown_thing", ABILITY_RULES) is None
    assert kind_for("poison", STATE_RULES) == "poison"
    assert kind_for("frost_lynx", PET_RULES) == "pet_lynx"
    assert kind_for("anything", PET_RULES) == "pet_paw"
    assert all(kind in DRAWINGS for _, kind in ABILITY_RULES + STATE_RULES + PET_RULES)


def test_monograms_are_distinct_and_steady():
    from asteria.graphics.forged_icons import forge_monogram

    a, b = forge_monogram("zzz_mystery", 32), forge_monogram("qux_enigma", 32)
    assert a.get_size() == (32, 32)
    pixels = lambda image: [tuple(image.get_at((x, y))) for x in range(32) for y in range(32)]  # noqa: E731
    assert pixels(a) != pixels(b)
    assert pixels(a) == pixels(forge_monogram("zzz_mystery", 32))
    assert sum(1 for p in pixels(a) if p[3] > 0) > 200


def test_apply_writes_png_files_and_only_touches_icon_lines(tmp_path):
    data = {
        "gameplay_library": {
            "abilities": [
                {"ability_id": "fireball"},
                {"ability_id": "keeper", "icon_id": "mine.png"},
                {"ability_id": "potion", "icon_id": "item.png"},
            ],
            "states": [{"state_id": "poison"}],
        },
        "rpg_database": {"pet_species": [{"species_id": "frost_lynx"}]},
    }
    path = tmp_path / "project.asteria.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    counts = apply_to_project_file(path, replace=True, keep=("potion",))
    assert counts == {"abilities": 2, "states": 1, "pets": 1}  # "keeper" gets a monogram
    written = json.loads(path.read_text())
    abilities = {
        a["ability_id"]: a.get("icon_id") for a in written["gameplay_library"]["abilities"]
    }
    assert abilities["fireball"] == "playable_assets/icons/skill_fire.png"
    assert abilities["potion"] == "item.png"
    assert abilities["keeper"] == "playable_assets/icons/skill_mono_keeper.png"
    assert (tmp_path / abilities["keeper"]).is_file()
    assert (tmp_path / "playable_assets/icons/skill_fire.png").is_file()
    again = apply_to_project_file(path, replace=False)
    assert again == {"abilities": 0, "states": 0, "pets": 0}  # existing icons are kept


@pytest.mark.parametrize("name", ["octopath_demo", "diablo_demo"])
def test_the_reference_projects_have_working_original_icons(name):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.menu_icons import icon_source

    folder = ROOT / "reference_projects" / name
    project = Project.load_json(
        folder / "project.asteria.json", EditorDocument().component_registry
    )
    library = project.gameplay_library.abilities
    icons = [library.get(i).icon_id for i in library.ids() if "skill_" in library.get(i).icon_id]
    assert len(icons) >= 20
    for icon_id in icons:
        assert (folder / icon_id).is_file(), icon_id
        assert icon_source(project, icon_id) is not None
    if name == "octopath_demo":
        for species in project.rpg_database.pet_species.values():
            assert species.icon_id and (folder / species.icon_id).is_file()
