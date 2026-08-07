# Security Policy

## Supported versions

This project is pre-1.0 (see [Versioning and releases](CONTRIBUTING.md#versioning-and-releases) in CONTRIBUTING.md). Only the latest published release receives security fixes; there is no support for older `0.x` versions.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a suspected security vulnerability.

Instead, use [GitHub's private vulnerability reporting](https://github.com/Charlesreilly0/agentevents/security/advisories/new) for this repository (Security tab → Report a vulnerability). This opens a private advisory visible only to the maintainer until a fix is ready.

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce, or a minimal proof-of-concept.
- The affected version(s), if known.

This is a single-maintainer project without a dedicated security team or a fixed SLA. Reports will be acknowledged as soon as reasonably possible, and a fix released as a new patch or minor version once confirmed. Credit will be given in the release notes / `CHANGELOG.md` unless you'd prefer otherwise.

## Scope

Reports about the `agentevents` package's own code (`src/agentevents/`) are in scope. Vulnerabilities in dependencies (`pydantic`, `redis`, etc.) should be reported directly to those projects; if a dependency vulnerability affects `agentevents` specifically (e.g. through how it's used here), a report here is still welcome.
