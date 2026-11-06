# The package's names are imported when first used (PEP 562): importing one module of it
# no longer imports every other one (and what they import), which made a cycle with
# asteria.assets and slowed every import. Generated from the eager imports it replaces.

from importlib import import_module

_EXPORTS = {  # name -> (module, attribute; None: the module itself)
    "ActorClassCoverage": (".rpg_actor_class_authoring", "ActorClassCoverage"),
    "AsteriaEditorWindow": (".shell", "AsteriaEditorWindow"),
    "BattlePresentationAuthoringController": (
        ".battle_presentation_authoring",
        "BattlePresentationAuthoringController",
    ),
    "BattlePresentationAuthoringError": (
        ".battle_presentation_authoring",
        "BattlePresentationAuthoringError",
    ),
    "BattlePresentationInformationArchitecture": (
        ".battle_presentation_authoring",
        "BattlePresentationInformationArchitecture",
    ),
    "BattlePresentationSection": (".battle_presentation_authoring", "BattlePresentationSection"),
    "BattlePresentationWorkspaceModel": (
        ".battle_presentation_workspace",
        "BattlePresentationWorkspaceModel",
    ),
    "BattlePresentationWorkspaceSnapshot": (
        ".battle_presentation_workspace",
        "BattlePresentationWorkspaceSnapshot",
    ),
    "BattleRuleGroup": (".rpg_battle_rules_authoring", "BattleRuleGroup"),
    "BattleRuleKind": (".rpg_battle_rules_authoring", "BattleRuleKind"),
    "BattleRulesInformationArchitecture": (
        ".rpg_battle_rules_authoring",
        "BattleRulesInformationArchitecture",
    ),
    "BattleRulesWorkspaceSnapshot": (
        ".rpg_battle_rules_workspace",
        "BattleRulesWorkspaceSnapshot",
    ),
    "CommandStack": (".commands", "CommandStack"),
    "CommandTransaction": (".commands", "CommandTransaction"),
    "ComponentChoice": (".component_picker", "ComponentChoice"),
    "EditError": (".editing", "EditError"),
    "EditorClipboard": (".clipboard", "EditorClipboard"),
    "EditorDocument": (".model", "EditorDocument"),
    "EditorSelection": (".model", "EditorSelection"),
    "EnemyEncounterInformationArchitecture": (
        ".rpg_enemy_encounter_authoring",
        "EnemyEncounterInformationArchitecture",
    ),
    "EnemyEncounterSection": (".rpg_enemy_encounter_authoring", "EnemyEncounterSection"),
    "EnemyEncounterWorkspaceSnapshot": (
        ".rpg_enemy_encounter_workspace",
        "EnemyEncounterWorkspaceSnapshot",
    ),
    "EntityMarker": (".viewport", "EntityMarker"),
    "FieldGameFlowAuthoringController": (
        ".field_game_flow_authoring",
        "FieldGameFlowAuthoringController",
    ),
    "FieldGameFlowAuthoringError": (".field_game_flow_authoring", "FieldGameFlowAuthoringError"),
    "FieldGameFlowInformationArchitecture": (
        ".field_game_flow_authoring",
        "FieldGameFlowInformationArchitecture",
    ),
    "FieldGameFlowSection": (".field_game_flow_authoring", "FieldGameFlowSection"),
    "FieldGameFlowWorkspaceModel": (".field_game_flow_workspace", "FieldGameFlowWorkspaceModel"),
    "FieldGameFlowWorkspaceSnapshot": (
        ".field_game_flow_workspace",
        "FieldGameFlowWorkspaceSnapshot",
    ),
    "HierarchyEditError": (".hierarchy", "HierarchyEditError"),
    "InspectorFieldModel": (".inspector", "InspectorFieldModel"),
    "ItemEquipmentInformationArchitecture": (
        ".rpg_item_equipment_authoring",
        "ItemEquipmentInformationArchitecture",
    ),
    "ItemEquipmentSection": (".rpg_item_equipment_authoring", "ItemEquipmentSection"),
    "ItemEquipmentWorkspaceSnapshot": (
        ".rpg_item_equipment_workspace",
        "ItemEquipmentWorkspaceSnapshot",
    ),
    "PartyFormationInformationArchitecture": (
        ".rpg_party_formation_authoring",
        "PartyFormationInformationArchitecture",
    ),
    "PartyFormationSection": (".rpg_party_formation_authoring", "PartyFormationSection"),
    "PartyFormationWorkspaceSnapshot": (
        ".rpg_party_formation_workspace",
        "PartyFormationWorkspaceSnapshot",
    ),
    "PlaytestProfile": (".playtest_profiles", "PlaytestProfile"),
    "PlaytestProfileError": (".playtest_profiles", "PlaytestProfileError"),
    "PlaytestProfileLibrary": (".playtest_profiles", "PlaytestProfileLibrary"),
    "ProgressionEditorInformationArchitecture": (
        ".rpg_progression_authoring",
        "ProgressionEditorInformationArchitecture",
    ),
    "ProgressionEditorSection": (".rpg_progression_authoring", "ProgressionEditorSection"),
    "ProgressionWorkspaceSnapshot": (".rpg_progression_workspace", "ProgressionWorkspaceSnapshot"),
    "ProjectWorkspaceController": (".project_workspace", "ProjectWorkspaceController"),
    "ProjectWorkspaceError": (".project_workspace", "ProjectWorkspaceError"),
    "ProjectWorkspaceState": (".project_workspace", "ProjectWorkspaceState"),
    "RecentProjectStore": (".project_workspace", "RecentProjectStore"),
    "RpgActorClassAuthoringController": (
        ".rpg_actor_class_authoring",
        "RpgActorClassAuthoringController",
    ),
    "RpgActorClassAuthoringError": (".rpg_actor_class_authoring", "RpgActorClassAuthoringError"),
    "RpgBattleRulesAuthoringController": (
        ".rpg_battle_rules_authoring",
        "RpgBattleRulesAuthoringController",
    ),
    "RpgBattleRulesAuthoringError": (
        ".rpg_battle_rules_authoring",
        "RpgBattleRulesAuthoringError",
    ),
    "RpgBattleRulesWorkspaceModel": (
        ".rpg_battle_rules_workspace",
        "RpgBattleRulesWorkspaceModel",
    ),
    "RpgEnemyEncounterAuthoringController": (
        ".rpg_enemy_encounter_authoring",
        "RpgEnemyEncounterAuthoringController",
    ),
    "RpgEnemyEncounterAuthoringError": (
        ".rpg_enemy_encounter_authoring",
        "RpgEnemyEncounterAuthoringError",
    ),
    "RpgEnemyEncounterWorkspaceModel": (
        ".rpg_enemy_encounter_workspace",
        "RpgEnemyEncounterWorkspaceModel",
    ),
    "RpgItemEquipmentAuthoringController": (
        ".rpg_item_equipment_authoring",
        "RpgItemEquipmentAuthoringController",
    ),
    "RpgItemEquipmentAuthoringError": (
        ".rpg_item_equipment_authoring",
        "RpgItemEquipmentAuthoringError",
    ),
    "RpgItemEquipmentWorkspaceModel": (
        ".rpg_item_equipment_workspace",
        "RpgItemEquipmentWorkspaceModel",
    ),
    "RpgPartyFormationAuthoringController": (
        ".rpg_party_formation_authoring",
        "RpgPartyFormationAuthoringController",
    ),
    "RpgPartyFormationAuthoringError": (
        ".rpg_party_formation_authoring",
        "RpgPartyFormationAuthoringError",
    ),
    "RpgPartyFormationWorkspaceModel": (
        ".rpg_party_formation_workspace",
        "RpgPartyFormationWorkspaceModel",
    ),
    "RpgProgressionAuthoringController": (
        ".rpg_progression_authoring",
        "RpgProgressionAuthoringController",
    ),
    "RpgProgressionAuthoringError": (".rpg_progression_authoring", "RpgProgressionAuthoringError"),
    "RpgProgressionWorkspaceModel": (".rpg_progression_workspace", "RpgProgressionWorkspaceModel"),
    "RuntimeStateIntegrationController": (
        ".runtime_state_integration",
        "RuntimeStateIntegrationController",
    ),
    "RuntimeStateIntegrationError": (".runtime_state_integration", "RuntimeStateIntegrationError"),
    "SceneEditError": (".scenes", "SceneEditError"),
    "SceneEntityAuthoringController": (
        ".scene_entity_authoring",
        "SceneEntityAuthoringController",
    ),
    "SceneEntityAuthoringError": (".scene_entity_authoring", "SceneEntityAuthoringError"),
    "SceneEntityCoverage": (".scene_entity_authoring", "SceneEntityCoverage"),
    "SetAttributeCommand": (".commands", "SetAttributeCommand"),
    "StructureEditError": (".structure", "StructureEditError"),
    "ViewportCamera": (".viewport", "ViewportCamera"),
    "authoring_context": (".authoring_context", None),
    "authoring_hub_widget": (".authoring_hub_widget", None),
    "battle_presentation_authoring": (".battle_presentation_authoring", None),
    "battle_presentation_workspace": (".battle_presentation_workspace", None),
    "build_add_component_command": (".structure", "build_add_component_command"),
    "build_add_entity_command": (".structure", "build_add_entity_command"),
    "build_add_scene_command": (".scenes", "build_add_scene_command"),
    "build_component_choices": (".component_picker", "build_component_choices"),
    "build_duplicate_entity_command": (".clipboard", "build_duplicate_entity_command"),
    "build_inspector_fields": (".inspector", "build_inspector_fields"),
    "build_move_entity_to_scene_command": (".hierarchy", "build_move_entity_to_scene_command"),
    "build_paste_entity_command": (".clipboard", "build_paste_entity_command"),
    "build_remove_component_command": (".structure", "build_remove_component_command"),
    "build_remove_entity_command": (".structure", "build_remove_entity_command"),
    "build_remove_scene_command": (".scenes", "build_remove_scene_command"),
    "build_rename_command": (".structure", "build_rename_command"),
    "build_reorder_entity_command": (".hierarchy", "build_reorder_entity_command"),
    "build_reorder_scene_command": (".scenes", "build_reorder_scene_command"),
    "build_set_component_field_command": (".editing", "build_set_component_field_command"),
    "clipboard": (".clipboard", None),
    "code_workspace": (".code_workspace", None),
    "coerce_field_value": (".editing", "coerce_field_value"),
    "collision_overlay": (".collision_overlay", None),
    "commands": (".commands", None),
    "component_picker": (".component_picker", None),
    "create_character_command": (".create_character_command", None),
    "dock_title": (".dock_title", None),
    "editing": (".editing", None),
    "entity_kinds": (".entity_kinds", None),
    "entity_render": (".entity_render", None),
    "event_editing": (".event_editing", None),
    "event_editor_widget": (".event_editor_widget", None),
    "field_game_flow_authoring": (".field_game_flow_authoring", None),
    "field_game_flow_workspace": (".field_game_flow_workspace", None),
    "flow_layout": (".flow_layout", None),
    "game_flow_overview_widget": (".game_flow_overview_widget", None),
    "gizmo": (".gizmo", None),
    "hierarchy": (".hierarchy", None),
    "i18n": (".i18n", None),
    "icons": (".icons", None),
    "inspector": (".inspector", None),
    "integrated_authoring": (".integrated_authoring", None),
    "launch_editor": (".shell", "launch_editor"),
    "model": (".model", None),
    "panel_switch": (".panel_switch", None),
    "pick_entity": (".viewport", "pick_entity"),
    "place_character": (".place_character", None),
    "playmode": (".playmode", None),
    "playtest_profiles": (".playtest_profiles", None),
    "project_workspace": (".project_workspace", None),
    "qt_texture_renderer": (".qt_texture_renderer", None),
    "record_vocabulary": (".record_vocabulary", None),
    "resource_resolver": (".resource_resolver", None),
    "responsive_form": (".responsive_form", None),
    "rpg_actor_class_authoring": (".rpg_actor_class_authoring", None),
    "rpg_battle_rules_authoring": (".rpg_battle_rules_authoring", None),
    "rpg_battle_rules_workspace": (".rpg_battle_rules_workspace", None),
    "rpg_enemy_encounter_authoring": (".rpg_enemy_encounter_authoring", None),
    "rpg_enemy_encounter_workspace": (".rpg_enemy_encounter_workspace", None),
    "rpg_item_equipment_authoring": (".rpg_item_equipment_authoring", None),
    "rpg_item_equipment_workspace": (".rpg_item_equipment_workspace", None),
    "rpg_party_formation_authoring": (".rpg_party_formation_authoring", None),
    "rpg_party_formation_workspace": (".rpg_party_formation_workspace", None),
    "rpg_progression_authoring": (".rpg_progression_authoring", None),
    "rpg_progression_workspace": (".rpg_progression_workspace", None),
    "runtime_launcher": (".runtime_launcher", None),
    "runtime_state_integration": (".runtime_state_integration", None),
    "scene_entity_authoring": (".scene_entity_authoring", None),
    "scene_markers": (".viewport", "scene_markers"),
    "scene_render": (".scene_render", None),
    "scenes": (".scenes", None),
    "scrolling_tabs": (".scrolling_tabs", None),
    "selected_scene": (".viewport", "selected_scene"),
    "shell": (".shell", None),
    "skeleton_editing": (".skeleton_editing", None),
    "skeleton_view": (".skeleton_view", None),
    "skeleton_widget": (".skeleton_widget", None),
    "skeleton_workspace_page": (".skeleton_workspace_page", None),
    "storage": (".storage", None),
    "structure": (".structure", None),
    "theme": (".theme", None),
    "tile_edit": (".tile_edit", None),
    "tile_layers_widget": (".tile_layers_widget", None),
    "tile_palette": (".tile_palette", None),
    "tile_palette_widget": (".tile_palette_widget", None),
    "tool_strip": (".tool_strip", None),
    "ui_fit": (".ui_fit", None),
    "viewport": (".viewport", None),
    "viewport_widget": (".viewport_widget", None),
    "widgets": (".widgets", None),
    "workspace": (".workspace", None),
    "world_command_form": (".world_command_form", None),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    try:
        module, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = import_module(module, __name__)
    if attribute is not None:
        value = getattr(value, attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_EXPORTS})
