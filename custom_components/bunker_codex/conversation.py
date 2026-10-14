"""Native conversation entity with user-isolated Codex contexts."""
import hashlib
import json
import logging
from dataclasses import replace
from time import monotonic

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .client import BridgeError
from .const import DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)
_LOCAL_AGENT = "conversation.home_assistant"


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    async_add_entities([BunkerCodexConversation(entry)])


class BunkerCodexConversation(conversation.ConversationEntity):
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL
    _attr_icon = 'mdi:robot-outline'

    def __init__(self, entry):
        self.entry = entry
        self._attr_name = entry.options.get('name', entry.data.get('name', DEFAULT_NAME))
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self):
        return '*'

    async def _async_handle_message(self, user_input, chat_log):
        settings = {**self.entry.data, **self.entry.options}
        user_id = user_input.context.user_id
        user = await self.hass.auth.async_get_user(user_id) if user_id else None
        if (user_id and (not user or not user.is_active or not user.is_admin)) or (
                not user_id and not settings.get('allow_voice_without_user', False)):
            response = intent.IntentResponse(language=user_input.language)
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN,
                'Bunker Codex ist für Administratoren eingerichtet. Sprachgeräte ohne Benutzerzuordnung können in den Integrationsoptionen freigegeben werden.')
            return conversation.ConversationResult(response=response, conversation_id=chat_log.conversation_id)
        session_key = hashlib.sha256((self.entry.entry_id + ':' + (user_id or 'voice') + ':' + chat_log.conversation_id).encode()).hexdigest()
        # Keep Codex follow-ups with Codex, including clarification/approval replies.
        history = getattr(chat_log, 'content', [])
        codex_started = any(getattr(item, 'role', None) == 'assistant' and
            getattr(item, 'agent_id', None) == user_input.agent_id for item in history)
        if settings.get('prefer_local_intents', True) and not codex_started:
            started = monotonic()
            local_input = replace(user_input, agent_id=_LOCAL_AGENT)
            speech = await conversation.async_handle_sentence_triggers(self.hass, local_input, chat_log)
            if speech is not None:
                local_response = intent.IntentResponse(language=user_input.language)
                local_response.async_set_speech(speech)
            else:
                # HA's strict local-intent API falls through on recognition/target
                # mismatches, but returns handling errors without retrying actions.
                local_response = await conversation.async_handle_intents(self.hass, local_input, chat_log)
            _LOGGER.debug('Local Assist completed in %.3fs', monotonic() - started)
            if local_response is not None:
                speech = local_response.speech.get('plain', {}).get('speech', '')
                chat_log.async_add_assistant_content_without_tools(conversation.AssistantContent(
                    agent_id=_LOCAL_AGENT, content=speech))
                return conversation.ConversationResult(response=local_response,
                    conversation_id=chat_log.conversation_id,
                    continue_conversation=chat_log.continue_conversation)
        text = user_input.text
        if not codex_started and any(getattr(item, 'agent_id', None) == _LOCAL_AGENT for item in history):
            # Codex has not seen earlier locally answered exchanges. Include their
            # context once so "why?" and other follow-ups can refer to them.
            previous = [{'role': item.role, 'content': item.content} for item in history[:-1]
                if getattr(item, 'role', None) in ('user', 'assistant') and getattr(item, 'content', None)]
            text = 'Previous Assist conversation (context only):\n' + json.dumps(previous[-6:], ensure_ascii=False)[-6000:] + '\nCurrent request:\n' + text
        started = monotonic()
        try:
            result = await self.entry.runtime_data.converse(session_key, text, user_input.language)
            _LOGGER.debug('Codex bridge completed in %.3fs', monotonic() - started)
        except BridgeError:
            response = intent.IntentResponse(language=user_input.language)
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN,
                'Bunker Codex ist gerade nicht erreichbar. Bitte prüfe den Dienst auf bunker.')
            return conversation.ConversationResult(response=response, conversation_id=chat_log.conversation_id)
        speech = result['speech']
        chat_log.async_add_assistant_content_without_tools(conversation.AssistantContent(
            agent_id=user_input.agent_id, content=speech))
        response = intent.IntentResponse(language=user_input.language)
        if result['status'] == 'failed':
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, speech)
        else:
            response.async_set_speech(speech)
        return conversation.ConversationResult(response=response,
            conversation_id=chat_log.conversation_id,
            continue_conversation=bool(result.get('continue_conversation')))
