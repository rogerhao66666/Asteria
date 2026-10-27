"""Game Start authoring: the New Game state of a project as a form (undoable).

The start definition lives in ``Project.game_start`` (design data, not a Player Save). This
controller exposes the common fields as a flat, Qt-free record: start scene, facing, position,
party, bag, spare gear (the equipment bag, D98), currencies and owned pets. Anything the form
does not show (progression, loadouts, event variables...) is kept exactly as it is.
"""

from __future__ import annotations

import copy

from asteria.runtime.game_start import GameStartDefinition

from .game_systems_authoring import F, FormField

FACINGS = ("down", "up", "left", "right")
_PET = (
    F("species_id", "Species", "ref", source="pet_species"),
    F("nickname", "Nickname", "text", default=""),
    F("level", "Level", "int", default=1),
    F("affinity", "Affinity", "float", default=0.0),
)
GAME_START_FORM: tuple[FormField, ...] = (
    F(
        "scene_id",
        "Start Scene",
        "optional_ref",
        source="scenes",
        default="",
        empty_label="(the project's startup scene)",
    ),
    F("player_facing", "Player Facing", "choice", choices=FACINGS, default="down"),
    F(
        "position_x",
        "Start X (unticked: the scene's spawn point)",
        "optional_int",
        default=None,
        toggle_label="Set position",
    ),
    F(
        "position_y",
        "Start Y (unticked: the scene's spawn point)",
        "optional_int",
        default=None,
        toggle_label="Set position",
    ),
    F("party_actor_ids", "Party", "ref_list", source="actors", default=()),
    F("items", "Starting Items", "amounts", source="items", default={}),
    # D98: spare pieces in the equipment bag (worn gear is each hero's loadout)
    F("gear", "Starting Gear (spare, in the bag)", "amounts", source="equipment", default={}),
    F("currencies", "Starting Currencies", "amounts", default={}),
    F("pets", "Starting Pets", "table", fields=_PET, default=()),
    F("active_pet", "Pet Sent Out First (1-based; 0: first pet)", "int", default=0),
)


class GameStartAuthoringError(RuntimeError):
    pass


class _SetGameStart:
    label = "Edit Game Start"

    def __init__(self, project, new, old):
        self.project, self.new, self.old = project, new, old

    def redo(self):
        self.project.game_start = self.new

    def undo(self):
        self.project.game_start = self.old


