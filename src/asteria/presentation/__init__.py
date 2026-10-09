from .battle import (
    BattleCombatantVisual,
    BattlePresentationCoordinator,
    BattlePresentationEvent,
    BattlePresentationEventKind,
    BattlePresentationScene,
    BattleVisualAnchor,
)
from .battle_runtime import (
    BattleAnimationRole,
    BattleCombatantAnimator,
    BattlePresentationFrame,
    CombatantOverlay,
    BattlePresentationRuntime,
)

__all__ = [
    "BattleAnimationRole",
    "BattleCombatantAnimator",
    "BattleCombatantVisual",
    "BattlePresentationCoordinator",
    "BattlePresentationEvent",
    "BattlePresentationEventKind",
    "BattlePresentationFrame",
    "BattlePresentationRuntime",
    "BattlePresentationScene",
    "BattleVisualAnchor",
    "CombatantOverlay",
]

from .battle_feedback import (
    BattleAudioCue,
    BattleFeedbackLabel,
    BattleFeedbackProfile,
    BattleFeedbackRuntime,
    BattleFloatingValue,
    BattleValueKind,
    BattleVfxCue,
    gauge_threshold_payloads,
    resolved_value_payload,
)

from .battle_camera_feedback import (
    BattleCameraFeedbackFrame,
    BattleCameraFeedbackRuntime,
    BattleCameraImpulse,
    BattleScreenFxCue,
    BattleTargetIndicator,
)

__all__.extend([
    "BattleCameraFeedbackFrame",
    "BattleCameraFeedbackRuntime",
    "BattleCameraImpulse",
    "BattleScreenFxCue",
    "BattleTargetIndicator",
])

from .battle_hud import (
    BattleHudGauge,
    BattleHudMember,
    BattleHudProfile,
    BattleHudResourceStyle,
    BattleHudRuntime,
    BattleHudStatusIcon,
    BattleHudStatusStyle,
)

__all__.extend([
    "BattleHudGauge",
    "BattleHudMember",
    "BattleHudProfile",
    "BattleHudResourceStyle",
    "BattleHudRuntime",
    "BattleHudStatusIcon",
    "BattleHudStatusStyle",
])

from .battle_turn_timeline import (
    BattleCastEntry,
    BattleTurnEntry,
    BattleTurnTimelineRuntime,
    BattleTurnTimelineView,
)

__all__.extend([
    "BattleCastEntry",
    "BattleTurnEntry",
    "BattleTurnTimelineRuntime",
    "BattleTurnTimelineView",
])

from .battle_result import (
    BattleCurrencyRewardView,
    BattleItemRewardView,
    BattleProgressionRewardView,
    BattleResultPresentationRuntime,
    BattleResultProfile,
    BattleResultView,
)

__all__.extend([
    "BattleCurrencyRewardView",
    "BattleItemRewardView",
    "BattleProgressionRewardView",
    "BattleResultPresentationRuntime",
    "BattleResultProfile",
    "BattleResultView",
])

from .battle_ui import (
    BattleUiComposer,
    BattleUiFrame,
    BattleUiGaugeBar,
    BattleUiIcon,
    BattleUiLayoutProfile,
    BattleUiMarker,
    BattleUiPanel,
    BattleUiText,
)

__all__.extend([
    "BattleUiComposer",
    "BattleUiFrame",
    "BattleUiGaugeBar",
    "BattleUiIcon",
    "BattleUiLayoutProfile",
    "BattleUiMarker",
    "BattleUiPanel",
    "BattleUiText",
])

from .battle_ui_renderer import (
    BattleUiRenderer,
    BattleUiTheme,
    HeadlessBattleUiBackend,
)

__all__.extend([
    "BattleUiRenderer",
    "BattleUiTheme",
    "HeadlessBattleUiBackend",
])

from .battle_screen import BattleScreenRenderResult, BattleScreenRuntime

__all__.extend([
    "BattleScreenRenderResult",
    "BattleScreenRuntime",
])

from .battle_party_layout import (
    BattlePartyLayoutPolicy,
    BattlePartyLayoutResult,
    BattlePartyPlacement,
    BattlePartyZoneLayout,
)

