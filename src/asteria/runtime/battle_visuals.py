"""Resolve canonical battle visuals for the battle presentation (CB2).

Data contract (all canonical project data, no runtime code per project):

* **Sprite sheet assets** — ``CanonicalAsset`` of kind ``"sprite_sheet"``
  whose ``source.uri`` is an image path relative to the project resource
  root, with metadata:

  - ``frame_size``: ``[width, height]`` of one frame (row-major grid);
  - ``pivot``: ``[x, y]`` in 0..1 (default ``[0.5, 1.0]``, feet);
  - ``clips``: ``{name: {"frames": [index, ...], "frame_duration": seconds,
    "loop": bool, "events": {"<keyframe position>": [names]}}}``.

  Combatant sheets and VFX sheets use the same format. VFX sheets (tag
  ``vfx``) play their ``play`` clip and may carry ``vfx`` placement
  metadata (EDT-08): ``anchor`` (``feet`` / ``center`` / ``head`` of the
  member), ``offset`` ``[x, y]`` in world pixels, ``scale``, ``opacity``
  (0..1) and ``blend`` (``normal`` / ``add``). A beat payload may override
  any of them. ``vfx_rect`` is the single placement rule used by the
  battle renderer and the editor preview.

* **Combatant visual profiles** — battle presentation library category
  ``combatant_visuals``. A member uses the profile whose id equals its actor
  id (heroes) or its enemy id (enemies). ``assets.battlefield_asset_id`` names
  the sprite sheet asset; each state maps a battle role (``idle``,
  ``attack``, ``hit``, ``ko``) to a clip; ``transform.scale_*`` scales the
  sprite and ``offset_*`` shifts its anchor.

* **Action choreography** — category ``motion_sequences``. The sequence
  whose id equals the ability id (else ``"default_action"``) supplies timed
  beats on the channels ``animation`` (cue = role), ``vfx`` (cue = sprite
  sheet asset id), ``audio`` (cue = audio id), ``camera`` (cue = effect) and
  ``screen_fx`` (cue = effect). A beat's ``member_id`` is ``"@source"`` or
  ``"@target"`` (every target).
"""

from __future__ import annotations

from asteria.graphics import SpriteClip, SpriteFrame, SpriteKeyframe, SpriteSheet
from asteria.presentation.battle import BattleCombatantVisual, BattleVisualAnchor
from asteria.runtime.animation_library import AnimationClipSet

SPRITE_SHEET_KIND = "sprite_sheet"
DEFAULT_SEQUENCE_ID = "default_action"
VFX_ANCHORS = ("feet", "center", "head")
VFX_BLENDS = ("normal", "add")
VFX_DEFAULTS = {
    "anchor": "center",
    "offset": [0.0, 0.0],
    "scale": 0.6,
    "opacity": 1.0,
    "blend": "normal",
}


def vfx_placement(meta, overrides=None):
    """Placement of a VFX sheet: defaults, then the sheet's ``vfx`` metadata, then beat payload
    overrides."""
    placement = {**VFX_DEFAULTS, **dict((meta or {}).get("vfx", {}))}
    for key in VFX_DEFAULTS:
        if overrides and key in overrides:
            placement[key] = overrides[key]
    placement["offset"] = [float(placement["offset"][0]), float(placement["offset"][1])]
    placement["scale"] = float(placement["scale"])
    placement["opacity"] = max(0.0, min(1.0, float(placement["opacity"])))
    if placement["anchor"] not in VFX_ANCHORS:
        placement["anchor"] = VFX_DEFAULTS["anchor"]
    if placement["blend"] not in VFX_BLENDS:
        placement["blend"] = VFX_DEFAULTS["blend"]
    return placement


def vfx_keyframe(age, duration, keyframe_count):
    """Keyframe a VFX shows ``age`` seconds into an effect lasting ``duration`` (played once,
    stretched to fit)."""
    progress = min(0.999, max(0.0, float(age) / max(float(duration), 1e-6)))
    return int(progress * int(keyframe_count))


def vfx_rect(placement, anchor_x, anchor_y, body_height, frame_width, frame_height):
    """World-space ``(centre_x, centre_y, width, height)`` of a VFX frame on a member standing at
    the anchor."""
    lift = {"feet": 0.0, "center": 0.5, "head": 1.0}[placement["anchor"]] * body_height
    width, height = frame_width * placement["scale"], frame_height * placement["scale"]
    return (
        anchor_x + placement["offset"][0],
        anchor_y - lift + placement["offset"][1],
        width,
        height,
    )


