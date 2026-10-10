from __future__ import annotations

from dataclasses import dataclass


class RuntimeRpgUiAuthoringError(RuntimeError):
    pass


@dataclass(slots=True)
class _ProfileCommand:
    library: object
    category: str
    profile_id: str
    new_value: object | None
    old_value: object | None
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        if self.new_value is None:
            if self.library.get(self.category, self.profile_id) is not None:
                self.library.remove(self.category, self.profile_id)
        else:
            self.library.set(self.category, self.profile_id, self.new_value)

    def undo(self):
        if self.old_value is None:
            if self.library.get(self.category, self.profile_id) is not None:
                self.library.remove(self.category, self.profile_id)
        else:
            self.library.set(self.category, self.profile_id, self.old_value)


@dataclass(frozen=True, slots=True)
class RuntimeRpgUiSection:
    section_id: str
    label: str
    categories: tuple[str, ...]
    detail_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeRpgUiInformationArchitecture:
    sections: tuple[RuntimeRpgUiSection, ...] = (
        RuntimeRpgUiSection(
            "character",
            "Character",
            ("rpg_character_screen",),
            (
                "Preview",
                "Section Order",
                "Stats & Resources",
                "Equipment Summary",
                "Abilities",
                "Progression",
                "Status",
            ),
        ),
        RuntimeRpgUiSection(
            "build",
            "Build & Progression",
            ("rpg_equipment_screen", "rpg_ability_screen", "rpg_progression_screen"),
            (
                "Preview",
                "Equipment & Accessories",
                "Sockets / Attachments",
                "Skills",
                "Passives",
                "Skill Trees",
                "Growth",
            ),
        ),
        RuntimeRpgUiSection(
            "party",
            "Party & Formation",
            ("rpg_party_screen",),
            ("Preview", "Active Party", "Reserve", "Formation Slots", "Member Labels", "Density / Overflow"),
        ),
        RuntimeRpgUiSection(
            "inventory",
            "Inventory",
            ("rpg_inventory_screen",),
            ("Preview", "Groups", "Items", "Labels", "Visible Limits"),
        ),
    )
    primary_navigation: str = "runtime_ui_section_sidebar"
    secondary_navigation: str = "screen_profile_tabs"
    browser_pattern: str = "search_filter_list"
    inspector_pattern: str = "preview_plus_contextual_detail"
    progressive_disclosure: bool = True
    live_preview_expected: bool = True
    show_all_screens_simultaneously: bool = False
    show_all_details_simultaneously: bool = False

    def section(self, key):
        return next((x for x in self.sections if x.section_id == str(key)), None)


class RuntimeRpgUiAuthoringController:
    information_architecture = RuntimeRpgUiInformationArchitecture()
    CATEGORIES = (
        "rpg_character_screen",
        "rpg_equipment_screen",
        "rpg_ability_screen",
        "rpg_progression_screen",
        "rpg_inventory_screen",
        "rpg_party_screen",
    )

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise RuntimeRpgUiAuthoringError("project required")
        return self.document.project

    @property
    def library(self):
        return self.project.battle_presentation_library

    def _category(self, c):
        c = str(c)
        if c not in self.CATEGORIES:
            raise KeyError(c)
        return c

    def create(self, category, profile_id, value):
        category = self._category(category)
        profile_id = str(profile_id).strip()
        if self.library.get(category, profile_id) is not None:
            raise RuntimeRpgUiAuthoringError(f"duplicate runtime UI profile: {category}/{profile_id}")
        self.library._validate_type(category, value)
        self.document.execute(
            _ProfileCommand(self.library, category, profile_id, value, None, f"Add Runtime UI {category}/{profile_id}")
        )
        return value

    def edit(self, category, profile_id, value):
        category = self._category(category)
        profile_id = str(profile_id)
        old = self.library.get(category, profile_id)
        if old is None:
            raise RuntimeRpgUiAuthoringError(f"unknown runtime UI profile: {category}/{profile_id}")
        self.library._validate_type(category, value)
        self.document.execute(
            _ProfileCommand(self.library, category, profile_id, value, old, f"Edit Runtime UI {category}/{profile_id}")
        )
        return value

    def delete(self, category, profile_id):
        category = self._category(category)
        profile_id = str(profile_id)
        old = self.library.get(category, profile_id)
        if old is None:
            raise RuntimeRpgUiAuthoringError(f"unknown runtime UI profile: {category}/{profile_id}")
        self.document.execute(
            _ProfileCommand(self.library, category, profile_id, None, old, f"Delete Runtime UI {category}/{profile_id}")
        )

    def duplicate(self, category, profile_id, new_profile_id):
        return self.create(category, new_profile_id, self.library.require(category, profile_id))

    def definitions(self, category):
        category = self._category(category)
        return tuple(self.library.require(category, x) for x in self.library.ids(category))

    def validate(self):
        try:
            self.project.validate()
        except Exception as exc:
            return (str(exc),)
        return ()
