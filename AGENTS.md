# Integration repository

This repository packages only the `bunker_codex` Home Assistant integration.
Preserve the integration domain, config-entry identity, entity IDs and UI setup.
Keep runtime credentials, host-specific configuration and private workspaces out
of this repository. Use synthetic fixtures in tests. Never import Git history from
an operational workspace. Run package validation, applicable tests and Gitleaks
against the entire history before pushing. Review staged files explicitly.

The companion bridge is an external service, documented in docs/bridge-protocol.md.
Do not imply that installing the HACS component provisions Codex or private tools.
