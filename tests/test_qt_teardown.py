"""Regression coverage for Qt-owned popup widgets during pytest teardown."""

import pytest


def test_qt_cleanup_only_targets_parentless_top_level_widgets():
    widgets = pytest.importorskip("PySide6.QtWidgets")

    import conftest

    app = widgets.QApplication.instance() or widgets.QApplication([])
    owner = widgets.QMainWindow()
    combo = widgets.QComboBox(owner)
    combo.addItems(["one", "two"])
    owner.setCentralWidget(combo)
    owner.show()
    combo.showPopup()
    app.processEvents()

    top_levels = app.topLevelWidgets()
    parented_popups = [widget for widget in top_levels if widget.parentWidget() is combo]
    assert owner in top_levels
    assert parented_popups

    cleanup_roots = conftest._application_owned_top_level_widgets(app)

    assert owner in cleanup_roots
    assert all(widget not in cleanup_roots for widget in parented_popups)
    owner.close()
