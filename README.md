# Bunker Codex — native Home Assistant assistant

Use an existing, signed-in Codex service as a native Home Assistant **Assist**
conversation agent. Supports follow-up conversations, your configured HA speech
services, and the tools/skills available in the Codex workspace.

This HACS package installs the Home Assistant integration. It connects to an
**existing compatible HTTPS bridge** on the Codex host; it does not install Codex,
copy its login, or provision MCP/database credentials. A raw `codex app-server`
endpoint is not the bridge API required by this integration.

## Install using HACS

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/felixsteghofer/home-assistant_custom-assistant` with type
   **Integration**.
3. Download **Bunker Codex**, then restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Bunker Codex**.
5. Enter your existing bridge's HTTPS address, access token and CA certificate
   (PEM, if it uses a private/self-signed certificate).
6. Under **Settings → Voice assistants**, create/select an assistant using
   **Bunker Codex** as its conversation agent. Select your existing STT/TTS engines.
7. Open **Assist** and select that assistant.

Requires **Home Assistant 2026.10.1 or later**. Tested against Core 2026.10.1.

### Existing manual installation

The integration domain remains `bunker_codex`, so installing through HACS over the
existing component preserves its integration entry, entity IDs and saved settings.
Do not remove the integration entry or recreate its conversation entity. Restart
Home Assistant after HACS replaces the files. HACS updates the HA component only;
the existing bridge and private workspace remain managed separately.

## Configure

Use **Settings → Devices & services → Bunker Codex → Configure** to edit:

- Assistant name and bridge HTTPS address.
- Bridge access token and TLS CA certificate.
- Response timeout: 5–120 seconds (default 90).
- Whether voice devices without an HA user identity may use this personal agent.

HTTPS and certificate/hostname validation are always required. Use a host name or
IP included in your certificate. Leave the CA field empty for a normally trusted
certificate. This integration needs the **bridge token**, not an OpenAI API key.
The existing Codex service can use its ChatGPT login and account usage limits.

Administrator users are allowed by default. Identified non-admin users are
rejected. Enabling the voice-device option deliberately grants satellites without
a user identity access to the same personal agent and its existing tools.

Follow-ups reuse a user-isolated Codex context. Single clarification questions can
be answered through Assist. Permission approvals are handled in the existing
Hausassistent panel, never automatically accepted from a spoken “yes”. Long-running
work can continue on the bridge after Assist's wait limit; inspect its panel for
progress, approvals and results.

## Bridge requirements

Your existing bridge must support authenticated `/api/health` and
`/api/conversation` endpoints. See [the bridge protocol](docs/bridge-protocol.md).
Configure Codex login, MCP, workspace skills and any database/SSH access on that
host, outside this repository.

## Development and security

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/validate_package.py
```

Entity tests run in a Home Assistant Python environment; they skip when HA is not
installed. Run a full-history secret scan before publishing:

```sh
gitleaks dir . --redact
gitleaks git . --log-opts="--all" --redact
```

Credentials belong in HA's UI configuration or private runtime files. Do not add
`.env`, tokens, connection files, certificates, database passwords, Codex login
files, SSH keys, or recorder exports to Git. See [SECURITY.md](SECURITY.md).

Licensed under [MIT](LICENSE).
