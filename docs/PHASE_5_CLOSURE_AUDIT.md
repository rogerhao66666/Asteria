# Asteria Phase 5 Closure Audit

Version: `v0.49.0a49`
Status: **FROZEN — Event VM / Dialogue / Authoring Foundation**

## Scope audited

Phase 5 Batches 36–48 plus closure fixes:

- Event VM and deterministic instruction execution
- EventContext: switches, variables, local/self state
- conditions and control flow
- interaction trigger foundation
- EventProgramRegistry / EventRunner
- Dialogue / Choice blocking semantics
- WorldCommand service boundary
- CALL / RETURN and reusable/common events
- Autorun / Parallel scheduler
- Scene / Entity EventBinding model
- canonical Project persistence for EventPrograms / SceneEventBindings
- Event Editor GUI vertical slice
- Scene / Code / Event / Animation workspace
- Python Authoring API v1
- Code workspace execution, rollback, diagnostics, selection context

## Closure blockers found and fixed

### 1. Blocking dialogue/choice was not part of active-event snapshots

Before closure, the VM program counter had already advanced when a DIALOGUE or
CHOICE instruction opened UI state. A snapshot restored only VM/call-stack
state, so restoring while blocked could incorrectly continue past the pending
dialogue/choice.

Fixed by:
- serializing DialogueRequest
- serializing ChoiceRequest
- serializing DialogueRuntimeState
- ActiveEvent snapshot schema v3 includes `dialogue_state`
- v1/v2 ActiveEvent snapshots remain readable

Validated:
- restore while dialogue is blocked does not skip following instructions
- restore while choice is blocked preserves choices and result target

### 2. Scheduled Autorun/Parallel runners did not receive WorldCommandRouter

EventScheduler constructed EventRunner instances without forwarding the
configured world-command service. A WORLD instruction inside Autorun/Parallel
could therefore fail even though foreground events had a valid router.

Fixed by:
- EventScheduler owns optional `world_commands`
- every scheduled EventRunner receives the same router
- SceneEventRuntime.build accepts and propagates the router

Validated with Parallel PLAY_AUDIO and Autorun TRANSFER paths.

## Final execution architecture

```text
Interaction / Autorun / Parallel
             |
             v
        EventBinding
             |
             v
      EventProgramRegistry
             |
             v
     EventRunner / Scheduler
             |
             v
          EventVM
   +---------+----------+
   |         |          |
Context   Dialogue    WorldCommand
Switches  Choice      Router
Variables Wait
Local     Call/Return
```

Authoring paths:

```text
Scene / Inspector ---------+
Event Editor ---------------+--> canonical Project data --> runtime
Python Authoring API -------+
```

## Frozen Phase 5 invariants

1. EventProgram is backend-neutral deterministic data.
2. Persistent references use stable IDs; names are convenience/presentation.
3. EventContext is serializable and UI-independent.
4. Dialogue/Choice are true blocking runtime states.
5. Save/resume must preserve blocked dialogue/choice and call-stack position.
6. World effects cross the Event -> game boundary through WorldCommandRouter.
7. Autorun/Parallel scheduling is separate from the foreground interaction runner.
8. Scene bindings are canonical Project data, not editor-only state.
9. Event Editor edits canonical EventProgram/EventBinding data.
10. Python authoring and GUI authoring operate on the same canonical model.
11. Authoring/runtime core has no Qt dependency.
12. Authoring/runtime core has no pygame dependency.
13. Code workspace script failure rolls back already-applied authoring mutations.
14. A successful script run is one Editor undo/redo transaction.
15. Project scripts are trusted local Python; the runner is not a security sandbox.

## Validation

- full pytest: **168 passed**
- compileall: **PASS**
- Event / Authoring / Core Qt import audit: **PASS**
- Event / Authoring / Core pygame import audit: **PASS**
- Project v2 compatibility: **PASS**
- ActiveEvent snapshot v1/v2 compatibility: **PASS**
- ActiveEvent v3 blocked-dialogue/choice resume: **PASS**
- scheduled WORLD command routing: **PASS**
- script rollback / single-step undo: **PASS**

## Non-blocking deferred work

These are future usability/tooling improvements, not Phase 5 architecture blockers:

- richer Event Editor structured property panels
- visual indentation / ELSE presentation for branches
- condition edit/remove UI
- event rename/duplicate/delete UX
- command search/palette
- Event VM debugger / breakpoints / current-instruction highlighting
- richer Code editor features such as completion/LSP integration
- broader Python Authoring API coverage as Phase 6+ systems are added
- final Dialogue presentation/UI skin

## Closure decision

No remaining architecture blocker was found for the Phase 5 boundary after the
two closure fixes above.

**Phase 5 is FROZEN at v0.49.0a49.**

Next phase:
**Phase 6 — Generic Gameplay Framework**
(Stats, Resource, Modifier, Effect, State, Ability, Trigger, Condition, Tags,
Targeting and related canonical authoring/runtime foundations.)
