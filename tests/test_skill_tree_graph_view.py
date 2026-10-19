"""The editor's skill tree graph shows the design (a card per node with its icon, name, ranks and
what it gives, arrows from prerequisites) and Game Data follows the project that is open."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsPixmapItem,
    QGraphicsTextItem,
)

from asteria.editor import EditorDocument  # noqa: E402
from asteria.editor.authoring_hub_widget import (  # noqa: E402
    _NODE_H,
    _NODE_W,
    SkillTreeGraphView,
    _spread,
)
from asteria.editor.storage import load_document  # noqa: E402
from asteria.project import Project  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "reference_projects"
DEMO = ROOT / "full_verification_demo" / "project.asteria.json"
REFERENCE = ROOT / "complex_reference_rpg" / "project.asteria.json"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _document(path):
    document = EditorDocument()
    load_document(document, path)
    return document


def test_every_node_card_shows_its_name_ranks_gift_and_icon(app):
    document = _document(DEMO)
    graph = document.project.rpg_database.progression_graphs["bishop_tree"]
    view = SkillTreeGraphView(document=document)
    view.set_graph_data(graph.to_data())
    assert len(view.node_items) == len(graph.nodes)
    for node in graph.nodes:
        card = view.node_items[node.node_id]
        texts = [c for c in card.childItems() if isinstance(c, QGraphicsTextItem)]
        icons = [c for c in card.childItems() if isinstance(c, QGraphicsPixmapItem)]
        assert len(texts) == 3 and texts[0].toPlainText(), node.node_id  # name, ranks, gift
        assert icons, f"{node.node_id} has no picture"
        assert card.toolTip()
    arrows = sum(len(n.prerequisites) + len(n.any_prerequisites) for n in graph.nodes)
    assert len(view._edges) == arrows


def test_a_saved_layout_is_spread_so_cards_never_overlap():
    spread = _spread({"a": [0, 0], "b": [30, 10], "c": [60, 0]})
    points = list(spread.values())
    for i, (ax, ay) in enumerate(points):
        for bx, by in points[i + 1 :]:
            assert abs(ax - bx) >= _NODE_W + 16 - 1e-6 or abs(ay - by) >= _NODE_H + 16 - 1e-6
    assert _spread({"a": [0, 0], "b": [400, 0]}) == {"a": [0.0, 0.0], "b": [400.0, 0.0]}


def test_game_data_follows_a_newly_opened_project_with_the_same_id(app):
    from asteria.editor.shell import AsteriaEditorWindow

    first = Project.load_json(REFERENCE, EditorDocument().component_registry)
    window = AsteriaEditorWindow(first)
    window.refresh_all()
    second = Project.load_json(DEMO, EditorDocument().component_registry)
    second.id = first.id  # a project copied from another keeps its id
    window.set_project(second)
    family = window.rpg_authoring.child  # the Game Data surface shown now
    index = family.category.findData("graphs")
    family.category.setCurrentIndex(index)
    assert len(family._ids) == len(second.rpg_database.progression_graphs) >= 20
    window.close()
