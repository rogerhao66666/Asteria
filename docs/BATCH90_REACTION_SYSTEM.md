# Batch 90 — Generic Reaction System

Asteria reactions are a deterministic queue mechanism, not named hard-coded combat rules.
`ReactionDefinition` maps an open trigger to a reactor selector, optional ability, target selector,
priority, tag conditions, per-chain limit, and optional action-target mutation policy.

Common content can express counter, follow-up, cover/intercept, auto-action, reflect-like reactions,
or custom project mechanics. Selector and mutation policy names are open strings; projects/plugins may
register additional resolvers.

## Engine guarantees
- deterministic priority/order;
- inactive reactors can be filtered;
- reaction abilities reuse the normal `BattleAction -> AbilityRuntime` path;
- nested reaction chains are bounded by per-rule counts, max depth and max total reactions;
- reaction-generated actions carry the `reaction` event tag so authored data can allow/block re-entry;
- pre-action target replacement is available as mechanism, without a dedicated `CoverSystem`.

## Game-author responsibility
Asteria does not decide whether counter may counter a counter, cover beats intercept, KO cancels a
reaction, reflect can reflect reflect, or a follow-up costs a turn. Those are project rules. Engine
limits prevent malformed author rules from deadlocking/crashing the runtime, but do not attempt to
make the game's design balanced or sensible.

Battle transaction ownership, full reaction snapshot state and cross-system restore are finalized in
Batch 92/93.