__all__.extend([
    "BattlePartyLayoutPolicy",
    "BattlePartyLayoutResult",
    "BattlePartyPlacement",
    "BattlePartyZoneLayout",
])

from .battle_action_menu import (
    BattleActionEntry,
    BattleActionMenuPolicy,
    BattleActionMenuRuntime,
    BattleActionMenuView,
)

__all__.extend([
    "BattleActionEntry",
    "BattleActionMenuPolicy",
    "BattleActionMenuRuntime",
    "BattleActionMenuView",
])

from .battle_action_workflow import (
    BattleActionWorkflowDefinition,
    BattleActionWorkflowRuntime,
    BattleActionWorkflowView,
    BattleWorkflowOption,
    BattleWorkflowSelection,
    BattleWorkflowStep,
)

__all__.extend([
    "BattleActionWorkflowDefinition",
    "BattleActionWorkflowRuntime",
    "BattleActionWorkflowView",
    "BattleWorkflowOption",
    "BattleWorkflowSelection",
    "BattleWorkflowStep",
])

from .battle_presentation_director import (
    BattleDirectedEvent,
    BattlePresentationDirection,
    BattlePresentationDirector,
    BattlePresentationDirectorAdvance,
    BattlePresentationDirectorProfile,
    BattlePresentationDirectorRule,
)

__all__.extend([
    "BattleDirectedEvent",
    "BattlePresentationDirection",
    "BattlePresentationDirector",
    "BattlePresentationDirectorAdvance",
    "BattlePresentationDirectorProfile",
    "BattlePresentationDirectorRule",
])

from .battle_animation_timing import (
    BattleAnimationTimingProfile,
    BattleAnimationTimingRule,
    BattleHitRhythm,
    easing_value,
)

__all__.extend([
    "BattleAnimationTimingProfile",
    "BattleAnimationTimingRule",
    "BattleHitRhythm",
    "easing_value",
])

from .battle_presentation_layering import (
    BattlePresentationChannelPolicy,
    BattlePresentationLayerContext,
    BattlePresentationLayeringProfile,
    BattlePresentationLayeringRuntime,
)

__all__.extend([
    "BattlePresentationChannelPolicy",
    "BattlePresentationLayerContext",
    "BattlePresentationLayeringProfile",
    "BattlePresentationLayeringRuntime",
])

from .battle_ui_polish import BattleUiPolishProfile

__all__.append("BattleUiPolishProfile")

from .rpg_character_screen import (
    CharacterScreenAbilityView,
    CharacterScreenEquipmentItemView,
    CharacterScreenEquipmentSlotView,
    CharacterScreenProfile,
    CharacterScreenProgressionView,
    CharacterScreenResourceView,
    CharacterScreenRuntime,
    CharacterScreenSection,
    CharacterScreenStatView,
    CharacterScreenView,
)

__all__.extend([
    "CharacterScreenAbilityView",
    "CharacterScreenEquipmentItemView",
    "CharacterScreenEquipmentSlotView",
    "CharacterScreenProfile",
    "CharacterScreenProgressionView",
    "CharacterScreenResourceView",
    "CharacterScreenRuntime",
    "CharacterScreenSection",
    "CharacterScreenStatView",
    "CharacterScreenView",
])

from .rpg_party_screen import (
    PartyFormationSlotView,
    PartyGroupView,
    PartyMemberPresentation,
    PartyScreenProfile,
    PartyScreenRuntime,
    PartyScreenView,
)

__all__.extend([
    "PartyFormationSlotView",
    "PartyGroupView",
    "PartyMemberPresentation",
    "PartyScreenProfile",
    "PartyScreenRuntime",
    "PartyScreenView",
])

from .rpg_equipment_screen import (
    EquipmentCandidateView,
    EquipmentGrowthView,
    EquipmentScreenProfile,
    EquipmentScreenRuntime,
    EquipmentScreenView,
    EquipmentSlotView,
    EquipmentSocketView,
    EquippedItemView,
)

__all__.extend([
    "EquipmentCandidateView",
    "EquipmentGrowthView",
    "EquipmentScreenProfile",
    "EquipmentScreenRuntime",
    "EquipmentScreenView",
    "EquipmentSlotView",
    "EquipmentSocketView",
    "EquippedItemView",
])

