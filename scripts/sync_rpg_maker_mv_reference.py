from __future__ import annotations

import argparse
import json
from pathlib import Path

from asteria.assets.local_reference import (
    build_rpg_maker_mv_source_inventory,
    compare_inventories,
    inventory_tree,
    synchronize_tree,
    write_inventory,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Additively synchronize a local RPG Maker MV reference library"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    args = parser.parse_args(argv)

    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    required = (
        source / "RPG Maker MV.app" / "Contents" / "MacOS" / "Generator",
        source / "RPG Maker MV.app" / "Contents" / "MacOS" / "NewData",
        source / "dlc",
    )
    if not all(path.is_dir() for path in required):
        parser.error("source must contain RPG Maker MV NewData and dlc trees")

    destination.mkdir(parents=True, exist_ok=True)
    copied = synchronize_tree(required[0], destination / "Generator")
    copied += synchronize_tree(required[1], destination / "NewData")
    copied += synchronize_tree(required[2], destination / "dlc")
    source_inventory = build_rpg_maker_mv_source_inventory(source)
    destination_inventory = inventory_tree(destination)

    mismatches = compare_inventories(source_inventory, destination_inventory)
    from asteria.assets.local_reference import ReferenceInventory

    write_inventory(
        ReferenceInventory("local_reference/rpg_maker_mv", destination_inventory.files),
        args.inventory,
    )
    summary = {
        "copied_files": copied,
        "source_files": source_inventory.file_count,
        "destination_files": destination_inventory.file_count,
        "source_bytes": source_inventory.total_bytes,
        "destination_bytes": destination_inventory.total_bytes,
        "mismatches": [
            {"relative_path": item.relative_path, "reason": item.reason} for item in mismatches
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
