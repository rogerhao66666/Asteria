"""Scene asset-reference serialization, resolution and runtime binding seam."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .registry import AssetRegistry
from .scene_placement import SceneAssetRef


def asset_ref_to_dict(ref: SceneAssetRef) -> dict[str, str]:
    return {"asset_id": ref.asset_id, "kind": ref.kind}


def asset_ref_from_dict(data: Mapping[str, Any]) -> SceneAssetRef:
    if not isinstance(data, Mapping):
        raise TypeError("asset ref must be an object")
    aid = data.get("asset_id")
    kind = data.get("kind")
    if not isinstance(aid, str) or not aid:
        raise ValueError("asset_id")
    if not isinstance(kind, str) or not kind:
        raise ValueError("kind")
    return SceneAssetRef(aid, kind)


@dataclass(frozen=True, slots=True)
class SceneAssetBinding:
    object_id: str
    component_type: str
    asset_ref: SceneAssetRef
    properties: tuple[tuple[str, Any], ...] = ()


def binding_to_dict(binding: SceneAssetBinding) -> dict[str, Any]:
    return {
        "object_id": binding.object_id,
        "component_type": binding.component_type,
        "asset_ref": asset_ref_to_dict(binding.asset_ref),
        "properties": dict(binding.properties),
    }


def binding_from_dict(data: Mapping[str, Any]) -> SceneAssetBinding:
    if not isinstance(data, Mapping):
        raise TypeError("binding must be an object")
    oid = data.get("object_id")
    ctype = data.get("component_type", "asset")
    props = data.get("properties", {})
    if not isinstance(oid, str) or not oid:
        raise ValueError("object_id")
    if not isinstance(ctype, str) or not ctype:
        raise ValueError("component_type")
    if not isinstance(props, Mapping):
        raise ValueError("properties")
    return SceneAssetBinding(oid, ctype, asset_ref_from_dict(data.get("asset_ref", {})), tuple(props.items()))


@dataclass(frozen=True, slots=True)
class ResolvedSceneAsset:
    binding: SceneAssetBinding
    canonical: Any


class SceneAssetResolver:
    def __init__(self, registry: AssetRegistry):
        self.registry = registry

    def resolve(self, binding: SceneAssetBinding) -> ResolvedSceneAsset:
        asset = self.registry.resolve(binding.asset_ref.asset_id)
        if asset.kind != binding.asset_ref.kind:
            raise ValueError(f"asset kind mismatch: scene={binding.asset_ref.kind}, registry={asset.kind}")
        return ResolvedSceneAsset(binding, asset)

    def resolve_many(self, bindings):
        return tuple(self.resolve(x) for x in bindings)


RuntimeBinder = Callable[[ResolvedSceneAsset, Any], Any]


class RuntimeBindingRegistry:
    def __init__(self):
        self._binders = {}

    def register(self, component_type: str, binder: RuntimeBinder, *, replace_existing=False):
        if not component_type:
            raise ValueError("component_type")
        if component_type in self._binders and not replace_existing:
            raise ValueError("binder exists")
        self._binders[component_type] = binder

    def unregister(self, component_type):
        self._binders.pop(component_type, None)

    def bind(self, resolved: ResolvedSceneAsset, runtime_context: Any = None):
        ctype = resolved.binding.component_type
        binder = self._binders.get(ctype) or self._binders.get("*")
        if binder is None:
            raise KeyError(f"no runtime binder: {ctype}")
        return binder(resolved, runtime_context)


def generic_runtime_binder(resolved: ResolvedSceneAsset, runtime_context=None):
    return {
        "object_id": resolved.binding.object_id,
        "asset_id": resolved.canonical.asset_id,
        "kind": resolved.canonical.kind,
        "component_type": resolved.binding.component_type,
        "properties": dict(resolved.binding.properties),
    }
