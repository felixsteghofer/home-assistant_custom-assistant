import asyncio
import importlib.util
from pathlib import Path
import ssl
import unittest
from unittest.mock import AsyncMock

import aiohttp

path = Path(__file__).resolve().parents[1] / 'custom_components/bunker_codex/client.py'
spec = importlib.util.spec_from_file_location('bunker_client', path)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class ConfigurationTests(unittest.TestCase):
    def test_only_credential_free_https_origins_are_accepted(self):
        for url in ('http://host', 'https://fixture:fixture@host', 'https://host/private',
                    'https://host?secret=fixture', 'https://host#fragment'):
            with self.assertRaises(ValueError):
                client.normalize_url(url)
        self.assertEqual(client.normalize_url('https://codex.example:8844/'), 'https://codex.example:8844')

    def test_tls_always_validates_hostname_and_certificate(self):
        context = client.tls_context('')
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)


class Response:
    def __init__(self, status, data):
        self.status, self.data = status, data
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def json(self):
        return self.data


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def make(self, status=200, data=None):
        class Session:
            def request(self, *args, **kwargs):
                self.kwargs = kwargs
                return Response(status, data)
        session = Session()
        bridge = client.BunkerClient(session, 'https://codex.example', 'synthetic-test-fixture', client.tls_context(''))
        return bridge, session

    async def test_health_requires_native_protocol_and_ready_service(self):
        for data in ({'ready': False, 'native_assist': 1}, {'ready': True}):
            bridge, _ = self.make(data=data)
            with self.assertRaises(client.BridgeError):
                await bridge.health()
        bridge, session = self.make(data={'ready': True, 'native_assist': 1})
        await bridge.health()
        self.assertFalse(session.kwargs['allow_redirects'])
        self.assertTrue(session.kwargs['ssl'].check_hostname)

    async def test_auth_failure_is_distinct_and_sanitized(self):
        bridge, _ = self.make(status=401, data={'error': 'should not be exposed'})
        with self.assertRaises(client.BridgeAuthError) as result:
            await bridge.health()
        self.assertNotIn('synthetic-test-fixture', str(result.exception))
        self.assertNotIn('should not be exposed', str(result.exception))

    async def test_native_response_schema_rejects_invalid_speech_and_status(self):
        for data in ({'speech': 'answer', 'status': 'unexpected'}, {'speech': 42, 'status': 'completed'}):
            bridge, _ = self.make(data=data)
            with self.assertRaises(client.BridgeError):
                await bridge.converse('fixture-session', 'Question', 'de')
        bridge, session = self.make(data={'speech': 'Native answer', 'status': 'completed'})
        result = await bridge.converse('fixture-session', 'Question', 'de')
        self.assertEqual(result['speech'], 'Native answer')
        self.assertEqual(session.kwargs['json']['timeout'], 90)

    async def test_connection_exception_does_not_expose_private_urls(self):
        class Session:
            def request(self, *args, **kwargs):
                raise aiohttp.ClientError('https://private.example/?credential=fixture')
        bridge = client.BunkerClient(Session(), 'https://codex.example', 'synthetic-test-fixture', client.tls_context(''))
        with self.assertRaises(client.BridgeError) as result:
            await bridge.health()
        self.assertNotIn('private.example', str(result.exception))


if __name__ == '__main__':
    unittest.main()
