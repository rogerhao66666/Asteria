# The package's names are imported when first used (PEP 562): importing one module of it
# no longer imports every other one (and what they import), which made a cycle with
# asteria.assets and slowed every import. Generated from the eager imports it replaces.

from importlib import import_module

_EXPORTS = {  # name -> (module, attribute; None: the module itself)
    "ActorClassCoverage": ("asteria.editor.rpg.actor_class_authoring", "ActorClassCoverage"),
    "AsteriaEditorWindow": ("asteria.editor.shell", "AsteriaEditorWindow"),
    "BattlePresentationAuthoringController": (
        "asteria.editor.combat.battle_presentation_authoring",
        "BattlePresentationAuthoringController",
    ),
    "BattlePresentationAuthoringError": (
        "asteria.editor.combat.battle_presentation_authoring",
        "BattlePresentationAuthoringError",
    ),
    "BattlePresentationInformationArchitecture": (
        "asteria.editor.combat.battle_presentation_authoring",
        "BattlePresentationInformationArchitecture",
    ),
    "BattlePresentationSection": (
        "asteria.editor.combat.battle_presentation_authoring",
        "BattlePresentationSection",
    ),
    "BattleRuleGroup": ("asteria.editor.rpg.battle_rules_authoring", "BattleRuleGroup"),
    "BattleRuleKind": ("asteria.editor.rpg.battle_rules_authoring", "BattleRuleKind"),
    "BattleRulesInformationArchitecture": (
        "asteria.editor.rpg.battle_rules_authoring",
        "BattleRulesInformationArchitecture",
    ),
    "CommandStack": ("asteria.editor.project.commands", "CommandStack"),
    "CommandTransaction": ("asteria.editor.project.commands", "CommandTransaction"),
    "ComponentChoice": ("asteria.editor.scene.component_picker", "ComponentChoice"),
    "EditError": ("asteria.editor.project.editing", "EditError"),
    "EditorClipboard": ("asteria.editor.project.clipboard", "EditorClipboard"),
    "EditorDocument": ("asteria.editor.project.model", "EditorDocument"),
    "EditorSelection": ("asteria.editor.project.model", "EditorSelection"),
    "EnemyEncounterInformationArchitecture": (
        "asteria.editor.rpg.enemy_encounter_authoring",
        "EnemyEncounterInformationArchitecture",
    ),
    "EnemyEncounterSection": (
        "asteria.editor.rpg.enemy_encounter_authoring",
        "EnemyEncounterSection",
    ),
    "EntityMarker": ("asteria.editor.scene.viewport", "EntityMarker"),
    "FieldGameFlowAuthoringController": (
        "asteria.editor.rpg.field_game_flow_authoring",
        "FieldGameFlowAuthoringController",
    ),
    "FieldGameFlowAuthoringError": (
        "asteria.editor.rpg.field_game_flow_authoring",
        "FieldGameFlowAuthoringError",
    ),
    "FieldGameFlowInformationArchitecture": (
        "asteria.editor.rpg.field_game_flow_authoring",
        "FieldGameFlowInformationArchitecture",
    ),
    "FieldGameFlowSection": (
        "asteria.editor.rpg.field_game_flow_authoring",
        "FieldGameFlowSection",
    ),
    "HierarchyEditError": ("asteria.editor.scene.hierarchy", "HierarchyEditError"),
    "InspectorFieldModel": ("asteria.editor.scene.inspector", "InspectorFieldModel"),
    "ItemEquipmentInformationArchitecture": (
        "asteria.editor.rpg.item_equipment_authoring",
        "ItemEquipmentInformationArchitecture",
    ),
    "ItemEquipmentSection": (
        "asteria.editor.rpg.item_equipment_authoring",
        "ItemEquipmentSection",
    ),
    "PartyFormationInformationArchitecture": (
        "asteria.editor.rpg.party_formation_authoring",
        "PartyFormationInformationArchitecture",
    ),
    "PartyFormationSection": (
        "asteria.editor.rpg.party_formation_authoring",
        "PartyFormationSection",
    ),
    "PlaytestProfile": ("asteria.editor.project.playtest_profiles", "PlaytestProfile"),
    "PlaytestProfileError": ("asteria.editor.project.playtest_profiles", "PlaytestProfileError"),
    "PlaytestProfileLibrary": (
        "asteria.editor.project.playtest_profiles",
        "PlaytestProfileLibrary",
    ),
    "ProgressionEditorInformationArchitecture": (
        "asteria.editor.rpg.progression_authoring",
        "ProgressionEditorInformationArchitecture",
    ),
    "ProgressionEditorSection": (
        "asteria.editor.rpg.progression_authoring",
        "ProgressionEditorSection",
    ),
    "ProjectWorkspaceController": (
        "asteria.editor.project.project_workspace",
        "ProjectWorkspaceController",
    ),
    "ProjectWorkspaceError": ("asteria.editor.project.project_workspace", "ProjectWorkspaceError"),
    "ProjectWorkspaceState": ("asteria.editor.project.project_workspace", "ProjectWorkspaceState"),
    "RecentProjectStore": ("asteria.editor.project.project_workspace", "RecentProjectStore"),
    "RpgActorClassAuthoringController": (
        "asteria.editor.rpg.actor_class_authoring",
        "RpgActorClassAuthoringController",
    ),
    "RpgActorClassAuthoringError": (
        "asteria.editor.rpg.actor_class_authoring",
        "RpgActorClassAuthoringError",
    ),
    "RpgBattleRulesAuthoringController": (
        "asteria.editor.rpg.battle_rules_authoring",
        "RpgBattleRulesAuthoringController",
    ),
    "RpgBattleRulesAuthoringError": (
        "asteria.editor.rpg.battle_rules_authoring",
        "RpgBattleRulesAuthoringError",
    ),
    "RpgEnemyEncounterAuthoringController": (
        "asteria.editor.rpg.enemy_encounter_authoring",
        "RpgEnemyEncounterAuthoringController",
    ),
    "RpgEnemyEncounterAuthoringError": (
        "asteria.editor.rpg.enemy_encounter_authoring",
        "RpgEnemyEncounterAuthoringError",
    ),
    "RpgItemEquipmentAuthoringController": (
        "asteria.editor.rpg.item_equipment_authoring",
        "RpgItemEquipmentAuthoringController",
    ),
    "RpgItemEquipmentAuthoringError": (
        "asteria.editor.rpg.item_equipment_authoring",
        "RpgItemEquipmentAuthoringError",
    ),
    "RpgPartyFormationAuthoringController": (
        "asteria.editor.rpg.party_formation_authoring",
        "RpgPartyFormationAuthoringController",
    ),
    "RpgPartyFormationAuthoringError": (
        "asteria.editor.rpg.party_formation_authoring",
        "RpgPartyFormationAuthoringError",
    ),
    "RpgProgressionAuthoringController": (
        "asteria.editor.rpg.progression_authoring",
        "RpgProgressionAuthoringController",
    ),
    "RpgProgressionAuthoringError": (
        "asteria.editor.rpg.progression_authoring",
        "RpgProgressionAuthoringError",
    ),
    "SceneEditError": ("asteria.editor.project.scenes", "SceneEditError"),
    "SetAttributeCommand": ("asteria.editor.project.commands", "SetAttributeCommand"),
    "StructureEditError": ("asteria.editor.project.structure", "StructureEditError"),
    "ViewportCamera": ("asteria.editor.scene.viewport", "ViewportCamera"),
    "build_add_component_command": (
        "asteria.editor.project.structure",
        "build_add_component_command",
    ),
    "build_add_entity_command": ("asteria.editor.project.structure", "build_add_entity_command"),
    "build_add_scene_command": ("asteria.editor.project.scenes", "build_add_scene_command"),
    "build_component_choices": (
        "asteria.editor.scene.component_picker",
        "build_component_choices",
    ),
    "build_duplicate_entity_command": (
        "asteria.editor.project.clipboard",
        "build_duplicate_entity_command",
    ),
    "build_inspector_fields": ("asteria.editor.scene.inspector", "build_inspector_fields"),
    "build_move_entity_to_scene_command": (
        "asteria.editor.scene.hierarchy",
        "build_move_entity_to_scene_command",
    ),
    "build_paste_entity_command": (
        "asteria.editor.project.clipboard",
        "build_paste_entity_command",
    ),
    "build_remove_component_command": (
        "asteria.editor.project.structure",
        "build_remove_component_command",
    ),
    "build_remove_entity_command": (
        "asteria.editor.project.structure",
        "build_remove_entity_command",
    ),
    "build_remove_scene_command": ("asteria.editor.project.scenes", "build_remove_scene_command"),
    "build_rename_command": ("asteria.editor.project.structure", "build_rename_command"),
    "build_reorder_entity_command": (
        "asteria.editor.scene.hierarchy",
        "build_reorder_entity_command",
    ),
    "build_reorder_scene_command": (
        "asteria.editor.project.scenes",
        "build_reorder_scene_command",
    ),
    "build_set_component_field_command": (
        "asteria.editor.project.editing",
        "build_set_component_field_command",
    ),
    "coerce_field_value": ("asteria.editor.project.editing", "coerce_field_value"),
    "launch_editor": ("asteria.editor.shell", "launch_editor"),
    "pick_entity": ("asteria.editor.scene.viewport", "pick_entity"),
    "scene_markers": ("asteria.editor.scene.viewport", "scene_markers"),
    "selected_scene": ("asteria.editor.scene.viewport", "selected_scene"),
    "shell": ("asteria.editor.shell", None),
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
