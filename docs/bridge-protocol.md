# Compatible Codex bridge API

The integration connects to an existing HTTPS bridge. Both endpoints require
`Authorization: Bearer <runtime bridge token>`. Actual credentials are provided
through Home Assistant's configuration flow, never repository files.

## Health

`GET /api/health` returns an object containing:

```json
{"ready": true, "native_assist": 1}
```

Extra bridge fields are ignored. `native_assist: 1` declares this protocol version.

## Conversation

`POST /api/conversation` accepts:

```json
{
  "session_key": "64-character opaque SHA-256 value",
  "text": "A question or follow-up",
  "language": "de",
  "timeout": 90
}
```

The integration hashes its entry ID, HA user ID and HA conversation ID to derive
`session_key`. The bridge must persist a mapping to owned Codex threads, resume
those threads for follow-ups, and serialize requests for the same session.
Different session keys must not share conversational context.

The response is an object with a nonempty `speech` string and a `status` from:

- `completed`: final answer available.
- `needs_input`: clarification question available.
- `needs_approval`: continue in the bridge's approval UI.
- `running`: work continues beyond the native wait limit.
- `busy`: an existing request is still being handled.
- `failed`: the request failed.

Optional `continue_conversation` tells Assist whether to listen for a follow-up.
An optional `thread_id` can identify the corresponding conversation in the bridge
UI; the integration does not expose or depend on it.

The bridge must keep native requests associated with the correct Codex thread,
return final assistant text rather than reasoning/tool logs, and preserve Codex's
existing permission checks. Single user-input requests may be resumed with the
next native answer; command/file/permission approvals must not be accepted from
ordinary conversation text. The deployed bunker bridge implements this contract.

Home Assistant communicates with this bridge server-to-server. Browser microphone
permissions are handled by native Assist and the existing speech pipeline.
