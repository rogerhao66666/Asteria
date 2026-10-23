"""Real-window pictures of the Translations page's project data (D60 T2), in English and in
Chinese, on the Full Verification demo.

    python scripts/data_translation_editor_live_check.py OUTPUT_DIR

Opens the editor (Cocoa), Database ▸ Game Systems ▸ Translations ▸ zh-TW, and saves: the page
with its data groups folded, a search that opens the items group, the Project data filter, the
page after Give dialogue lines keys (the lines group), and the same in the Chinese editor.
``results.json`` lists what each picture shows. Nothing is saved to the project.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
DEMO = REPO / "reference_projects" / "full_verification_demo" / "project.asteria.json"


def _untranslated(project):
    """Take the demo's data translations and dialogue keys out (in memory only), so the page
    shows what an author meets first: data rows to fill and lines without keys."""
    from asteria.events.program import EventInstruction, EventProgram
    from asteria.rpg.localization import LocaleTable

    for locale, table in list(project.rpg_database.locale_tables.items()):
        kept = {
            k: v for k, v in dict(table.entries).items() if not k.startswith(("data.", "dlg."))
        }
        project.rpg_database.locale_tables[locale] = LocaleTable(locale, kept)
    programs = project.event_programs
    for program_id in programs.ids():
        old = programs.require(program_id)
        instructions = []
        for instruction in old.instructions:
            args = {
                k: v for k, v in instruction.args.items() if k not in ("text_key", "prompt_key")
            }
            if isinstance(args.get("choices"), list):
                args["choices"] = [
                    {k: v for k, v in c.items() if k != "text_key"} if isinstance(c, dict) else c
                    for c in args["choices"]
                ]
            instructions.append(EventInstruction(instruction.opcode, args))
        programs.replace(program_id, EventProgram(instructions, name=old.name))


def _data_count(text):
    """The number of data texts in the page's count line (English or Chinese)."""
    import re

    found = re.search(r"(\d+) data texts|資料文字 (\d+)", text)
    return None if found is None else int(found.group(1) or found.group(2))


def main(argv=None):
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor import data_translation as dt
    from asteria.editor.i18n import install, set_language
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.theme import apply_asteria_theme
    from asteria.editor.translation_table import TranslationTable
    from asteria.editor.workspace import WorkspaceMode
    from asteria.project import Project

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs/audits/evidence/data_translation")
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(
        ["data_translation_live", "-ApplePersistenceIgnoreState", "YES"]
    )
    apply_asteria_theme(app, None)
    install(app, "en")
    project = Project.load_json(DEMO, EditorDocument().component_registry)
    _untranslated(project)  # the demo before its own Chinese (T3): the page as a new project
    window = AsteriaEditorWindow(project)
    window.document.file_path = DEMO
    window.document.mark_saved()
    window._resolve_project_resources()
    window.refresh_all()
    window.resize(1600, 1000)
    window.show()

    def settle(seconds=0.5):
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(0.02)

    settle(1.0)
    systems = window.game_systems_editor
    window.workspace.set_mode(WorkspaceMode.RPG)
    window.rpg_workspace.setCurrentWidget(systems)
    systems.set_kind("locale_tables")
    settle()
    systems.refresh(select="zh-TW")
    settle()
    page = window.findChild(TranslationTable)
    shots, facts = [], {"platform": app.platformName()}

    def shot(name, what):
        settle(0.4)
        window.grab().save(str(out / f"{name}.png"))
        shots.append({"file": f"{name}.png", "shows": what})

    def group(title):
        for i in range(page.tree.topLevelItemCount()):
            item = page.tree.topLevelItem(i)
            if item.data(0, 0x0101) == title:
                return item
        return None

    def to_group(title):
        item = group(title)
        if item is not None:
            from PySide6.QtWidgets import QAbstractItemView

            page.tree.setCurrentItem(item)
            page.tree.scrollToItem(item, QAbstractItemView.PositionAtTop)

    to_group("Data: actors")
    facts["data_groups_folded"] = not group("Data: items").isExpanded()
    facts["count"] = page.count.text()
    shot("t2_en_data_groups", "English editor: the data groups, folded, below the engine words")
    page.search.setText("Healing")
    facts["search_opens_items"] = group("Data: items").isExpanded()
    to_group("Data: items")
    shot("t2_en_search_healing", "Search 'Healing': the items and skills groups open")
    page.search.setText("")
    page.show_box.setCurrentIndex(page.show_box.findData("Project data"))
    to_group("Data: actors")
    group("Data: actors").setExpanded(True)
    group("Data: enemies").setExpanded(True)
    shot("t2_en_project_data_filter", "Show: Project data (actors, enemies opened)")
    missing = dt.dialogue_without_keys(project)
    changed = page.give_dialogue_keys()
    facts["dialogue_without_keys_before"] = missing
    facts["programs_given_keys"] = changed
    facts["dialogue_without_keys_after"] = dt.dialogue_without_keys(project)
    lines = group(dt.LINES_GROUP)
    facts["lines_listed"] = 0 if lines is None else lines.childCount()
    if lines is not None:
        lines.setExpanded(True)
        to_group(dt.LINES_GROUP)
    shot("t2_en_dialogue_keys", "After Give dialogue lines keys: the lines and choices group")
    window.undo()  # Edit ▸ Undo, as the player of the editor would
    settle()
    facts["undo_restores"] = dt.dialogue_without_keys(project) == missing
    set_language("zh_TW")
    settle()
    page = next(t for t in window.findChildren(TranslationTable) if t.isVisible())
    facts["count_after_undo"] = page.count.text()
    page.show_box.setCurrentIndex(page.show_box.findData("Project data"))
    group("Data: items").setExpanded(True)
    to_group("Data: items")
    facts["count_zh"] = page.count.text()
    shot("t2_zh_project_data", "Chinese editor: group titles, filter and count in Chinese")
    page.show_box.setCurrentIndex(0)
    page.search.setText("Aegis")
    to_group("Data: skills")
    shot("t2_zh_search_aegis", "Chinese editor: search 'Aegis' opens the skills group")
    set_language("en")
    report = {"facts": facts, "screenshots": shots}
    report["status"] = (
        "PASS"
        if facts["platform"] == "cocoa"
        and facts["data_groups_folded"]
        and facts["search_opens_items"]
        and facts["dialogue_without_keys_after"] == 0
        and facts["undo_restores"]
        and _data_count(facts["count_after_undo"]) == _data_count(facts["count"])
        else "FAIL"
    )
    (out / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    window.document.mark_saved()
    window.close()
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
