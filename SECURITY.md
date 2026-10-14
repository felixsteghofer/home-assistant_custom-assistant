# Security and private configuration

This repository contains integration source, tests and public documentation only.
Configure runtime credentials through Home Assistant's UI. Never commit tokens,
Codex authentication files, SSH keys, certificates, `.env` files, Home Assistant
storage/configuration exports, database connection strings, logs or sensor exports.

The integration requires verified HTTPS, redacts connection settings in diagnostics,
and isolates backend conversation keys by HA user and conversation. Access to the
personal Codex agent is restricted to administrators by default. Anonymous voice
access is a deliberate opt-in setting; identified non-admin users remain blocked.

Before pushing, run Gitleaks against both the directory and all Git history. The
ignore rules are a convenience, not a substitute for reviewing staged files.
GitHub Actions also scan the checked-out history. Test credentials must be clearly
synthetic fixtures, never copies of live configuration.

If a credential is accidentally published, rotate/revoke it immediately; deleting
it from the latest file does not remove it from Git history. Do not submit real
credentials or private logs in issues. Use GitHub's private vulnerability reporting
if available for sensitive reports.
