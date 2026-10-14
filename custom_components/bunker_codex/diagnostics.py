"""Diagnostics contain no tokens, certificate material, threads or messages."""
async def async_get_config_entry_diagnostics(hass, entry):
    settings = {**entry.data, **entry.options}
    return {'name': settings.get('name'), 'backend_url': '**REDACTED**',
        'access_token': '**REDACTED**', 'ca_certificate': '**REDACTED**',
        'timeout': settings.get('timeout', 90),
        'allow_voice_without_user': settings.get('allow_voice_without_user', False)}
