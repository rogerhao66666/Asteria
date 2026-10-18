"""Closing the editor must not take the application's style with it: the centred dock tab
style once wrapped (and so owned) the shared application style, the window deleted it, and
QApplication crashed on exit - which pygame's crash handler turned into a hang (force quit)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QProxyStyle, QTabBar  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_the_dock_tab_style_has_its_own_base_and_the_app_style_survives_the_window(app):
    from asteria.editor.shell import AsteriaEditorWindow, _CenteredDockTabStyle

    window = AsteriaEditorWindow(None)
    bar = QTabBar(window)  # a dock tab bar as Qt makes it for the bottom panel
    for title in ("Assets", "Console"):
        bar.addTab(title)
    window.hide_stale_dock_tab_bars()
    shared = QApplication.style()
    # the proxies hang under the window (a style sheet may wrap what bar.style() returns)
    proxies = [p for p in window.findChildren(QProxyStyle) if isinstance(p, _CenteredDockTabStyle)]
    assert proxies, "no dock tab bar got the centred style"
    assert all(p.baseStyle() is not shared for p in proxies)
    name = shared.name()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert QApplication.style().name() == name  # still there after the window is gone