class GameStartAuthoringController:
    form = GAME_START_FORM

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise GameStartAuthoringError("project required")
        return self.document.project

    def references(self, source):
        db = self.project.rpg_database
        if source == "scenes":  # shown by name, kept by id; a repeated name gets a short id
            scenes = list(self.project.scenes())
            names = [s.name or "Untitled Scene" for s in scenes]
            return tuple(
                (s.id, n if names.count(n) == 1 else f"{n} ({s.id[:8]})")
                for s, n in zip(scenes, names, strict=True)
            )
        if source == "actors":  # the party list shows each member's name, keeps the id
            return tuple(
                (actor_id, f"{db.actors[actor_id].display_name or actor_id} ({actor_id})")
                for actor_id in sorted(db.actors)
            )
        stores = {
            "items": db.items,
            "equipment": db.equipment,
            "actors": db.actors,
            "pet_species": db.pet_species,
        }
        return tuple(sorted(stores.get(source, {})))

    # -- reading -------------------------------------------------------------------------
    def form_data(self):
        start = self.project.game_start
        state = (start.rpg_state_data or {}) if start.rpg_state_data is not None else {}
        inventory = state.get("inventory", {})
        items = dict(inventory.get("counts", {})) if isinstance(inventory, dict) else {}
        pets = [
            {
                "species_id": p["species_id"],
                "nickname": p.get("nickname", ""),
                "level": p.get("level", 1),
                "affinity": p.get("affinity", 0.0),
            }
            for p in state.get("pets", ())
        ]
        active = state.get("active_pet_id", "")
        order = [p["instance_id"] for p in state.get("pets", ())]
        position = start.player_position
        return {
            "scene_id": start.scene_id or "",
            "player_facing": start.player_facing,
            "position_x": None if position is None else int(position[0]),
            "position_y": None if position is None else int(position[1]),
            "party_actor_ids": list(state.get("party_actor_ids", ())),
            "items": items,
            "gear": _gear_counts(state.get("equipment_bag", ())),
            "currencies": dict(state.get("currencies", {})),
            "pets": pets,
            "active_pet": order.index(active) + 1 if active in order else 0,
        }

    # -- writing -------------------------------------------------------------------------
    def apply(self, data):
        """Validate ``data`` against the whole project, then replace the start (undoable)."""
        project = self.project
        old = project.game_start
        new = self._build(old, data)
        try:
            new.validate(project)
        except (KeyError, TypeError, ValueError) as exc:
            raise GameStartAuthoringError(f"invalid game start: {exc}") from exc
        self.document.execute(_SetGameStart(project, new, old))
        return new

    def _build(self, old, data):
        state = copy.deepcopy(old.rpg_state_data) if old.rpg_state_data is not None else None
        if state is None:
            from asteria.rpg.progression import ProgressionRuntime
            from asteria.rpg.save_state import RpgRuntimeState

            db = self.project.rpg_database
            state = RpgRuntimeState(
                progression=ProgressionRuntime(db.progression_tracks.values())
            ).to_data()
        party = [str(x) for x in data.get("party_actor_ids", ())]
        state["party_actor_ids"] = party
        state["party_active_actor_ids"] = [
            x for x in state.get("party_active_actor_ids", party) if x in party
        ] or party
        state["currencies"] = {str(k): v for k, v in dict(data.get("currencies", {})).items() if v}
        state["inventory"] = _with_items(state.get("inventory", {}), data.get("items", {}))
        gear = {str(k): int(v) for k, v in dict(data.get("gear", {})).items() if int(v) > 0}
        if gear != _gear_counts(state.get("equipment_bag", ())):
            state = self._with_gear(state, gear)
        pets, serial = [], {}
        for raw in data.get("pets", ()):
            species = str(raw["species_id"])
            serial[species] = serial.get(species, 0) + 1
            pet = {
                "instance_id": f"{species}#{serial[species]}",
                "species_id": species,
                "nickname": str(raw.get("nickname", "")),
                "level": max(1, int(raw.get("level", 1))),
                "experience": 0.0,
            }
            if float(raw.get("affinity", 0) or 0):
                pet["affinity"] = float(raw["affinity"])
            pets.append(pet)
        state.pop("pets", None)
        state.pop("active_pet_id", None)
        if pets:
            state["pets"] = pets
            index = int(data.get("active_pet", 0) or 0)
            chosen = pets[index - 1] if 1 <= index <= len(pets) else pets[0]
            state["active_pet_id"] = chosen["instance_id"]
        x, y = data.get("position_x"), data.get("position_y")
        position = None if x is None or y is None else (float(x), float(y))
        return GameStartDefinition(
            str(data.get("scene_id", "")).strip() or None,
            old.player_entity_id,
            str(data.get("player_facing", "down")),
            position,
            state,
            old.event_context_data,
        )

    def _with_gear(self, state, gear):
        """``state`` holding ``gear`` (``{equipment id: pieces}``) in its equipment bag: a piece
        it holds already is kept as it is (its growth, its sockets), a new one is made as the
        game makes found gear. An older state gains only the keys the bag's version needs;
        everything else stays as written."""
        from asteria.rpg.items import EquippedItem
        from asteria.rpg.progression import ProgressionRuntime
        from asteria.rpg.save_state import RpgRuntimeState

        db = self.project.rpg_database
        state = copy.deepcopy(state)
        if "equipment_bag" not in state:  # versions before 8: the bag and the keys before it
            fresh = RpgRuntimeState(
                progression=ProgressionRuntime(db.progression_tracks.values())
            ).to_data()
            for key in ("shop_stock", "quests", "world", "equipment_bag"):
                state.setdefault(key, fresh[key])
            state["version"] = fresh["version"]
        bag = state["equipment_bag"]
        taken = {piece["instance_id"] for piece in bag}
        for loadout in state.get("loadouts", {}).values():
            for pieces in dict(loadout.get("equipped", {})).values():
                taken.update(piece.get("instance_id", "") for piece in pieces)
        kept = []
        for equipment_id, count in gear.items():
            pieces = [g for g in bag if g["equipment_id"] == equipment_id][:count]
            kept += pieces
            serial = 0
            for _ in range(count - len(pieces)):
                serial += 1
                while f"{equipment_id}:bag{serial}" in taken:
                    serial += 1
                instance_id = f"{equipment_id}:bag{serial}"
                taken.add(instance_id)
                piece = EquippedItem(db.equipment[equipment_id], instance_id=instance_id)
                kept.append(piece.to_data())
        state["equipment_bag"] = kept
        return state


def _gear_counts(bag):
    """``{equipment id: pieces}`` of a serialised equipment bag."""
    counts = {}
    for piece in bag or ():
        counts[piece["equipment_id"]] = counts.get(piece["equipment_id"], 0) + 1
    return dict(sorted(counts.items()))


def _with_items(inventory, items):
    """The serialised inventory with its ``counts`` replaced (other keys are kept)."""
    result = copy.deepcopy(inventory) if isinstance(inventory, dict) else {}
    result.setdefault("schema", "asteria.rpg.inventory")
    result.setdefault("version", 1)
    result["counts"] = {str(k): int(v) for k, v in sorted(dict(items).items()) if int(v) > 0}
    return result
