"""Animation state machine editor API (ANI-02).

A sprite sheet's state machine is stored in its asset metadata
(``state_machine``, an ``AnimationStateMachineDefinition``) next to the clips it
chooses between; the runtime clip set carries it to ``AnimationSystem``.
Node positions for the graph view are kept in ``state_machine_layout``.
Every edit is one undoable command and is validated against the sheet's clips.
"""

from __future__ import annotations

from dataclasses import replace

from asteria.runtime.animation import AnimatorState
from asteria.runtime.animation_state_machine import (
    AnimationCondition,
    AnimationStateMachine,
    AnimationStateMachineDefinition,
    AnimationTransition,
)

from .animation_authoring import AnimationAuthoringController, _ReplaceAssetCommand

OPERATORS = ("==", "!=", "<", "<=", ">", ">=")


class StateMachineAuthoringError(ValueError):
    pass


class AnimationStateMachineAuthoring:
    def __init__(self, document, *, resource_root=None):
        self.document = document
        self.animation = AnimationAuthoringController(document, resource_root=resource_root)

    def sheets(self):
        return self.animation.sheets()

    def clips(self, asset_id):
        return tuple(sorted(self.animation.data(asset_id)["clips"]))

    def definition(self, asset_id):
        raw = self.animation.asset(asset_id).meta().get("state_machine")
        return None if not raw else AnimationStateMachineDefinition.from_data(raw)

    def layout(self, asset_id):
        return dict(self.animation.asset(asset_id).meta().get("state_machine_layout", {}))

    def _commit(self, asset_id, definition, label, layout=None):
        if definition is not None:
            missing = sorted(c for c in definition.states.values() if c not in self.clips(asset_id))
            if missing:
                raise StateMachineAuthoringError(f"states use clips this sheet does not have: {', '.join(missing)}")
        before = self.animation.asset(asset_id)
        meta = before.meta()
        if definition is None:
            meta.pop("state_machine", None)
        else:
            meta["state_machine"] = definition.to_data()
        if layout is not None:
            meta["state_machine_layout"] = layout
        after = replace(before, metadata=tuple(sorted(meta.items())))
        self.document.execute(_ReplaceAssetCommand(self.animation.project.assets, before, after, label))
        return self.definition(asset_id)

    def _rebuild(self, asset_id, label, **changes):
        current = self.definition(asset_id)
        if current is None:
            raise StateMachineAuthoringError(f"{asset_id} has no state machine yet")
        values = {
            "states": dict(current.states),
            "initial": current.initial,
            "transitions": current.transitions,
            "parameters": dict(current.parameters),
            "triggers": current.triggers,
        }
        values.update(changes)
        try:
            definition = AnimationStateMachineDefinition(**values)
        except (TypeError, ValueError) as exc:
            raise StateMachineAuthoringError(str(exc)) from exc
        return self._commit(asset_id, definition, label)

    # -- edits -------------------------------------------------------------------------------------
    def create(self, asset_id, initial_clip=None):
        if self.definition(asset_id) is not None:
            raise StateMachineAuthoringError(f"{asset_id} already has a state machine")
        clips = self.clips(asset_id)
        clip = initial_clip or ("idle" if "idle" in clips else clips[0])
        definition = AnimationStateMachineDefinition({clip: clip}, clip)
        return self._commit(asset_id, definition, f"State machine for {asset_id}", layout={clip: [40.0, 40.0]})

    def remove_machine(self, asset_id):
        return self._commit(asset_id, None, f"Remove state machine of {asset_id}")

    def add_state(self, asset_id, state, clip, position=None):
        current = self.definition(asset_id)
        if state in current.states:
            raise StateMachineAuthoringError(f"state {state} exists")
        with self.document.group(f"Add state {state}"):  # adding and placing is one undo step
            result = self._rebuild(asset_id, f"Add state {state}", states={**current.states, str(state): str(clip)})
            if position is not None:
                result = self.move_state(asset_id, state, *position)
        return result

    def set_state_clip(self, asset_id, state, clip):
        current = self.definition(asset_id)
        return self._rebuild(asset_id, f"State {state} plays {clip}", states={**current.states, state: str(clip)})

    def remove_state(self, asset_id, state):
        current = self.definition(asset_id)
        if state == current.initial:
            raise StateMachineAuthoringError("the initial state cannot be removed (choose another initial first)")
        states = {k: v for k, v in current.states.items() if k != state}
        transitions = tuple(t for t in current.transitions if state not in (t.source, t.target))
        return self._rebuild(asset_id, f"Remove state {state}", states=states, transitions=transitions)

    def set_initial(self, asset_id, state):
        return self._rebuild(asset_id, f"Initial state {state}", initial=str(state))

    def add_parameter(self, asset_id, name, default=0.0, *, trigger=False):
        current = self.definition(asset_id)
        if name in current.parameters or name in current.triggers:
            raise StateMachineAuthoringError(f"parameter {name} exists")
        if trigger:
            return self._rebuild(asset_id, f"Add trigger {name}", triggers=(*current.triggers, str(name)))
        return self._rebuild(asset_id, f"Add parameter {name}", parameters={**current.parameters, str(name): default})

    def add_transition(self, asset_id, source, target, *, conditions=(), when_finished=False, priority=0):
        current = self.definition(asset_id)
        conditions = tuple(
            c if isinstance(c, AnimationCondition) else AnimationCondition(c[0], c[1], c[2]) for c in conditions
        )
        transition = AnimationTransition(str(source), str(target), conditions, bool(when_finished), int(priority))
        return self._rebuild(
            asset_id, f"Transition {source} → {target}", transitions=(*current.transitions, transition)
        )

    def edit_transition(self, asset_id, index, **changes):
        current = self.definition(asset_id)
        transitions = list(current.transitions)
        old = transitions[int(index)]
        if "conditions" in changes:
            changes["conditions"] = tuple(
                c if isinstance(c, AnimationCondition) else AnimationCondition(c[0], c[1], c[2])
                for c in changes["conditions"]
            )
        transitions[int(index)] = replace(old, **changes)
        return self._rebuild(asset_id, f"Edit transition {old.source} → {old.target}", transitions=tuple(transitions))

    def remove_transition(self, asset_id, index):
        current = self.definition(asset_id)
        transitions = list(current.transitions)
        removed = transitions.pop(int(index))
        return self._rebuild(
            asset_id, f"Remove transition {removed.source} → {removed.target}", transitions=tuple(transitions)
        )

    def move_state(self, asset_id, state, x, y):
        layout = self.layout(asset_id)
        layout[str(state)] = [round(float(x), 1), round(float(y), 1)]
        return self._commit(asset_id, self.definition(asset_id), f"Move {state}", layout=layout)

    # -- preview -----------------------------------------------------------------------------------
    def simulate(self, asset_id, steps):
        """Run the runtime state machine over ``steps`` = ``[(dt, {param: value}, [triggers])]``; returns states."""
        from asteria.runtime.battle_visuals import BattleVisualResolver

        definition = self.definition(asset_id)
        if definition is None:
            raise StateMachineAuthoringError(f"{asset_id} has no state machine")
        project = self.document.project
        resolver = BattleVisualResolver(project, lambda uri: self.animation.image_size(asset_id))
        clip_set = resolver.clip_set(asset_id)
        first = clip_set.get(definition.states[definition.initial])
        machine = AnimationStateMachine(clip_set.state_machine, clip_set, AnimatorState(first))
        states = [machine.state]
        for dt, parameters, triggers in steps:
            for name, value in dict(parameters or {}).items():
                machine.set(name, value)
            for name in triggers or ():
                machine.trigger(name)
            states.append(machine.update(float(dt)))
        return states
