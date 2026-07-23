# Threat Model

Primary risks:

- accidental secret exposure in logs, diagnostics, evidence, or Git
- accidental deletion of unrelated Docker resources
- false success reporting for partial or unhealthy runtime states
- corrupt or malicious snapshot archives
- stale API tokens after restore or reset

Controls:

- `.env`, runtime tokens, snapshots, runtime browser evidence, and temporary
  artifacts are ignored
- redaction covers likely passwords, tokens, Authorization headers, credential
  URLs, and secret-like environment names
- command execution uses argument lists and finite timeouts
- `restore` and `reset` require `--force`
- destructive workflows verify Compose ownership labels
- snapshot restore validates schema, checksums, archive paths, and link members
- diagnostics are read-only

Non-goals:

- production hardening of Gitea
- multi-user secret management
- remote deployment
- GitHub repository administration
