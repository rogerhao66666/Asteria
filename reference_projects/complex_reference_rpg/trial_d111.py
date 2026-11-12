"""D111: no more "Actor Kind" / "Roster" labels in this project either.

``actor.playable`` and ``roster.NN`` were labels no rule read (D110 took them out of the other
projects). They go from the actors, and from the character snapshots the saves and playtest
profiles carry, so a loaded save shows the same properties as the actor's page.
``build_project.py`` no longer writes them. Re-runnable.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GONE = ("actor.", "roster.")


def _kept(tags):
    return [t for t in tags if not (isinstance(t, str) and t.startswith(GONE))]


def strip(value):
    """``value`` with the labels gone from every actor's tags and every tag set."""
    if isinstance(value, dict):
        out = {k: strip(v) for k, v in value.items()}
        if out.get("schema") == "asteria.tag_set" and isinstance(out.get("values"), list):
            out["values"] = _kept(out["values"])
        if "actor_id" in out and isinstance(out.get("tags"), list):
            out["tags"] = _kept(out["tags"])
        return out
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


def paths():
    yield HERE / "project.asteria.json"
    yield from sorted((HERE / "saves").glob("*.json"))
    yield from sorted((HERE / "playtest_profiles").glob("*.json"))


def main():
    for path in paths():
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        new = strip(data)
        if new != data:
            ending = "\n" if text.endswith("\n") else ""
            path.write_text(json.dumps(new, indent=2) + ending, encoding="utf-8")


if __name__ == "__main__":
    main()
