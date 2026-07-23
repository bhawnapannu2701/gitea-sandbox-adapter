# Snapshot Format

A snapshot is a directory under ignored `snapshots/`.

Required files:

- `manifest.json`
- `postgres.dump`
- `gitea-data.tar.gz`
- `gitea-config.tar.gz`

`postgres.dump` is produced by `pg_dump` inside the actual PostgreSQL container
with custom format and no ownership or privilege restoration.

The Gitea archives are produced from the project Gitea container volumes:

- `/var/lib/gitea`
- `/etc/gitea`

The manifest includes:

- schema version
- UTC creation timestamp
- package name
- Compose project identity
- pinned image references
- safe database metadata
- fixture manifest hash
- SHA-256 checksum and byte size for each payload

Restore rejects missing payloads, checksum mismatches, path traversal, symlinks,
hardlinks, corrupt archives, and incompatible Compose project identity.
