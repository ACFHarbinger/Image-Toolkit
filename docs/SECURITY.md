# Security

Security posture and practices for Image-Toolkit.

## Scope

- Desktop application (Python backend + GUI)
- Browser extension and web integration surfaces
- Local database and model weights
- Optional LAN / remote control paths
- Submodules (ASP, CRE, CSG) and third-party vendors

## Principles

1. **Local-first:** Prefer processing on the user’s machine; do not send private image corpora to third-party APIs unless the user configures it.
2. **Explicit process invocation:** Prefer `subprocess` with argument lists over shell strings.
3. **Path boundaries:** User-selected workspace and dump directories should be validated; reject unexpected traversal when serving files.
4. **Secrets:** API keys and DB credentials live in env files (see `env/`); never commit live secrets.
5. **Dependencies:** Follow [DEPENDENCY_POLICY.md](DEPENDENCY_POLICY.md); audit high-risk ML and network packages.

## Reporting

Report security issues privately to the project maintainers (ACFHarbinger) rather than opening a public issue with exploit detail.

## Related

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
