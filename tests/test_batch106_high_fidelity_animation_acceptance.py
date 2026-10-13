from asteria.presentation.attachments import Socket, SocketKey, SocketRig, Transform2D


def test_32_frame_socket_track_supports_dense_authored_motion():
    keys = tuple(
        SocketKey(i, Transform2D(x=float(i) * 1.25, y=float(i % 4), rotation_deg=float(i) * 3.0))
        for i in range(32)
    )
    rig = SocketRig()
    rig.add(Socket("hand_r", keys=keys))
    assert rig.sample("hand_r", 31).x == 31 * 1.25
    mid = rig.sample("hand_r", 10, 0.5)
    assert 12.5 < mid.x < 13.75
