# EON Cloud AGI State

Updated: 2026-10-21T04:40:21Z
Worker: agi-cloud-v10, persistent=True, store=do-storage, cron=do-alarm+gh-actions.
Cycles: 6061. Passed: 5778. Failed: 283. Score: 95.3%.
Self-mods: 241. Lessons: 50. Provisions: 32. Goals: 20.
Best prompt: direct. LLM accuracy: 82%.

Domains: math=82%(n=112) string=79%(n=179) compare=77%(n=274) logic=82%(n=126) spatial=99%(n=84) temporal=86%(n=74) causal=99%(n=75) creative=92%(n=84).
Last run: 2026-10-21T04:36:38.008Z.
Transfer probe: spatial -> revlex delta 0 (applied=False).

Architecture map: https://github.com/didicola/eon-opencode-cloud/blob/main/ARCHITECTURE.md
Known gaps: termux2 offline; ubuntu SSH/ports firewalled, 443 mTLS half-up; Vercel uses read-only Neon role wk_vercel.
No secrets in this card.