# Phase 6 Batch 56 — Action Timeline / Presentation Seam

Version: `v0.56.0a56`

## Goal

Make gameplay timing and presentation authorable together without coupling
Ability rules to animation/render/audio backends.

```text
AbilityDefinition = what the action does
ActionTimeline    = when gameplay and presentation cues occur
```

## Cue kinds

- gameplay ability
- character animation
- VFX
- audio
- camera
- light
- screen FX

Only `GAMEPLAY_ABILITY` changes gameplay state. Other cues are emitted as
backend-neutral presentation data.

Example:

```text
0.00 animation  sword windup
0.12 VFX        charge
0.24 animation  slash
0.27 VFX        slash arc
0.28 GAMEPLAY   execute ability
0.29 camera     impact shake
0.29 audio      heavy hit
0.31 light      flash
```

## Why this boundary matters

A turn-based battle controller may advance the timeline according to battle
flow. A realtime ARPG controller may advance it every frame. Both invoke the
same AbilityRuntime at authored gameplay cues.

The renderer/audio/editor can consume presentation cues independently.

## Determinism and save/resume

Cues are ordered by `(time, cue_id)`. A large `dt` dispatches every crossed cue
once. Timeline player snapshots preserve the next cue index, preventing already
executed gameplay hits from replaying after restore.

## Visual authoring direction

Future Action Timeline Editor can expose tracks for:

```text
Actor | Weapon | VFX | Gameplay Hit | Audio | Camera | Light | Screen FX
```

Beginner presets can generate the same canonical ActionTimeline automatically.
Advanced users can edit exact timing.

## Deferred intentionally

- spatial hitbox/projectile queries
- animation asset binding details
- renderer implementation
- audio implementation
- hit-stop clock ownership
- cooldowns
- combo/input windows
- full Timeline Editor GUI

These belong to later ARPG/editor/polish layers, not Ability core.

## Next

Batch 57 should consolidate Phase 6 canonical gameplay definitions/registries
and authoring/editor seams before Phase 6 closure, rather than prematurely
building Phase 7 RPG-specific systems.
