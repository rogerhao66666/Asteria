"""Editing the menu screens' layouts and the menu theme (U2b, ``presentation/menu_layout``).

The controller behind Presentation ▸ Menu Screens ▸ Layout: every change is one undoable
document command that replaces the screen's whole ``MenuLayout`` (or the theme), so Ctrl+Z
steps back one edit at a time. A screen with no layout draws as the engine always drew it;
``reset`` removes the layout again.
"""

from __future__ import annotations

from dataclasses import replace

from asteria.presentation.menu_layout import (
    EXTRA,
    SCREEN_IDS,
    MenuElement,
    MenuLayout,
    MenuTheme,
    base_screen,
    screen_spec,
)

from .runtime_rpg_ui_authoring import _ProfileCommand


class MenuLayoutAuthoringError(RuntimeError):
    pass


# screens each record of a kind may have its own layout of (``<screen>.<record id>``): every
# workstation (U4), quest board, recruiting office and gacha banner (U5)
VARIANTS = {
    "crafting": "workstations",
    "quest_board": "quest_boards",
    "recruit": "recruit_offices",
    "gacha": "gacha_banners",
}


class MenuLayoutAuthoringController:
    LAYOUT, THEME = "menu_layout", "menu_theme"

    def __init__(self, document):
        self.document = document

    @property
    def library(self):
        project = self.document.project
        if project is None:
            raise MenuLayoutAuthoringError("open a project first")
        return project.battle_presentation_library

    # --- reading ------------------------------------------------------------------------
    def screens(self):
        """``[(screen_id, title, customised)]`` in the editor's order."""
        out = []
        for screen_id in SCREEN_IDS:
            spec = screen_spec(screen_id)
            out.append((screen_id, spec.title, self.layout(screen_id) is not None))
            for record_id, title in self.records(screen_id):
                variant = f"{screen_id}.{record_id}"
                custom = self.layout(variant) is not None
                out.append((variant, f"  ▸ {title}", custom))  # under its screen
        return out

    def records(self, screen_id):
        """``[(id, name)]`` of the records that may have their own layout of ``screen_id``."""
        store = VARIANTS.get(screen_id)
        db = self.document.project.rpg_database
        records = getattr(db, store, None) or {} if store else {}
        return [(k, v.display_name) for k, v in sorted(records.items())]

    def stations(self):
        """``[(station id, name)]`` of the project's workstations."""
        return self.records("crafting")

    def layout(self, screen_id):
        return self.library.get(self.LAYOUT, self._screen(screen_id))

    def element_ids(self, screen_id):
        """The screen's own elements, then the author's own ones in the layout."""
        spec = screen_spec(self._screen(screen_id))
        own = [e[0] for e in spec.elements]
        layout = self.layout(screen_id)
        extras = [e.element_id for e in layout.elements if e.extra] if layout else []
        return own + extras

    def element(self, screen_id, element_id):
        """The layout's element, else an empty one of the right kind (nothing changed yet)."""
        layout = self.layout(screen_id)
        found = layout.element(element_id) if layout is not None else None
        if found is not None:
            return found
        kind = next(
            (k for i, k, _d in screen_spec(screen_id).elements if i == element_id), "panel"
        )
        return MenuElement(element_id, kind)

    def theme(self):
        ids = self.library.ids(self.THEME)
        if not ids:
            return None
        return self.library.require(self.THEME, "default" if "default" in ids else ids[0])

    # --- changing -----------------------------------------------------------------------
    def set_element(self, screen_id, element, label=None):
        """Put ``element`` in the screen's layout (made when the screen had none)."""
        screen_id = self._screen(screen_id)
        old = self.layout(screen_id)
        layout = (old or MenuLayout(screen_id)).with_element(element)
        self._run(screen_id, layout, old, label or f"Edit {screen_id} ▸ {element.element_id}")
        return layout

    def change(self, screen_id, element_id, **fields):
        """Change some fields of one element (``rect=(x, y, w, h)``, ``color=...``)."""
        element = replace(self.element(screen_id, element_id), **fields)
        return self.set_element(screen_id, element)

    def add_element(self, screen_id, kind, name=None, rect=(40, 40, 200, 60)):
        """A new element of the author's own (``extra.<name>``) on the screen."""
        layout = self.layout(screen_id)
        taken = {e.element_id for e in layout.elements} if layout else set()
        base = str(name or kind).strip().replace(" ", "_") or kind
        element_id, n = f"{EXTRA}{base}", 2
        while element_id in taken:
            element_id, n = f"{EXTRA}{base}_{n}", n + 1
        element = MenuElement(element_id, kind, rect=rect, text="Text" if kind == "text" else "")
        self.set_element(screen_id, element, f"Add {element_id} to {screen_id}")
        return element_id

    def remove_element(self, screen_id, element_id):
        """Take an element out of the layout: the author's own goes away, one of the screen's
        own goes back to the engine's place and look."""
        old = self.layout(screen_id)
        if old is None or old.element(element_id) is None:
            return
        layout = old.without_element(element_id)
        self._run(screen_id, layout, old, f"Remove {screen_id} ▸ {element_id}")

    def set_background(self, screen_id, **fields):
        old = self.layout(screen_id)
        layout = replace(old or MenuLayout(self._screen(screen_id)), **fields)
        self._run(screen_id, layout, old, f"Edit {screen_id} background")

    def reset(self, screen_id):
        """The screen back to the engine's own layout."""
        old = self.layout(screen_id)
        if old is not None:
            self._run(screen_id, None, old, f"Reset {screen_id} layout")

    def copy_from(self, screen_id, source_id):
        """The elements another screen's layout shares with this one (same names), its
        background and the author's own elements, copied onto this screen."""
        source = self.layout(source_id)
        if source is None:
            raise MenuLayoutAuthoringError(f"{source_id} has no layout to copy")
        names = set(self.element_ids(screen_id)) | {
            e.element_id for e in source.elements if e.extra
        }
        elements = tuple(e for e in source.elements if e.element_id in names)
        layout = replace(source, screen_id=self._screen(screen_id), elements=elements)
        self._run(screen_id, layout, self.layout(screen_id), f"Copy {source_id} to {screen_id}")
        return layout

    def set_theme(self, theme):
        if not isinstance(theme, MenuTheme):
            raise TypeError("a MenuTheme is required")
        old = self.theme()
        empty = theme == MenuTheme()
        self.document.execute(
            _ProfileCommand(
                self.library, self.THEME, "default", None if empty else theme, old, "Menu theme"
            )
        )

    def change_theme(self, **fields):
        self.set_theme(replace(self.theme() or MenuTheme(), **fields))

    # --- helpers ------------------------------------------------------------------------
    def _screen(self, screen_id):
        screen_id = str(screen_id)
        if base_screen(screen_id) not in SCREEN_IDS:
            raise KeyError(f"unknown menu screen: {screen_id}")
        return screen_id

    def _run(self, screen_id, new, old, label):
        if new is not None and not new.elements and new == MenuLayout(new.screen_id):
            new = None  # nothing left to say: the engine's own layout
        self.document.execute(
            _ProfileCommand(self.library, self.LAYOUT, screen_id, new, old, label)
        )
