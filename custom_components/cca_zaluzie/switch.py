"""Pause automatic decisions without losing configured behavior."""
from homeassistant.components.switch import SwitchEntity

from .entity import CCAEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([CCASwitch(entry.runtime_data, "automation", "Automatika")])


class CCASwitch(CCAEntity, SwitchEntity):
    _attr_icon = "mdi:blinds-horizontal"

    @property
    def is_on(self):
        return self.controller.config["enabled"]

    async def async_turn_on(self, **kwargs):
        await self.controller.async_control("enable")

    async def async_turn_off(self, **kwargs):
        await self.controller.async_control("disable")
