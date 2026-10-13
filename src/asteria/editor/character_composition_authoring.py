"""Character composition authoring (CMP-01, CMP-02, CMP-04): sockets, attachments and visual
layers.

A body sprite sheet carries, in its asset metadata:

* ``socket_rig`` — ``SocketRig`` sockets (a point on the body, optionally keyed per frame)
* ``attachments`` — ``Attachment`` records worn on sockets (weapons, hats, effects...)
* ``visual_layers`` — ``ActorVisualLayerTrack`` layers drawn with matching body frames
  (layered characters: a cape or hand layer in front of / behind the body)

This is the same data the runtime draws (``asteria.presentation.character_composition``), so the
editor, scripts and the game agree. Every edit is one undoable command.
"""

from __future__ import annotations

from dataclasses import asdict, replace

from asteria.presentation.actor_visual_layers import ActorVisualLayerTrack, FrameVisualLayer
from asteria.presentation.attachments import (
    Attachment,
    GripTransform,
    Socket,
    SocketKey,
    SocketRig,
    Transform2D,
)
from asteria.presentation.character_composition import (
    CharacterComposition,
    attachment_to_data,
    composition_of,
)

from .animation_authoring import AnimationAuthoringController, _ReplaceAssetCommand


class CompositionAuthoringError(ValueError):
    pass


