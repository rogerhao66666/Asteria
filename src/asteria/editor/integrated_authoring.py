from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from asteria.gameplay import AbilityDefinition
from asteria.rpg import (
    AbilityEvolutionRule,
    ActorDefinition,
    AttachmentDefinition,
    ClassDefinition,
    CompositionRecipeDefinition,
    EncounterDefinition,
    EnemyAIDefinition,
    EnemyDefinition,
    EquipmentDefinition,
    EquipmentGrowthDefinition,
    FormationDefinition,
    ItemDefinition,
    PartyPresentationPolicyDefinition,
    PartySetupDefinition,
    PassiveDefinition,
    ProgressionGraphDefinition,
    ProgressionTrackDefinition,
)

from .battle_presentation_authoring import BattlePresentationAuthoringController
from .field_game_flow_authoring import FieldGameFlowAuthoringController
from .rpg_actor_class_authoring import RpgActorClassAuthoringController
from .rpg_battle_rules_authoring import RpgBattleRulesAuthoringController
from .rpg_enemy_encounter_authoring import RpgEnemyEncounterAuthoringController
from .rpg_item_equipment_authoring import RpgItemEquipmentAuthoringController
from .rpg_party_formation_authoring import RpgPartyFormationAuthoringController
from .rpg_progression_authoring import RpgProgressionAuthoringController
from .runtime_rpg_ui_authoring import RuntimeRpgUiAuthoringController


@dataclass(frozen=True, slots=True)
class AuthoringCategoryAdapter:
    category_id: str
    label: str
    ids: Callable[[], tuple[str, ...]]
    get: Callable[[str], object]
    edit: Callable[[str, object], object]
    delete: Callable[[str], object]
    encode: Callable[[object], dict]
    decode: Callable[[dict], object]
    duplicate: Callable[[str, str], object] | None = None
    create: Callable[[str, object], object] | None = None  # (new id, decoded record) — paste (EDT-13)


