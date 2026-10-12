from dataclasses import dataclass

from asteria.core.metadata import get_component_schema


@dataclass(frozen=True, slots=True)
class InspectorFieldModel:
    name: str
    label: str
    value: object
    value_type: type
    type_name: str
    editable: bool
    minimum: float | int | None = None
    maximum: float | int | None = None
    choices: tuple | None = None
    tooltip: str = ""


def build_inspector_fields(component):
    schema = get_component_schema(type(component))
    fields = schema.fields.values()
    return tuple(
        InspectorFieldModel(
            name=f.name,
            label=f.label or f.name.replace("_", " ").title(),
            value=getattr(component, f.name),
            value_type=f.value_type,
            type_name=f.value_type.__name__,
            editable=bool(f.serialize),
            minimum=f.minimum,
            maximum=f.maximum,
            choices=tuple(f.choices) if f.choices is not None else None,
            tooltip=f.tooltip,
        )
        for f in fields
    )


def build_follow_entity_choices(component):
    """Return display labels mapped to canonical entity IDs for Camera2D."""
    from asteria.core import Transform

    try:
        owner = component.entity
    except RuntimeError:
        return (("Fixed", ""),)
    scene = owner.scene
    if scene is None:
        return (("Fixed", ""),)
    choices = [("Fixed", "")]
    for entity in scene.entities():
        if entity is owner or entity.try_get(Transform) is None:
            continue
        choices.append((f"Follow {entity.name}", entity.id))
    current = str(getattr(component, "follow_entity_id", ""))
    if current and all(value != current for _, value in choices):
        choices.append((f"Missing entity ({current})", current))
    return tuple(choices)


def _with_missing(choices, current, label):
    current = str(current or "")
    if current and all(value != current for _, value in choices):
        choices.append((f"Missing {label} ({current})", current))
    return tuple(choices)


def build_actor_link_choices(project, current=""):
    """Return display labels mapped to Actor ids for ActorLinkComponent."""
    choices = [("— None —", "")]
    actors = project.rpg_database.actors if project is not None else {}
    for actor_id in sorted(actors):
        choices.append((f"{actors[actor_id].display_name} ({actor_id})", actor_id))
    return _with_missing(choices, current, "actor")


def build_asset_id_choices(ids, current="", *, label="asset"):
    """Dropdown entries for an asset-id field from the asset ids the editor resolved."""
    choices = [("— None —", "")]
    choices.extend((asset_id, asset_id) for asset_id in ids)
    return _with_missing(choices, current, label)


def inspector_choices(document, component, field):
    """Choices for an Inspector field, or None when it is edited as plain text."""
    if field.name == "follow_entity_id":
        return build_follow_entity_choices(component)
    if field.name == "parent_id":
        return build_parent_choices(component)
    if field.name == "actor_id":
        return build_actor_link_choices(document.project, field.value)
    if field.name == "sprite_sheet_asset_id":
        return build_asset_id_choices(document.asset_views.sprite_sheet_ids(), field.value, label="sprite sheet")
    if field.name == "effect_id" and document.project is not None:  # ParticleEmitter2D (VFX-01)
        from asteria.presentation.particles import PARTICLE_KIND

        ids = sorted(a.asset_id for a in document.project.assets.query(kind=PARTICLE_KIND))
        return build_asset_id_choices(ids, field.value, label="particle effect")
    if field.name == "clip_set_id":
        return build_asset_id_choices(document.asset_views.clip_set_ids(), field.value, label="clip set")
    if field.choices:
        return tuple((str(choice), choice) for choice in field.choices)
    return None


def build_parent_choices(component):
    """Transform parent dropdown: entities in the same scene that would not form a cycle."""
    from asteria.core import can_parent

    try:
        owner = component.entity
    except RuntimeError:
        return (("— None —", ""),)
    choices = [("— None —", "")]
    scene = owner.scene
    if scene is not None:
        choices.extend((e.name, e.id) for e in scene.entities() if e is not owner and can_parent(owner, e))
    return _with_missing(choices, getattr(component, "parent_id", ""), "entity")
