"""Editor UI audit (D19): open the reference project in a real editor window, visit every
workspace and
sub-tab, take a screenshot of each and list visible defects a person would see:

* ``clipped``  - text wider than the widget showing it (labels, buttons, check boxes, combo boxes,
  tab
  titles, table headers); elided text drawn with "…" on purpose is not reported
* ``overflow`` - a visible widget that sticks out of its parent's rectangle (outside scroll areas)
* ``tiny``     - an interactive control squeezed under 12 px
* ``scrolled`` - (informational) a tab outside its bar's visible part, reached with the scroll
  buttons
* ``page_scroll_x`` / ``page_scroll_y`` - a workspace page larger than its area (the user must
  scroll it)
* ``columns_scroll_x`` - table / tree columns wider than the table (the user must scroll sideways)

Usage: python scripts/editor_ui_audit.py OUTPUT_DIR [--size 1600x1000] [--tag before] [--theme
twilight]
                                         [--surfaces scene rpg_database ...]
Writes OUTPUT_DIR/<tag>_<workspace>.png and OUTPUT_DIR/<tag>_report.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_FILE = ROOT / "reference_projects" / "complex_reference_rpg" / "project.asteria.json"
sys.path.insert(0, str(ROOT / "src"))


def _text_width(widget, text):
    return widget.fontMetrics().horizontalAdvance(text.replace("&&", "&").replace("&", ""))


def _single_line(text):
    return text and "\n" not in text and "<" not in text


def defects_in(window):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractButton,
        QAbstractScrollArea,
        QCheckBox,
        QComboBox,
        QHeaderView,
        QLabel,
        QLineEdit,
        QPushButton,
        QRadioButton,
        QSpinBox,
        QTabBar,
        QToolButton,
        QWidget,
    )

    found = []

    def where(widget):
        names = []
        w = widget
        while w is not None and w is not window:
            if w.objectName():
                names.append(w.objectName())
            elif w.metaObject().className().startswith("Q") is False:
                names.append(w.metaObject().className())
            w = w.parentWidget()
        return "/".join(reversed(names[:4])) or widget.metaObject().className()

    def add(kind, widget, detail):
        found.append(
            {
                "kind": kind,
                "widget": widget.metaObject().className(),
                "where": where(widget),
                **detail,
            }
        )

    def inside_scroll(widget):
        w = widget.parentWidget()
        while w is not None:
            if isinstance(w, QAbstractScrollArea):
                return True
            w = w.parentWidget()
        return False

    for widget in window.findChildren(QWidget):
        if not widget.isVisible() or widget.width() <= 0:
            continue
        if isinstance(widget, QLabel) and not widget.wordWrap() and _single_line(widget.text()):
            need = _text_width(widget, widget.text())
            have = (
                widget.contentsRect().width() - 2 * widget.margin() - widget.indent()
                if widget.indent() > 0
                else widget.contentsRect().width() - 2 * widget.margin()
            )
            if need > have + 1:
                add("clipped", widget, {"text": widget.text(), "need": need, "have": have})
        elif isinstance(widget, (QPushButton, QToolButton)) and _single_line(widget.text()):
            if (
                isinstance(widget, QToolButton)
                and widget.toolButtonStyle() == Qt.ToolButtonIconOnly
            ):  # icon only
                continue
            icon = widget.iconSize().width() + 4 if not widget.icon().isNull() else 0
            need = _text_width(widget, widget.text()) + icon + 12
            if need > widget.width() + 1:
                add(
                    "clipped",
                    widget,
                    {"text": widget.text(), "need": need, "have": widget.width()},
                )
        elif isinstance(widget, (QCheckBox, QRadioButton)) and _single_line(widget.text()):
            need = _text_width(widget, widget.text()) + 20
            if need > widget.width() + 1:
                add(
                    "clipped",
                    widget,
                    {"text": widget.text(), "need": need, "have": widget.width()},
                )
        elif isinstance(widget, QComboBox) and widget.currentText():
            need = _text_width(widget, widget.currentText()) + 28
            if (
                need > widget.width() + 1
                and widget.sizeAdjustPolicy() != QComboBox.AdjustToContents
            ):
                add(
                    "clipped",
                    widget,
                    {"text": widget.currentText(), "need": need, "have": widget.width()},
                )
        elif isinstance(widget, QTabBar):
            for i in range(widget.count()):
                text = widget.tabText(i)
                rect = widget.tabRect(i)
                if rect.width() <= 0:
                    continue
                need = _text_width(widget, text) + 16
                if need > rect.width() + 1:
                    add("clipped", widget, {"text": text, "need": need, "have": rect.width()})
                elif rect.right() > widget.width() + 1 or rect.left() < 0:
                    add(
                        "scrolled", widget, {"text": text}
                    )  # reachable with the bar's scroll buttons
        elif isinstance(widget, QHeaderView):
            model = widget.model()
            if model is None:
                continue
            count = (
                model.columnCount() if widget.orientation() == Qt.Horizontal else model.rowCount()
            )
            for i in range(count):
                if widget.isSectionHidden(i) or widget.sectionSize(i) <= 0:
                    continue
                text = str(model.headerData(i, widget.orientation()) or "")
                if not text:
                    continue
                need = _text_width(widget, text) + 6
                if need > widget.sectionSize(i) + 1:
                    add(
                        "clipped",
                        widget,
                        {"text": text, "need": need, "have": widget.sectionSize(i)},
                    )
        if isinstance(widget, (QAbstractButton, QComboBox, QLineEdit, QSpinBox)):
            if widget.width() < 12 or widget.height() < 12:
                add("tiny", widget, {"size": [widget.width(), widget.height()]})
        parent = widget.parentWidget()
        if (
            parent is not None
            and not widget.isWindow()
            and not inside_scroll(widget)
            and not isinstance(widget, QTabBar)
            and widget.metaObject().className()
            not in ("QDockWidget", "QMainWindowTabBar", "QRubberBand")
        ):
            r = widget.geometry()
            p = parent.rect()
            if (
                r.right() > p.right() + 2
                or r.bottom() > p.bottom() + 2
                or r.left() < -2
                or r.top() < -2
            ):
                add(
                    "overflow",
                    widget,
                    {
                        "rect": [r.x(), r.y(), r.width(), r.height()],
                        "parent": [p.width(), p.height()],
                    },
                )
    # needs scrolling: a page wider / taller than its area, or table columns wider than the table
    from PySide6.QtWidgets import QAbstractItemView, QScrollArea

    for widget in window.findChildren(QAbstractScrollArea):
        if not widget.isVisible() or widget.width() < 40:
            continue
        bar = widget.horizontalScrollBar()
        if bar.isVisible() and bar.maximum() > 8:
            kind = "page_scroll_x" if isinstance(widget, QScrollArea) else "columns_scroll_x"
            if isinstance(widget, QAbstractItemView) or isinstance(widget, QScrollArea):
                add(
                    kind,
                    widget,
                    {"overflow_px": bar.maximum(), "width": widget.viewport().width()},
                )
        vbar = widget.verticalScrollBar()
        if isinstance(widget, QScrollArea) and vbar.isVisible() and vbar.maximum() > 8:
            add(
                "page_scroll_y",
                widget,
                {"overflow_px": vbar.maximum(), "height": widget.viewport().height()},
            )
    unique = {}
    for item in found:
        unique.setdefault(
            (item["kind"], item["where"], item.get("text", ""), item["widget"]), item
        )
    return list(unique.values())


def surfaces(window):
    """``(name, activate)`` for every workspace and sub-tab."""
    from PySide6.QtWidgets import QTabWidget

    from asteria.editor.workspace import WorkspaceMode

    out = []
    for mode in WorkspaceMode:
        page = window.workspace._pages.get(mode)
        if isinstance(page, QTabWidget):
            for i in range(page.count()):
                title = page.tabText(i).replace("&&", "and").replace(" ", "_").replace("/", "-")
                name = f"{mode.value}_{title.lower()}"
                out.append(
                    (
                        name,
                        lambda m=mode, p=page, i=i: (
                            window.workspace.set_mode(m),
                            p.setCurrentIndex(i),
                        ),
                    )
                )
        else:
            out.append((mode.value, lambda m=mode: window.workspace.set_mode(m)))
    # every Game Systems kind and every database category (forms and tables differ per kind)
    from asteria.editor.workspace import WorkspaceMode as WM

    systems = window.game_systems_editor
    for kind in systems.controller.kinds:
        out.append(
            (
                f"rpg_game_systems_{kind.kind_id}",
                lambda k=kind.kind_id: (
                    window.workspace.set_mode(WM.RPG),
                    window.rpg_workspace.setCurrentWidget(systems),
                    systems.set_kind(k),
                ),
            )
        )
    combat = (
        window.combat_editor
    )  # D22 A9: each Real-Time Combat kind has its own cards and preview
    from asteria.editor.combat_authoring import KINDS

    for spec in KINDS:
        out.append(
            (
                f"rpg_combat_{spec.kind_id}",
                lambda k=spec.kind_id: (
                    window.workspace.set_mode(WM.RPG),
                    window.rpg_workspace.setCurrentWidget(combat),
                    combat.show_kind(k),
                ),
            )
        )
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--size", default="1600x1000")
    parser.add_argument(
        "--also",
        nargs="*",
        default=(),
        help="more window sizes to audit after --size (e.g. 1100x700); a narrow window finds "
        "labels that clip and pages that scroll sideways",
    )
    parser.add_argument("--tag", default="audit")
    parser.add_argument("--theme", default=None, help="palette: graphite, twilight or daylight")
    parser.add_argument("--surfaces", nargs="*", help="only these surface names")
    parser.add_argument(
        "--project", default=None, help="a project file instead of the reference project"
    )
    args = parser.parse_args(argv)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    width, height = (int(v) for v in args.size.split("x"))

    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.theme import apply_asteria_theme
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    apply_asteria_theme(app, args.theme)
    project_file = Path(args.project) if args.project else PROJECT_FILE
    project = Project.load_json(project_file, EditorDocument().component_registry)
    window = AsteriaEditorWindow(project)
    window.document.file_path = (
        project_file  # as File > Open does: asset paths resolve next to the project
    )
    window.document.mark_saved()
    window._resolve_project_resources()  # as File > Open does: tile maps and sprites load
    window.refresh_all()
    window.resize(width, height)
    window.show()

    def settle(seconds=0.4):
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(0.02)

    settle(1.0)
    total_all = 0
    for size in (args.size, *args.also):
        width, height = (int(v) for v in size.split("x"))
        window.resize(width, height)
        settle(0.6)
        tag = args.tag if size == args.size else f"{args.tag}_{size}"
        report = {"size": [width, height], "dpr": window.devicePixelRatioF(), "surfaces": {}}
        for name, activate in surfaces(window):
            if args.surfaces and name not in args.surfaces:
                continue
            activate()
            settle()
            window.grab().save(str(out / f"{tag}_{name}.png"))
            report["surfaces"][name] = defects_in(window)
        layout_kinds = ("scrolled", "page_scroll_x", "page_scroll_y", "columns_scroll_x")
        total = sum(
            1
            for v in report["surfaces"].values()
            for item in v
            if item["kind"] not in layout_kinds
        )
        report["scrolling"] = sum(
            1
            for v in report["surfaces"].values()
            for item in v
            if item["kind"] in layout_kinds[1:]
        )
        report["total"] = total
        total_all += total
        (out / f"{tag}_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
        print(f"== {size}")
        for name, items in report["surfaces"].items():
            kinds = [i["kind"] for i in items if i["kind"] != "scrolled"]
            print(f"{name}: {len(kinds)} {sorted(set(kinds))}")
        print("total", total, "scrolling", report["scrolling"], "dpr", report["dpr"])
    window.document.mark_saved()
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
