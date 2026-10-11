"""CCA Žalúzie: one independently managed vertical cover per entry."""

from __future__ import annotations

import probatio as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, PLATFORMS
from .controller import CoverController


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {"controllers": {}})

    async def control(call: ServiceCall):
        controller = hass.data[DOMAIN]["controllers"].get(call.data["entry_id"])
        if controller is None:
            raise HomeAssistantError("Žalúzia nie je načítaná")
        try:
            await controller.async_control(call.data["action"], call.data.get("position"))
        except ValueError as error:
            raise HomeAssistantError(str(error)) from error

    hass.services.async_register(
        DOMAIN,
        "control",
        control,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Required("action"): vol.In(
                    [
                        "open",
                        "close",
                        "stop",
                        "shade",
                        "ventilate",
                        "position",
                        "enable",
                        "disable",
                        "clear_override",
                        "reconcile",
                        "reset",
                        "cancel_reset",
                    ]
                ),
                vol.Optional("position"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .api import async_setup_panel

    await async_setup_panel(hass)
    controller = CoverController(hass, entry)
    entry.runtime_data = controller
    hass.data[DOMAIN]["controllers"][entry.entry_id] = controller
    try:
        await controller.async_start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await controller.async_stop()
        hass.data[DOMAIN]["controllers"].pop(entry.entry_id, None)
        raise
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    controller = entry.runtime_data
    await controller.async_stop()
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN]["controllers"].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]["controllers"]:
            from homeassistant.components import frontend

            from .const import PANEL_PATH

            frontend.async_remove_panel(hass, PANEL_PATH)
            hass.data[DOMAIN]["panel_registered"] = False
        return True
    return False


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    from homeassistant.helpers.storage import Store

    from .const import STORAGE_VERSION

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version > 1:
        return False
    hass.config_entries.async_update_entry(entry, version=1, minor_version=1)
    return True
