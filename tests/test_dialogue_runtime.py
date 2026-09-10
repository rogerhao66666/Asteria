import pytest

from asteria.events import (
    EventContext,
    EventInstruction,
    EventProgram,
    EventProgramRegistry,
    EventRunner,
    EventRunnerError,
)


def make_runner(program):
    registry = EventProgramRegistry()
    registry.register("event", program)
    runner = EventRunner(registry, context=EventContext())
    runner.start("event", source_entity_id="npc", local_scope_id="npc-scope")
    return runner


def test_dialogue_blocks_runner_until_acknowledged():
    runner = make_runner(
        EventProgram(
            [
                EventInstruction(
                    "DIALOGUE",
                    {
                        "speaker": "Lina",
                        "text": "Welcome to Asteria.",
                        "portrait_asset_id": "portrait-lina",
                    },
                ),
                EventInstruction(
                    "SET_SWITCH", {"name": "after_dialogue", "value": True}
                ),
                EventInstruction("END"),
            ]
        )
    )

    assert runner.update() == ()
    assert runner.dialogue.blocked
    request = runner.dialogue.dialogue
    assert request.line.speaker == "Lina"
    assert request.line.text == "Welcome to Asteria."
    assert request.line.portrait_asset_id == "portrait-lina"
    assert runner.context.get_switch("after_dialogue") is False

    # Additional updates cannot advance while UI has not acknowledged.
    assert runner.update() == ()
    assert runner.context.get_switch("after_dialogue") is False

    runner.acknowledge_dialogue()
    runner.update()
    assert runner.context.get_switch("after_dialogue") is True


def test_choice_blocks_and_writes_selected_value_to_variable():
    runner = make_runner(
        EventProgram(
            [
                EventInstruction(
                    "CHOICE",
                    {
                        "prompt": "Where should we go?",
                        "choices": [
                            {"text": "Town", "value": "town"},
                            {"text": "Forest", "value": "forest"},
                        ],
                        "variable_name": "destination",
                    },
                ),
                EventInstruction("END"),
            ]
        )
    )

    runner.update()
    assert runner.dialogue.choice.prompt == "Where should we go?"
    selected = runner.choose(1)
    assert selected.text == "Forest"
    assert runner.context.get_variable("destination") == "forest"
    runner.update()
    assert runner.vm.completed


def test_choice_can_store_self_local_state():
    runner = make_runner(
        EventProgram(
            [
                EventInstruction(
                    "CHOICE",
                    {
                        "prompt": "Open chest?",
                        "choices": [
                            {"text": "Yes", "value": True},
                            {"text": "No", "value": False},
                        ],
                        "local_name": "accepted",
                    },
                ),
                EventInstruction("END"),
            ]
        )
    )
    runner.update()
    runner.choose(0)
    assert runner.context.get_local("npc-scope", "accepted") is True


def test_dialogue_and_choice_do_not_leak_as_passthrough_host_commands():
    runner = make_runner(
        EventProgram(
            [
                EventInstruction("CUSTOM", {"n": 1}),
                EventInstruction("DIALOGUE", {"text": "Hi"}),
                EventInstruction("CUSTOM", {"n": 2}),
            ]
        )
    )
    yielded = runner.update()
    assert [x.args["n"] for x in yielded] == [1]
    assert runner.dialogue.dialogue is not None


def test_invalid_dialogue_or_choice_contract_is_rejected():
    runner = make_runner(EventProgram([EventInstruction("DIALOGUE", {})]))
    with pytest.raises(EventRunnerError):
        runner.update()

    runner = make_runner(EventProgram([EventInstruction("CHOICE", {"choices": []})]))
    with pytest.raises(EventRunnerError):
        runner.update()


def test_choice_index_validation():
    runner = make_runner(
        EventProgram(
            [
                EventInstruction(
                    "CHOICE",
                    {
                        "choices": [{"text": "Only", "value": 1}],
                    },
                ),
            ]
        )
    )
    runner.update()
    with pytest.raises(IndexError):
        runner.choose(2)
