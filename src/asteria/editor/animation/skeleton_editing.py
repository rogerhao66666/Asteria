"""Validated immutable-style edits for skeleton bones and animation tracks."""

from dataclasses import replace

from asteria.graphics.skeleton import Key, Skeleton, SkeletonClip


def _ordered(bones):
    pending = list(bones)
    ordered = []
    known = set()
    while pending:
        ready = next((bone for bone in pending if not bone.parent or bone.parent in known), None)
        if ready is None:
            raise ValueError("bone parent is missing or creates a cycle")
        pending.remove(ready)
        ordered.append(ready)
        known.add(ready.bone_id)
    return tuple(ordered)


def _replace(skeleton, *, bones=None, slots=None, clips=None):
    return Skeleton(
        skeleton.skeleton_id,
        skeleton.bones if bones is None else tuple(bones),
        skeleton.slots if slots is None else tuple(slots),
        skeleton.clips if clips is None else clips,
    )


def add_bone(skeleton, bone):
    if any(row.bone_id == bone.bone_id for row in skeleton.bones):
        raise ValueError(f"duplicate bone id: {bone.bone_id}")
    return _replace(skeleton, bones=(*skeleton.bones, bone))


def edit_bone(skeleton, current_id, **changes):
    allowed = {"bone_id", "parent", "x", "y", "rotation", "scale_x", "scale_y", "length"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"unsupported bone fields: {sorted(unknown)}")
    found = False
    old_id = current_id
    new_id = str(changes.get("bone_id", old_id)).strip()
    if not new_id:
        raise ValueError("bone id is required")
    if new_id != old_id and any(row.bone_id == new_id for row in skeleton.bones):
        raise ValueError(f"duplicate bone id: {new_id}")
    updated = []
    for bone in skeleton.bones:
        if bone.bone_id == old_id:
            found = True
            updated.append(replace(bone, **changes))
        else:
            parent = new_id if bone.parent == old_id else bone.parent
            updated.append(replace(bone, parent=parent))
    if not found:
        raise KeyError(old_id)
    bones = _ordered(updated)
    slots = tuple(
        replace(slot, bone_id=new_id) if slot.bone_id == old_id else slot
        for slot in skeleton.slots
    )
    clips = {}
    for name, clip in skeleton.clips.items():
        tracks = {
            (new_id if track_bone == old_id else track_bone, channel): keys
            for (track_bone, channel), keys in clip.tracks
        }
        clips[name] = SkeletonClip(
            clip.name,
            clip.duration,
            loop=clip.loop,
            tracks=tracks,
            frames=dict(clip.frames),
        )
    return _replace(skeleton, bones=bones, slots=slots, clips=clips)


def delete_bone(skeleton, bone_id):
    if not any(bone.bone_id == bone_id for bone in skeleton.bones):
        raise KeyError(bone_id)
    removed = {bone_id}
    while True:
        children = {bone.bone_id for bone in skeleton.bones if bone.parent in removed}
        if children <= removed:
            break
        removed.update(children)
    slots = tuple(slot for slot in skeleton.slots if slot.bone_id not in removed)
    removed_slots = {slot.slot_id for slot in skeleton.slots if slot.bone_id in removed}
    clips = {}
    for name, clip in skeleton.clips.items():
        tracks = {key: values for key, values in clip.tracks if key[0] not in removed}
        frames = {slot_id: rows for slot_id, rows in clip.frames if slot_id not in removed_slots}
        clips[name] = SkeletonClip(
            clip.name,
            clip.duration,
            loop=clip.loop,
            tracks=tracks,
            frames=frames,
        )
    bones = tuple(bone for bone in skeleton.bones if bone.bone_id not in removed)
    return _replace(skeleton, bones=bones, slots=slots, clips=clips)


def set_key(
    skeleton,
    clip_name,
    bone_id,
    channel,
    source_time,
    *,
    time=None,
    value=None,
    easing=None,
    delete=False,
):
    clip = skeleton.clips[clip_name]
    if not any(bone.bone_id == bone_id for bone in skeleton.bones):
        raise KeyError(bone_id)
    tracks = {track: list(keys) for track, keys in clip.tracks}
    track_id = (bone_id, channel)
    keys = tracks.get(track_id, [])
    index = next((i for i, key in enumerate(keys) if key.time == source_time), None)
    if delete:
        if index is None:
            raise KeyError(source_time)
        del keys[index]
    else:
        target_time = float(source_time if time is None else time)
        if target_time < 0 or target_time > clip.duration:
            raise ValueError("key time must lie inside the clip")
        if index is None and value is None:
            raise ValueError("a new key requires a value")
        prior = keys[index] if index is not None else None
        updated = Key(
            target_time,
            float(value if value is not None else prior.value),
            easing or (prior.easing if prior else "linear"),
        )
        if index is not None:
            del keys[index]
        keys = [key for key in keys if key.time != target_time]
        keys.append(updated)
        keys.sort(key=lambda key: key.time)
    if keys:
        tracks[track_id] = keys
    else:
        tracks.pop(track_id, None)
    clips = dict(skeleton.clips)
    clips[clip_name] = SkeletonClip(
        clip.name,
        clip.duration,
        loop=clip.loop,
        tracks={key: tuple(rows) for key, rows in tracks.items()},
        frames=dict(clip.frames),
    )
    return _replace(skeleton, clips=clips)
