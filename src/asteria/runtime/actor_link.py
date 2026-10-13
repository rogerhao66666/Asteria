"""Marks a Scene entity as the field-map representation of an RPG Actor.

Purely a bookkeeping tag: it does not resolve stats, abilities, or presence
by itself. The Editor uses it to find every Entity that stands in for a
given ActorDefinition, so editing that Actor's name/field appearance can be
pushed onto the map — see asteria.editor.actor_appearance. Battle/gameplay
code has no reason to read this component; combat identity already flows
through ResolvedActorBuild independently of any field-map placement.
"""

from asteria.core import Component, Field, component_schema


@component_schema(
    type_name="asteria.ActorLink",
    version=1,
    fields=(Field("actor_id", str, "", label="Actor"),),
)
class ActorLinkComponent(Component):
    def __init__(self):
        super().__init__()
        self.actor_id = ""


@component_schema(
    type_name="asteria.ClassAppearance",
    version=1,
    fields=(
        Field(
            "looks",
            str,
            "",
            label="Looks by class",
            tooltip="class_id=sprite_sheet_asset_id|animation_asset_id; ... The entity's linked "
            "actor shows the look of its active class (the last one that has a look wins), so a "
            "class change changes what the player sees.",
        ),
    ),
)
class ClassAppearanceComponent(Component):
    """Different sprite sheet and animation set per class of the linked actor (D23)."""

    def __init__(self):
        super().__init__()
        self.looks = ""

    def parsed(self):
        """``{class_id: (sprite_sheet_asset_id, animation_asset_id)}``."""
        out = {}
        for chunk in str(self.looks or "").replace("\n", ";").split(";"):
            if "=" not in chunk:
                continue
            class_id, _, rest = chunk.partition("=")
            sheet, _, clips = rest.partition("|")
            if class_id.strip() and sheet.strip():
                out[class_id.strip()] = (sheet.strip(), clips.strip())
        return out
