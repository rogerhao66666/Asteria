"""AttachmentRuntime (used by Character Composition): attaching over an active attachment."""

import pytest

from asteria.presentation.attachment_runtime import AttachmentRuntime, AttachmentState
from asteria.presentation.attachments import Attachment, Socket, SocketRig, Transform2D


def _runtime():
    rig = SocketRig()
    rig.add(Socket("hand_r", default=Transform2D(x=24, y=20)))
    return AttachmentRuntime(rig)


def test_attaching_twice_needs_replace_and_replace_detaches_the_old_one_first():
    runtime = _runtime()
    detached = []
    runtime.on_detach(lambda instance: detached.append(instance.spec.asset_id))
    first = runtime.attach(Attachment("held", "iron_sword", "hand_r"))
    with pytest.raises(ValueError):
        runtime.attach(Attachment("held", "steel_sword", "hand_r"))
    second = runtime.attach(Attachment("held", "steel_sword", "hand_r"), replace=True)
    assert detached == ["iron_sword"] and first.state == AttachmentState.DETACHED
    assert runtime.instances["held"] is second and second.spec.asset_id == "steel_sword"
