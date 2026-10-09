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
    fields=(
        Field("actor_id", str, "", label="Actor"),
    ),
)
class ActorLinkComponent(Component):
    def __init__(self):
        super().__init__()
        self.actor_id = ""
