from asteria.rpg import ActionSequenceDefinition, ActionSequenceRuntime, ActionSequenceStep

triple = ActionSequenceDefinition("triple_slash", [ActionSequenceStep("slash", repeat=3)])
duet = ActionSequenceDefinition(
    "inferno_cyclone",
    [
        ActionSequenceStep("fire", participant_index=0, emitted_tags=("heated",)),
        ActionSequenceStep("wind", participant_index=1, required_previous_tags=("heated",)),
    ],
    min_participants=2,
    max_participants=None,
)
rt = ActionSequenceRuntime((triple, duet))
p1 = rt.plan("triple_slash", ("hero",), ("enemy",))
p2 = rt.plan("inferno_cyclone", ("mage", "rogue"), ("boss",))
assert len(p1.steps) == 3
assert [x.actor_id for x in p2.steps] == ["mage", "rogue"]
print("Batch 88 action sequence demo: PASS")
print("triple hits:", len(p1.steps))
print("cooperative actors:", ", ".join(x.actor_id for x in p2.steps))
