import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.rpg_party_formation_authoring import (
    RpgPartyFormationAuthoringController,
    RpgPartyFormationAuthoringError,
)
from asteria.editor.rpg_party_formation_workspace import (
    RpgPartyFormationWorkspaceModel,
)
from asteria.project import Project
from asteria.rpg import (
    ActorDefinition,
    FormationDefinition,
    FormationSlotDefinition,
    PartyPlacementDefinition,
    PartyPresentationPolicyDefinition,
    PartySetupDefinition,
)


def make():
    p = Project("Game")
    p.add_scene(Scene("Main"))
    for actor_id in ("a", "b", "c", "d", "e", "f"):
        p.rpg_database.add_actor(ActorDefinition(actor_id, actor_id.upper()))
    doc = EditorDocument(p)
    return p, doc, RpgPartyFormationAuthoringController(doc)


def formation():
    return FormationDefinition(
        "line",
        (
            FormationSlotDefinition("front_l", x=0, y=0, tags=("front",), adjacent_to=("front_r", "back_l")),
            FormationSlotDefinition("front_r", x=1, y=0, tags=("front",), adjacent_to=("front_l", "back_r")),
            FormationSlotDefinition("back_l", x=0, y=1, tags=("back",), adjacent_to=("front_l", "back_r")),
            FormationSlotDefinition("back_r", x=1, y=1, tags=("back",), adjacent_to=("front_r", "back_l")),
        ),
    )


def test_formation_full_slot_data_and_undo():
    p, doc, c = make()
    f = c.create_formation(formation())
    assert f.slot("front_l").tags == ("front",)
    assert "back_l" in f.slot("front_l").adjacent_to
    edited = FormationDefinition("line", (FormationSlotDefinition("solo", x=3, y=4, tags=("focus",)),))
    c.edit_formation("line", edited)
    assert p.rpg_database.formations["line"].slot("solo").x == 3
    assert doc.undo()
    assert p.rpg_database.formations["line"].slot("front_l").x == 0


def test_party_roster_active_reserve_policy_and_placements():
    p, doc, c = make()
    c.create_formation(formation())
    party = c.create_party(
        PartySetupDefinition(
            "main",
            "Main Party",
            roster_actor_ids=("a", "b", "c", "d", "e", "f"),
            active_actor_ids=("a", "b", "c", "d"),
            active_capacity=4,
            formation_id="line",
            placements=(
                PartyPlacementDefinition("a", "front_l"),
                PartyPlacementDefinition("b", "front_r"),
                PartyPlacementDefinition("c", "back_l"),
                PartyPlacementDefinition("d", "back_r"),
            ),
            allow_reserve=True,
            allow_swap=True,
            allow_reorder=False,
            tags=("player",),
        )
    )
    assert party.reserve_actor_ids == ("e", "f")
    assert not party.allow_reorder
    assert len(party.placements) == 4


def test_set_active_preserves_valid_placements_only():
    p, doc, c = make()
    c.create_formation(formation())
    c.create_party(
        PartySetupDefinition(
            "main",
            roster_actor_ids=("a", "b", "c", "d", "e"),
            active_actor_ids=("a", "b", "c", "d"),
            active_capacity=4,
            formation_id="line",
            placements=(PartyPlacementDefinition("a", "front_l"), PartyPlacementDefinition("b", "front_r")),
        )
    )
    c.set_active("main", ("a", "c", "d", "e"))
    party = p.rpg_database.party_setups["main"]
    assert party.active_actor_ids == ("a", "c", "d", "e")
    assert party.reserve_actor_ids == ("b",)
    assert tuple(x.actor_id for x in party.placements) == ("a",)


def test_place_actor_replaces_slot_occupant_without_duplicates():
    p, doc, c = make()
    c.create_formation(formation())
    c.create_party(
        PartySetupDefinition(
            "main",
            roster_actor_ids=("a", "b"),
            active_actor_ids=("a", "b"),
            active_capacity=2,
            formation_id="line",
            placements=(PartyPlacementDefinition("a", "front_l"),),
        )
    )
    c.place_actor("main", "b", "front_l")
    party = p.rpg_database.party_setups["main"]
    assert party.placements == (PartyPlacementDefinition("b", "front_l"),)


