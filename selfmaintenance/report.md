# Self-Maintenance Report (2026-10-25)

| Lane | Status |
|---|---|
| cloud-brain API (cloud-brain.eon-sovereign.workers.dev) | UP — v2.1-tools |
| AGI engine (eon-agi.eon-sovereign.workers.dev/health) | UP — eon-200-for-all |
| recommended.workers.dev/v1/models | DOWN — DNS resolution failed |
| Fleet nodes (out/admin.json) | 13 nodes, all OK |

**DOWN items:** recommended.workers.dev/v1/models (curl error 6 / DNS failure).

**Recommended action:** Investigate DNS/zone configuration for recommended.workers.dev and re-check the models endpoint.
