"""UI setup and options for Bunker Codex; no YAML or OpenAI key required."""
import ssl

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (BooleanSelector, NumberSelector,
    NumberSelectorConfig, NumberSelectorMode, TextSelector, TextSelectorConfig, TextSelectorType)

from .client import BunkerClient, BridgeAuthError, BridgeError, normalize_url, tls_context
from .const import DEFAULT_NAME, DEFAULT_TIMEOUT, DEFAULT_URL, DOMAIN


def schema(values):
    return vol.Schema({
        vol.Required('name', default=values.get('name', DEFAULT_NAME)): str,
        vol.Required('backend_url', default=values.get('backend_url', DEFAULT_URL)): str,
        vol.Required('access_token', default=values.get('access_token', '')):
            TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        vol.Optional('ca_certificate', default=values.get('ca_certificate', '')):
            TextSelector(TextSelectorConfig(multiline=True)),
        vol.Required('timeout', default=values.get('timeout', DEFAULT_TIMEOUT)):
            NumberSelector(NumberSelectorConfig(min=5, max=120, step=1, mode=NumberSelectorMode.BOX)),
        vol.Required('allow_voice_without_user', default=values.get('allow_voice_without_user', False)): BooleanSelector(),
    })


async def validate(hass, data):
    try:
        data['backend_url'] = normalize_url(data['backend_url'])
        if not data['access_token'].strip() or not data['name'].strip():
            return {'base': 'invalid_settings'}
        context = await hass.async_add_executor_job(tls_context, data.get('ca_certificate', ''))
        client = BunkerClient(async_get_clientsession(hass), data['backend_url'], data['access_token'], context)
        await client.health()
    except BridgeAuthError:
        return {'base': 'invalid_auth'}
    except (ValueError, ssl.SSLError):
        return {'base': 'invalid_settings'}
    except BridgeError:
        return {'base': 'cannot_connect'}
    return {}


class BunkerCodexConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = await validate(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input['name'], data=user_input)
        return self.async_show_form(step_id='user', data_schema=schema(user_input or {}), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        values = {**entry.data, **entry.options}
        errors = {}
        if user_input is not None:
            values.update(user_input)
            errors = await validate(self.hass, values)
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=values, options={})
        return self.async_show_form(step_id='reauth_confirm', data_schema=schema(values), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BunkerCodexOptionsFlow()


class BunkerCodexOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        values = {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            errors = await validate(self.hass, user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(self.config_entry, title=user_input['name'])
                return self.async_create_entry(title='', data=user_input)
            values.update(user_input)
        return self.async_show_form(step_id='init', data_schema=schema(values), errors=errors)
