"""Integrated save/close/reload seam for the headless presentation pipeline."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Mapping
import json
from .e2e_pipeline import SceneActorBinding, PresentationE2EPipeline
from .presentation_state import capture_state, restore_state, PresentationStateCodec
from .render_integration import RenderTransform

SESSION_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ActorSession:
    actor_id: str
    actor_asset_id: str
    base_transform: RenderTransform
    presentation_json: str
    metadata: Mapping


@dataclass(frozen=True, slots=True)
class PresentationSession:
    actors: tuple[ActorSession, ...]
    playhead_ms: float

    def __post_init__(self):
        if self.playhead_ms < 0:
            raise ValueError("negative playhead")
        ids = [x.actor_id for x in self.actors]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate actor id")


class SessionCodec:
    @staticmethod
    def dumps(s):
        def tx(t):
            return {
                "x": t.x,
                "y": t.y,
                "rotation_deg": t.rotation_deg,
                "scale_x": t.scale_x,
                "scale_y": t.scale_y,
                "opacity": t.opacity,
                "visible": t.visible,
            }

        return json.dumps(
            {
                "schema_version": SESSION_SCHEMA_VERSION,
                "playhead_ms": s.playhead_ms,
                "actors": [
                    {
                        "actor_id": a.actor_id,
                        "actor_asset_id": a.actor_asset_id,
                        "base_transform": tx(a.base_transform),
                        "presentation_json": a.presentation_json,
                        "metadata": dict(a.metadata),
                    }
                    for a in s.actors
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def loads(text):
        r = json.loads(text)
        if int(r.get("schema_version", 0)) != SESSION_SCHEMA_VERSION:
            raise ValueError("unsupported session schema")
        actors = tuple(
            ActorSession(
                str(a["actor_id"]),
                str(a["actor_asset_id"]),
                RenderTransform(**a.get("base_transform", {})),
                str(a["presentation_json"]),
                dict(a.get("metadata", {})),
            )
            for a in r.get("actors", ())
        )
        return PresentationSession(actors, float(r.get("playhead_ms", 0)))


def capture_session(pipeline, playhead_ms):
    # Property animator is shared by the current E2E pipeline. Persist it with each
    # actor state so each reconstructed runtime is independently valid.
    actors = []
    for a in pipeline.actors:
        state = capture_state(a.attachments, pipeline.properties, playhead_ms, a.metadata)
        actors.append(
            ActorSession(
                a.actor_id, a.actor_asset_id, a.base_transform, PresentationStateCodec.dumps(state), a.metadata
            )
        )
    return PresentationSession(tuple(actors), float(playhead_ms))


def restore_session(session, animator_factory: Callable[[str], object], asset_exists=None):
    actors = []
    shared_properties = None
    for a in session.actors:
        state = PresentationStateCodec.loads(a.presentation_json)
        runtime, props = restore_state(state)
        if shared_properties is None:
            shared_properties = props
        elif props.curves != shared_properties.curves or props.modulations != shared_properties.modulations:
            raise ValueError("inconsistent shared property state")
        actors.append(
            SceneActorBinding(
                a.actor_id, a.actor_asset_id, animator_factory(a.actor_id), runtime, a.base_transform, a.metadata
            )
        )
    from .property_animation import PropertyAnimator

    return PresentationE2EPipeline(actors, shared_properties or PropertyAnimator(), asset_exists)
