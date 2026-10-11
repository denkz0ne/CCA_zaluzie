"""Explicit recover/calibrate controls belonging to each controller."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import CCAEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            CCAButton(entry.runtime_data, action, name)
            for action, name in [
                ("reset", "Reset polohy"),
                ("clear_override", "Ukončiť ručný režim"),
                ("reconcile", "Prepočítať a obnoviť cieľ"),
            ]
        ]
    )


class CCAButton(CCAEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller, action, name):
        super().__init__(controller, action, name)
        self.action = action

    async def async_press(self):
        await self.controller.async_control(self.action)
