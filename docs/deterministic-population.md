# Deterministic Population

The fixture manifest is `fixtures/gitea_seed.json`.

Population flow:

1. Ensure the local Gitea administrator exists.
2. Reuse or regenerate a local API token without printing it.
3. Create or update organization `sandbox-labs`.
4. Create or update repository `adapter-demo`.
5. Create or update team `developers`.
6. Create or update deterministic files through the contents API.
7. Create or update labels, milestone, issue, and release.

Idempotency rules:

- second and later runs must not create duplicate fixture resources
- expected resources are updated when safe
- unrelated resources are not deleted
- final state is measured by API validation duplicate counts and file hashes

Expected file hashes from the verified run:

- `README.md`:
  `beefd4e6566b7f7c8768915be577cf34bb64820a5aa979c88f44eb7ecb979035`
- `docs/phase-2-notes.md`:
  `10b40f7052a182be8f60c4dc055d6cadda693b91834d4c98c1fa97d281977593`
