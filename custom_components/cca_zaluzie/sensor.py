"""Concise state sensors; full traces live in the panel and diagnostics."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory

from .entity import CCAEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            CCASensor(entry.runtime_data, key, name)
            for key, name in [
                ("status", "Stav"),
                ("target", "Cieľová poloha"),
                ("next", "Najbližšia udalosť"),
                ("reason", "Dôvod rozhodnutia"),
            ]
        ]
    )


class CCASensor(CCAEntity, SensorEntity):
    def __init__(self, controller, key, name):
        super().__init__(controller, key, name)
        self.key = key
        self._attr_icon = "mdi:blinds-horizontal"
        if key == "target":
            self._attr_native_unit_of_measurement = "%"
        if key in ("next", "reason"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        decision = self.controller.decision
        if self.key == "target":
            return decision.target
        if self.key == "next":
            from homeassistant.util import dt as dt_util

            return (
                dt_util.utc_from_timestamp(decision.next_at).isoformat()
                if decision.next_at
                else None
            )
        if self.key == "reason":
            return decision.reason[:255]
        return decision.inhibit or decision.pending or decision.mode

    @property
    def extra_state_attributes(self):
        if self.key == "status":
            rt = self.controller.runtime
            return {
                "mode": self.controller.decision.mode,
                "inhibit": self.controller.decision.inhibit,
                "manual_override": rt.manual_since is not None,
                "shading": rt.shading,
                "reset": rt.reset,
                "fault": rt.fault,
                "cover_entity": self.controller.config["cover_entity"],
            }
        return None
