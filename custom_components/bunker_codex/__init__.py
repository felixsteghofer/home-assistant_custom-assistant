"""Bunker Codex: use the existing signed-in Codex service as native HA Assist."""
import ssl

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import BunkerClient, BridgeAuthError, BridgeError, tls_context
from .const import PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    settings = {**entry.data, **entry.options}
    try:
        context = await hass.async_add_executor_job(tls_context, settings.get('ca_certificate', ''))
        client = BunkerClient(async_get_clientsession(hass), settings['backend_url'],
            settings['access_token'], context, settings.get('timeout', 90))
        await client.health()
    except BridgeAuthError as error:
        raise ConfigEntryAuthFailed(str(error)) from error
    except (BridgeError, ValueError, ssl.SSLError) as error:
        raise ConfigEntryNotReady('Bunker Codex ist nicht erreichbar oder die TLS-Konfiguration ist ungültig.') from error
    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
