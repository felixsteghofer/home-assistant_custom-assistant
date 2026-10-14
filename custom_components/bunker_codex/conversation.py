"""Native conversation entity with user-isolated Codex contexts."""
import hashlib

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .client import BridgeError
from .const import DEFAULT_NAME


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
        try:
            result = await self.entry.runtime_data.converse(session_key, user_input.text, user_input.language)
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
