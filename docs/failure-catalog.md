# Failure Catalog

Observed during Phase 2 execution:

- Sandboxed Docker access initially failed until Docker Desktop was reachable
  through the approved execution path.
- Plain `python` was not on PATH; the project virtual environment provided
  Python `3.12.13`.
- Pytest first attempted to use a user temp directory that was inaccessible
  from the local sandbox. A later GitHub-hosted clean runner exposed that
  configuring pytest under `.gitea-sandbox/pytest-tmp` assumed an ignored parent
  directory already existed. Pytest now uses its normal portable temporary
  directory behavior.
- The first Linux Docker integration run on GitHub passed start, population,
  API validation, and snapshot creation, then restore failed because
  Playwright's Chromium browser binary had not been installed on the runner.
- First stopped `diagnose` crashed because recursive redaction converted nested
  container dictionaries to strings; redaction now preserves nested mappings.
- Gitea returned `201` for issue `PATCH`; population now accepts the actual
  successful response.
- Playwright Chromium download exceeded the first 10-minute timeout; the longer
  retry completed.
- Browser login submit selector was wrong for Gitea 1.27; validation now clicks
  the rendered `Sign In` button by role/name.
- Gitea frontend did not reliably reach Playwright `networkidle`; validation now
  uses load and URL-based waits.
- Hidden mobile-only text caused brittle visible-text assertions; browser
  validation now uses page title for authenticated dashboard confirmation.
- Windows console encoding could not print Playwright Unicode diagnostics; CLI
  error output now escapes non-ASCII safely.

Controlled fault scenarios:

- PostgreSQL stopped
- Gitea stopped
- corrupt snapshot checksum
- missing `.env` in isolated temporary configuration
- occupied default port selection through unit-level port availability fakes
