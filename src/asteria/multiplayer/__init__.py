"""Optional, game-agnostic multiplayer building blocks for Asteria projects."""

from .adapter import (
    AdapterUpdate,
    GameNetworkAdapter,
    InputGameNetworkAdapter,
    TickableGameNetworkAdapter,
)
from .client import MultiplayerClient, MultiplayerClientError
from .protocol import PROTOCOL_VERSION, ProtocolError
from .persistence import SQLiteMultiplayerStore

__all__ = [
    "AdapterUpdate",
    "CooperativeBossAdapter",
    "GameNetworkAdapter",
    "InputGameNetworkAdapter",
    "MultiplayerClient",
    "MultiplayerClientError",
    "MultiplayerServer",
    "PROTOCOL_VERSION",
    "ProtocolError",
    "SQLiteMultiplayerStore",
    "TickableGameNetworkAdapter",
    "build_boss_adapter",
    "create_server",
]


def __getattr__(name):
    if name in {"CooperativeBossAdapter", "build_boss_adapter"}:
        from .boss_demo import CooperativeBossAdapter, build_boss_adapter

        return {
            "CooperativeBossAdapter": CooperativeBossAdapter,
            "build_boss_adapter": build_boss_adapter,
        }[name]
    if name in {"MultiplayerServer", "create_server"}:
        from .server import MultiplayerServer, create_server

        return {"MultiplayerServer": MultiplayerServer, "create_server": create_server}[name]
    raise AttributeError(name)
