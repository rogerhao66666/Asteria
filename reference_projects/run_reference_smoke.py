"""Run from repository root:
PYTHONPATH=src python reference_projects/run_reference_smoke.py
"""

from asteria.validation import (
    BattlePresentationStressHarness,
    EverythingCombinedScenario,
    NonPartyRpgGeneralityHarness,
)


def main():
    combined = EverythingCombinedScenario().run()
    general = NonPartyRpgGeneralityHarness().run()
    stress = BattlePresentationStressHarness(vfx_draws=1000, offscreen_draws=300).run(
        planner_iterations=3
    )
    print("everything_combined:", combined)
    print(
        "generality:",
        [(x.archetype_id, x.roster_size, x.action_count) for x in general.archetypes],
    )
    print("stress:", stress)


if __name__ == "__main__":
    main()
