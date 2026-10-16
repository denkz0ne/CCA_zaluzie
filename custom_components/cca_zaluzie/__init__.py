"""CCA Žalúzie: one independently managed vertical cover per entry."""

from __future__ import annotations

import logging

import probatio as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN, PLATFORMS
from .controller import CoverController

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {"controllers": {}})

    async def control(call: ServiceCall):
        controller = hass.data[DOMAIN]["controllers"].get(call.data["entry_id"])
        if controller is None:
            raise HomeAssistantError("Žalúzia nie je načítaná")
        try:
            await controller.async_control(
                call.data["action"], call.data.get("position"), context=call.context
            )
        except ValueError as error:
            raise HomeAssistantError(str(error)) from error

    async_register_admin_service(
        hass,
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
                        "simulation_on",
                        "simulation_off",
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
        from .const import EVENT_UPDATED

        hass.bus.async_fire(EVENT_UPDATED, {"entry_id": entry.entry_id})
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
        from .const import EVENT_UPDATED

        hass.bus.async_fire(EVENT_UPDATED, {"entry_id": entry.entry_id})
        # A temporary unload (options reload or unavailable entry) must keep the
        # sidebar and mounted panel so selection and unsaved drafts survive.
        return True
    return False


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    from homeassistant.helpers.storage import Store

    from .const import STORAGE_VERSION

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
    from .const import EVENT_UPDATED

    hass.bus.async_fire(EVENT_UPDATED, {"entry_id": entry.entry_id, "removed": True})
    if not any(
        candidate.entry_id != entry.entry_id
        for candidate in hass.config_entries.async_entries(DOMAIN)
    ):
        from homeassistant.components import frontend

        from .const import PANEL_PATH

        frontend.async_remove_panel(hass, PANEL_PATH)
        hass.data[DOMAIN]["panel_registered"] = False


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .config import ConfigError, validate_config

    if entry.version != 1 or entry.minor_version > 2:
        return False
    if entry.minor_version < 2:
        try:
            normalized = validate_config({**entry.data, **entry.options})
        except ConfigError:
            _LOGGER.exception("Cannot safely migrate CCA Žalúzie settings for %s", entry.entry_id)
            return False
        hass.config_entries.async_update_entry(
            entry,
            data=normalized,
            options={},
            version=1,
            minor_version=2,
        )
    return True
