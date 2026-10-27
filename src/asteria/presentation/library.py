from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass

from .battle_action_menu import BattleActionMenuPolicy
from .battle_action_workflow import BattleActionWorkflowDefinition
from .battle_animation_timing import BattleAnimationTimingProfile
from .battle_combatant_visuals import (
    BattleCombatantVisualProfile,
    BattleVisualAssetSet,
    BattleVisualStateDefinition,
    BattleVisualTransform,
)
from .battle_feedback import BattleFeedbackProfile
from .battle_hud import BattleHudProfile
from .battle_interaction import BattleInteractionLayer, BattleInteractionProfile
from .battle_motion_sequence import BattleMotionBeat, BattleMotionSequence
from .battle_party_layout import BattlePartyLayoutPolicy
from .battle_portrait_party_template import (
    BattlePortraitPartyTemplateProfile,
    BattlePortraitPartyZone,
)
from .battle_presentation_director import BattlePresentationDirectorProfile
from .battle_presentation_layering import BattlePresentationLayeringProfile
from .battle_result import BattleResultProfile
from .battle_sideview_template import BattleSideviewTemplateProfile, BattleSideviewZone
from .battle_ui import BattleUiLayoutProfile
from .battle_ui_polish import BattleUiPolishProfile
from .battle_ui_renderer import BattleUiTheme
from .creature_screens import CreatureScreenSettings
from .dialogue_window import DialogueWindowStyle
from .menu_layout import MenuBitmapFont, MenuLayout, MenuTheme
from .retired_screens import RETIRED_CATEGORIES


@dataclass(frozen=True, slots=True)
class BattlePresentationProfileRef:
    category: str
    profile_id: str