def test_unknown_actor_and_slot_refs_are_rejected():
    _, _, c = make()
    c.create_formation(formation())
    with pytest.raises(RpgPartyFormationAuthoringError):
        c.create_party(PartySetupDefinition("bad", roster_actor_ids=("missing",), active_actor_ids=()))
    with pytest.raises(RpgPartyFormationAuthoringError):
        c.create_party(
            PartySetupDefinition(
                "bad2",
                roster_actor_ids=("a",),
                active_actor_ids=("a",),
                formation_id="line",
                placements=(PartyPlacementDefinition("a", "missing"),),
            )
        )


def test_delete_formation_protects_party_reference():
    _, _, c = make()
    c.create_formation(formation())
    c.create_party(
        PartySetupDefinition(
            "main",
            roster_actor_ids=("a",),
            active_actor_ids=("a",),
            formation_id="line",
            placements=(PartyPlacementDefinition("a", "front_l"),),
        )
    )
    with pytest.raises(RpgPartyFormationAuthoringError):
        c.delete_formation("line")


def test_presentation_policy_is_canonical_and_undoable():
    p, doc, c = make()
    profile = PartyPresentationPolicyDefinition(
        "default",
        group_order=("active", "reserve"),
        group_labels={"active": "Front Team", "reserve": "Bench"},
        visible_limits={"active": 4, "reserve": 6},
        slot_labels={"front_l": "Front Left"},
    )
    c.set_presentation_profile("default", profile)
    assert p.rpg_database.party_presentation_policies["default"].visible_limits == (("active", 4), ("reserve", 6))
    assert doc.undo()
    assert "default" not in p.rpg_database.party_presentation_policies
    assert doc.redo()


def test_database_v22_roundtrip_preserves_party_setup_and_ui_policy():
    p, doc, c = make()
    c.create_formation(formation())
    c.create_party(
        PartySetupDefinition(
            "main",
            roster_actor_ids=("a", "b"),
            active_actor_ids=("a",),
            active_capacity=2,
            formation_id="line",
            placements=(PartyPlacementDefinition("a", "front_l"),),
        )
    )
    c.set_presentation_profile(
        "default", PartyPresentationPolicyDefinition("default", visible_limits={"active": 4, "reserve": 8})
    )
    raw = p.to_data()
    assert raw["rpg_database"]["version"] == 28
    clone = Project.from_data(raw, doc.component_registry)
    assert clone.to_data() == raw
    assert clone.rpg_database.party_setups["main"].reserve_actor_ids == ("b",)
    assert clone.rpg_database.party_presentation_policies["default"].profile_id == "default"


def test_old_v21_database_remains_backward_readable():
    p, doc, c = make()
    raw = p.rpg_database.to_data()
    raw["version"] = 21
    raw.pop("party_setups")
    raw.pop("party_presentation_policies")
    from asteria.rpg import RpgDatabase

    restored = RpgDatabase.from_data(raw)
    assert restored.party_setups == {}
    assert restored.party_presentation_policies == {}


def test_information_architecture_avoids_large_party_visual_sprawl():
    _, _, c = make()
    ia = c.information_architecture
    assert ia.roster_pattern == "browser_plus_active_reserve"
    assert ia.formation_pattern == "canvas_plus_contextual_slot_inspector"
    assert ia.progressive_disclosure
    assert not ia.show_all_members_as_full_cards
    assert not ia.show_all_details_simultaneously


def test_workspace_focus_is_contextual():
    _, _, c = make()
    c.create_formation(formation())
    c.create_party(PartySetupDefinition("main", roster_actor_ids=("a", "b"), active_actor_ids=("a",)))
    w = RpgPartyFormationWorkspaceModel(c)
    w.select("main")
    w.focus_actor("b")
    assert w.snapshot().focused_actor_id == "b"
    w.set_section("formations")
    assert w.snapshot().focused_actor_id is None
    w.select("line")
    w.focus_slot("front_r")
    assert w.snapshot().focused_slot_id == "front_r"


def test_project_validation_after_party_authoring():
    p, _, c = make()
    c.create_formation(formation())
    c.create_party(
        PartySetupDefinition(
            "main",
            roster_actor_ids=("a", "b", "c"),
            active_actor_ids=("a", "b"),
            active_capacity=2,
            formation_id="line",
            placements=(PartyPlacementDefinition("a", "front_l"), PartyPlacementDefinition("b", "front_r")),
        )
    )
    assert c.validate() == ()
    assert p.validate()
