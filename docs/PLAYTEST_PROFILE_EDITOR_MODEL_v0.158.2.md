# Editor Playtest Profile Model

Asteria now separates four concepts:

1. **Project** — authored game definitions.
2. **Playtest Profile** — developer-only initial runtime template/overrides used by Editor Run.
3. **Runtime State** — mutable state of the currently running game session.
4. **Player Save** — game-facing persistence created/loaded by the player runtime.

Normal Editor UX is now:

`Open Project -> choose optional Playtest Profile -> Run`

No Player Save is required.

The Complex Reference RPG ships Default/Early/Mid/Endgame/Boss Stress developer
profiles. Every Run instantiates a fresh state, so stopping play cannot mutate the
profile or canonical Project.

Player Save serialization remains supported because games built with Asteria may
need New Game / Continue / Load Game. It is no longer the primary Editor launch
workflow.