class BattlePresentationLibrary:
    """Canonical project-owned battle presentation profiles.

    Gameplay never depends on this library. It stores presentation-only data and
    can resolve records back into the runtime profile types used by presentation.
    """

    SCHEMA = "asteria.battle_presentation_library"
    VERSION = 1

    CATEGORIES = (
        "combatant_visuals",
        "feedback",
        "hud",
        "ui_layout",
        "ui_polish",
        "sideview_templates",
        "portrait_templates",
        "animation_timing",
        "director",
        "layering",
        "action_menu",
        "interaction",
        "results",
        "party_layout",
        "ui_theme",
        "motion_sequences",
        "action_workflows",
        "menu_layout",  # one per menu screen, keyed by its screen id (U2)
        "menu_theme",
        "bitmap_font",  # fonts drawn by hand, keyed by font id (V1)
        "dialogue_window",  # the picture message window, record "default" (V2)
        "creature_screen",  # a creature game's own screens, by manifest path (V5)
    )
    # written only when they hold something: older project files stay byte-identical
    OPTIONAL_CATEGORIES = (
        "menu_layout",
        "menu_theme",
        "bitmap_font",
        "dialogue_window",
        "creature_screen",
    )

    def __init__(self):
        self._records = {k: {} for k in self.CATEGORIES}
        self.retired = {}  # D98: an old file's retired screen records, until moved

    def categories(self):
        return self.CATEGORIES

    def ids(self, category):
        return tuple(sorted(self._records[self._category(category)]))

    def _category(self, category):
        category = str(category)
        if category not in self._records:
            raise KeyError(f"unknown battle presentation category: {category}")
        return category

    def add(self, category, profile_id, value):
        category = self._category(category)
        profile_id = str(profile_id).strip()
        if not profile_id:
            raise ValueError("profile_id is required")
        if profile_id in self._records[category]:
            raise ValueError(f"duplicate presentation profile: {category}/{profile_id}")
        self._validate_type(category, value)
        self._records[category][profile_id] = value
        return value

    def set(self, category, profile_id, value):
        category = self._category(category)
        profile_id = str(profile_id).strip()
        if not profile_id:
            raise ValueError("profile_id is required")
        self._validate_type(category, value)
        self._records[category][profile_id] = value
        return value

    def get(self, category, profile_id):
        return self._records[self._category(category)].get(str(profile_id))

    def require(self, category, profile_id):
        value = self.get(category, profile_id)
        if value is None:
            raise KeyError(f"{category}/{profile_id}")
        return value

    def remove(self, category, profile_id):
        return self._records[self._category(category)].pop(str(profile_id))

    def validate(self):
        for category, mapping in self._records.items():
            for value in mapping.values():
                self._validate_type(category, value)
        return True

    @staticmethod
    def _expected(category):
        return {
            "combatant_visuals": BattleCombatantVisualProfile,
            "feedback": BattleFeedbackProfile,
            "hud": BattleHudProfile,
            "ui_layout": BattleUiLayoutProfile,
            "ui_polish": BattleUiPolishProfile,
            "sideview_templates": BattleSideviewTemplateProfile,
            "portrait_templates": BattlePortraitPartyTemplateProfile,
            "animation_timing": BattleAnimationTimingProfile,
            "director": BattlePresentationDirectorProfile,
            "layering": BattlePresentationLayeringProfile,
            "action_menu": BattleActionMenuPolicy,
            "interaction": BattleInteractionProfile,
            "results": BattleResultProfile,
            "party_layout": BattlePartyLayoutPolicy,
            "ui_theme": BattleUiTheme,
            "motion_sequences": BattleMotionSequence,
            "action_workflows": BattleActionWorkflowDefinition,
            "menu_layout": MenuLayout,
            "menu_theme": MenuTheme,
            "bitmap_font": MenuBitmapFont,
            "dialogue_window": DialogueWindowStyle,
            "creature_screen": CreatureScreenSettings,
        }[category]

    def _validate_type(self, category, value):
        cls = self._expected(category)
        if not isinstance(value, cls):
            raise TypeError(f"{category} values must be {cls.__name__}")

    @staticmethod
    def _plain(value):
        if hasattr(value, "to_data"):
            return value.to_data()
        if is_dataclass(value):
            raw = asdict(value)
            return raw
        raise TypeError(f"presentation value is not serializable: {type(value).__name__}")

    @staticmethod
    def _visual_to_data(value):
        return {
            "profile_id": value.profile_id,
            "assets": asdict(value.assets),
            "states": [asdict(x) for x in value.states],
            "transform": asdict(value.transform),
            "battlefield_visible": value.battlefield_visible,
            "hud_visible": value.hud_visible,
        }

    @staticmethod
    def _visual_from_data(data):
        return BattleCombatantVisualProfile(
            data["profile_id"],
            BattleVisualAssetSet(**data["assets"]),
            tuple(BattleVisualStateDefinition(**x) for x in data["states"]),
            BattleVisualTransform(**data["transform"]),
            bool(data.get("battlefield_visible", True)),
            bool(data.get("hud_visible", True)),
        )

    @staticmethod
    def _interaction_to_data(value):
        return {
            "layers": [asdict(x) for x in value.layers],
            "page_size": value.page_size,
            "max_primary_layers": value.max_primary_layers,
        }

    @staticmethod
    def _interaction_from_data(data):
        return BattleInteractionProfile(
            tuple(BattleInteractionLayer(**x) for x in data.get("layers", ())),
            page_size=data.get("page_size", 8),
            max_primary_layers=data.get("max_primary_layers", 6),
        )

    @staticmethod
    def _sideview_to_data(value):
        return {
            "template_id": value.template_id,
            "left_zone": asdict(value.left_zone),
            "right_zone": asdict(value.right_zone),
            "left_hud_zone_id": value.left_hud_zone_id,
            "right_hud_zone_id": value.right_hud_zone_id,
            "battlefield_center_x": value.battlefield_center_x,
            "max_visible_per_zone": value.max_visible_per_zone,
        }

    @staticmethod
    def _sideview_from_data(data):
        return BattleSideviewTemplateProfile(
            data["template_id"],
            BattleSideviewZone(**data["left_zone"]),
            BattleSideviewZone(**data["right_zone"]),
            left_hud_zone_id=data.get("left_hud_zone_id", "hud.left"),
            right_hud_zone_id=data.get("right_hud_zone_id", "hud.right"),
            battlefield_center_x=data.get("battlefield_center_x", 160.0),
            max_visible_per_zone=data.get("max_visible_per_zone"),
        )

    @staticmethod
    def _portrait_to_data(value):
        return {
            "template_id": value.template_id,
            "battlefield_zone": asdict(value.battlefield_zone),
            "portrait_hud_zone_id": value.portrait_hud_zone_id,
            "battlefield_hud_zone_id": value.battlefield_hud_zone_id,
            "hide_portrait_party_bodies": value.hide_portrait_party_bodies,
            "max_visible_battlefield_members": value.max_visible_battlefield_members,
        }

    @staticmethod
    def _portrait_from_data(data):
        return BattlePortraitPartyTemplateProfile(
            data["template_id"],
            BattlePortraitPartyZone(**data["battlefield_zone"]),
            portrait_hud_zone_id=data.get("portrait_hud_zone_id", "hud.party"),
            battlefield_hud_zone_id=data.get("battlefield_hud_zone_id", "hud.battlefield"),
            hide_portrait_party_bodies=data.get("hide_portrait_party_bodies", True),
            max_visible_battlefield_members=data.get("max_visible_battlefield_members"),
        )

    @staticmethod
    def _motion_to_data(value):
        return {
            "sequence_id": value.sequence_id,
            "duration": value.duration,
            "beats": [asdict(x) for x in value.beats],
            "recovery_at": value.recovery_at,
        }

    @staticmethod
    def _motion_from_data(data):
        return BattleMotionSequence(
            data["sequence_id"],
            data["duration"],
            tuple(BattleMotionBeat(**x) for x in data.get("beats", ())),
            recovery_at=data.get("recovery_at"),
        )

    def encode_for_editor(self, category, value):
        """Like ``_encode`` but with every field shown: the optional layout options (menu over
        the stage, row buttons, bars under the feet, the right side's front and column spacing)
        stay reachable in the editor even while they hold their default."""
        if category == "ui_layout":
            data = asdict(value)
            if data.get("stage_front_right") is None:
                data["stage_front_right"] = data["stage_front"]
            if data.get("column_spacing_right") is None:
                data["column_spacing_right"] = data["column_spacing"]
            return data
        if category == "action_workflows":  # every step shows its options list, even empty
            data = self._encode(category, value)
            for step in data.get("steps", ()):
                step.setdefault("options", [])
            return data
        return self._encode(category, value)

    def decode_from_editor(self, category, data):
        if category == "ui_layout":
            data = dict(data)
            if data.get("stage_front_right") == data.get("stage_front"):
                data["stage_front_right"] = None
            if data.get("column_spacing_right") == data.get("column_spacing", 0.0):
                data["column_spacing_right"] = None
        return self._decode(category, data)

    def _encode(self, category, value):
        if category == "combatant_visuals":
            return self._visual_to_data(value)
        if category == "interaction":
            return self._interaction_to_data(value)
        if category == "sideview_templates":
            return self._sideview_to_data(value)
        if category == "portrait_templates":
            return self._portrait_to_data(value)
        if category == "motion_sequences":
            return self._motion_to_data(value)
        if category == "ui_layout":
            data = asdict(value)
            if data.get("stage_front") == 0.30:  # optional: left out at its default
                data.pop("stage_front")
            if not data.get("row_buttons"):
                data.pop("row_buttons", None)
            if data.get("column_size") == 3:
                data.pop("column_size")
            if data.get("stage_front_right") is None:
                data.pop("stage_front_right", None)
            if not data.get("column_spacing"):
                data.pop("column_spacing", None)
            if data.get("column_spacing_right") is None:
                data.pop("column_spacing_right", None)
            if data.get("feet_on_ground", True):
                data.pop("feet_on_ground", None)
            if data.get("overhead_below", True):
                data.pop("overhead_below", None)
            if data.get("overhead_bars", True):
                data.pop("overhead_bars", None)
            if not data.get("command_counts"):
                data.pop("command_counts", None)
            if not data.get("menu_over_stage"):
                data.pop("menu_over_stage", None)
            for key in ("stage_template", "command_pages"):
                if not data.get(key):
                    data.pop(key, None)
            if data.get("hud_portraits") == "left":
                data.pop("hud_portraits")
            if not data.get("hud_portrait_size"):
                data.pop("hud_portrait_size", None)
            return data
        return self._plain(value)

    def _decode(self, category, data):
        if category == "combatant_visuals":
            return self._visual_from_data(data)
        if category == "interaction":
            return self._interaction_from_data(data)
        if category == "sideview_templates":
            return self._sideview_from_data(data)
        if category == "portrait_templates":
            return self._portrait_from_data(data)
        if category == "motion_sequences":
            return self._motion_from_data(data)
        if category == "ui_layout":
            return BattleUiLayoutProfile(**data)
        cls = self._expected(category)
        if hasattr(cls, "from_data"):
            return cls.from_data(data)
        return cls(**data)

    def to_data(self):
        self.validate()
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "categories": {
                category: {
                    key: self._encode(category, value) for key, value in sorted(mapping.items())
                }
                for category, mapping in self._records.items()
                if mapping or category not in self.OPTIONAL_CATEGORIES
            },
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle presentation library")
        result = cls()
        raw_categories = dict(data.get("categories", {}))
        # the screen records retired in D98: kept as data for the project to move (Project)
        result.retired = {
            k: raw_categories.pop(k) for k in RETIRED_CATEGORIES if k in raw_categories
        }
        unknown = set(raw_categories) - set(cls.CATEGORIES)
        if unknown:
            raise ValueError(
                "unknown battle presentation categories: " + ", ".join(sorted(unknown))
            )
        for category in cls.CATEGORIES:
            for key, raw in raw_categories.get(category, {}).items():
                result.add(category, key, result._decode(category, raw))
        return result
