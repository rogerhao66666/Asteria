import pytest

from asteria.editor.actor_appearance import ActorAppearanceError, ActorAppearanceLibrary


def test_set_then_get_round_trips(tmp_path):
    library = ActorAppearanceLibrary(tmp_path)
    library.set("hero_01", "sheet-id", frame_index=3, flip_x=True)

    reloaded = ActorAppearanceLibrary(tmp_path)
    value = reloaded.get("hero_01")
    assert value.sprite_sheet_asset_id == "sheet-id"
    assert value.frame_index == 3
    assert value.flip_x is True


def test_unknown_actor_returns_none(tmp_path):
    library = ActorAppearanceLibrary(tmp_path)
    assert library.get("nobody") is None


def test_remove_deletes_the_entry(tmp_path):
    library = ActorAppearanceLibrary(tmp_path)
    library.set("hero_01", "sheet-id")
    library.remove("hero_01")
    assert ActorAppearanceLibrary(tmp_path).get("hero_01") is None


def test_missing_file_is_treated_as_empty(tmp_path):
    library = ActorAppearanceLibrary(tmp_path / "does_not_exist_yet")
    assert library.get("hero_01") is None


def test_wrong_schema_raises(tmp_path):
    path = tmp_path / "actor_appearances.json"
    path.write_text('{"schema": "nope", "version": 1}', encoding="utf-8")
    library = ActorAppearanceLibrary(tmp_path)
    with pytest.raises(ActorAppearanceError):
        library.get("hero_01")
