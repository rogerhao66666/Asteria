"""Everything in the Full Verification demo can be opened, changed and applied again in the editor.

The demo is a reference for users, so its data must go through the editor's own controllers
unchanged: every record of every category, every game-system form, every presentation layout.
"""

import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

from asteria.editor import EditorDocument  # noqa: E402
from asteria.editor.game_systems_authoring import (  # noqa: E402
    FORMS,
    KINDS,
    GameSystemsAuthoringController,
)
from asteria.editor.integrated_authoring import IntegratedAuthoringControllers  # noqa: E402
from asteria.project import Project  # noqa: E402


@pytest.fixture(scope="module")
def opened():
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    document = EditorDocument(project)
    return document, IntegratedAuthoringControllers(document)


def _adapters(controllers):
    for group in (
        "rpg_categories",
        "battle_categories",
        "presentation_categories",
    ):
        for adapter in getattr(controllers, group)():
            yield group, adapter


def test_every_record_of_every_category_round_trips_through_the_editor(opened):
    document, controllers = opened
    seen, problems = 0, []
    for group, adapter in _adapters(controllers):
        for key in adapter.ids():
            record = adapter.get(key)
            try:
                again = adapter.decode(adapter.encode(record))
                if again != record:
                    problems.append(f"{group}/{adapter.category_id}/{key}: decode differs")
                    continue
                adapter.edit(key, again)  # what Apply Changes does with untouched fields
                if adapter.get(key) != record:
                    problems.append(f"{group}/{adapter.category_id}/{key}: edit changed it")
            except Exception as error:  # noqa: BLE001 - listed, not hidden
                problems.append(f"{group}/{adapter.category_id}/{key}: {error!r}")
            seen += 1
    assert seen > 300, seen  # the demo is big: a near-empty walk would be a bug in the test
    assert not problems, "\n".join(problems[:25])


def test_every_game_system_form_round_trips(opened):
    document, _ = opened
    api = GameSystemsAuthoringController(document)
    problems, seen = [], 0
    for kind in KINDS:
        for key in api.ids(kind.kind_id):
            record = api.get(kind.kind_id, key)
            data = api.form_data(kind.kind_id, key)
            missing = {f.key for f in FORMS[kind.kind_id]} - set(data)
            if missing:
                problems.append(f"{kind.kind_id}/{key}: form lacks {sorted(missing)}")
                continue
            api.edit(kind.kind_id, key, data)
            if api.get(kind.kind_id, key) != record:
                problems.append(f"{kind.kind_id}/{key}: apply changed it")
            seen += 1
    assert seen >= 4, seen
    assert not problems, "\n".join(problems[:25])


def test_every_motion_sequence_passes_the_timeline_editors_checks(opened):
    from asteria.editor.action_timeline_authoring import ActionTimelineController

    document, _ = opened
    api = ActionTimelineController(document)
    problems = []
    for sequence_id in api.sequences():
        found = api.problems(api.get(sequence_id))
        problems.extend(found)
    assert len(api.sequences()) > 100
    assert not problems, "\n".join(problems[:20])


def test_the_editors_templates_for_new_skill_fields_make_valid_records():
    import dataclasses

    from asteria.editor.authoring_hub_widget import StructuredRecordEditor
    from asteria.gameplay import AbilityDefinition

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    base = project.gameplay_library.abilities.get("cleave")
    template = dict(StructuredRecordEditor.LIST_TEMPLATES["forms"])
    shaped = dataclasses.replace(base, forms=(template,))
    again = AbilityDefinition.from_data(shaped.to_data())
    assert again.forms[0]["form_id"] == "new_form" and "tags" not in again.forms[0]
