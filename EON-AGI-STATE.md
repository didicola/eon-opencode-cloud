# EON Cloud AGI State

Updated: 2026-10-20T21:34:28Z
Worker: agi-cloud-v10, persistent=True, store=do-storage, cron=do-alarm+gh-actions.
Cycles: 5856. Passed: 5587. Failed: 269. Score: 95.4%.
Self-mods: 233. Lessons: 50. Provisions: 32. Goals: 20.
Best prompt: direct. LLM accuracy: 82%.

Domains: math=83%(n=108) string=79%(n=175) compare=77%(n=272) logic=83%(n=123) spatial=99%(n=81) temporal=86%(n=72) causal=99%(n=71) creative=91%(n=80).
Last run: 2026-10-20T21:31:23.280Z.
Transfer probe: spatial -> revlex delta 0 (applied=True).

Architecture map: https://github.com/didicola/eon-opencode-cloud/blob/main/ARCHITECTURE.md
Known gaps: termux2 offline; ubuntu SSH/ports firewalled, 443 mTLS half-up; Vercel uses read-only Neon role wk_vercel.
No secrets in this card.