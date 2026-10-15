"""Measure what the multiplayer protocol costs: server CPU, bandwidth and recovery on bad links.

Runs the cooperative boss encounter with four clients that move and attack, once per link
profile, and prints (and optionally writes as JSON) per-profile numbers:

    python scripts/multiplayer_netbench.py [--seconds 8] [--json out.json]

Numbers are from loopback with the clients in this same process, so the server's CPU share is an
upper bound on a dedicated machine; bandwidth is exact (bytes the server wrote).
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from asteria.multiplayer import MultiplayerClient, MultiplayerServer  # noqa: E402
from asteria.multiplayer.boss_demo import build_boss_adapter  # noqa: E402
from asteria.multiplayer.netsim import LinkProfile, LinkSimulator  # noqa: E402

PROFILES = {
    "ideal": (None, None),
    "lan 5ms": (LinkProfile(delay_ms=5, jitter_ms=2), LinkProfile(delay_ms=5, jitter_ms=2)),
    "wan 60ms": (LinkProfile(delay_ms=60, jitter_ms=20), LinkProfile(delay_ms=60, jitter_ms=20)),
    "bad wan 120ms 5% loss": (
        LinkProfile(delay_ms=120, jitter_ms=40, loss=0.05),
        LinkProfile(delay_ms=120, jitter_ms=40, loss=0.05),
    ),
}


def run_profile(name, up, down, seconds):
    server = MultiplayerServer(("127.0.0.1", 0), adapter=build_boss_adapter())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    link = (
        LinkSimulator(server.server_address[:2], upstream=up, downstream=down, seed=1).start()
        if up or down
        else None
    )
    address = link.address if link else server.server_address[:2]
    boxes = [queue.Queue() for _ in range(4)]
    clients = [MultiplayerClient(on_message=box.put) for box in boxes]
    try:
        for index, client in enumerate(clients):
            client.connect(*address, f"P{index + 1}", heartbeat=0.5)
        started = time.monotonic()
        step = 0
        while time.monotonic() - started < seconds:
            for index, client in enumerate(clients):
                angle = 1.0 if (step // 10 + index) % 2 == 0 else -1.0
                client.send_input({"move_x": angle, "attack": True})
            step += 1
            time.sleep(1 / 20)
        time.sleep(0.8)
        snapshot = server.metrics_snapshot()
        latest = [None] * 4
        for i, box in enumerate(boxes):
            while True:
                try:
                    message = box.get_nowait()
                except queue.Empty:
                    break
                state = message.get("state") if message.get("type") == "game_update" else None
                if state and "boss" in state:
                    latest[i] = state
        healths = [None if s is None else s["boss"]["hp"] for s in latest]
        ticks = [None if s is None else s["tick"] for s in latest]
        return {
            "profile": name,
            "seconds": seconds,
            "server_bytes_out_per_player_second": round(snapshot["bytes_out_per_player_second"]),
            "server_tick_ms_average": round(snapshot["tick_ms_average"], 3),
            "server_tick_ms_worst": round(snapshot["tick_ms_worst"], 3),
            "server_tick_cpu_share": round(snapshot["tick_cpu_share"], 4),
            "client_gaps_noticed": sum(c.gaps for c in clients),
            "boss_hp_seen_by_each_client": healths,
            "tick_spread": None if None in ticks else max(ticks) - min(ticks),
            "clients_agree": None not in healths and len(set(healths)) == 1,
            "link_dropped_frames": (link.stats["up"]["dropped"] + link.stats["down"]["dropped"])
            if link
            else 0,
        }
    finally:
        for client in clients:
            client.close()
        if link:
            link.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--json", help="write the results here")
    args = parser.parse_args(argv)
    results = []
    for name, (up, down) in PROFILES.items():
        result = run_profile(name, up, down, args.seconds)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0 if all(r["clients_agree"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
