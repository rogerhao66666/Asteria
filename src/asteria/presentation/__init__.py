# The package's names are imported when first used (PEP 562): importing one module of it
# no longer imports every other one (and what they import), which made a cycle with
# asteria.assets and slowed every import. Generated from the eager imports it replaces.

from importlib import import_module

_EXPORTS = {  # name -> (module, attribute; None: the module itself)
    "AbilityCollectionEntry": (
        "asteria.presentation.screens.ability",
        "AbilityCollectionEntry",
    ),
    "AbilityCollectionGroup": (
        "asteria.presentation.screens.ability",
        "AbilityCollectionGroup",
    ),
    "AbilityScreenProfile": ("asteria.presentation.screens.ability", "AbilityScreenProfile"),
    "AbilityScreenRuntime": ("asteria.presentation.screens.ability", "AbilityScreenRuntime"),
    "AbilityScreenView": ("asteria.presentation.screens.ability", "AbilityScreenView"),
    "BattleActionEntry": ("asteria.presentation.battle.action_menu", "BattleActionEntry"),
    "BattleActionMenuPolicy": (
        "asteria.presentation.battle.action_menu",
        "BattleActionMenuPolicy",
    ),
    "BattleActionMenuRuntime": (
        "asteria.presentation.battle.action_menu",
        "BattleActionMenuRuntime",
    ),
    "BattleActionMenuView": ("asteria.presentation.battle.action_menu", "BattleActionMenuView"),
    "BattleActionWorkflowDefinition": (
        "asteria.presentation.battle.action_workflow",
        "BattleActionWorkflowDefinition",
    ),
    "BattleActionWorkflowRuntime": (
        "asteria.presentation.battle.action_workflow",
        "BattleActionWorkflowRuntime",
    ),
    "BattleActionWorkflowView": (
        "asteria.presentation.battle.action_workflow",
        "BattleActionWorkflowView",
    ),
    "BattleAnimationRole": ("asteria.presentation.battle.runtime", "BattleAnimationRole"),
    "BattleAnimationTimingProfile": (
        "asteria.presentation.battle.animation_timing",
        "BattleAnimationTimingProfile",
    ),
    "BattleAnimationTimingRule": (
        "asteria.presentation.battle.animation_timing",
        "BattleAnimationTimingRule",
    ),
    "BattleAssetPreloadRegistry": (
        "asteria.presentation.battle.render_performance",
        "BattleAssetPreloadRegistry",
    ),
    "BattleAudioCue": ("asteria.presentation.battle.feedback", "BattleAudioCue"),
    "BattleCameraFeedbackFrame": (
        "asteria.presentation.battle.camera_feedback",
        "BattleCameraFeedbackFrame",
    ),
    "BattleCameraFeedbackRuntime": (
        "asteria.presentation.battle.camera_feedback",
        "BattleCameraFeedbackRuntime",
    ),
    "BattleCameraImpulse": ("asteria.presentation.battle.camera_feedback", "BattleCameraImpulse"),
    "BattleCastEntry": ("asteria.presentation.battle.turn_timeline", "BattleCastEntry"),
    "BattleCombatantAnimator": ("asteria.presentation.battle.runtime", "BattleCombatantAnimator"),
    "BattleCombatantVisual": ("asteria.presentation.battle.scene", "BattleCombatantVisual"),
    "BattleCombatantVisualProfile": (
        "asteria.presentation.battle.combatant_visuals",
        "BattleCombatantVisualProfile",
    ),
    "BattleCombatantVisualRuntime": (
        "asteria.presentation.battle.combatant_visuals",
        "BattleCombatantVisualRuntime",
    ),
    "BattleCombatantVisualState": (
        "asteria.presentation.battle.combatant_visuals",
        "BattleCombatantVisualState",
    ),
    "BattleCurrencyRewardView": ("asteria.presentation.battle.result", "BattleCurrencyRewardView"),
    "BattleDirectedEvent": (
        "asteria.presentation.battle.director",
        "BattleDirectedEvent",
    ),
    "BattleFeedbackLabel": ("asteria.presentation.battle.feedback", "BattleFeedbackLabel"),
    "BattleFeedbackProfile": ("asteria.presentation.battle.feedback", "BattleFeedbackProfile"),
    "BattleFeedbackRuntime": ("asteria.presentation.battle.feedback", "BattleFeedbackRuntime"),
    "BattleFloatingValue": ("asteria.presentation.battle.feedback", "BattleFloatingValue"),
    "BattleFrameBudgetMetrics": (
        "asteria.presentation.battle.render_performance",
        "BattleFrameBudgetMetrics",
    ),
    "BattleFrameBudgetTracker": (
        "asteria.presentation.battle.render_performance",
        "BattleFrameBudgetTracker",
    ),
    "BattleHitRhythm": ("asteria.presentation.battle.animation_timing", "BattleHitRhythm"),
    "BattleHudGauge": ("asteria.presentation.battle.hud", "BattleHudGauge"),
    "BattleHudMember": ("asteria.presentation.battle.hud", "BattleHudMember"),
    "BattleHudProfile": ("asteria.presentation.battle.hud", "BattleHudProfile"),
    "BattleHudResourceStyle": ("asteria.presentation.battle.hud", "BattleHudResourceStyle"),
    "BattleHudRuntime": ("asteria.presentation.battle.hud", "BattleHudRuntime"),
    "BattleHudStatusIcon": ("asteria.presentation.battle.hud", "BattleHudStatusIcon"),
    "BattleHudStatusStyle": ("asteria.presentation.battle.hud", "BattleHudStatusStyle"),
    "BattleInformationItem": ("asteria.presentation.battle.information", "BattleInformationItem"),
    "BattleInformationPolicy": (
        "asteria.presentation.battle.information",
        "BattleInformationPolicy",
    ),
    "BattleInformationRule": ("asteria.presentation.battle.information", "BattleInformationRule"),
    "BattleInformationRuntime": (
        "asteria.presentation.battle.information",
        "BattleInformationRuntime",
    ),
    "BattleInformationView": ("asteria.presentation.battle.information", "BattleInformationView"),
    "BattleInteractionContext": (
        "asteria.presentation.battle.interaction",
        "BattleInteractionContext",
    ),
    "BattleInteractionLayer": (
        "asteria.presentation.battle.interaction",
        "BattleInteractionLayer",
    ),
    "BattleInteractionProfile": (
        "asteria.presentation.battle.interaction",
        "BattleInteractionProfile",
    ),
    "BattleInteractionRuntime": (
        "asteria.presentation.battle.interaction",
        "BattleInteractionRuntime",
    ),
    "BattleInteractionView": ("asteria.presentation.battle.interaction", "BattleInteractionView"),
    "BattleItemRewardView": ("asteria.presentation.battle.result", "BattleItemRewardView"),
    "BattleMotionBeat": ("asteria.presentation.battle.motion_sequence", "BattleMotionBeat"),
    "BattleMotionFrame": ("asteria.presentation.battle.motion_sequence", "BattleMotionFrame"),
    "BattleMotionMetrics": ("asteria.presentation.battle.motion_sequence", "BattleMotionMetrics"),
    "BattleMotionRuntime": ("asteria.presentation.battle.motion_sequence", "BattleMotionRuntime"),
    "BattleMotionSequence": (
        "asteria.presentation.battle.motion_sequence",
        "BattleMotionSequence",
    ),
    "BattlePartyLayoutPolicy": (
        "asteria.presentation.battle.party_layout",
        "BattlePartyLayoutPolicy",
    ),
    "BattlePartyLayoutResult": (
        "asteria.presentation.battle.party_layout",
        "BattlePartyLayoutResult",
    ),
    "BattlePartyPlacement": ("asteria.presentation.battle.party_layout", "BattlePartyPlacement"),
    "BattlePartyZoneLayout": ("asteria.presentation.battle.party_layout", "BattlePartyZoneLayout"),
    "BattlePortraitPartyPlacement": (
        "asteria.presentation.battle.portrait_party_template",
        "BattlePortraitPartyPlacement",
    ),
    "BattlePortraitPartyTemplateProfile": (
        "asteria.presentation.battle.portrait_party_template",
        "BattlePortraitPartyTemplateProfile",
    ),
    "BattlePortraitPartyTemplateResult": (
        "asteria.presentation.battle.portrait_party_template",
        "BattlePortraitPartyTemplateResult",
    ),
    "BattlePortraitPartyTemplateRuntime": (
        "asteria.presentation.battle.portrait_party_template",
        "BattlePortraitPartyTemplateRuntime",
    ),
    "BattlePortraitPartyZone": (
        "asteria.presentation.battle.portrait_party_template",
        "BattlePortraitPartyZone",
    ),
    "BattlePresentationChannelPolicy": (
        "asteria.presentation.battle.layering",
        "BattlePresentationChannelPolicy",
    ),
    "BattlePresentationCoordinator": (
        "asteria.presentation.battle.scene",
        "BattlePresentationCoordinator",
    ),
    "BattlePresentationDirection": (
        "asteria.presentation.battle.director",
        "BattlePresentationDirection",
    ),
    "BattlePresentationDirector": (
        "asteria.presentation.battle.director",
        "BattlePresentationDirector",
    ),
    "BattlePresentationDirectorAdvance": (
        "asteria.presentation.battle.director",
        "BattlePresentationDirectorAdvance",
    ),
    "BattlePresentationDirectorProfile": (
        "asteria.presentation.battle.director",
        "BattlePresentationDirectorProfile",
    ),
    "BattlePresentationDirectorRule": (
        "asteria.presentation.battle.director",
        "BattlePresentationDirectorRule",
    ),
    "BattlePresentationEvent": ("asteria.presentation.battle.scene", "BattlePresentationEvent"),
    "BattlePresentationEventKind": (
        "asteria.presentation.battle.scene",
        "BattlePresentationEventKind",
    ),
    "BattlePresentationFrame": ("asteria.presentation.battle.runtime", "BattlePresentationFrame"),
    "BattlePresentationLayerContext": (
        "asteria.presentation.battle.layering",
        "BattlePresentationLayerContext",
    ),
    "BattlePresentationLayeringProfile": (
        "asteria.presentation.battle.layering",
        "BattlePresentationLayeringProfile",
    ),
    "BattlePresentationLayeringRuntime": (
        "asteria.presentation.battle.layering",
        "BattlePresentationLayeringRuntime",
    ),
    "BattlePresentationLibrary": ("asteria.presentation.library", "BattlePresentationLibrary"),
    "BattlePresentationProfileRef": (
        "asteria.presentation.library",
        "BattlePresentationProfileRef",
    ),
    "BattlePresentationRuntime": (
        "asteria.presentation.battle.runtime",
        "BattlePresentationRuntime",
    ),
    "BattlePresentationScene": ("asteria.presentation.battle.scene", "BattlePresentationScene"),
    "BattleProgressionRewardView": (
        "asteria.presentation.battle.result",
        "BattleProgressionRewardView",
    ),
    "BattleRenderBatch": ("asteria.presentation.battle.render_performance", "BattleRenderBatch"),
    "BattleRenderBatcher": (
        "asteria.presentation.battle.render_performance",
        "BattleRenderBatcher",
    ),
    "BattleRenderCullResult": (
        "asteria.presentation.battle.render_performance",
        "BattleRenderCullResult",
    ),
    "BattleRenderDraw": ("asteria.presentation.battle.render_performance", "BattleRenderDraw"),
    "BattleRenderVisibilityCuller": (
        "asteria.presentation.battle.render_performance",
        "BattleRenderVisibilityCuller",
    ),
    "BattleResultPresentationRuntime": (
        "asteria.presentation.battle.result",
        "BattleResultPresentationRuntime",
    ),
    "BattleResultProfile": ("asteria.presentation.battle.result", "BattleResultProfile"),
    "BattleResultView": ("asteria.presentation.battle.result", "BattleResultView"),
    "BattleRosterDensityPolicy": (
        "asteria.presentation.battle.information",
        "BattleRosterDensityPolicy",
    ),
    "BattleRosterSummary": ("asteria.presentation.battle.information", "BattleRosterSummary"),
    "BattleScreenFxCue": ("asteria.presentation.battle.camera_feedback", "BattleScreenFxCue"),
    "BattleScreenRenderResult": ("asteria.presentation.battle.screen", "BattleScreenRenderResult"),
    "BattleScreenRuntime": ("asteria.presentation.battle.screen", "BattleScreenRuntime"),
    "BattleSideviewPlacement": (
        "asteria.presentation.battle.sideview_template",
        "BattleSideviewPlacement",
    ),
    "BattleSideviewTemplateProfile": (
        "asteria.presentation.battle.sideview_template",
        "BattleSideviewTemplateProfile",
    ),
    "BattleSideviewTemplateResult": (
        "asteria.presentation.battle.sideview_template",
        "BattleSideviewTemplateResult",
    ),
    "BattleSideviewTemplateRuntime": (
        "asteria.presentation.battle.sideview_template",
        "BattleSideviewTemplateRuntime",
    ),
    "BattleSideviewZone": ("asteria.presentation.battle.sideview_template", "BattleSideviewZone"),
    "BattleTargetIndicator": (
        "asteria.presentation.battle.camera_feedback",
        "BattleTargetIndicator",
    ),
    "BattleTransientObject": (
        "asteria.presentation.battle.render_performance",
        "BattleTransientObject",
    ),
    "BattleTransientPool": (
        "asteria.presentation.battle.render_performance",
        "BattleTransientPool",
    ),
    "BattleTurnEntry": ("asteria.presentation.battle.turn_timeline", "BattleTurnEntry"),
    "BattleTurnTimelineRuntime": (
        "asteria.presentation.battle.turn_timeline",
        "BattleTurnTimelineRuntime",
    ),
    "BattleTurnTimelineView": (
        "asteria.presentation.battle.turn_timeline",
        "BattleTurnTimelineView",
    ),
    "BattleUiComposer": ("asteria.presentation.battle.ui", "BattleUiComposer"),
    "BattleUiFrame": ("asteria.presentation.battle.ui", "BattleUiFrame"),
    "BattleUiGaugeBar": ("asteria.presentation.battle.ui", "BattleUiGaugeBar"),
    "BattleUiIcon": ("asteria.presentation.battle.ui", "BattleUiIcon"),
    "BattleUiLayoutProfile": ("asteria.presentation.battle.ui", "BattleUiLayoutProfile"),
    "BattleUiMarker": ("asteria.presentation.battle.ui", "BattleUiMarker"),
    "BattleUiPanel": ("asteria.presentation.battle.ui", "BattleUiPanel"),
    "BattleUiPolishProfile": ("asteria.presentation.battle.ui_polish", "BattleUiPolishProfile"),
    "BattleUiPortrait": ("asteria.presentation.battle.ui", "BattleUiPortrait"),
    "BattleUiRenderer": ("asteria.presentation.battle.ui_renderer", "BattleUiRenderer"),
    "BattleUiText": ("asteria.presentation.battle.ui", "BattleUiText"),
    "BattleUiTheme": ("asteria.presentation.battle.ui_renderer", "BattleUiTheme"),
    "BattleValueKind": ("asteria.presentation.battle.feedback", "BattleValueKind"),
    "BattleVfxCue": ("asteria.presentation.battle.feedback", "BattleVfxCue"),
    "BattleVisualAnchor": ("asteria.presentation.battle.scene", "BattleVisualAnchor"),
    "BattleVisualAssetSet": (
        "asteria.presentation.battle.combatant_visuals",
        "BattleVisualAssetSet",
    ),
    "BattleVisualStateDefinition": (
        "asteria.presentation.battle.combatant_visuals",
        "BattleVisualStateDefinition",
    ),
    "BattleVisualTransform": (
        "asteria.presentation.battle.combatant_visuals",
        "BattleVisualTransform",
    ),
    "BattleWorkflowOption": (
        "asteria.presentation.battle.action_workflow",
        "BattleWorkflowOption",
    ),
    "BattleWorkflowSelection": (
        "asteria.presentation.battle.action_workflow",
        "BattleWorkflowSelection",
    ),
    "BattleWorkflowStep": ("asteria.presentation.battle.action_workflow", "BattleWorkflowStep"),
    "CAPABILITIES": ("asteria.presentation.visuals.fidelity", "CAPABILITIES"),
    "CharacterScreenAbilityView": (
        "asteria.presentation.screens.character",
        "CharacterScreenAbilityView",
    ),
    "CharacterScreenEquipmentItemView": (
        "asteria.presentation.screens.character",
        "CharacterScreenEquipmentItemView",
    ),
    "CharacterScreenEquipmentSlotView": (
        "asteria.presentation.screens.character",
        "CharacterScreenEquipmentSlotView",
    ),
    "CharacterScreenProfile": (
        "asteria.presentation.screens.character",
        "CharacterScreenProfile",
    ),
    "CharacterScreenProgressionView": (
        "asteria.presentation.screens.character",
        "CharacterScreenProgressionView",
    ),
    "CharacterScreenResourceView": (
        "asteria.presentation.screens.character",
        "CharacterScreenResourceView",
    ),
    "CharacterScreenRuntime": (
        "asteria.presentation.screens.character",
        "CharacterScreenRuntime",
    ),
    "CharacterScreenSection": (
        "asteria.presentation.screens.character",
        "CharacterScreenSection",
    ),
    "CharacterScreenStatView": (
        "asteria.presentation.screens.character",
        "CharacterScreenStatView",
    ),
    "CharacterScreenView": ("asteria.presentation.screens.character", "CharacterScreenView"),
    "Choreography": ("asteria.presentation.visuals.composition", "Choreography"),
    "ChoreographyFrame": ("asteria.presentation.visuals.choreography", "ChoreographyFrame"),
    "ChoreographyTimeline": ("asteria.presentation.visuals.choreography", "ChoreographyTimeline"),
    "ClipSampler": ("asteria.presentation.visuals.composition", "ClipSampler"),
    "CombatantOverlay": ("asteria.presentation.battle.runtime", "CombatantOverlay"),
    "Command": ("asteria.presentation.workspace", "Command"),
    "CompositionFrame": ("asteria.presentation.visuals.composition", "CompositionFrame"),
    "Context": ("asteria.presentation.runtime", "Context"),
    "EquipmentCandidateView": (
        "asteria.presentation.screens.equipment",
        "EquipmentCandidateView",
    ),
    "EquipmentGrowthView": ("asteria.presentation.screens.equipment", "EquipmentGrowthView"),
    "EquipmentScreenProfile": (
        "asteria.presentation.screens.equipment",
        "EquipmentScreenProfile",
    ),
    "EquipmentScreenRuntime": (
        "asteria.presentation.screens.equipment",
        "EquipmentScreenRuntime",
    ),
    "EquipmentScreenView": ("asteria.presentation.screens.equipment", "EquipmentScreenView"),
    "EquipmentSlotView": ("asteria.presentation.screens.equipment", "EquipmentSlotView"),
    "EquipmentSocketView": ("asteria.presentation.screens.equipment", "EquipmentSocketView"),
    "EquippedItemView": ("asteria.presentation.screens.equipment", "EquippedItemView"),
    "Executor": ("asteria.presentation.bridge", "Executor"),
    "ExecutorRegistry": ("asteria.presentation.bridge", "ExecutorRegistry"),
    "ExecutorSignal": ("asteria.presentation.bridge", "ExecutorSignal"),
    "Expression": ("asteria.presentation.canonical", "Expression"),
    "FidelityCapability": ("asteria.presentation.visuals.fidelity", "FidelityCapability"),
    "FidelityEditorViewState": (
        "asteria.presentation.visuals.fidelity_editor",
        "FidelityEditorViewState",
    ),
    "Frame": ("asteria.presentation.runtime", "Frame"),
    "FrameBudget": ("asteria.presentation.visuals.fidelity_editor", "FrameBudget"),
    "FrameDiagnostics": ("asteria.presentation.visuals.performance", "FrameDiagnostics"),
    "FrameTiming": ("asteria.presentation.visuals.fidelity_editor", "FrameTiming"),
    "HeadlessBattleUiBackend": (
        "asteria.presentation.battle.ui_renderer",
        "HeadlessBattleUiBackend",
    ),
    "HighFidelityClip": ("asteria.presentation.visuals.fidelity_editor", "HighFidelityClip"),
    "HighFidelityEditorModel": (
        "asteria.presentation.visuals.fidelity_editor",
        "HighFidelityEditorModel",
    ),
    "ImmediateExecutor": ("asteria.presentation.bridge", "ImmediateExecutor"),
    "InspectorField": ("asteria.presentation.workspace", "InspectorField"),
    "InventoryGroupView": ("asteria.presentation.screens.inventory", "InventoryGroupView"),
    "InventoryItemView": ("asteria.presentation.screens.inventory", "InventoryItemView"),
    "InventoryScreenProfile": (
        "asteria.presentation.screens.inventory",
        "InventoryScreenProfile",
    ),
    "InventoryScreenRuntime": (
        "asteria.presentation.screens.inventory",
        "InventoryScreenRuntime",
    ),
    "InventoryScreenView": ("asteria.presentation.screens.inventory", "InventoryScreenView"),
    "Kind": ("asteria.presentation.visual_authoring", "Kind"),
    "LayerSample": ("asteria.presentation.visuals.composition", "LayerSample"),
    "LayoutState": ("asteria.presentation.visual_authoring", "LayoutState"),
    "Library": ("asteria.presentation.runtime", "Library"),
    "Node": ("asteria.presentation.visual_editing", "Node"),
    "PaletteItem": ("asteria.presentation.workspace", "PaletteItem"),
    "PassiveCollectionEntry": (
        "asteria.presentation.screens.ability",
        "PassiveCollectionEntry",
    ),
    "PresentationEditorModel": ("asteria.presentation.visual_editing", "PresentationEditorModel"),
    "PresentationRunner": ("asteria.presentation.bridge", "PresentationRunner"),
    "PresentationVisualEditor": (
        "asteria.presentation.visual_editing",
        "PresentationVisualEditor",
    ),
    "PresentationVisualProjection": (
        "asteria.presentation.visual_authoring",
        "PresentationVisualProjection",
    ),
    "PresentationWorkspaceModel": ("asteria.presentation.workspace", "PresentationWorkspaceModel"),
    "Runtime": ("asteria.presentation.bridge", "Runtime"),
    "RuntimeEvent": ("asteria.presentation.bridge", "RuntimeEvent"),
    "RuntimeLimits": ("asteria.presentation.runtime", "RuntimeLimits"),
    "RuntimeSafetyError": ("asteria.presentation.runtime", "RuntimeSafetyError"),
    "Sequence": ("asteria.presentation.editor_model", "Sequence"),
    "SyncCue": ("asteria.presentation.visuals.composition", "SyncCue"),
    "TimeSegment": ("asteria.presentation.visuals.choreography", "TimeSegment"),
    "TimedExecutor": ("asteria.presentation.bridge", "TimedExecutor"),
    "TimelineBlock": ("asteria.presentation.visual_authoring", "TimelineBlock"),
    "TrackEvent": ("asteria.presentation.visuals.choreography", "TrackEvent"),
    "VisualEdge": ("asteria.presentation.visual_authoring", "VisualEdge"),
    "VisualEditState": ("asteria.presentation.visual_editing", "VisualEditState"),
    "VisualLayer": ("asteria.presentation.visuals.fidelity", "VisualLayer"),
    "VisualNode": ("asteria.presentation.visual_authoring", "VisualNode"),
    "WorkspaceState": ("asteria.presentation.workspace", "WorkspaceState"),
    "battle": ("asteria.presentation.battle.scene", None),
    "battle_action_menu": ("asteria.presentation.battle.action_menu", None),
    "battle_action_workflow": ("asteria.presentation.battle.action_workflow", None),
    "battle_animation_timing": ("asteria.presentation.battle.animation_timing", None),
    "battle_camera_feedback": ("asteria.presentation.battle.camera_feedback", None),
    "battle_combatant_visuals": ("asteria.presentation.battle.combatant_visuals", None),
    "battle_feedback": ("asteria.presentation.battle.feedback", None),
    "battle_hud": ("asteria.presentation.battle.hud", None),
    "battle_information": ("asteria.presentation.battle.information", None),
    "battle_interaction": ("asteria.presentation.battle.interaction", None),
    "battle_motion_sequence": ("asteria.presentation.battle.motion_sequence", None),
    "battle_party_layout": ("asteria.presentation.battle.party_layout", None),
    "battle_portrait_party_template": (
        "asteria.presentation.battle.portrait_party_template",
        None,
    ),
    "battle_presentation_director": ("asteria.presentation.battle.director", None),
    "battle_presentation_layering": ("asteria.presentation.battle.layering", None),
    "battle_render_performance": ("asteria.presentation.battle.render_performance", None),
    "battle_result": ("asteria.presentation.battle.result", None),
    "battle_runtime": ("asteria.presentation.battle.runtime", None),
    "battle_screen": ("asteria.presentation.battle.screen", None),
    "battle_sideview_template": ("asteria.presentation.battle.sideview_template", None),
    "battle_turn_timeline": ("asteria.presentation.battle.turn_timeline", None),
    "battle_ui": ("asteria.presentation.battle.ui", None),
    "battle_ui_polish": ("asteria.presentation.battle.ui_polish", None),
    "battle_ui_renderer": ("asteria.presentation.battle.ui_renderer", None),
    "bind": ("asteria.presentation.runtime", "bind"),
    "bridge": ("asteria.presentation.bridge", None),
    "canonical": ("asteria.presentation.canonical", None),
    "choreography": ("asteria.presentation.visuals.choreography", None),
    "composition": ("asteria.presentation.visuals.composition", None),
    "creature_screens": ("asteria.presentation.screens.creature", None),
    "default_dungeon_portrait_party_profile": (
        "asteria.presentation.battle.portrait_party_template",
        "default_dungeon_portrait_party_profile",
    ),
    "default_jrpg_visual_states": (
        "asteria.presentation.battle.combatant_visuals",
        "default_jrpg_visual_states",
    ),
    "default_sideview_jrpg_profile": (
        "asteria.presentation.battle.sideview_template",
        "default_sideview_jrpg_profile",
    ),
    "diagnose": ("asteria.presentation.visuals.fidelity_editor", "diagnose"),
    "dialogue_window": ("asteria.presentation.text.dialogue_window", None),
    "easing_value": ("asteria.presentation.battle.animation_timing", "easing_value"),
    "editor_model": ("asteria.presentation.editor_model", None),
    "event": ("asteria.presentation.visuals.choreography", "event"),
    "fidelity": ("asteria.presentation.visuals.fidelity", None),
    "fidelity_editor": ("asteria.presentation.visuals.fidelity_editor", None),
    "fidelity_warnings": ("asteria.presentation.visuals.fidelity", "fidelity_warnings"),
    "gauge_threshold_payloads": (
        "asteria.presentation.battle.feedback",
        "gauge_threshold_payloads",
    ),
    "hold": ("asteria.presentation.visuals.choreography", "hold"),
    "library": ("asteria.presentation.library", None),
    "make_reference_smooth_attack_sequence": (
        "asteria.presentation.battle.motion_sequence",
        "make_reference_smooth_attack_sequence",
    ),
    "menu_layout": ("asteria.presentation.screens.menu_layout", None),
    "message_codes": ("asteria.presentation.text.message_codes", None),
    "performance": ("asteria.presentation.visuals.performance", None),
    "presentation_cues": ("asteria.presentation.visuals.composition", "presentation_cues"),
    "resolved_value_payload": ("asteria.presentation.battle.feedback", "resolved_value_payload"),
    "retired_screens": ("asteria.presentation.screens.retired", None),
    "rpg_ability_screen": ("asteria.presentation.screens.ability", None),
    "rpg_character_screen": ("asteria.presentation.screens.character", None),
    "rpg_equipment_screen": ("asteria.presentation.screens.equipment", None),
    "rpg_inventory_screen": ("asteria.presentation.screens.inventory", None),
    "runtime": ("asteria.presentation.runtime", None),
    "text_cells": ("asteria.presentation.text.cells", None),
    "time_scale": ("asteria.presentation.visuals.choreography", "time_scale"),
    "ui_skin": ("asteria.presentation.screens.ui_skin", None),
    "visual_authoring": ("asteria.presentation.visual_authoring", None),
    "visual_editing": ("asteria.presentation.visual_editing", None),
    "workspace": ("asteria.presentation.workspace", None),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    try:
        module, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = import_module(module)
    if attribute is not None:
        value = getattr(value, attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_EXPORTS})
