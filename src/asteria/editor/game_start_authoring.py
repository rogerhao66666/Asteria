"""Game Start authoring: the New Game state of a project as a form (undoable).

The start definition lives in ``Project.game_start`` (design data, not a Player Save). This
controller exposes the common fields as a flat, Qt-free record: start scene, facing, position,
party, bag, currencies and owned pets. Anything the form does not show (progression, loadouts,
event variables...) is kept exactly as it is.
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
    F("scene_id", "Start Scene (empty: project startup scene)", "text", default=""),
    F("player_facing", "Player Facing", "choice", choices=FACINGS, default="down"),
    F("position_x", "Start X (empty: spawn point)", "optional_int", default=None),
    F("position_y", "Start Y (empty: spawn point)", "optional_int", default=None),
    F("party_actor_ids", "Party", "ref_list", source="actors", default=()),
    F("items", "Starting Items", "amounts", source="items", default={}),
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
        stores = {"items": db.items, "actors": db.actors, "pet_species": db.pet_species}
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


def _with_items(inventory, items):
    """The serialised inventory with its ``counts`` replaced (other keys are kept)."""
    result = copy.deepcopy(inventory) if isinstance(inventory, dict) else {}
    result.setdefault("schema", "asteria.rpg.inventory")
    result.setdefault("version", 1)
    result["counts"] = {str(k): int(v) for k, v in sorted(dict(items).items()) if int(v) > 0}
    return result
