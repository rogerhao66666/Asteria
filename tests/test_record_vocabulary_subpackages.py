"""The editor's choice lists are read from every engine module, also those in subpackages
(``asteria.rpg.battle``, ``asteria.rpg.items``...): a field whose allowed values are written in
a subpackage module still gets its list."""

from asteria.editor.records.vocabulary import engine_enums


def test_choice_lists_come_from_modules_inside_subpackages():
    enums = engine_enums()
    # rpg.battle.interactions (InteractionDisposition) and rpg.battle.targeting (TargetRelation)
    assert {"absorb", "reflect"} <= set(enums["disposition"])
    assert {"ally", "opponent"} <= set(enums["relation"])
    # rpg.battle.resources (BattleResourceStartMode)
    assert "maximum" in enums["start_mode"]