class IntegratedAuthoringControllers:
    """One shared controller bundle for the real Editor shell.

    The shell creates this once around its existing EditorDocument.  Every
    authoring family therefore edits the exact same canonical Project and command
    stack as Scene/Event/Code editing.
    """

    def __init__(self, document):
        self.document = document
        self.actor_class = RpgActorClassAuthoringController(document)
        self.progression = RpgProgressionAuthoringController(document)
        self.items = RpgItemEquipmentAuthoringController(document)
        self.party = RpgPartyFormationAuthoringController(document)
        self.enemy = RpgEnemyEncounterAuthoringController(document)
        self.battle = RpgBattleRulesAuthoringController(document)
        self.presentation = BattlePresentationAuthoringController(document)
        self.runtime_ui = RuntimeRpgUiAuthoringController(document)
        self.flow = FieldGameFlowAuthoringController(document)

    @property
    def project(self):
        return self.document.project

    def rpg_categories(self):
        db = self.project.rpg_database
        ac = self.actor_class
        pr = self.progression
        it = self.items
        pa = self.party
        en = self.enemy

        def td(v):
            return v.to_data()

        def fd(cls):
            return lambda d: cls.from_data(d)

        def edit_actor(key, v):
            return ac.edit_actor(
                key,
                display_name=v.display_name,
                class_assignments=v.class_assignments,
                base_stats=v.base_stats,
                base_resources=v.base_resources,
                tags=v.tags,
                abilities=v.abilities,
            )

        def edit_class(key, v):
            return ac.edit_class(
                key,
                display_name=v.display_name,
                stat_bonuses=v.stat_bonuses,
                resource_bonuses=v.resource_bonuses,
                granted_tags=v.granted_tags,
                granted_abilities=v.granted_abilities,
            )

        def edit_passive(key, v):
            return pr.edit_passive(
                key,
                display_name=v.display_name,
                tags=v.tags,
                modifiers=v.modifiers,
                granted_abilities=v.granted_abilities,
                triggers=v.triggers,
            )

        def edit_track(key, v):
            return pr.edit_track(key, display_name=v.display_name, milestones=v.milestones)

        def edit_graph(key, v):
            return pr.edit_graph(
                key,
                display_name=v.display_name,
                nodes=v.nodes,
                tags=v.tags,
                editor_view=v.editor_view,
                node_positions=v.node_positions,
            )

        def edit_evolution(key, v):
            return pr.edit_evolution(
                key,
                source_ability_id=v.source_ability_id,
                result_ability_id=v.result_ability_id,
                progression_track_id=v.progression_track_id,
                minimum_rank=v.minimum_rank,
                priority=v.priority,
                retain_source=v.retain_source,
            )

        categories = [
            AuthoringCategoryAdapter(
                "actors",
                "Actors",
                lambda: tuple(sorted(db.actors)),
                lambda k: db.actors[k],
                edit_actor,
                ac.delete_actor,
                td,
                fd(ActorDefinition),
                lambda old, new: ac.duplicate_actor(old, new),
            ),
            AuthoringCategoryAdapter(
                "classes",
                "Classes / Jobs",
                lambda: tuple(sorted(db.classes)),
                lambda k: db.classes[k],
                edit_class,
                ac.delete_class,
                td,
                fd(ClassDefinition),
                lambda old, new: ac.duplicate_class(old, new),
            ),
            AuthoringCategoryAdapter(
                "abilities",
                "Abilities",
                lambda: tuple(sorted(pr.abilities.ids())),
                lambda k: pr.abilities.require(k),
                pr.edit_ability,
                pr.delete_ability,
                td,
                fd(AbilityDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "passives",
                "Passives",
                lambda: tuple(sorted(db.passives)),
                lambda k: db.passives[k],
                edit_passive,
                pr.delete_passive,
                td,
                fd(PassiveDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "tracks",
                "Progression Tracks",
                lambda: tuple(sorted(db.progression_tracks)),
                lambda k: db.progression_tracks[k],
                edit_track,
                pr.delete_track,
                td,
                fd(ProgressionTrackDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "graphs",
                "Skill Trees",
                lambda: tuple(sorted(db.progression_graphs)),
                lambda k: db.progression_graphs[k],
                edit_graph,
                pr.delete_graph,
                td,
                fd(ProgressionGraphDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "evolutions",
                "Ability Evolutions",
                lambda: tuple(sorted(db.ability_evolutions)),
                lambda k: db.ability_evolutions[k],
                edit_evolution,
                pr.delete_evolution,
                td,
                fd(AbilityEvolutionRule),
                None,
            ),
            AuthoringCategoryAdapter(
                "items",
                "Items",
                lambda: tuple(sorted(db.items)),
                lambda k: db.items[k],
                it.edit_item,
                it.delete_item,
                td,
                fd(ItemDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "equipment",
                "Equipment",
                lambda: tuple(sorted(db.equipment)),
                lambda k: db.equipment[k],
                it.edit_equipment,
                it.delete_equipment,
                td,
                fd(EquipmentDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "attachments",
                "Attachments",
                lambda: tuple(sorted(db.attachments)),
                lambda k: db.attachments[k],
                it.edit_attachment,
                it.delete_attachment,
                td,
                fd(AttachmentDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "growth",
                "Equipment Growth",
                lambda: tuple(sorted(db.equipment_growth)),
                lambda k: db.equipment_growth[k],
                it.edit_growth,
                it.delete_growth,
                td,
                fd(EquipmentGrowthDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "recipes",
                "Crafting / Alchemy",
                lambda: tuple(sorted(db.composition_recipes)),
                lambda k: db.composition_recipes[k],
                it.edit_recipe,
                it.delete_recipe,
                td,
                fd(CompositionRecipeDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "parties",
                "Party Setups",
                lambda: tuple(sorted(db.party_setups)),
                lambda k: db.party_setups[k],
                pa.edit_party,
                pa.delete_party,
                td,
                fd(PartySetupDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "formations",
                "Formations",
                lambda: tuple(sorted(db.formations)),
                lambda k: db.formations[k],
                pa.edit_formation,
                pa.delete_formation,
                td,
                fd(FormationDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "party_ui",
                "Party UI Policy",
                lambda: tuple(sorted(db.party_presentation_policies)),
                lambda k: db.party_presentation_policies[k],
                lambda k, v: pa.set_presentation_profile(k, v),
                pa.delete_presentation_profile,
                td,
                fd(PartyPresentationPolicyDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "enemies",
                "Enemies / Bosses",
                lambda: tuple(sorted(db.enemies)),
                lambda k: db.enemies[k],
                en.edit_enemy,
                en.delete_enemy,
                td,
                fd(EnemyDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "encounters",
                "Encounters",
                lambda: tuple(sorted(db.encounters)),
                lambda k: db.encounters[k],
                en.edit_encounter,
                en.delete_encounter,
                td,
                fd(EncounterDefinition),
                None,
            ),
            AuthoringCategoryAdapter(
                "ai",
                "Enemy AI / Boss Phases",
                lambda: tuple(sorted(db.enemy_ai)),
                lambda k: db.enemy_ai[k],
                en.edit_ai,
                en.delete_ai,
                td,
                fd(EnemyAIDefinition),
                None,
            ),
        ]
        mappings = {
            "actors": db.actors,
            "classes": db.classes,
            "passives": db.passives,
            "tracks": db.progression_tracks,
            "graphs": db.progression_graphs,
            "evolutions": db.ability_evolutions,
            "items": db.items,
            "equipment": db.equipment,
            "attachments": db.attachments,
            "growth": db.equipment_growth,
            "recipes": db.composition_recipes,
            "parties": db.party_setups,
            "formations": db.formations,
            "party_ui": db.party_presentation_policies,
            "enemies": db.enemies,
            "encounters": db.encounters,
            "ai": db.enemy_ai,
        }
        result = []
        for adapter in categories:
            if adapter.category_id == "abilities":
                create = lambda key, value: pr.create_ability(value)  # noqa: E731
            elif adapter.category_id in mappings:
                create = self._mapping_create(mappings[adapter.category_id], adapter.label)
            else:
                create = None
            result.append(replace(adapter, create=create))
        return tuple(result)

    def _mapping_create(self, mapping, label):
        def create(key, value):
            from .rpg_actor_class_authoring import _DefinitionCommand

            key = str(key)
            if key in mapping:
                raise ValueError(f"{label} {key} already exists")
            self.document.execute(_DefinitionCommand(mapping, key, value, None, f"Add {label} {key}"))
            return value

        return create

    def battle_categories(self):
        c = self.battle
        result = []
        for kind in c.information_architecture.kinds:
            result.append(
                AuthoringCategoryAdapter(
                    kind.kind_id,
                    kind.label,
                    lambda k=kind.kind_id: tuple(
                        str(getattr(v, c.information_architecture.kind(k).key_attr)) for v in c.definitions(k)
                    ),
                    lambda key, k=kind.kind_id: getattr(c.database, c.information_architecture.kind(k).mapping_name)[
                        key
                    ],
                    lambda key, value, k=kind.kind_id: c.edit(k, key, value),
                    lambda key, k=kind.kind_id: c.delete(k, key),
                    lambda value: value.to_data(),
                    lambda data, k=kind.kind_id: c.information_architecture.kind(k).definition_type.from_data(data),
                    None,
                    lambda key, value, k=kind.kind_id: c.create(k, value),
                )
            )
        return tuple(result)

    def presentation_categories(self):
        c = self.presentation
        labels = {
            "combatant_visuals": "Combatant Visuals",
            "feedback": "Feedback",
            "hud": "Battle HUD",
            "ui_layout": "UI Layout",
            "ui_polish": "UI Polish",
            "sideview_templates": "Side View",
            "portrait_templates": "Portrait Party",
            "animation_timing": "Animation Timing",
            "director": "Presentation Director",
            "layering": "Layering",
            "action_menu": "Action Menu",
            "interaction": "Battle Interaction",
            "results": "Battle Result",
            "party_layout": "Party Layout",
            "ui_theme": "UI Theme",
            "motion_sequences": "Motion Sequences",
            "action_workflows": "Action Workflows",
        }
        result = []
        for category in c.library.categories():
            if category.startswith("rpg_"):
                continue
            result.append(
                AuthoringCategoryAdapter(
                    category,
                    labels.get(category, category.replace("_", " ").title()),
                    lambda cat=category: c.library.ids(cat),
                    lambda key, cat=category: c.library.require(cat, key),
                    lambda key, value, cat=category: c.edit(cat, key, value),
                    lambda key, cat=category: c.delete(cat, key),
                    lambda value, cat=category: c.library._encode(cat, value),
                    lambda data, cat=category: c.library._decode(cat, data),
                    lambda old, new, cat=category: c.duplicate(cat, old, new),
                    lambda key, value, cat=category: c.create(cat, key, value),
                )
            )
        return tuple(result)

    def runtime_ui_categories(self):
        c = self.runtime_ui
        labels = {
            "rpg_character_screen": "Character Screen",
            "rpg_equipment_screen": "Equipment Screen",
            "rpg_ability_screen": "Ability / Passive Screen",
            "rpg_progression_screen": "Progression / Skill Tree Screen",
            "rpg_inventory_screen": "Inventory Screen",
            "rpg_party_screen": "Party / Formation Screen",
        }
        return tuple(
            AuthoringCategoryAdapter(
                cat,
                labels[cat],
                lambda cat=cat: c.library.ids(cat),
                lambda key, cat=cat: c.library.require(cat, key),
                lambda key, value, cat=cat: c.edit(cat, key, value),
                lambda key, cat=cat: c.delete(cat, key),
                lambda value, cat=cat: c.library._encode(cat, value),
                lambda data, cat=cat: c.library._decode(cat, data),
                lambda old, new, cat=cat: c.duplicate(cat, old, new),
                lambda key, value, cat=cat: c.create(cat, key, value),
            )
            for cat in c.CATEGORIES
        )
