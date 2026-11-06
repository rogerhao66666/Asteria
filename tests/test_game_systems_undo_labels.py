"""Game Systems undo entries name one record of the kind in full: cutting the label's last
letter made "Add Music Roo" and "Delete Pet Rules (creature party"."""

from pathlib import Path

from asteria.editor import EditorDocument
from asteria.editor.game_systems_authoring import KINDS, GameSystemsAuthoringController
from asteria.project import Project

REF = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"


def test_each_kind_has_a_whole_singular_noun():
    nouns = {kind.kind_id: kind.noun for kind in KINDS}
    assert nouns["shops"] == "Shop"
    assert nouns["tag_definitions"] == "Property"  # "Properties"
    assert nouns["music_tracks"] == "Music Room"  # one word already
    assert nouns["pet_species"] == "Pet Species"
    assert nouns["pet_rules"] == "Pet Rule"  # "Pet Rules (creature party)"
    assert nouns["refine_rules"] == "Weapon Refine"  # "Weapon Refine (+N)"
    for kind in KINDS:  # never a cut word or a half bracket
        assert kind.noun and "(" not in kind.noun
        assert kind.label.startswith(kind.noun) or kind.noun.endswith("y")


def test_add_edit_and_delete_are_named_with_the_noun():
    document = EditorDocument()
    document.set_project(Project.load_json(REF, document.component_registry), file_path=REF)
    api = GameSystemsAuthoringController(document)
    api.create_new("shops", "corner_shop")
    assert document.commands.undo_label == "Add Shop corner_shop"
    api.edit("shops", "corner_shop", api.form_data("shops", "corner_shop"))
    assert document.commands.undo_label == "Edit Shop corner_shop"
    api.delete("shops", "corner_shop")
    assert document.commands.undo_label == "Delete Shop corner_shop"
