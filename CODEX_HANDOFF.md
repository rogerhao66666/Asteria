# Asteria Codex Integration Handoff

Treat this repository as the canonical architecture. Do not redesign frozen systems merely to accommodate RPG Maker MV.

1. Read the five canonical `ASTERIA_*.md` documents, `ASTERIA_FINAL_ALIGNMENT_AUDIT.md`, and `.agents/skills/asteria-asset-production/SKILL.md` before changes.
2. Run the full repository regression suite and compile checks in the real repo environment.
3. Use the user's local RPG Maker MV installation/project assets only as private development fixtures. Do not copy them into the distributable Asteria repository.
4. Implement/repair MV import compatibility through existing generic asset adapters/canonicalization. Keep MV semantics out of Core Runtime, Battle, Scene, and Presentation.
5. Validate useful real MV categories available locally: map characters (including normal multi-character sheets and `$`/`!` filename semantics where applicable), faces, side-view actors, enemies, tilesets, animations/effects and other image resources that map cleanly to Asteria's generic asset model.
6. Exercise PySide6 Editor workflows, Pygame/ModernGL rendering paths, audio-device paths, filesystem/package flows, and representative animation/VFX stress cases that Chat-side headless tests cannot fully validate.
7. Preserve Character Generator as an optional authoring framework. Do not restore rejected AI/derived Starter art.
8. Produce a final closure audit separating PASS, repaired, remaining external limitation, and deferred production content. Never mark production Starter art PASS without the art/motion gates.
