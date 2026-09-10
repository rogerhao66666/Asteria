from __future__ import annotations

from asteria.core import Component, Field, component_schema

from .stats import ResourcePool, StatBlock
from .tags import TagSet


@component_schema(
    type_name="asteria.GameplayAttributes",
    version=1,
    fields=(
        Field("stats", dict, {}, label="Stats", category="Gameplay"),
        Field("resources", dict, {}, label="Resources", category="Gameplay"),
        Field("tags", list, [], label="Tags", category="Gameplay"),
    ),
)
class GameplayAttributesComponent(Component):
    """Canonical persistent owner for generic stats/resources/tags.

    Serialized representation stays JSON-native so normal Project persistence,
    Inspector metadata, scripting and future database tooling share one source.
    """

    def __init__(self):
        super().__init__()
        self.stats = {}
        self.resources = {}
        self.tags = []

    def stat_block(self):
        return StatBlock(self.stats)

    def set_stat_block(self, block: StatBlock):
        if not isinstance(block, StatBlock):
            raise TypeError("block must be StatBlock")
        self.stats = dict(block.to_data()["values"])

    def resource_pool(self):
        return ResourcePool.from_data(
            {
                "schema": "asteria.resource_pool",
                "version": 1,
                "values": self.resources,
            }
        )

    def set_resource_pool(self, pool: ResourcePool):
        if not isinstance(pool, ResourcePool):
            raise TypeError("pool must be ResourcePool")
        self.resources = dict(pool.to_data()["values"])

    def tag_set(self):
        return TagSet(self.tags)

    def set_tag_set(self, tags: TagSet):
        if not isinstance(tags, TagSet):
            raise TypeError("tags must be TagSet")
        self.tags = list(tags.values())
