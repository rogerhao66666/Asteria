"""D96: the game menu's pages are built from blocks (Game Systems ▸ Menu Pages).

D87-D89 wrote the Status and Items pages' settings on one record, "Trial menu pages", next to
the pause menu's order. Now that record is the Pause Menu only, and each page is a record of
its own made of blocks:

* **status** - Profile and Stat Points in the left column, Stat Details on the right: the
  same stat graph, columns, detail groups and lines as before;
* **items** - one Item List with the same tabs, filters and details panel;
* **materials** - an example of a page of the project's own: an Item List holding only the
  Materials tab, a pause entry of its own after Items.

Status and Items draw exactly as they did. Run it once over ``project.asteria.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from asteria.rpg.menu_pages import MenuBlock, MenuPage, default_pages  # noqa: E402
from asteria.rpg.menu_rules import MenuRules  # noqa: E402

PAGE_SETTINGS = (
    *("stat_graph", "stat_columns", "stat_rows", "stat_groups", "stat_lines"),
    *("item_categories", "item_filters", "item_details"),
)

CHINESE = {
    "data.menu_rules.trial_menu.name": "暫停選單",
    "data.menu_page.status.name": "狀態",
    "data.menu_page.items.name": "道具",
    "data.menu_page.materials.name": "素材",
}


def main():
    path = HERE / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    db = data["rpg_database"]
    (record,) = db["menu_rules"]
    assert record["rules_id"] == "trial_menu" and not db.get("menu_pages")
    pages = default_pages(MenuRules.from_data(record))
    (materials,) = [c for c in pages["items"].block("item_list").item_categories
                    if c.category_id == "materials"]  # fmt: skip
    pages["materials"] = MenuPage(
        "materials",
        "Materials",  # no icon: the other entries have none (D98)
        blocks=(MenuBlock("item_list", item_categories=(materials,)),),
    )
    db["menu_pages"] = [pages[k].to_data() for k in ("status", "items", "materials")]
    for key in PAGE_SETTINGS:
        record.pop(key, None)  # now each page's own
    record["display_name"] = "Pause menu"
    (zh,) = [t for t in db["locale_tables"] if t["locale"] == "zh-TW"]
    zh["entries"].update(CHINESE)  # the record's new name and the pages' names
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("status, items and materials are menu pages of blocks")


if __name__ == "__main__":
    main()
