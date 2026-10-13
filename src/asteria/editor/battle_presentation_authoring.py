from __future__ import annotations

from dataclasses import dataclass


class BattlePresentationAuthoringError(RuntimeError):
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
class BattlePresentationSection:
    section_id: str
    label: str
    categories: tuple[str, ...]
    detail_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BattlePresentationInformationArchitecture:
    sections: tuple[BattlePresentationSection, ...] = (
        BattlePresentationSection(
            "visuals",
            "Combatants & Layout",
            ("combatant_visuals", "sideview_templates", "portrait_templates", "party_layout"),
            (
                "Preview",
                "Selected Combatant",
                "Visual States",
                "Anchors & Transform",
                "Adaptive Layout",
            ),
        ),
        BattlePresentationSection(
            "motion",
            "Animation & Motion",
            ("motion_sequences", "animation_timing", "director", "layering"),
            ("Timeline", "Selected Beat", "Timing", "Direction Rules", "Channels / Layers"),
        ),
        BattlePresentationSection(
            "feedback",
            "VFX / Camera / Audio / Feedback",
            ("feedback", "ui_theme"),
            ("Value Feedback", "Labels", "VFX", "Audio", "Theme"),
        ),
        BattlePresentationSection(
            "hud",
            "HUD & Interaction",
            ("hud", "ui_layout", "ui_polish", "action_menu", "interaction", "action_workflows"),
            ("HUD Resources", "Statuses", "Layout", "Action Layers", "Workflow", "Polish"),
        ),
        BattlePresentationSection(
            "result",
            "Battle Result",
            ("results",),
            ("Headline", "Currencies", "Progression", "Items"),
        ),
    )
    primary_navigation: str = "presentation_section_sidebar"
    secondary_navigation: str = "category_tabs"
    browser_pattern: str = "search_filter_list"
    inspector_pattern: str = "preview_plus_contextual_detail"
    progressive_disclosure: bool = True
    live_preview_expected: bool = True
    show_all_categories_simultaneously: bool = False
    show_all_details_simultaneously: bool = False

    def section(self, key):
        return next((x for x in self.sections if x.section_id == str(key)), None)


class BattlePresentationAuthoringController:
    information_architecture = BattlePresentationInformationArchitecture()

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise BattlePresentationAuthoringError("project required")
        return self.document.project

    @property
    def library(self):
        return self.project.battle_presentation_library

    def _execute(self, c):
        self.document.execute(c)
        return c

    def create(self, category, profile_id, value):
        category = str(category)
        profile_id = str(profile_id)
        if self.library.get(category, profile_id) is not None:
            raise BattlePresentationAuthoringError(
                f"duplicate presentation profile: {category}/{profile_id}"
            )
        self.library._validate_type(category, value)
        self._execute(
            _ProfileCommand(
                self.library,
                category,
                profile_id,
                value,
                None,
                f"Add Battle Presentation {category}/{profile_id}",
            )
        )
        return value

    def edit(self, category, profile_id, value):
        category = str(category)
        profile_id = str(profile_id)
        old = self.library.get(category, profile_id)
        if old is None:
            raise BattlePresentationAuthoringError(
                f"unknown presentation profile: {category}/{profile_id}"
            )
        self.library._validate_type(category, value)
        self._execute(
            _ProfileCommand(
                self.library,
                category,
                profile_id,
                value,
                old,
                f"Edit Battle Presentation {category}/{profile_id}",
            )
        )
        return value

    def delete(self, category, profile_id):
        category = str(category)
        profile_id = str(profile_id)
        old = self.library.get(category, profile_id)
        if old is None:
            raise BattlePresentationAuthoringError(
                f"unknown presentation profile: {category}/{profile_id}"
            )
        self._execute(
            _ProfileCommand(
                self.library,
                category,
                profile_id,
                None,
                old,
                f"Delete Battle Presentation {category}/{profile_id}",
            )
        )

    def duplicate(self, category, profile_id, new_profile_id):
        value = self.library.require(category, profile_id)
        # immutable profile objects may be shared safely until edited/replaced.
        return self.create(category, new_profile_id, value)

    def definitions(self, category):
        return tuple(self.library.require(category, x) for x in self.library.ids(category))

    def validate(self):
        try:
            self.project.validate()
        except Exception as exc:
            return (str(exc),)
        return ()
