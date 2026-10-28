"""A record's Note and its Players See It switch (Qt-free): the database keeps both beside the
records - ``author_notes`` ({store: {id: text}}) and ``hidden_descriptions`` ({kind: {id:
True}}, by the record's locale-table kind) - so every kind of record has them alike."""

from __future__ import annotations

# the record kinds whose description the game shows somewhere: these get Players See It
SHOWN_KINDS = frozenset(
    {
        "ability", "item", "equipment", "enemy", "class", "quest", "achievement",
        "quest_board", "gacha_banner", "stat", "tag", "slot",
    }
)  # fmt: skip


# Game Data's categories whose description the game shows (the others' stay in the editor)
SHOWN_CATEGORIES = frozenset({"classes", "abilities", "items", "equipment", "enemies"})
UNSHOWN_HELP = (
    "The game does not show this description: it stays in the editor (and in translation"
    " tables). For your own notes, use Note below."
)


def description_words(category, label, help_text):
    """A record's Description label and help: "(editor only)" where the game never shows it."""
    if not category or category in SHOWN_CATEGORIES:
        return label, help_text
    return f"{label} (editor only)", UNSHOWN_HELP


def note_of(project, store, key):
    """The note on record ``key`` of ``store`` (``""``: none)."""
    db = getattr(project, "rpg_database", None)
    notes = getattr(db, "author_notes", None) or {}
    return notes.get(str(store), {}).get(str(key), "")


def note_command(project, store, key, text):
    """The undoable command setting the note (``""`` removes it), or None if unchanged."""
    from .game_systems_authoring import _MapCommand

    notes = project.rpg_database.author_notes.setdefault(str(store), {})
    old = notes.get(str(key)) or None
    new = str(text) if str(text or "").strip() else None
    if new == old:
        return None
    return _MapCommand(notes, str(key), new, old, f"Note on {key}")


def shown_kind(record):
    """``(kind, id)`` of a record whose description players can read, else None."""
    from asteria.rpg.data_text import kind_of

    known = kind_of(record) if record is not None else None
    return known if known is not None and known[0] in SHOWN_KINDS else None


def is_shown(project, record):
    known = shown_kind(record)
    return known is None or not project.rpg_database.description_hidden(*known)


def shown_command(project, record, shown):
    """The undoable command showing or hiding ``record``'s description, or None."""
    from .game_systems_authoring import _MapCommand

    known = shown_kind(record)
    if known is None or bool(shown) == is_shown(project, record):
        return None
    kind, record_id = known
    hidden = project.rpg_database.hidden_descriptions.setdefault(kind, {})
    words = "Show" if shown else "Hide"
    return _MapCommand(
        hidden, record_id, None if shown else True, True if shown else None, f"{words} {record_id}"
    )
