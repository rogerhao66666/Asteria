"""Scene tabs above the map: every scene opened this session has a tab; a click shows it, a tab
closes with its ✕ (the scene stays in the project), tabs drag into any order, and ▾ lists every
scene of the project to open. The scene shown always has a tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMenu, QTabBar, QToolButton, QVBoxLayout, QWidget


class SceneTabs(QWidget):
    def __init__(self, document, open_scene, parent=None):
        """``open_scene(scene)`` shows a scene (the window selects it and refreshes)."""
        super().__init__(parent)
        self.setObjectName("SceneTabs")
        self.document = document
        self.open_scene = open_scene
        self.bar = QTabBar(self)
        self.bar.setObjectName("SceneTabBar")
        self.bar.setDocumentMode(True)
        self.bar.setTabsClosable(True)
        self.bar.setMovable(True)
        self.bar.setExpanding(False)
        self.bar.setElideMode(Qt.ElideRight)
        self.bar.setUsesScrollButtons(True)
        self.bar.tabBarClicked.connect(self._clicked)
        self.bar.tabCloseRequested.connect(self.close_tab)
        self.more = QToolButton(self)
        self.more.setObjectName("SceneTabsMore")
        self.more.setText("▾")
        self.more.setToolTip("Open another scene")
        self.more.setPopupMode(QToolButton.InstantPopup)
        self.menu = QMenu(self.more)
        self.menu.aboutToShow.connect(self._fill_menu)
        self.more.setMenu(self.menu)
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 6, 0)
        row.setSpacing(4)
        row.addWidget(self.bar, 1)
        row.addWidget(self.more)
        self._syncing = False

    def scene_ids(self):
        return [self.bar.tabData(i) for i in range(self.bar.count())]

    def _scenes(self):
        project = getattr(self.document, "project", None)
        return {s.id: s for s in project.scenes()} if project is not None else {}

    def sync(self, current=None):
        """Tabs for scenes that still exist, named as they are now; ``current`` (the scene
        shown) gets a tab and is chosen."""
        self._syncing = True
        try:
            scenes = self._scenes()
            for index in reversed(range(self.bar.count())):
                if self.bar.tabData(index) not in scenes:
                    self.bar.removeTab(index)
            for index in range(self.bar.count()):
                scene = scenes[self.bar.tabData(index)]
                if self.bar.tabText(index) != scene.name:
                    self.bar.setTabText(index, scene.name)
            if current is not None and current.id in scenes:
                ids = self.scene_ids()
                index = ids.index(current.id) if current.id in ids else -1
                if index < 0:
                    index = self.bar.addTab(current.name)
                    self.bar.setTabData(index, current.id)
                    self.bar.setTabToolTip(index, current.id)
                self.bar.setCurrentIndex(index)
            self._closable()
        finally:
            self._syncing = False

    def _closable(self):
        """The last tab does not close: a scene is always shown."""
        alone = self.bar.count() <= 1
        for index in range(self.bar.count()):
            button = self.bar.tabButton(index, QTabBar.RightSide)
            if button is not None:
                button.setVisible(not alone)

    def _clicked(self, index):
        if self._syncing or index < 0:
            return
        scene = self._scenes().get(self.bar.tabData(index))
        if scene is not None:
            self.open_scene(scene)

    def close_tab(self, index):
        if self.bar.count() <= 1 or index < 0:
            return
        was_current = index == self.bar.currentIndex()
        self.bar.removeTab(index)
        if was_current:
            self._clicked(self.bar.currentIndex())
        self._closable()

    def _fill_menu(self):
        self.menu.clear()
        shown = set(self.scene_ids())
        for scene in self._scenes().values():
            action = self.menu.addAction(scene.name)
            action.setCheckable(True)
            action.setChecked(scene.id in shown)
            action.triggered.connect(lambda _checked=False, s=scene: self.open_scene(s))


def with_scene_tabs(viewport, tabs):
    """The map with its scene tabs above it, as one page of the Scene workspace."""
    page = QWidget()
    page.setObjectName("ScenePage")
    column = QVBoxLayout(page)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(0)
    column.addWidget(tabs)
    column.addWidget(viewport, 1)
    return page