class CharacterCompositionAuthoring:
    def __init__(self, document, *, resource_root=None):
        self.document = document
        self.animation = AnimationAuthoringController(document, resource_root=resource_root)

    def sheets(self):
        return self.animation.sheets()

    def composition(self, asset_id):
        return composition_of(self.animation.asset(asset_id).meta())

    def _commit(self, asset_id, label, *, rig=None, attachments=None, layers=None):
        before = self.animation.asset(asset_id)
        meta = before.meta()
        current_rig, current_attachments, current_layers = composition_of(meta)
        rig = current_rig if rig is None else rig
        attachments = current_attachments if attachments is None else tuple(attachments)
        layers = current_layers if layers is None else layers
        try:
            rig.validate()
            for attachment in attachments:
                attachment.validate()
                if attachment.socket_id not in rig.sockets:
                    raise ValueError(
                        f"attachment {attachment.id} uses unknown socket {attachment.socket_id}"
                    )
            if len({a.id for a in attachments}) != len(attachments):
                raise ValueError("attachment ids must be unique")
        except (ValueError, KeyError) as exc:
            raise CompositionAuthoringError(str(exc)) from exc
        meta["socket_rig"] = rig.to_dict()
        meta["attachments"] = [attachment_to_data(a) for a in attachments]
        meta["visual_layers"] = layers.to_dict()
        after = replace(before, metadata=tuple(sorted(meta.items())))
        self.document.execute(
            _ReplaceAssetCommand(self.animation.project.assets, before, after, label)
        )
        return self.composition(asset_id)

    # -- sockets ----------------------------------------------------------------------------------
    def add_socket(self, asset_id, socket_id, x=0.0, y=0.0, *, parent=None):
        rig, _, _ = self.composition(asset_id)
        if socket_id in rig.sockets:
            raise CompositionAuthoringError(f"socket {socket_id} exists")
        rig = SocketRig(dict(rig.sockets))
        rig.add(Socket(str(socket_id), parent=parent, default=Transform2D(float(x), float(y))))
        return self._commit(asset_id, f"Add socket {socket_id}", rig=rig)

    def set_socket_key(self, asset_id, socket_id, frame, x, y, rotation=0.0, scale=1.0):
        rig, _, _ = self.composition(asset_id)
        old = rig.sockets[socket_id]
        keys = {k.frame: k for k in old.keys}
        keys[int(frame)] = SocketKey(
            int(frame),
            Transform2D(float(x), float(y), float(rotation), float(scale), float(scale)),
        )
        sockets = dict(rig.sockets)
        sockets[socket_id] = replace(old, keys=tuple(keys[f] for f in sorted(keys)))
        return self._commit(asset_id, f"Key {socket_id} at frame {frame}", rig=SocketRig(sockets))

    def remove_socket(self, asset_id, socket_id):
        rig, attachments, _ = self.composition(asset_id)
        if any(a.socket_id == socket_id for a in attachments):
            raise CompositionAuthoringError(f"socket {socket_id} holds attachments")
        if any(s.parent == socket_id for s in rig.sockets.values()):
            raise CompositionAuthoringError(f"socket {socket_id} has child sockets")
        sockets = {k: v for k, v in rig.sockets.items() if k != socket_id}
        return self._commit(asset_id, f"Remove socket {socket_id}", rig=SocketRig(sockets))

    # -- attachments ------------------------------------------------------------------------------
    def attach(
        self,
        asset_id,
        attachment_id,
        item_asset_id,
        socket_id,
        *,
        x=0.0,
        y=0.0,
        rotation=0.0,
        scale=1.0,
        front=True,
        frame=0,
        grip=None,
    ):
        """Wear frame ``frame`` of sheet ``item_asset_id`` on a socket; ``grip`` is the item's hold
        point (pixels)."""
        _, attachments, _ = self.composition(asset_id)
        try:
            self.animation.asset(item_asset_id)
        except Exception as exc:  # noqa: BLE001 - the attached image must be a sprite sheet in the project
            raise CompositionAuthoringError(str(exc)) from exc
        attachment = Attachment(
            str(attachment_id),
            str(item_asset_id),
            str(socket_id),
            Transform2D(
                float(x),
                float(y),
                float(rotation),
                float(scale),
                float(scale),
                z_offset=1 if front else -1,
            ),
            metadata={"frame": int(frame)},
            grip=GripTransform(*(float(v) for v in grip)) if grip else GripTransform(),
        )
        return self._commit(
            asset_id, f"Attach {attachment_id}", attachments=(*attachments, attachment)
        )

    def edit_attachment(self, asset_id, attachment_id, **local):
        _, attachments, _ = self.composition(asset_id)
        updated = []
        for a in attachments:
            if a.id == attachment_id:
                fields = asdict(a.local)
                fields.update(local)
                a = replace(a, local=Transform2D(**fields))
            updated.append(a)
        return self._commit(asset_id, f"Edit {attachment_id}", attachments=updated)

    def detach(self, asset_id, attachment_id):
        _, attachments, _ = self.composition(asset_id)
        return self._commit(
            asset_id,
            f"Detach {attachment_id}",
            attachments=[a for a in attachments if a.id != attachment_id],
        )

    # -- visual layers ----------------------------------------------------------------------------
    def add_layer(
        self, asset_id, layer_asset_id, *, component_id="foreground", z=1.0, frames=(), clips=()
    ):
        _, _, layers = self.composition(asset_id)
        self.animation.asset(
            layer_asset_id
        )  # must exist (a sheet whose frames line up with the body's)
        layer = FrameVisualLayer(
            str(layer_asset_id),
            str(component_id),
            float(z),
            Transform2D(),
            tuple(frames),
            tuple(clips),
        )
        return self._commit(
            asset_id,
            f"Add layer {component_id}",
            layers=ActorVisualLayerTrack((*layers.layers, layer)),
        )

    def remove_layer(self, asset_id, index):
        _, _, layers = self.composition(asset_id)
        kept = [x for i, x in enumerate(layers.layers) if i != int(index)]
        return self._commit(asset_id, "Remove layer", layers=ActorVisualLayerTrack(kept))

    # -- preview ----------------------------------------------------------------------------------
    def parts(self, asset_id, frame_index, clip_id=""):
        """What the game draws with this body frame (``CompositionPart`` list, back to front)."""
        composition = CharacterComposition(*self.composition(asset_id))
        return composition.parts(clip_id, int(frame_index))
