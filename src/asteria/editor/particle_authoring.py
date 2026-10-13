"""Particle effect authoring (VFX-01): create, edit, duplicate and delete ``particle_effect``
assets, undoably.

Every edit replaces the whole asset through the document's command stack, so Undo / Redo restore
exactly
what the runtime reads (``asteria.presentation.particles``). Nothing is refused for being "too
much": any
number the definition accepts can be authored. Deleting an effect that is still used is allowed;
``usages``
lists where, so the editor can say so first.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.assets.canonical import AssetRef
from asteria.presentation.particles import (
    PARTICLE_KIND,
    PRESETS,
    ParticleEffectDefinition,
    effect_definition,
    particle_effect_asset,
    preset,
)

from .animation_authoring import _ReplaceAssetCommand
from .vfx_authoring import _AddAssetCommand


class ParticleAuthoringError(ValueError):
    pass


@dataclass(slots=True)
class _RemoveAssetCommand:
    registry: object
    asset: object
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        self.registry.remove(self.asset.asset_id)

    def undo(self):
        self.registry.register(self.asset)


class ParticleAuthoringController:
    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise ParticleAuthoringError("project required")
        return self.document.project

    def ids(self):
        return tuple(sorted(a.asset_id for a in self.project.assets.query(kind=PARTICLE_KIND)))

    def definition(self, effect_id):
        definition = effect_definition(self.project.assets, effect_id)
        if definition is None:
            raise ParticleAuthoringError(f"no particle effect {effect_id}")
        return definition

    def _asset(self, effect_id):
        return self.project.assets.resolve(effect_id)

    def create(self, effect_id, preset_name="fire"):
        effect_id = str(effect_id).strip()
        try:
            AssetRef(effect_id)
        except ValueError as exc:
            raise ParticleAuthoringError(f"invalid id {effect_id!r}") from exc
        if any(a.asset_id == effect_id for a in self.project.assets.snapshot()):
            raise ParticleAuthoringError(f"{effect_id} already exists")
        if preset_name not in PRESETS:
            raise ParticleAuthoringError(f"unknown preset {preset_name}")
        asset = particle_effect_asset(preset(preset_name, effect_id))
        self.document.execute(
            _AddAssetCommand(self.project.assets, asset, f"New particle effect {effect_id}")
        )
        return effect_id

    def update(self, effect_id, definition):
        if not isinstance(definition, ParticleEffectDefinition):
            raise ParticleAuthoringError("definition must be a ParticleEffectDefinition")
        before = self._asset(effect_id)
        definition = definition.replace(effect_id=effect_id)
        after = particle_effect_asset(
            definition, tags=tuple(sorted(before.tags)) or ("vfx", "particles")
        )
        if after == before:
            return False
        self.document.execute(
            _ReplaceAssetCommand(
                self.project.assets, before, after, f"Edit particle effect {effect_id}"
            )
        )
        return True

    def duplicate(self, effect_id, new_id):
        definition = self.definition(effect_id)
        self.create(new_id)
        self.update(new_id, definition)
        return new_id

    def delete(self, effect_id):
        asset = self._asset(effect_id)
        self.document.execute(
            _RemoveAssetCommand(self.project.assets, asset, f"Delete particle effect {effect_id}")
        )

    def usages(self, effect_id):
        """Where the effect is used: field emitters, event programs (PLAY_VFX) and action timeline
        beats."""
        from asteria.runtime.environment2d import ParticleEmitter2DComponent

        project, found = self.project, []
        for scene in project.scenes():
            for entity in scene.entities():
                component = entity.try_get(ParticleEmitter2DComponent)
                if component is not None and component.effect_id == effect_id:
                    found.append(f"{scene.name} / {entity.name}")
        for program_id in project.event_programs.ids():
            for instruction in project.event_programs.get(program_id).instructions:
                args = instruction.args.get("args", {}) if instruction.opcode == "WORLD" else {}
                if (
                    instruction.args.get("command") == "PLAY_VFX"
                    and args.get("asset_id") == effect_id
                ):
                    found.append(f"event {program_id}")
        library = project.battle_presentation_library
        for sequence_id in library.ids("motion_sequences"):
            for beat in library.require("motion_sequences", sequence_id).beats:
                if beat.channel == "vfx" and beat.cue == effect_id:
                    found.append(f"action timeline {sequence_id}.{beat.beat_id}")
        return tuple(dict.fromkeys(found))
