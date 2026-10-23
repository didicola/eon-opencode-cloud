# Self-Maintenance Report (2026-10-23)

| Lane | Endpoint | Status |
|---|---|---|
| cloud-brain API | https://cloud-brain.eon-sovereign.workers.dev/v1/models | DOWN (301 redirect, no follow) |
| AGI engine | https://eon-agi.eon-sovereign.workers.dev/health | UP (200) |
| fleet nodes (admin.json) | ghost, ghost-dashboard, ghost-twin, ghost-2..4, alpha, tiny-matrix, tiny-1..5 | UP (13/13) |

- cloud-brain API returned 301 Moved Permanently; endpoint may need redirect follow or re-pointing.
- AGI engine healthy; fleet snapshot shows all workers healthy.

Recommended action: follow the cloud-brain 301 redirect and verify the target endpoint returns 200.
