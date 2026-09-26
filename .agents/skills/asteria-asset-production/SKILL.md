---
name: asteria-asset-production
description: Use when creating, regenerating, validating, packaging, or reviewing formal Asteria production art assets, especially character animations, sprites, weapons, monsters, VFX, tiles, props, portraits, icons, or Starter Pack content.
---

# Asteria Asset Production — Executable Production Protocol v2

## Non-negotiable completion contract

A generation attempt is never the deliverable. The user receives **one complete useful asset unit**. For animation this means the complete requested animation (all required directions and frames), never an individual frame, source board, contact sheet, or raw generator output.

A task is complete only after the canonical output passes every applicable gate. **Technical PASS alone is never final.** Failed internal attempts stay internal unless a genuine blocker requires user input.

## Authority and separation of responsibilities

The production protocol decides animation semantics. The image generator does **not** decide frame count, facing, pose progression, timing, foot contacts, anchors, sockets, weapon trajectory, anticipation, impact, recovery, or loop structure. The generator is an art renderer for an already-defined frame specification.

Before generating pixels, create an `AnimationProductionPlan` containing:

- asset/character ID and approved Master Reference ID;
- animation ID and purpose;
- required directions;
- frame count per direction;
- per-frame duration;
- per-frame pose intent and motion phase;
- planted/contact foot or support state where relevant;
- root/foot target and expected silhouette envelope;
- socket/grip targets where relevant;
- loop seam requirements;
- canonical canvas policy (preset target plus permission to grow);
- identity invariants: face, hair, costume, proportions, palette, authored attachments.

Do not begin final frame production until this plan exists.

## Internal frame production loop

For each direction, create frames sequentially. Each frame is produced with three references: **Master Reference + current Frame Specification + adjacent accepted frame(s)**. A previous generated frame never replaces the Master Reference as identity authority.

For every source frame:

1. Render/draw the requested pose only; do not ask the generator to invent the animation.
2. Run **Source Integrity Gate before any crop, resize, background removal, or canonicalization**.
3. Require complete authored subject, full head/hair, hands/arms, legs/feet, clothing/cape, applicable attachments, and safe source margin. Source clipping is a hard failure.
4. Compare against the Master Reference for identity and against adjacent accepted frames for local continuity.
5. Compare pose/silhouette/contact state against the Frame Specification. A beautiful frame with the wrong motion is a failure.
6. If failed, regenerate/rework only the smallest affected unit and repeat. Do not continue downstream with a known-bad frame.
7. Freeze the accepted source frame and continue to the next frame.

Do not deliver after a frame passes. Continue until the entire requested animation exists.

## Canonicalization

Canonicalize accepted source frames only. Perform alpha/background cleanup, bbox analysis, proportional scaling, stable root/foot alignment, cross-frame stabilization, socket preservation, and packing. Never crop authored content to force 48x48. 48x48 is a Starter preset, not an engine limit. Increase canonical canvas when motion or authored content needs it.

Stabilization may correct translation/scale jitter introduced by generation/import. It must not redraw anatomy, alter intended pose, change costume, or hide identity drift. Those failures return to source production.

## Mandatory gates — exact order

1. **Source Integrity** — complete authored subject, safe source margin, no source-level clipping.
2. **Technical** — format, dimensions, alpha, aspect/scale, anchor, canonical clipping, direction/frame structure, metadata.
3. **Cross-animation** — Master Reference identity, project scale, anchor convention, facing convention, sockets and shared contracts remain compatible with other accepted animations.
4. **Visual Continuity** — no morphing, flicker, costume/equipment drift, palette drift, unexplained proportion or silhouette jumps.
5. **Motion Readability** — requested action is readable; pose progression, contacts, weight, anticipation/action/recovery and loop seam are correct.
6. **Character Identity** — same face, hair, costume, proportions and art direction as the Master Reference.
7. **Assistant Art/Motion Review** — visually inspect the actual canonical frames/sheet at useful scale and as an animation sequence. Numeric checks alone cannot pass this gate.

Any failed gate returns to the smallest affected production unit and reruns every downstream applicable gate. Never convert a failure into a warning merely to finish the task.

## Evidence required before PASS

A validation report must record objective checks (dimensions, alpha, edge contact/clipping, anchors, frame/direction counts, metadata) separately from visual judgments (identity, continuity, motion, art quality). PASS fields must correspond to checks actually performed. Text printed inside an image is never evidence.

For animation, inspect both individual canonical frames and temporal playback/sequence. A spritesheet that looks plausible as a still image can still fail motion.

## Packaging contract

A completed animation package contains:

- `frames/` canonical per-frame images;
- canonical packed sheet/atlas where applicable;
- animation metadata with direction/frame order, durations, anchors and sockets;
- `animation_production_plan.json` (or equivalent canonical metadata);
- `validation_report.json` with gate evidence and final status.

Only the complete package is delivered. Source experiments, rejected frames, showcase boards, checkerboards, labels and editor overlays are excluded from canonical runtime assets.

## Modular equipment rule

Starter character motions are weaponless by default. Weapons are independent assets with grip/socket metadata and are composed through generic attachment/presentation systems. Validate the actual visual composite, including facing, grip alignment, rotation, scale, render order and hand occlusion. Anchor math alone is insufficient. Baked and hybrid animations remain supported when they produce better art.

## Non-animation assets

Apply the same control principle: define the asset contract before generation, preserve authored fidelity, run Source Integrity where applicable, canonicalize only accepted source, perform technical and visual/art review, then package one complete useful asset.

## Red flags — automatic failure

- Prompting for a whole animation/spritesheet and accepting the generator's invented motion structure.
- Delivering a single frame for a complete-animation request.
- Calling raw generator output canonical art.
- Calling Technical PASS final.
- Canonical bbox looks safe but source was already clipped.
- Cropping a character only to satisfy 48x48.
- Identity/costume/proportion drift between frames.
- Wrong pose/contact/trajectory accepted because the image is attractive.
- Validation says PASS without pixel inspection and actual visual/temporal review.
- Asking the user to discover technical failures the assistant can inspect.

## Completion wording

Use **Starter Pack Candidate** only after all applicable gates pass. Otherwise keep reworking internally. The production task ends at a validated, packaged useful asset—not at image generation.
