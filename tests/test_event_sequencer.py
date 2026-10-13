"""EVT-04: the event sequencer — parallel tracks, shared dialogue, completion, skip, cancel,
save/resume."""

import pytest

from asteria.events import EventContext, EventInstruction, EventProgram
from asteria.events.registry import EventProgramRegistry
from asteria.events.runner import EventRunner
from asteria.events.sequencer import SequenceError
from asteria.events.world_commands import WorldCommandRouter


class Host:
    def __init__(self):
        self.pos = {"hero": (0.0, 0.0), "npc": (10.0, 0.0)}
        self.log = []

    def position(self, e):
        return self.pos[e]

    def set_position(self, e, x, y):
        self.pos[e] = (x, y)

    def set_facing(self, e, f):
        self.log.append(("face", e, f))

    def play_animation(self, e, c):
        self.log.append(("anim", e, c))


def I(op, **args):  # noqa: E743 - short helper for instructions
    return EventInstruction(op, args)


def tr(name, *ins):
    return {"name": name, "instructions": [i.to_data() for i in ins]}


def _runner(*instructions, **seq):
    seen = []
    router = WorldCommandRouter()
    for name in ("PLAY_BGM", "CAMERA_FOCUS", "PLAY_VFX"):
        router.register(name, lambda c, n=name: seen.append((n, dict(c.args))))
    registry = EventProgramRegistry()
    registry.register("cut", EventProgram(instructions))
    runner = EventRunner(registry, context=EventContext(), world_commands=router)
    runner.sequence_host = Host()
    return runner, seen


CUTSCENE = (
    I(
        "SEQUENCE",
        cutscene=True,
        skippable=True,
        tracks=[
            tr(
                "hero",
                I("MOVE", entity="hero", x=30, y=0, duration=1.0),
                I("FACE", entity="hero", facing="left"),
            ),
            tr(
                "camera",
                I("WORLD", command="CAMERA_FOCUS", args={"entity": "npc"}, wait=0.5),
                I("DIALOGUE", speaker="Npc", text="Halt!"),
                I("SET_SWITCH", name="spoke", value=True),
            ),
            tr(
                "npc",
                I("WORLD", command="PLAY_BGM", args={"asset_id": "tension"}),
                I("MOVE", entity="npc", x=-5, y=0, relative=True, speed=10),
            ),
        ],
    ),
    I("SET_SWITCH", name="after", value=True),
)


def test_tracks_run_in_parallel_and_the_event_continues_only_when_all_finish():
    runner, seen = _runner(*CUTSCENE)
    runner.start("cut")
    runner.update(0.0)
    assert [n for n, _ in seen] == [
        "CAMERA_FOCUS",
        "PLAY_BGM",
    ]  # both tracks started in the same frame
    assert runner.cutscene and runner.busy
    runner.update(0.5)
    host = runner.sequence_host
    assert host.pos["hero"] == (15.0, 0.0) and host.pos["npc"] == (
        5.0,
        0.0,
    )  # moving at the same time
    assert runner.dialogue.blocked and not runner.context.get_switch("after")
    runner.update(0.25)
    assert host.pos["hero"] == (15.0, 0.0)  # an open dialogue line pauses the whole scene
    runner.acknowledge_dialogue()
    runner.update(0.25)
    assert runner.context.get_switch("spoke") and not runner.context.get_switch(
        "after"
    )  # hero still walking
    runner.update(0.3)
    assert host.pos["hero"] == (30.0, 0.0) and ("face", "hero", "left") in host.log
    assert runner.context.get_switch("after") and not runner.busy and not runner.cutscene


def test_skipping_lands_on_the_same_end_state_as_watching():
    watched, watched_seen = _runner(*CUTSCENE)
    watched.start("cut")
    for _ in range(40):
        watched.update(0.05)
        if watched.dialogue.blocked:
            watched.acknowledge_dialogue()
    skipped, skipped_seen = _runner(*CUTSCENE)
    skipped.start("cut")
    skipped.update(0.1)
    assert skipped.can_skip and skipped.skip_sequences() == 1
    skipped.update(0.0)
    assert skipped.sequence_host.pos == watched.sequence_host.pos
    assert skipped.context.switches == watched.context.switches == {"spoke": True, "after": True}
    assert sorted(n for n, _ in skipped_seen) == sorted(
        n for n, _ in watched_seen
    )  # world commands ran once each
    assert not skipped.busy


def test_save_in_the_middle_of_a_cutscene_resumes_it():
    first, _ = _runner(*CUTSCENE)
    first.start("cut")
    first.update(0.0)
    first.update(0.3)
    snapshot = first.snapshot()
    assert snapshot["version"] == 4 and snapshot["sequences"]
    resumed, _ = _runner(*CUTSCENE)
    resumed.sequence_host.pos = dict(first.sequence_host.pos)
    resumed.restore(snapshot)
    for _ in range(40):
        resumed.update(0.05)
        if resumed.dialogue.blocked:
            resumed.acknowledge_dialogue()
    assert resumed.sequence_host.pos["hero"] == (30.0, 0.0) and resumed.context.get_switch("after")


def test_cancel_stops_tracks_where_they_are():
    runner, _ = _runner(*CUTSCENE)
    runner.start("cut")
    runner.update(0.0)
    runner.update(0.5)
    runner.stop()
    runner.update(1.0)
    assert runner.sequence_host.pos["hero"] == (15.0, 0.0) and not runner.cutscene


def test_wait_none_lets_the_event_continue_alongside_its_tracks():
    runner, _ = _runner(
        I(
            "SEQUENCE",
            wait="none",
            tracks=[tr("walk", I("MOVE", entity="hero", x=10, y=0, duration=1.0))],
        ),
        I("SET_SWITCH", name="next", value=True),
    )
    runner.start("cut")
    runner.update(0.0)
    assert runner.context.get_switch("next") and runner.sequence_host.pos["hero"] == (0.0, 0.0)
    runner.update(0.5)
    assert runner.sequence_host.pos["hero"] == (5.0, 0.0)
    runner.update(0.5)
    assert runner.sequence_host.pos["hero"] == (10.0, 0.0) and not runner.busy


def test_invalid_sequences_are_rejected():
    runner, _ = _runner(
        I(
            "SEQUENCE",
            tracks=[tr("bad", I("CHOICE", prompt="?", choices=[{"text": "a", "value": 1}]))],
        )
    )
    runner.start("cut")
    with pytest.raises(SequenceError, match="CHOICE"):
        runner.update(0.0)
    runner, _ = _runner(I("SEQUENCE", tracks=[tr("t", I("WAIT", seconds=1))]))
    runner.start("cut")
    runner.update(0.0)
    with pytest.raises(SequenceError, match="not skippable"):
        runner.skip_sequences() or runner.sequences[0][1].skip()
