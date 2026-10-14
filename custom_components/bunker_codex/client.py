"""Authenticated, TLS-verified transport to the existing bunker chat bridge."""
import asyncio
import ssl
from urllib.parse import urlsplit

import aiohttp


class BridgeError(Exception):
    """Sanitized bridge error, safe for UI/logs."""


class BridgeAuthError(BridgeError):
    """The backend capability is invalid."""


def normalize_url(value):
    value = value.strip().rstrip('/')
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path):
        raise ValueError('Use an HTTPS backend origin without credentials or a path')
    _ = url.port
    return value


def tls_context(certificate):
    """An optional custom CA never disables hostname/certificate validation."""
    return ssl.create_default_context(cadata=certificate.strip() or None)


class BunkerClient:
    def __init__(self, session, url, token, context, timeout=90):
        self.session = session
        self.url = normalize_url(url)
        self.headers = {'Authorization': 'Bearer ' + token.strip()}
        self.context = context
        self.timeout = timeout

    async def request(self, path, body=None, timeout=10):
        try:
            async with self.session.request('GET' if body is None else 'POST', self.url + path,
                    headers=self.headers, json=body, ssl=self.context,
                    timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=False) as response:
                if response.status == 401:
                    raise BridgeAuthError('Bunker-Zugangstoken wurde abgelehnt.')
                if response.status != 200:
                    raise BridgeError('Der Bunker-Dienst konnte die Anfrage nicht bearbeiten.')
                data = await response.json()
                if not isinstance(data, dict):
                    raise BridgeError('Der Bunker-Dienst lieferte eine ungültige Antwort.')
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
            raise BridgeError('Keine sichere Verbindung zum Bunker-Dienst möglich.') from error

    async def health(self):
        result = await self.request('/api/health')
        if not result.get('ready') or result.get('native_assist') != 1:
            raise BridgeError('Der Bunker-Dienst ist nicht bereit oder unterstützt natives Assist noch nicht.')
        return result

    async def converse(self, session_key, text, language):
        result = await self.request('/api/conversation', {'session_key': session_key, 'text': text,
            'language': language, 'timeout': self.timeout}, timeout=self.timeout + 20)
        if not isinstance(result.get('speech'), str) or result.get('status') not in (
                'completed', 'needs_input', 'needs_approval', 'running', 'busy', 'failed'):
            raise BridgeError('Der Bunker-Dienst lieferte keine gültige Assist-Antwort.')
        return result
