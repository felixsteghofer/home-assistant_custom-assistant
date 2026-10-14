"""Run against HA's installed framework: python tests/test_native_ha.py."""
import hashlib
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

try:
    from homeassistant.components import conversation
    from homeassistant.core import Context
    from homeassistant.helpers import intent
    from custom_components.bunker_codex.conversation import BunkerCodexConversation
except ImportError:
    conversation = None


@unittest.skipIf(conversation is None, 'Run in the Home Assistant Core Python environment')
class NativeHAEntityTests(unittest.IsolatedAsyncioTestCase):
    def make_entity(self, admin=True, user_id='admin', allow_voice=False):
        backend = SimpleNamespace(converse=AsyncMock(return_value={'speech': 'Native answer',
            'status': 'completed', 'continue_conversation': True}))
        entry = SimpleNamespace(entry_id='entry', data={'name': 'Bunker Codex',
            'allow_voice_without_user': allow_voice, 'prefer_local_intents': False}, options={}, runtime_data=backend)
        entity = BunkerCodexConversation(entry)
        entity.hass = SimpleNamespace(auth=SimpleNamespace(async_get_user=AsyncMock(return_value=
            SimpleNamespace(is_admin=admin, is_active=True))))
        user_input = conversation.ConversationInput(text='Question', context=Context(user_id=user_id),
            conversation_id='context', language='de', agent_id='conversation.bunker_codex', device_id=None, satellite_id=None)
        messages = []
        log = SimpleNamespace(conversation_id='context', content=messages, continue_conversation=False, async_add_assistant_content_without_tools=messages.append)
        trigger = patch('custom_components.bunker_codex.conversation.conversation.async_handle_sentence_triggers', new=AsyncMock(return_value=None))
        trigger.start()
        self.addCleanup(trigger.stop)
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


    def local_result(self, error=None):
        response = intent.IntentResponse(language='de')
        if error:
            response.async_set_error(error, 'Local error')
        else:
            response.async_set_speech('Local answer')
        return response

    async def test_local_answer_avoids_bridge_and_preserves_input_context(self):
        entity, backend, user_input, log, messages = self.make_entity()
        entity.entry.options['prefer_local_intents'] = True
        with patch('custom_components.bunker_codex.conversation.conversation.async_handle_intents',
                new=AsyncMock(return_value=self.local_result())) as local:
            result = await entity._async_handle_message(user_input, log)
        backend.converse.assert_not_awaited()
        self.assertEqual(result.conversation_id, 'context')
        self.assertEqual(result.response.speech['plain']['speech'], 'Local answer')
        self.assertEqual(messages[-1].agent_id, 'conversation.home_assistant')
        self.assertIs(local.await_args.args[1].context, user_input.context)
        self.assertEqual(local.await_args.args[1].language, 'de')
        self.assertEqual(local.await_args.args[1].device_id, user_input.device_id)
        self.assertEqual(local.await_args.args[1].satellite_id, user_input.satellite_id)

    async def test_unmatched_strict_intent_falls_back_and_codex_followups_stay(self):
        entity, backend, user_input, log, messages = self.make_entity()
        entity.entry.options['prefer_local_intents'] = True
        with patch('custom_components.bunker_codex.conversation.conversation.async_handle_intents',
                new=AsyncMock(return_value=None)) as local:
            await entity._async_handle_message(user_input, log)
            await entity._async_handle_message(user_input, log)
        self.assertEqual(backend.converse.await_count, 2)
        local.assert_awaited_once()
        self.assertEqual(len(messages), 2)

    async def test_local_handling_errors_never_repeat_through_codex(self):
        for error in (intent.IntentResponseErrorCode.FAILED_TO_HANDLE, intent.IntentResponseErrorCode.UNKNOWN):
            with self.subTest(error=error):
                entity, backend, user_input, log, _ = self.make_entity()
                entity.entry.options['prefer_local_intents'] = True
                with patch('custom_components.bunker_codex.conversation.conversation.async_handle_intents',
                        new=AsyncMock(return_value=self.local_result(error))):
                    result = await entity._async_handle_message(user_input, log)
                self.assertEqual(result.response.error_code, error)
                backend.converse.assert_not_awaited()

    async def test_authentication_precedes_local_commands(self):
        entity, backend, user_input, log, _ = self.make_entity(admin=False)
        entity.entry.options['prefer_local_intents'] = True
        with patch('custom_components.bunker_codex.conversation.conversation.async_handle_intents', new=AsyncMock()) as local:
            await entity._async_handle_message(user_input, log)
        local.assert_not_awaited()
        backend.converse.assert_not_awaited()

    async def test_sentence_trigger_avoids_intent_and_codex_even_with_empty_reply(self):
        entity, backend, user_input, log, _ = self.make_entity()
        entity.entry.options['prefer_local_intents'] = True
        with patch('custom_components.bunker_codex.conversation.conversation.async_handle_sentence_triggers',
                new=AsyncMock(return_value='')) as trigger, patch(
                'custom_components.bunker_codex.conversation.conversation.async_handle_intents', new=AsyncMock()) as local:
            await entity._async_handle_message(user_input, log)
        trigger.assert_awaited_once()
        local.assert_not_awaited()
        backend.converse.assert_not_awaited()

    async def test_handoff_includes_locally_answered_context_once(self):
        entity, backend, user_input, log, messages = self.make_entity()
        entity.entry.options['prefer_local_intents'] = True
        messages.extend([SimpleNamespace(role='user', content='Which lights?'),
            conversation.AssistantContent(agent_id='conversation.home_assistant', content='Kitchen light'),
            SimpleNamespace(role='user', content='Why?')])
        with patch('custom_components.bunker_codex.conversation.conversation.async_handle_intents',
                new=AsyncMock(return_value=None)):
            await entity._async_handle_message(user_input, log)
        text = backend.converse.await_args.args[1]
        self.assertIn('Kitchen light', text)
        self.assertIn('Which lights?', text)
        await entity._async_handle_message(user_input, log)
        self.assertEqual(backend.converse.await_args.args[1], 'Question')


if __name__ == '__main__':
    unittest.main()
