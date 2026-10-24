from asteria.core import (
    ComponentRegistry,
    Entity,
    Scene,
    Transform,
    deserialize_scene,
    serialize_scene,
)
from asteria.runtime import (
    InputSnapshot,
    Interaction2DComponent,
    InteractionController,
    InteractionQuery,
)


def make_interactable(scene, name, x, y, event_id, *, radius=24.0, facing=True):
    entity = scene.add_entity(Entity(name))
    entity.add_component(Transform(x, y))
    interaction = entity.add_component(Interaction2DComponent())
    interaction.event_program_id = event_id
    interaction.range = radius
    interaction.require_facing = facing
    return entity


def test_query_prefers_nearest_eligible_entity_and_facing():
    scene = Scene("Town")
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(10, 10))
    front = make_interactable(scene, "NPC", 10, 20, "event-npc")
    make_interactable(scene, "Behind", 10, 4, "event-behind", facing=True)
    make_interactable(scene, "Far", 10, 80, "event-far", radius=20)

    candidate = InteractionQuery().nearest(scene, hero, "down")
    assert candidate.entity is front
    assert candidate.component.event_program_id == "event-npc"


def test_non_facing_interaction_can_be_triggered_from_any_direction():
    scene = Scene("Town")
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(0, 0))
    chest = make_interactable(scene, "Chest", -8, 0, "event-chest", facing=False)

    assert InteractionQuery().nearest(scene, hero, "right").entity is chest


def test_action_button_is_edge_triggered_and_returns_event_start_seam():
    scene = Scene("Town")
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(0, 0))
    npc = make_interactable(scene, "NPC", 0, 12, "event-123")
    interaction = npc.get(Interaction2DComponent)
    interaction.local_scope_id = "npc-local-123"

    controller = InteractionController()
    released = InputSnapshot({"interact": 0})
    pressed = InputSnapshot({"interact": 1})

    assert controller.step(released, scene, hero, "down") is None
    trigger = controller.step(pressed, scene, hero, "down")
    assert trigger.source_entity_id == npc.id
    assert trigger.event_program_id == "event-123"
    assert trigger.local_scope_id == "npc-local-123"

    # Holding the button must not start the same event every frame.
    assert controller.step(pressed, scene, hero, "down") is None
    controller.step(released, scene, hero, "down")
    assert controller.step(pressed, scene, hero, "down") is not None


def test_a_release_seen_while_an_event_runs_lets_the_next_press_trigger():
    scene = Scene("Town")
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(10, 10))
    make_interactable(scene, "Sign", 10, 20, "event-sign")
    controller = InteractionController()
    down, up = InputSnapshot({"interact": 1.0}), InputSnapshot({"interact": 0.0})

    assert controller.step(down, scene, hero, "down") is not None  # a talk starts
    controller.observe(up)  # the release arrives while the talk's event runs
    assert controller.step(down, scene, hero, "down") is not None
    controller.observe(down)  # the press that closes a talk is still held when it ends
    assert controller.step(down, scene, hero, "down") is None


def test_default_local_scope_uses_stable_entity_id():
    scene = Scene("Town")
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(0, 0))
    chest = make_interactable(scene, "Chest", 0, 8, "event-chest")

    controller = InteractionController()
    trigger = controller.step(InputSnapshot({"interact": 1}), scene, hero, "down")
    assert trigger.local_scope_id == chest.id


def test_interaction_component_serialization_roundtrip():
    registry = ComponentRegistry()
    registry.register(Transform)
    registry.register(Interaction2DComponent)

    scene = Scene("Town")
    npc = make_interactable(scene, "NPC", 4, 7, "event-dialogue")
    c = npc.get(Interaction2DComponent)
    c.event_binding_id = "binding-npc"
    c.range = 30.0
    c.require_facing = False
    c.local_scope_id = "npc-scope"

    restored = deserialize_scene(serialize_scene(scene), registry)
    restored_component = restored.entities()[0].get(Interaction2DComponent)
    assert restored_component.event_program_id == "event-dialogue"
    assert restored_component.event_binding_id == "binding-npc"
    assert restored_component.range == 30.0
    assert restored_component.require_facing is False
    assert restored_component.local_scope_id == "npc-scope"
