# Batch 110 — Camera / VFX / Audio Layering

Batch 110 adds a shared presentation staging context across animation, VFX, camera, screen FX and audio cues.

## Shared staging context

Timeline cue payloads may provide project-authored `staging` metadata:

- `group_id`
- `layer`
- `intensity`
- `gain`
- `bus`
- `priority`

Cues that share a `group_id` can be treated as parts of the same authored impact/staging moment without creating gameplay coupling.

`BattlePresentationLayeringRuntime` copies and decorates already-resolved presentation events before they enter the existing animation/feedback/camera runtimes.

## Channel policy

`BattlePresentationLayeringProfile` provides project defaults per channel. Built-in channel names are merely presentation routing names:

- animation
- vfx
- camera
- screen_fx
- audio
- light

Projects may still introduce other cue kinds/channels.

Channel gain/intensity can scale presentation payloads. Camera amplitudes are presentation-scaled; audio receives gain/bus metadata; VFX/screen FX receive layer/intensity metadata.

## Ordering

Active VFX and screen FX are deterministically ordered by authored layer/priority. One-shot audio cues are drained in deterministic priority/layer/sequence order.

This is not gameplay ordering. It changes only how already-resolved effects are presented.

## Boundary

The layering runtime cannot create or resolve attacks, damage, hits, targets, resources, scheduler changes or outcomes. Non-timeline resolved events pass through unchanged.