def member_body_height(meta, frame_height, ratio):
    """Logical height of a combatant's body: the sheet's ``body_height`` metadata (source pixels)
    when it names one, else the frame height. Overhead bars and menus sit on this."""
    try:
        body = float((meta or {}).get("body_height") or 0.0)
    except (TypeError, ValueError):
        body = 0.0
    return (body if body > 0 else float(frame_height)) / float(ratio)


class BattleVisualError(ValueError):
    pass


class _TextureRef:
    """Minimal texture reference (``asset_id``) for SpriteSheet."""

    __slots__ = ("asset_id",)
    expected_kind = "texture"

    def __init__(self, asset_id):
        self.asset_id = asset_id


class BattleVisualResolver:
    """Builds SpriteSheets, AnimationClipSets, combatant visuals and choreography from project
    data.

    ``image_size(uri) -> (width, height)`` measures source images (the host
    loads them through its own cache).
    """

    def __init__(self, project, image_size):
        self.project = project
        self.image_size = image_size
        self._sheets = {}
        self._clips = {}
        # Generated sheets / profiles for combatants and effects that have no authored battle art
        # (asset id -> {"image", "size", "meta"}; member key -> profile). The host builds the
        # images.
        self._generated = {}
        self._generated_profiles = {}

    # -- generated visuals (projects without battle art) ------------------------
    def register_generated(
        self, asset_id, image, size, *, frame_size, clips, pivot=(0.5, 1.0), **meta
    ):
        """A sheet the host drew itself; ``clips`` uses the asset-metadata form ({name: {frames,
        ...}})."""
        data = {"frame_size": list(frame_size), "pivot": list(pivot), "clips": dict(clips), **meta}
        self._generated[str(asset_id)] = {"image": image, "size": tuple(size), "meta": data}
        self._sheets.pop(str(asset_id), None)
        self._clips.pop(str(asset_id), None)

    def register_generated_profile(self, member_key, asset_id, scale):
        from asteria.presentation.battle_combatant_visuals import (
            BattleCombatantVisualProfile,
            BattleVisualAssetSet,
            BattleVisualStateDefinition,
            BattleVisualTransform,
        )

        states = tuple(
            BattleVisualStateDefinition(role, role)
            for role in ("idle", "attack", "hit", "ko", "weak")
        )
        self._generated_profiles[str(member_key)] = BattleCombatantVisualProfile(
            str(member_key),
            BattleVisualAssetSet(str(asset_id)),
            states,
            BattleVisualTransform(scale, scale),
        )

    def is_generated(self, asset_id):
        return str(asset_id) in self._generated

    def generated_image(self, asset_id):
        entry = self._generated.get(str(asset_id))
        return None if entry is None else entry["image"]

    # -- assets ------------------------------------------------------------
    def asset(self, asset_id):
        try:
            asset = self.project.assets.resolve(str(asset_id))
        except KeyError:
            raise BattleVisualError(f"unknown sprite sheet asset: {asset_id}") from None
        if asset.kind != SPRITE_SHEET_KIND:
            raise BattleVisualError(f"asset {asset_id} is {asset.kind}, not {SPRITE_SHEET_KIND}")
        return asset

    def source_uri(self, asset_id):
        if self.is_generated(asset_id):
            raise BattleVisualError(f"{asset_id} is generated in memory; use generated_image()")
        return self.asset(asset_id).source.uri

    def sheet_meta(self, asset_id):
        if self.is_generated(asset_id):
            return dict(self._generated[str(asset_id)]["meta"])
        return self.asset(asset_id).meta()

    def sprite_sheet(self, asset_id):
        if asset_id not in self._sheets:
            meta = self.sheet_meta(asset_id)
            try:
                fw, fh = (int(x) for x in meta["frame_size"])
            except (KeyError, TypeError, ValueError):
                raise BattleVisualError(f"{asset_id}: frame_size metadata required") from None
            px, py = (float(x) for x in meta.get("pivot", (0.5, 1.0)))
            if self.is_generated(asset_id):
                width, height = self._generated[str(asset_id)]["size"]
            else:
                width, height = self.image_size(self.asset(asset_id).source.uri)
            columns, rows = width // fw, height // fh
            if columns < 1 or rows < 1:
                raise BattleVisualError(f"{asset_id}: image smaller than one frame")
            frames = [
                SpriteFrame(c * fw, r * fh, fw, fh, px, py)
                for r in range(rows)
                for c in range(columns)
            ]
            sheet = SpriteSheet(_TextureRef(str(asset_id)), frames)
            sheet.validate()
            self._sheets[asset_id] = sheet
        return self._sheets[asset_id]

    def clip_set(self, asset_id):
        if asset_id not in self._clips:
            meta = self.sheet_meta(asset_id)
            clips = {}
            for name, raw in dict(meta.get("clips", {})).items():
                frames = [int(x) for x in raw["frames"]]
                duration = float(raw.get("frame_duration", 0.12))
                events = {int(k): tuple(v) for k, v in dict(raw.get("events", {})).items()}
                clips[name] = SpriteClip(
                    name,
                    [SpriteKeyframe(f, duration, events.get(i, ())) for i, f in enumerate(frames)],
                    bool(raw.get("loop", True)),
                )
            machine = None
            if meta.get("state_machine"):
                from asteria.runtime.animation_state_machine import AnimationStateMachineDefinition

                # ANI-02: a sheet's authored state machine travels with its clips
                machine = AnimationStateMachineDefinition.from_data(meta["state_machine"])
            clip_set = AnimationClipSet(clips, machine)
            clip_set.validate(self.sprite_sheet(asset_id))
            self._clips[asset_id] = clip_set
        return self._clips[asset_id]

    def clip_duration(self, asset_id, clip_name):
        clip = self.clip_set(asset_id).get(clip_name)
        return 0.0 if clip is None else sum(k.duration for k in clip.keyframes)

    # -- combatants --------------------------------------------------------
    @property
    def library(self):
        return self.project.battle_presentation_library

    def profile_for(self, member_id):
        key = str(member_id).split(":", 1)[0]
        if key in self.library.ids("combatant_visuals"):
            return self.library.require("combatant_visuals", key)
        return self._generated_profiles.get(key)

    def missing_profiles(self, member_ids):
        return tuple(m for m in member_ids if self.profile_for(m) is None)

    def combatant_visuals(self, sides, placement, layout):
        """``sides``: ``{side_id: [member_id, ...]}``; ``placement``: ``{side_id:
        "left"|"right"}``.

        Combatants stand in the free stage between the HUD columns of the UI
        ``layout`` (BattleUiLayoutProfile), above the action menu: up to three
        per column, the first column nearest the centre, the second staggered
        behind it. Members on the right face left.
        """
        width = float(getattr(layout, "virtual_width", 320))
        height = float(getattr(layout, "virtual_height", 180))
        margin = float(getattr(layout, "margin", 8.0))
        panel = float(getattr(layout, "hud_panel_width", 112.0))
        hud_mode = getattr(layout, "party_hud", "column")
        if hud_mode == "side_list":
            # The party's list takes the right edge; the stage is everything left of it, down to
            # the bottom margin (the command menu sits in the lower part of that stage).
            left_edge, right_edge = margin, width - 2 * margin - panel
            top = max(
                float(getattr(layout, "timeline_y", 7.0)) + 30.0,
                height * float(getattr(layout, "stage_top", 0.0)),
            )
            bottom = height - margin - 6.0
        elif hud_mode == "bottom_row":
            # Side-view staging: the whole width is stage; feet stand on the
            # ground band between ``stage_top`` and the bottom HUD row.
            left_edge, right_edge = margin, width - margin
            top = max(
                float(getattr(layout, "timeline_y", 7.0)) + 30.0,
                height * float(getattr(layout, "stage_top", 0.0)),
            )
            bottom = height - margin - 24.0 - 6.0
        else:
            left_edge, right_edge = margin + panel, width - margin - panel
            top = float(getattr(layout, "timeline_y", 7.0)) + 52.0
            bottom = height * 0.60
        stage = max(1.0, right_edge - left_edge)
        visuals = []
        for side_id, members in sides.items():
            zone = placement.get(side_id, "left")
            direction = 1 if zone == "left" else -1
            front = float(getattr(layout, "stage_front", 0.30))
            front_x = left_edge + stage * front if zone == "left" else right_edge - stage * front

            def logical_size(member_id):
                profile = self.profile_for(member_id)
                if profile is None:
                    raise BattleVisualError(f"no combatant visual profile for {member_id}")
                frame = self.sprite_sheet(profile.assets.battlefield_asset_id).frames[0]
                return frame.width * float(profile.transform.scale_x), frame.height * float(
                    profile.transform.scale_y
                )

            sizes = {m: logical_size(m) for m in members}
            smallest = min(h for _, h in sizes.values()) if sizes else 0.0
            # Large combatants (bosses) get their own column behind the others.
            # a unit whose profile turns the HUD off (a pet, a summon) stands apart from the party
            # where the layout lists the zone in front_large_zones
            apart_zone = zone in tuple(getattr(layout, "front_large_zones", ()))

            def apart(member_id, apart_zone=apart_zone):
                profile = self.profile_for(member_id)
                return apart_zone and profile is not None and not profile.hud_visible

            large = [m for m in members if sizes[m][1] > smallest * 1.5 or apart(m)]
            regular = [m for m in members if m not in large]
            per_column = max(1, int(getattr(layout, "column_size", 3)))
            columns = [regular[i : i + per_column] for i in range(0, len(regular), per_column)]
            if zone in tuple(getattr(layout, "front_large_zones", ())):
                columns = [[m] for m in large] + columns  # toward the centre of the stage
            else:
                columns += [[m] for m in large]
            # Column centres: each column clears the previous one by the widest sprites.
            xs, x = [], front_x
            for index, column in enumerate(columns):
                if index:
                    previous = max(sizes[m][0] for m in columns[index - 1])
                    x -= direction * (previous / 2 + max(sizes[m][0] for m in column) / 2 + 4)
                xs.append(x)
            edge = left_edge if zone == "left" else right_edge
            outer = (
                xs[-1] - direction * max(sizes[m][0] for m in columns[-1]) / 2 if columns else edge
            )
            overflow = (edge - outer) * direction if (outer - edge) * direction < 0 else 0.0
            xs = [value + direction * overflow for value in xs]
            for column_index, column in enumerate(columns):
                x = xs[column_index]
                for row_index, member_id in enumerate(column):
                    profile = self.profile_for(member_id)
                    if profile is None:
                        raise BattleVisualError(f"no combatant visual profile for {member_id}")
                    sheet_id = profile.assets.battlefield_asset_id
                    self.clip_set(sheet_id)  # validates
                    transform = profile.transform
                    if len(column) == 1 and member_id in large:
                        y = (top + bottom) / 2 + sizes[member_id][1] / 3
                    elif hud_mode == "side_list":
                        # one slot per member of the column: name, sprite and the shield row
                        # (under the feet) all fit in it, so a column of three never overlaps
                        slot = (bottom - top) / max(1, len(column))
                        y = top + slot * (row_index + 1) - 6.0 - slot * 0.3 * (column_index % 2)
                    else:
                        y = top + (bottom - top) * (
                            (row_index + 0.5 + 0.5 * column_index) / max(3, len(column) + 0.5)
                        )
                    # Keep the whole sprite below the turn timeline (and its overhead bar).
                    tall = self.sprite_sheet(sheet_id).frames[0].height * float(transform.scale_y)
                    y = max(y, float(getattr(layout, "timeline_y", 7.0)) + 46.0 + tall)
                    anchor = BattleVisualAnchor(
                        x + transform.offset_x,
                        y + transform.offset_y,
                        "right" if zone == "left" else "left",
                        depth=y,
                    )
                    roles = {state.state_id: state.clip_role for state in profile.states}
                    visuals.append(
                        BattleCombatantVisual(
                            member_id,
                            sheet_id,
                            sheet_id,
                            anchor,
                            animation_roles=roles,
                            source_pixels_per_logical_pixel=1.0 / float(transform.scale_x),
                        )
                    )
        return tuple(visuals)

    # -- choreography ----------------------------------------------------------
    def motion_sequence(self, ability_id):
        ids = self.library.ids("motion_sequences")
        for key in (str(ability_id), DEFAULT_SEQUENCE_ID):
            if key in ids:
                return self.library.require("motion_sequences", key)
        return None