from .rpg_ability_screen import (
    AbilityCollectionEntry,
    AbilityCollectionGroup,
    AbilityScreenProfile,
    AbilityScreenRuntime,
    AbilityScreenView,
    PassiveCollectionEntry,
)

__all__.extend([
    "AbilityCollectionEntry",
    "AbilityCollectionGroup",
    "AbilityScreenProfile",
    "AbilityScreenRuntime",
    "AbilityScreenView",
    "PassiveCollectionEntry",
])

from .rpg_progression_screen import (
    ProgressionGraphView,
    ProgressionNodeView,
    ProgressionRequirementView,
    ProgressionScreenProfile,
    ProgressionScreenRuntime,
    ProgressionScreenView,
)

__all__.extend([
    "ProgressionGraphView",
    "ProgressionNodeView",
    "ProgressionRequirementView",
    "ProgressionScreenProfile",
    "ProgressionScreenRuntime",
    "ProgressionScreenView",
])

from .rpg_inventory_screen import (
    InventoryGroupView,
    InventoryItemView,
    InventoryScreenProfile,
    InventoryScreenRuntime,
    InventoryScreenView,
)

__all__.extend([
    "InventoryGroupView",
    "InventoryItemView",
    "InventoryScreenProfile",
    "InventoryScreenRuntime",
    "InventoryScreenView",
])

from .battle_interaction import (
    BattleInteractionContext,
    BattleInteractionLayer,
    BattleInteractionProfile,
    BattleInteractionRuntime,
    BattleInteractionView,
)

from .battle_information import (
    BattleInformationItem,
    BattleInformationPolicy,
    BattleInformationRule,
    BattleInformationRuntime,
    BattleInformationView,
    BattleRosterDensityPolicy,
    BattleRosterSummary,
)

from .battle_combatant_visuals import (
    BattleCombatantVisualProfile,
    BattleCombatantVisualRuntime,
    BattleCombatantVisualState,
    BattleVisualAssetSet,
    BattleVisualStateDefinition,
    BattleVisualTransform,
    default_jrpg_visual_states,
)

from .battle_ui_assembly import (
    BattleUiActionSurface,
    BattleUiAssemblyFrame,
    BattleUiAssemblyRuntime,
    BattleUiBattlefieldVisual,
    BattleUiMemberCard,
)

from .battle_motion_sequence import (
    BattleMotionBeat,
    BattleMotionFrame,
    BattleMotionMetrics,
    BattleMotionRuntime,
    BattleMotionSequence,
    make_reference_smooth_attack_sequence,
)

from .battle_sideview_template import (
    BattleSideviewPlacement,
    BattleSideviewTemplateProfile,
    BattleSideviewTemplateResult,
    BattleSideviewTemplateRuntime,
    BattleSideviewZone,
    default_sideview_jrpg_profile,
)

from .battle_portrait_party_template import (
    BattlePortraitPartyPlacement,
    BattlePortraitPartyTemplateProfile,
    BattlePortraitPartyTemplateResult,
    BattlePortraitPartyTemplateRuntime,
    BattlePortraitPartyZone,
    default_dungeon_portrait_party_profile,
)

from .battle_render_performance import (
    BattleAssetPreloadRegistry,
    BattleFrameBudgetMetrics,
    BattleFrameBudgetTracker,
    BattleRenderBatch,
    BattleRenderBatcher,
    BattleRenderCullResult,
    BattleRenderDraw,
    BattleRenderVisibilityCuller,
    BattleTransientObject,
    BattleTransientPool,
)

from .library import BattlePresentationLibrary, BattlePresentationProfileRef

# Generic composable presentation extensions (Asset/Presentation branch)
from .canonical import *
from .runtime import *
from .bridge import *
from .editor_model import *
from .workspace import *
from .preview import *
from .visual_authoring import *
from .visual_editing import *
from .workspace_controller import *
from .fidelity import *
from .composition import *
from .choreography import *
from .performance import *
from .fidelity_editor import *
# Export both legacy battle-presentation and generic composable-presentation APIs.
__all__ = sorted(set(__all__) | {name for name in globals() if not name.startswith('_')})
