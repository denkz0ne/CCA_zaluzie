"""Stable identities and one device grouping per cover controller."""
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class CCAEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, controller, key: str, name: str):
        self.controller = controller
        self._attr_unique_id = f"{controller.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, controller.entry.entry_id)}, name=controller.config["name"], manufacturer="CCA Žalúzie", model="Automatizácia žalúzie")

    @property
    def available(self):
        return self.controller.observe()[0]

    async def async_added_to_hass(self):
        self.async_on_remove(self.controller.subscribe(self.async_write_ha_state))
