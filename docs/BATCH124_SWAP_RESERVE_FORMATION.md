# Batch 124 — Swap / Reserve / Formation / Complex Party

Batch 124 validates large-party battle participation without introducing a
parallel reserve-party subsystem.

Reference configuration:
- 12 party members
- 4 currently active
- 8 reserve
- 4 project-authored formation slots

Reserve is represented as canonical lifecycle participation state. A swap:
1. releases the outgoing formation slot;
2. moves the outgoing member to non-actionable reserve state;
3. reactivates the incoming member;
4. places the incoming member into the released slot.

The party roster itself is not rewritten, so ordering/identity remains stable.
The incoming member uses an ordinary `BattleAction`; inactive reserve members
are rejected by canonical battle validation. Next-round actor selection filters
reserve members even though the turn queue owns the full stable roster.

No fixed four-person gameplay cap was introduced. The four active members are
only reference-project policy.

Presentation consequence:
large rosters require active/reserve hierarchy, focus, grouping and overflow.
The default HUD must not flatten all 12 members into equal-density battle cards.
