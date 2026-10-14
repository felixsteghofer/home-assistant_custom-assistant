"""Run against HA's installed framework: python tests/test_native_ha.py."""
import hashlib
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

try:
    from homeassistant.components import conversation
    from homeassistant.core import Context
    from custom_components.bunker_codex.conversation import BunkerCodexConversation
except ImportError:
    conversation = None


@unittest.skipIf(conversation is None, 'Run in the Home Assistant Core Python environment')
class NativeHAEntityTests(unittest.IsolatedAsyncioTestCase):
    def make_entity(self, admin=True, user_id='admin', allow_voice=False):
        backend = SimpleNamespace(converse=AsyncMock(return_value={'speech': 'Native answer',
            'status': 'completed', 'continue_conversation': True}))
        entry = SimpleNamespace(entry_id='entry', data={'name': 'Bunker Codex',
            'allow_voice_without_user': allow_voice}, options={}, runtime_data=backend)
        entity = BunkerCodexConversation(entry)
        entity.hass = SimpleNamespace(auth=SimpleNamespace(async_get_user=AsyncMock(return_value=
            SimpleNamespace(is_admin=admin, is_active=True))))
        user_input = conversation.ConversationInput(text='Question', context=Context(user_id=user_id),
            conversation_id='context', language='de', agent_id='conversation.bunker_codex', device_id=None, satellite_id=None)
        messages = []
        log = SimpleNamespace(conversation_id='context', async_add_assistant_content_without_tools=messages.append)
        return entity, backend, user_input, log, messages

    async def test_native_reply_preserves_ha_context_and_chat_log(self):
        entity, backend, user_input, log, messages = self.make_entity()
        result = await entity._async_handle_message(user_input, log)
        self.assertEqual(result.conversation_id, 'context')
        self.assertTrue(result.continue_conversation)
        self.assertEqual(result.response.speech['plain']['speech'], 'Native answer')
        self.assertEqual(messages[0].content, 'Native answer')
        backend.converse.assert_awaited_once_with(hashlib.sha256(b'entry:admin:context').hexdigest(), 'Question', 'de')

    async def test_non_admin_cannot_use_personal_bunker_agent(self):
        entity, backend, user_input, log, _ = self.make_entity(admin=False)
        result = await entity._async_handle_message(user_input, log)
        self.assertEqual(result.response.response_type.value, 'error')
        backend.converse.assert_not_awaited()

    async def test_anonymous_voice_requires_explicit_option(self):
        entity, backend, user_input, log, _ = self.make_entity(user_id=None)
        await entity._async_handle_message(user_input, log)
        backend.converse.assert_not_awaited()
        entity.entry.options['allow_voice_without_user'] = True
        await entity._async_handle_message(user_input, log)
        backend.converse.assert_awaited_once()

    async def test_each_user_has_a_separate_backend_context(self):
        entity, backend, user_input, log, _ = self.make_entity(user_id='other_admin')
        await entity._async_handle_message(user_input, log)
        key = backend.converse.await_args.args[0]
        self.assertNotEqual(key, hashlib.sha256(b'entry:admin:context').hexdigest())


if __name__ == '__main__':
    unittest.main()
