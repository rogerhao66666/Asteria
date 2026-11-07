"""Opening the equipment screen and the enhance screen (U3; they replace the old workshop)."""

from __future__ import annotations

from asteria.runtime.menus.enhance import EnhanceScreen
from asteria.runtime.menus.equipment import EquipmentScreen


class WorkshopMixin:
    # --- U3: the paper-doll equipment screen and the enhance screen ----------------------

    def open_equipment_screen(self, back="field"):
        self._gear_screen = EquipmentScreen(self, back=back)
        self._ui_mode = "equipment"

    def open_enhance_screen(self, back="field"):
        self._gear_screen = EnhanceScreen(self, back=back)
        self._ui_mode = "enhance"
