# Batch 153 — Field / Interaction / Game Flow Editor

Batch 153 connects existing canonical Scene/Entity, Interaction2D, EventBinding and
EventProgram systems into one field/game-flow authoring workflow.

The Editor can author and inspect:
- Scene flow context
- Entity action interactions
- Interaction range and facing requirements
- Event bindings and conditions
- Event programs / commands
- Encounter-start world commands
- The full Entity -> Interaction2D -> EventBinding -> EventProgram chain

The simplest intended encounter is now directly expressible as project data:
walk to a boss entity, face it, press Interact, run an event program, dispatch
START_ENCOUNTER, enter battle, then let game flow return to the field.

No random encounter or aggro system is required for this validation path.

## Information architecture

The workspace is divided into Scene Flow / Interactions / Event Programs /
Encounter Flow. It uses the scene viewport plus a contextual inspector. Selecting
an entity resolves its interaction/binding/program chain; selecting an event
command focuses only that command's detail.

This reuses the existing Event Editor and canonical event/runtime systems rather
than creating a second game-flow model.
