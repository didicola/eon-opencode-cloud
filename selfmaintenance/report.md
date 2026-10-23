# Self-Maintenance Report (2026-10-23)

| Lane | Endpoint | Status |
|---|---|---|
| cloud-brain API | https://cloud-brain.eon-sovereign.workers.dev/v1/models | 503 DOWN |
| AGI engine | https://eon-agi.eon-sovereign.workers.dev/health | 200 OK |
| fleet nodes (admin.json) | ghost, ghost-dashboard, ghost-twin, ghost-2..4, alpha, tiny-matrix, tiny-1..5 | 13/13 OK |

**DOWN:** cloud-brain API (503).
**Recommended action:** restart/redeploy the cloud-brain worker and re-check its health endpoint.
