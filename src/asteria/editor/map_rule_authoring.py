"""Undoable editing for region rules used by the Tiles panel."""

from __future__ import annotations

from asteria.rpg.map_rules import AreaRule, MapRuleSet

from .game_systems_authoring import GameSystemsAuthoringController


class MapRuleAuthoringError(ValueError):
    """The project has no active map ruleset or a region rule is invalid."""


class MapRuleAuthoringController:
    """Edit the same first-sorted map ruleset the field runtime currently binds."""

    def __init__(self, document):
        self.document = document
        self.systems = GameSystemsAuthoringController(document)

    @property
    def ruleset(self):
        sets = self.systems.database.map_rule_sets
        return sets[sorted(sets)[0]] if sets else None

    def create_ruleset(self):
        key = "map"
        suffix = 2
        while key in self.systems.database.map_rule_sets:
            key = f"map_{suffix}"
            suffix += 1
        return self.systems.create_new("map_rule_sets", key)

    def set_region_rule(self, rule):
        if not isinstance(rule, AreaRule) or not rule.key.startswith("region:"):
            raise MapRuleAuthoringError("a region rule must use an AreaRule key region:<id>")
        ruleset = self.ruleset
        if ruleset is None:
            raise MapRuleAuthoringError("create a map ruleset before editing regions")
        rules = {item.key: item for item in ruleset.rules}
        rules[rule.key] = rule
        replacement = MapRuleSet(
            ruleset.rules_id,
            tuple(rules[key] for key in sorted(rules)),
            region_layer=ruleset.region_layer,
            crouch_visibility=ruleset.crouch_visibility,
            still_visibility=ruleset.still_visibility,
        )
        return self.systems.edit("map_rule_sets", ruleset.rules_id, replacement)

    def remove_region_rule(self, region_id):
        ruleset = self.ruleset
        if ruleset is None:
            return False
        key = f"region:{int(region_id)}"
        rules = tuple(rule for rule in ruleset.rules if rule.key != key)
        if len(rules) == len(ruleset.rules):
            return False
        replacement = MapRuleSet(
            ruleset.rules_id,
            rules,
            region_layer=ruleset.region_layer,
            crouch_visibility=ruleset.crouch_visibility,
            still_visibility=ruleset.still_visibility,
        )
        self.systems.edit("map_rule_sets", ruleset.rules_id, replacement)
        return True
