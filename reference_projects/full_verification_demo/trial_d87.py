"""D87 on the built project: what ``build_project.py`` now writes, applied to the project as it
stands (later batches edited the built data by hand, so the demo is patched, not rebuilt).

- every sprite sheet of a figure stands on its feet (``feet_pivot_y``: the lowest row its
  art reaches, not the frame's empty bottom edge);
- people's feet boxes as wide as their bodies (14, was 10);
- every walking figure's walk plays as far as it moves (``Animator2D.stride``);
- Roger's House, the Hall of Heroes plaque, the Victory Banner, the Old Cache, the Sealed
  Vault and the bush block like the people do;
- the game folder settings: the walk's pace (``field.walk_speed``) and the menus' size
  (``render.menu_size``);
- Menu Pages (``trial_story.menu_pages``): the Status page's stat table, the Items page's tabs
  and filters, and their Chinese; the zh-TW table gets the engine's new words (the pause
  menu's Status is now only Status).

Run: ``python reference_projects/full_verification_demo/trial_d87.py`` (safe to run again).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from asteria.graphics.character_placement import feet_pivot_y  # noqa: E402
from asteria.rpg.built_in_text import engine_translations  # noqa: E402

STRIDE = 24.0  # trial_maps.STRIDE
BODY = 14.0  # trial_maps.BODY
WALK_SPEED = 48.0
MENU_SIZE = [1280, 720]
# name -> (width, height, offset_y) of the solid box at the foot of the picture
SOLIDS = {
    "Roger's House": (60.0, 40.0, -22.0),
    "Hall of Heroes": (14.0, 8.0, 0.0),
    "Victory Banner": (14.0, 8.0, 0.0),
    "Old Cache": (14.0, 8.0, 0.0),
    "Sealed Vault": (14.0, 8.0, 0.0),
    "doodad:bush.3": (20.0, 10.0, 0.0),
}


def collider(width, height, offset_y):
    return {
        "fields": {
            "enabled": True,
            "height": float(height),
            "is_trigger": False,
            "ladder": False,
            "layer": 0,
            "mask": 4294967295,
            "offset_x": 0.0,
            "offset_y": float(offset_y),
            "one_way": False,
            "radius": 8.0,
            "shape": "box",
            "width": float(width),
        },
        "type": "asteria.Collider2D",
        "version": 3,
    }


def _components(node):
    """Every component list in the project (scenes' entities and prefabs)."""
    if isinstance(node, dict):
        if isinstance(node.get("components"), list):
            yield node
        for value in node.values():
            yield from _components(value)
    elif isinstance(node, list):
        for value in node:
            yield from _components(value)


def patch_project(data):
    sheets = set()
    for holder in _components(data["scenes"]):
        types = {c.get("type") for c in holder["components"]}
        for component in holder["components"]:
            if component.get("type") == "asteria.Animator2D":
                fields = {**component["fields"], "stride": STRIDE}
                component["fields"] = dict(sorted(fields.items()))
                component["version"] = 2
            elif component.get("type") == "asteria.SpriteRenderer2D":
                sheets.add(component["fields"]["sprite_sheet_asset_id"])
            elif component.get("type") == "asteria.Collider2D":
                fields = component["fields"]
                if (fields["width"], fields["height"]) == (10.0, 8.0):  # a person's feet
                    fields["width"] = BODY
        name = holder.get("name")
        if name in SOLIDS and "asteria.Collider2D" not in types:
            holder["components"].append(collider(*SOLIDS[name]))
    return sheets


def patch_sheets(data, sheet_ids):
    from PIL import Image

    records = {a["id"]: a for a in data["assets"]["assets"]}
    changed = 0
    for sheet_id in sorted(sheet_ids):
        record = records.get(sheet_id)
        if record is None or record["kind"] != "sprite_sheet":
            continue
        path = HERE / record["source_path"]
        sheet = json.loads(path.read_text(encoding="utf-8"))
        frames = sheet.get("frames", [])
        if not frames or any((f["pivot_x"], f["pivot_y"]) != (0.5, 1.0) for f in frames):
            continue  # an authored pivot (or one already set) is left alone
        texture = records[sheet["texture_asset_id"]]
        with Image.open(HERE / texture["source_path"]) as image:
            pivot = feet_pivot_y(
                image, [(f["x"], f["y"], f["width"], f["height"]) for f in frames]
            )
        if pivot == 1.0:
            continue
        for frame in frames:
            frame["pivot_y"] = pivot
        path.write_text(json.dumps(sheet, indent=2) + "\n", encoding="utf-8")
        changed += 1
    return changed


MENU_ZH = {  # the Chinese of Menu Pages' words (data.<kind>.<id>.name)
    "data.menu_rules.trial_menu.name": "試煉選單頁面",
    "data.item_category.all.name": "全部",
    "data.item_category.consumables.name": "消耗品",
    "data.item_category.throwables.name": "投擲物",
    "data.item_category.materials.name": "素材",
    "data.item_category.weapons.name": "武器",
    "data.item_category.armour.name": "防具",
    "data.item_filter.usable.name": "現在可用",
    "data.item_filter.potions.name": "藥水",
    "data.item_filter.uniques.name": "獨特裝備",
}
CHANGED_WORDS = ("pause.status",)  # engine words whose meaning changed: the engine's again


# D88 / D89 set them: kept
LATER_FIELDS = ("item_details", "stat_groups", "stat_lines", "stat_columns")


def patch_menu_pages(data):
    sys.path.insert(0, str(HERE))
    from trial_story import menu_pages

    db = data["rpg_database"]
    record = menu_pages().to_data()
    old = next((r for r in db.get("menu_rules", []) if r["rules_id"] == record["rules_id"]), {})
    record.update({k: old[k] for k in LATER_FIELDS if k in old})
    db["menu_rules"] = [r for r in db.get("menu_rules", []) if r["rules_id"] != record["rules_id"]]
    db["menu_rules"].append(record)
    chinese = engine_translations("zh-TW")
    for table in db["locale_tables"]:
        if table["locale"] != "zh-TW":
            continue
        entries = table["entries"]
        for key, word in chinese.items():
            if key not in entries or key in CHANGED_WORDS:
                entries[key] = word
        entries.update(MENU_ZH)


def patch_manifest(path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["field"]["walk_speed"] = WALK_SPEED
    manifest.setdefault("render", {})["menu_size"] = MENU_SIZE
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    path = HERE / "project.asteria.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sheet_ids = patch_project(data)
    changed = patch_sheets(data, sheet_ids)
    patch_menu_pages(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    patch_manifest(HERE / "playable_test_manifest.json")
    print(f"sheets stood on their feet: {changed}")


if __name__ == "__main__":
    main()
