"""Battle pictures for projects without battle art: generated combatant and effect sheets."""

from __future__ import annotations

from asteria.gameplay import ActionCue, ActionCueKind, PresentationCue
from asteria.presentation import (
    BattlePresentationEventKind,
)
from asteria.presentation.battle.runtime import _mirrored
from asteria.presentation.visuals.particles import effect_definition
from asteria.rpg import BattleOutcome
from asteria.runtime.battle.presentation_parts import CHANNEL_KINDS, PARTY_SIDES
from asteria.runtime.battle.visuals import (
    member_body_height,
)


class GeneratedBattleArtMixin:
    """Battle pictures for projects without battle art: generated combatant and effect sheets."""

    def _source_image(self, member_id, side, index):
        """The manifest image a project without battle art shows for a combatant (None: draw a
        silhouette)."""
        battle = self.host.manifest.get("battle", {})
        try:
            if side == "heroes" and battle.get("heroes"):
                return self.host.load_image(battle["heroes"][index % len(battle["heroes"])]), False
            enemy = str(member_id).split(":", 1)[0]
            rel = battle.get("enemy_sprites", {}).get(enemy)
            if rel:
                return self.host.load_image(
                    rel
                ), True  # legacy screens drew enemies facing left: flip
        except Exception as exc:  # pygame.error for an unreadable image: fall back to a silhouette
            if type(exc).__name__ not in ("error", "FileNotFoundError"):
                raise
        return None, False

    def _body_height(self, visual):
        sheet = self.resolver.sprite_sheet(visual.sprite_sheet_asset_id)
        try:
            meta = self.resolver.sheet_meta(visual.sprite_sheet_asset_id)
        except Exception:  # noqa: BLE001 - a generated sheet without metadata
            meta = {}
        return member_body_height(
            meta, sheet.frames[0].height, visual.source_pixels_per_logical_pixel
        )

    def _body_extents(self, visual):
        """``(left, top, right, bottom)`` of the figure's visible pixels in its idle pose (every
        frame of the idle clip), in logical units round its feet (the anchor): what a name or
        caption must keep clear of. Names are hidden while a figure acts (see ``update``), so
        attack poses need no room. ``None`` when the picture cannot be read."""

        try:
            sheet = self.resolver.sprite_sheet(visual.sprite_sheet_asset_id)
            asset_id = sheet.texture.asset_id
            lookup = getattr(self.resolver, "generated_image", None)
            image = lookup(asset_id) if lookup is not None else None
            if image is None:
                image = self.host.load_image(self.resolver.source_uri(asset_id))
        except Exception:  # noqa: BLE001 - no picture: the estimate from the height is used
            return None
        cache = self._extent_cache
        mirrored = _mirrored(visual)
        ratio = float(visual.source_pixels_per_logical_pixel) or 1.0
        key = (asset_id, mirrored, ratio, id(image))
        if key in cache:
            return cache[key]
        bounds = image.get_rect()
        found = None
        idle = dict(visual.animation_roles).get("idle", "idle")
        try:
            clip = self.resolver.clip_set(visual.sprite_sheet_asset_id).clips.get(idle)
        except Exception:  # noqa: BLE001 - no clips: the first frame stands for the pose
            clip = None
        indices = {k.frame_index for k in clip.keyframes} if clip is not None else {0}
        for index in sorted(indices):
            if not 0 <= index < len(sheet.frames):
                continue
            frame = sheet.frames[index]
            rect = self.host.pg.Rect(frame.x, frame.y, frame.width, frame.height)
            if not bounds.contains(rect):
                continue
            seen = image.subsurface(rect).get_bounding_rect()
            if not seen.width or not seen.height:
                continue
            x0, x1 = seen.left, seen.right
            if mirrored:  # the picture is turned round inside its frame
                x0, x1 = frame.width - seen.right, frame.width - seen.left
            px, py = frame.width * frame.pivot_x, frame.height * frame.pivot_y
            part = ((x0 - px) / ratio, (seen.top - py) / ratio)
            part += ((x1 - px) / ratio, (seen.bottom - py) / ratio)
            found = (
                part
                if found is None
                else (
                    min(found[0], part[0]),
                    min(found[1], part[1]),
                    max(found[2], part[2]),
                    max(found[3], part[3]),
                )
            )
        cache[key] = found
        return found

    def _silhouette(self, member_id, side):
        pg = self.host.pg
        image = pg.Surface((64, 96), pg.SRCALPHA)
        color = (90, 140, 220) if side == "heroes" else (210, 90, 100)
        dark = tuple(c // 2 for c in color)
        pg.draw.ellipse(image, color, (10, 36, 44, 58))
        pg.draw.ellipse(image, dark, (10, 36, 44, 58), 3)
        pg.draw.circle(image, color, (32, 24), 18)
        pg.draw.circle(image, dark, (32, 24), 18, 3)
        pg.font.init()
        label = pg.font.Font(None, 30).render(str(member_id)[:1].upper(), True, (250, 250, 255))
        image.blit(label, label.get_rect(center=(32, 64)))
        return image

    def _combatant_sheet(self, image, *, flip):
        """Five frames from one picture: idle, attack (lunge), hit (flash), ko (fallen, dark),
        weak (slumped, pale - shown at low health when the manifest sets battle.weak_below)."""
        pg = self.host.pg
        if flip:
            image = pg.transform.flip(image, True, False)
        height = self.FRAME_HEIGHT
        w, h = image.get_size()
        width = max(1, round(w * height / h))
        if image.get_bitsize() < 24:
            image = image.convert(32, pg.SRCALPHA)
        body = pg.transform.smoothscale(image, (width, height))
        fw, fh = width + 20, height + 8
        sheet = pg.Surface((fw * 5, fh), pg.SRCALPHA)
        y = fh - height
        sheet.blit(body, (10, y))
        sheet.blit(body, (fw + 16, y - 3))  # lunge forward
        hit = body.copy()
        hit.fill((110, 110, 110, 0), special_flags=pg.BLEND_RGBA_ADD)
        sheet.blit(hit, (fw * 2 + 5, y))
        fallen = pg.transform.rotate(body, 80)
        fallen.fill((120, 115, 130, 255), special_flags=pg.BLEND_RGBA_MULT)
        if fallen.get_width() > fw or fallen.get_height() > fh:
            k = min(fw / fallen.get_width(), fh / fallen.get_height())
            fallen = pg.transform.smoothscale(
                fallen, (max(1, int(fallen.get_width() * k)), max(1, int(fallen.get_height() * k)))
            )
        sheet.blit(fallen, (fw * 3 + (fw - fallen.get_width()) // 2, fh - fallen.get_height()))
        weak = body.copy()  # worn out: slumped a little and paler
        weak.fill((205, 190, 190, 255), special_flags=pg.BLEND_RGBA_MULT)
        sheet.blit(weak, (fw * 4 + 10, y + 4))
        clips = {
            "weak": {"frames": [4], "frame_duration": 0.5, "loop": True},
            "idle": {"frames": [0], "frame_duration": 0.5, "loop": True},
            "attack": {"frames": [1, 1, 0], "frame_duration": 0.1, "loop": False},
            "hit": {"frames": [2, 2, 0], "frame_duration": 0.1, "loop": False},
            "ko": {"frames": [3], "frame_duration": 0.5, "loop": True},
        }
        return sheet, (fw, fh), clips

    def _show_new_combatants(self, game):
        """Members that joined after the battle began (SUMMON, reinforcements) get a visual and
        appear."""
        if not self.visuals_enabled:
            return
        shown = {v.member_id for v in self.screen.scene.combatants}
        sides = {
            side: [m.member_id for m in party.members]
            for side, party in game.battle.parties.items()
        }
        new = {side: [m for m in members if m not in shown] for side, members in sides.items()}
        if not any(new.values()):
            return
        self._register_fallback_visuals(new, self._layout)
        portraits = {**self.screen.member_portraits, **self._portraits(new)}
        visuals = self.resolver.combatant_visuals(
            sides,
            self.placement_by_side,
            self._layout,
            self._stage_template(game, self._layout),
            PARTY_SIDES,
            hud_portraits=portraits,
        )
        added = [v for v in visuals if v.member_id not in shown]
        for visual in added:
            self.screen.add_combatant(visual)
            self.screen.member_heights[visual.member_id] = self._body_height(visual)
            self.screen.member_extents[visual.member_id] = self._body_extents(visual)
        self._hide_unlisted_hud(added)
        self.screen.member_portraits = portraits
        self.screen.display_names = self._display_names(game)
        self.screen.animation.compositions.update(self._compositions(added))

    def _hide_unlisted_hud(self, visuals):
        """Members whose profile turns the HUD off get no party panel."""
        for visual in visuals:
            profile = self.resolver.profile_for(visual.member_id)
            if profile is not None and not profile.hud_visible:
                self.screen.hud_hidden.add(visual.member_id)

    def _portraits(self, sides):
        """``member_id: (portrait, small portrait)`` of the members of ``sides`` whose combatant
        profile names a portrait picture that loads: their party cards show it. A picture that
        is missing counts as none, so its card is drawn as it always was."""
        loads = getattr(self.host, "skin_image", None)  # the picture at its own size, or None
        found = {}
        for members in sides.values():
            for member_id in members:
                assets = getattr(self.resolver.profile_for(member_id), "assets", None)
                if assets is None or loads is None:
                    continue
                ids = tuple(
                    str(asset_id) if asset_id and loads(str(asset_id)) is not None else ""
                    for asset_id in (assets.portrait_asset_id, assets.small_portrait_asset_id)
                )
                if any(ids):
                    found[member_id] = ids
        return found

    def _register_fallback_visuals(self, sides, layout):
        """Every combatant without a combatant_visuals profile gets a generated one (no legacy
        fallback)."""
        target = (
            float(getattr(layout, "virtual_height", 180)) * 0.16
        )  # logical height of a regular combatant
        done = set()
        for side, members in sides.items():
            for index, member_id in enumerate(members):
                key = self.resolver.profile_key(member_id)
                if key in done or self.resolver.profile_for(member_id) is not None:
                    continue
                done.add(key)
                image, flip = self._source_image(member_id, side, index)
                sheet, frame_size, clips = self._combatant_sheet(
                    image if image is not None else self._silhouette(key, side), flip=flip
                )
                asset_id = f"generated.combatant.{key}"
                self.resolver.register_generated(
                    asset_id, sheet, sheet.get_size(), frame_size=frame_size, clips=clips
                )
                size = (
                    (self.host._enemy_layout(member_id) or {}).get("size")
                    if side != "heroes"
                    else None
                )
                logical = target * (float(size[1]) / 120.0 if size else 1.0)
                self.resolver.register_generated_profile(key, asset_id, logical / frame_size[1])

    def _manifest_skill_fx(self, ability_id):
        """Generated VFX sheet for a manifest skill ``fx`` image (4 columns, ``frames`` cells), or
        None."""
        meta = self.host.manifest.get("battle", {}).get("skills", {}).get(ability_id) or {}
        if not meta.get("fx"):
            return None
        asset_id = f"generated.fx.{ability_id}"
        if not self.resolver.is_generated(asset_id):
            try:
                image = self.host.load_image(meta["fx"])
            except (
                Exception
            ) as exc:  # pygame.error / missing file: no effect, the action still plays
                if type(exc).__name__ not in ("error", "FileNotFoundError"):
                    raise
                return None
            count = int(meta.get("frames", 16))
            columns = 4
            rows = max(1, (count + columns - 1) // columns)
            frame = (image.get_width() // columns, image.get_height() // rows)
            self.resolver.register_generated(
                asset_id,
                image,
                image.get_size(),
                frame_size=frame,
                clips={
                    "play": {
                        "frames": list(range(count)),
                        "frame_duration": 0.42 / max(1, count),
                        "loop": False,
                    }
                },
                pivot=(0.5, 0.5),
                vfx={"anchor": "center", "scale": 1.0},
            )
        return asset_id

    def _ensure(self):
        """Set up for the session's current battle if begin() was not called for it."""
        battle = self.host.game.battle
        if battle is not None and (self.screen is None or self._battle is not battle):
            self.begin()
        return self.screen is not None

    def consume(self, entries):
        if not self._ensure():
            return
        coordinator = self.screen.coordinator
        # Lifecycle events (KO / revive) were queued by Battle Core hooks while the
        # actions resolved; show them when the choreography reaches the end.
        hook_events = coordinator.drain()
        for entry in entries:
            at = max(self._clock, self._cursor)
            if entry.kind == "battle_started":
                coordinator.start()
            elif entry.kind == "turn":
                self._at(
                    at,
                    lambda e=entry: coordinator.push_custom("battle.turn", source_id=e.member_id),
                )
            elif entry.kind == "action":
                self._push_action(entry, at)
            elif entry.kind == "gauge":
                self._at(self._last_impact, lambda e=entry: coordinator.push_gauge_result(e.data))
            elif entry.kind == "battle_finished":
                data = entry.data
                outcome = BattleOutcome(
                    True, tuple(data["winning_sides"]), tuple(data["defeated_sides"])
                )
                self._at(at, lambda o=outcome, d=data: self._finish(o, d))
        for event in hook_events:
            self._at(
                self._last_impact if self.visuals_enabled else self._clock,
                lambda e=event: coordinator.reemit(e),
            )
        self._sync_lifecycle()
        self._release_due()

    def _sync_state_tint(self, member_id, member):
        """Battlers carrying a state with a ``tint`` are drawn in that colour (poison green,
        frozen blue...); several tints multiply."""
        states = getattr(member.subject, "states", None)
        tints = self.screen.animation.state_tints
        colour = None
        if states is not None and states.has_active:
            for active in states.active_states():
                rgb = states.registry.require(active.state_id).tint_rgb()
                if rgb is not None:
                    colour = (
                        rgb if colour is None else tuple(a * b // 255 for a, b in zip(colour, rgb))
                    )
        if colour is None:
            tints.pop(member_id, None)
        else:
            tints[member_id] = colour

    def _resolve_icon(self, asset_id):
        """A skill / item icon of the project (menu rows with an ``icon_id``), or ``None``."""
        try:
            return self.host.icon_image(asset_id, getattr(self, "_icon_px", 16))
        except Exception as exc:  # pygame.error / a missing file: the row shows a plain box
            if type(exc).__name__ not in ("error", "FileNotFoundError", "KeyError"):
                raise
            return None

    def _weak_fraction(self):
        """Health share below which a combatant shows its ``weak`` pose (the project's
        ``BattleOptions``, else manifest ``battle.weak_below``; 0 = never)."""
        try:
            return max(0.0, min(1.0, float(self.host.battle_option("weak_below"))))
        except (TypeError, ValueError):
            return 0.0

    def _sync_weak_pose(self, visual, member):
        """Low-health combatants rest in their ``weak`` pose; it ends when they recover."""
        limit = self._weak_fraction()
        if limit <= 0 or not visual.clip_for("weak"):
            return
        resource = self.host.game.rules.knockout_resource_id
        pool = member.subject.resources
        if not resource or not pool.contains(resource) or pool.maximum(resource) <= 0:
            return
        weak = pool.current(resource) / pool.maximum(resource) <= limit
        state = self.screen.animation.combatant(visual.member_id)
        role = state.role.value if hasattr(state.role, "value") else str(state.role)
        if weak and role == "idle":
            state.set_role("weak", restart=False)
        elif not weak and role == "weak":
            state.set_role("idle", restart=False)

    def _sync_lifecycle(self):
        """Mirror Battle Core knock-outs / revivals onto combatant poses at the right beat.

        Knock-outs decided by a resource (no lifecycle hook) are read from
        ``BattleRuntime.is_active``; the KO pose waits for the impact that
        caused it, a revival waits for the end of the queued choreography.
        """
        battle = self.host.game.battle
        if battle is None or not self.visuals_enabled:
            return
        for visual in self.screen.scene.combatants:
            member = battle.members.get(visual.member_id)
            if member is None:
                continue
            active = battle.is_active(member)
            if active:
                self._sync_weak_pose(visual, member)
            self._sync_state_tint(visual.member_id, member)
            shown_down = self._shown_down.get(visual.member_id, False)
            if not active and not shown_down:
                self._shown_down[visual.member_id] = True
                self._at(
                    self._last_impact,
                    lambda m=visual.member_id: self.screen.animation.combatant(m).mark_defeated(),
                )
            elif active and shown_down:
                self._shown_down[visual.member_id] = False
                self._at(
                    max(self._clock, self._cursor),
                    lambda m=visual.member_id: self.screen.animation.combatant(m).revive(),
                )

    def _finish(self, outcome, data):
        self.screen.present_result(outcome, perspective_side_ids=("heroes",))
        self.screen.coordinator.finish({"winning_sides": list(data["winning_sides"])})

    def _flinches(self, source, target):
        """A blow from the other side makes a fighter flinch; a guard or a friend's heal won't."""
        members = self._battle.members  # the game has let go of it once the last blow is struck
        if source not in members or target not in members:
            return True
        return members[source].side != members[target].side

    def _beat_cues(self, entry, beat):
        kind = CHANNEL_KINDS.get(beat.channel)
        if kind is None:
            return []
        targets = tuple(entry.target_ids) or (entry.member_id,)
        members = (
            (entry.member_id,)
            if beat.member_id in (None, "@source")
            else (targets if beat.member_id == "@target" else (beat.member_id,))
        )
        if kind == ActionCueKind.ANIMATION and beat.cue == "hit" and beat.member_id == "@target":
            members = tuple(m for m in members if self._flinches(entry.member_id, m))
        cues = []
        for member_id in members:
            payload = dict(beat.payload_dict())
            payload["member_id"] = member_id
            if kind == ActionCueKind.ANIMATION:
                payload["role"] = beat.cue
            elif kind == ActionCueKind.VFX:
                payload["asset_id"] = beat.cue
                particles = effect_definition(self.host.game.project.assets, beat.cue)
                if (
                    particles is not None
                ):  # VFX-01: emission plus the longest life, so every particle finishes
                    emit = 1.0 if particles.looping else particles.duration
                    payload.setdefault("duration", emit + particles.lifetime[1])
                else:
                    payload.setdefault(
                        "duration", max(0.05, self.resolver.clip_duration(beat.cue, "play"))
                    )
            elif kind == ActionCueKind.AUDIO:
                payload["asset_id"] = beat.cue
            else:
                payload["effect"] = beat.cue
            cues.append(
                PresentationCue(
                    f"action.{entry.ability_id}",
                    ActionCue(f"{member_id}.{beat.beat_id}", beat.at, kind, payload),
                )
            )
        return cues

    def _push_action(self, entry, start):
        coordinator = self.screen.coordinator
        targets = tuple(entry.target_ids)
        sequence = (
            self.resolver.motion_sequence(entry.ability_id) if self.visuals_enabled else None
        )

        def announce():
            coordinator.push_custom(
                "battle.action",
                source_id=entry.member_id,
                payload={"ability_id": entry.ability_id, "target_ids": list(targets)},
            )
            if targets:
                coordinator.push_target_selection(
                    targets, primary_target_id=targets[0], source_id=entry.member_id
                )

        def values():
            for target, outcome in entry.outcomes:
                coordinator.push_resolved_value(
                    outcome, target_id=target, source_id=entry.member_id
                )

        self._at(start, announce)
        if sequence is None:

            def default_cues():
                cues = [
                    PresentationCue(
                        f"action.{entry.ability_id}",
                        ActionCue(
                            f"{entry.member_id}.attack",
                            0.0,
                            ActionCueKind.ANIMATION,
                            {"member_id": entry.member_id, "role": "attack"},
                        ),
                    )
                ]
                cues.extend(
                    PresentationCue(
                        f"action.{entry.ability_id}",
                        ActionCue(
                            f"{target}.hit",
                            0.0,
                            ActionCueKind.ANIMATION,
                            {"member_id": target, "role": "hit"},
                        ),
                    )
                    for target, _ in entry.outcomes
                    if self._flinches(entry.member_id, target)
                )
                # Effects configured per skill in the manifest (projects without motion sequences).
                skill = (
                    self.host.manifest.get("battle", {}).get("skills", {}).get(entry.ability_id)
                    or {}
                )
                fx = self._manifest_skill_fx(entry.ability_id)
                for target in [t for t, _ in entry.outcomes][:1] if fx else ():
                    cues.append(
                        PresentationCue(
                            f"action.{entry.ability_id}",
                            ActionCue(
                                f"{target}.fx",
                                0.0,
                                ActionCueKind.VFX,
                                {"member_id": target, "asset_id": fx, "duration": 0.42},
                            ),
                        )
                    )
                if skill.get("sfx"):
                    cues.append(
                        PresentationCue(
                            f"action.{entry.ability_id}",
                            ActionCue(
                                f"{entry.member_id}.sfx",
                                0.0,
                                ActionCueKind.AUDIO,
                                {"member_id": entry.member_id, "asset_id": skill["sfx"]},
                            ),
                        )
                    )
                coordinator.consume_timeline_cues(cues)

            self._at(start, default_cues)
            self._at(start, values)
            self._last_impact = start
            return
        for beat in sequence.beats:
            if (
                beat.channel == "motion_fx"
            ):  # afterimage / trail echoes of the source or targets (VFX-03)
                payload = dict(beat.payload_dict())
                hold = float(payload.pop("duration", beat.duration) or 0.3)
                members = (
                    (entry.member_id,)
                    if beat.member_id in (None, "@source")
                    else (
                        tuple(entry.target_ids)
                        if beat.member_id == "@target"
                        else (beat.member_id,)
                    )
                )
                for member in members:
                    self._at(
                        start + beat.at,
                        lambda m=member, c=beat.cue, d=hold, p=payload: (
                            self.screen.animation.start_motion_fx(m, c, d, **p)
                        ),
                    )
                continue
            if (
                beat.channel == "move"
            ):  # step toward the first target ("advance") or back ("return")
                payload = dict(beat.payload_dict())
                members = (
                    (entry.member_id,)
                    if beat.member_id in (None, "@source")
                    else (
                        tuple(entry.target_ids)
                        if beat.member_id == "@target"
                        else (beat.member_id,)
                    )
                )
                target = (
                    entry.target_ids[0] if entry.target_ids and beat.cue == "advance" else None
                )
                for member in members:
                    self._at(
                        start + beat.at,
                        lambda m=member, t=target, d=beat.duration, e=beat.easing, p=payload: (
                            self.screen.animation.start_move(
                                m, target_id=t, duration=d or 0.18, easing=e, **p
                            )
                        ),
                    )
                continue
            if beat.channel == "timing" and beat.cue == "hit_stop":
                hold = float(beat.payload_dict().get("duration", beat.duration) or 0.0)
                self._at(start + beat.at, lambda d=hold: self._start_hit_stop(d))
                continue
            self._at(
                start + beat.at,
                lambda b=beat: coordinator.consume_timeline_cues(self._beat_cues(entry, b)),
            )
        impact = next(
            (b.at for b in sequence.beats if b.channel == "animation" and b.cue == "hit"), 0.0
        )
        self._at(start + impact, values)
        self._last_impact = start + impact
        self._cursor = start + sequence.duration

    def _semantics_from_events(self, events):
        """Rebuild rule-relevant meaning from the presentation events actually emitted.

        An action's values may be emitted in a later batch than its
        announcement (they wait for the impact beat), so the action being
        rebuilt is kept across batches and finalized when the next fact starts.
        """
        result = []
        pending = getattr(self, "_semantic_action", None)
        if pending is not None:
            result.append(pending)
        for event in events:
            kind, payload = event.kind, event.payload
            if kind == BattlePresentationEventKind.SCENE_STARTED:
                result.append(("battle_started",))
            elif (
                kind == BattlePresentationEventKind.CUSTOM
                and payload.get("event_id") == "battle.turn"
            ):
                result.append(("turn", event.source_id))
            elif (
                kind == BattlePresentationEventKind.CUSTOM
                and payload.get("event_id") == "battle.action"
            ):
                pending = [
                    event.source_id,
                    payload["ability_id"],
                    tuple(payload["target_ids"]),
                    [],
                ]
                result.append(pending)
            elif kind == BattlePresentationEventKind.RESOLVED_VALUE and pending is not None:
                pending[3].append(
                    (
                        payload["target_id"],
                        round(float(payload["value"]), 6),
                        tuple(sorted(payload["outcome_tags"])),
                    )
                )
            elif kind == BattlePresentationEventKind.GAUGE_THRESHOLD:
                key = ("gauge", event.source_id, payload["composition_id"])
                if result and isinstance(result[-1], tuple) and result[-1][:3] == key:
                    result[-1] = (*key, (*result[-1][3], payload["threshold_id"]))
                else:
                    result.append((*key, (payload["threshold_id"],)))
            elif kind == BattlePresentationEventKind.SCENE_FINISHED:
                result.append(("battle_finished", tuple(payload["result"]["winning_sides"])))
        # Keep the newest action open (its values may still arrive); report the rest.
        self._semantic_action = result.pop() if result and isinstance(result[-1], list) else None
        return [
            ("action", item[0], item[1], item[2], tuple(item[3]))
            if isinstance(item, list)
            else item
            for item in result
        ]

    def finalize_trace(self):
        """Close the action still being rebuilt (call once the presentation is idle)."""
        pending = getattr(self, "_semantic_action", None)
        if pending is not None:
            self.trace.append(("action", pending[0], pending[1], pending[2], tuple(pending[3])))
            self._semantic_action = None
        return self.trace
