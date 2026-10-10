"""Extensible canonical-asset -> backend request -> staged runtime resource bridge."""

from dataclasses import dataclass
from typing import Any, Callable
from .runtime_resources import StagedRuntimeObject, staged
from .scene_binding import ResolvedSceneAsset
from .runtime_adapters import (
    audio_request,
    font_request,
    material_request,
    icon_request,
    portrait_request,
    vfx_request,
    monster_clip_request,
)

AssetAdapter = Callable[[Any], Any]
ResourceFactory = Callable[[Any, Any], Any]


class RuntimeAdapterRegistry:
    def __init__(self):
        self._adapters = {}

    def register(self, kind: str, adapter: AssetAdapter, *, replace_existing=False):
        if not kind:
            raise ValueError("kind")
        if kind in self._adapters and not replace_existing:
            raise ValueError("adapter exists")
        self._adapters[kind] = adapter

    def unregister(self, kind):
        self._adapters.pop(kind, None)

    def adapt(self, canonical):
        kind = canonical.canonical.kind if hasattr(canonical, "canonical") else canonical.kind
        fn = self._adapters.get(kind) or self._adapters.get("*")
        if fn is None:
            raise KeyError(f"no runtime adapter: {kind}")
        return fn(canonical)

    def kinds(self):
        return tuple(sorted(self._adapters))


def install_builtin_runtime_adapters(r: RuntimeAdapterRegistry):
    for kind, fn in (
        ("audio", audio_request),
        ("font", font_request),
        ("material", material_request),
        ("icon", icon_request),
        ("portrait", portrait_request),
        ("vfx", vfx_request),
        ("monster", monster_clip_request),
    ):
        r.register(kind, fn, replace_existing=True)
    return r


@dataclass(frozen=True, slots=True)
class RuntimeResource:
    value: Any
    dispose: Callable[[], None] | None = None


def make_resource_aware_binder(adapters: RuntimeAdapterRegistry, factory: ResourceFactory):
    def binder(resolved: ResolvedSceneAsset, runtime_context=None):
        request = adapters.adapt(resolved.canonical)
        made = factory(request, runtime_context)
        if isinstance(made, StagedRuntimeObject):
            return made
        if isinstance(made, RuntimeResource):
            return staged(made.value, made.dispose)
        return staged(made)

    return binder
