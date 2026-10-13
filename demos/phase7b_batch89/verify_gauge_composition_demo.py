from asteria.rpg import (
    GaugeCompositionDefinition,
    GaugeImpactRule,
    GaugeThresholdRule,
)

composition = GaugeCompositionDefinition(
    "stagger_break",
    impacts=(
        GaugeImpactRule(
            "weakness_pressure",
            "stagger",
            "battle.hit",
            delta=-25,
            required_outcome_tags_all=("outcome.weak",),
        ),
        GaugeImpactRule(
            "heavy_pressure",
            "stagger",
            "battle.hit",
            delta=-10,
            required_outcome_tags_all=("attack.heavy",),
        ),
    ),
    thresholds=(
        GaugeThresholdRule(
            "broken",
            "stagger",
            "at_or_below",
            0,
            state_id="broken",
            timeline_shift=20,
            reset_to=100,
            emit_trigger="battle.break.triggered",
        ),
    ),
)
rebuilt = GaugeCompositionDefinition.from_data(composition.to_data())
assert rebuilt == composition
assert rebuilt.impacts[0].resource_id == "stagger"
assert rebuilt.thresholds[0].state_id == "broken"
print("Batch 89 gauge composition demo: PASS")
print("composition:", rebuilt.composition_id)
print("impacts:", ", ".join(x.impact_id for x in rebuilt.impacts))
print("threshold:", rebuilt.thresholds[0].threshold_id)
