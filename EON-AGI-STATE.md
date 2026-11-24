# EON Cloud AGI State

Updated: 2026-11-24T09:48:08Z
Worker: agi-cloud-v10 (v10); store=do-storage.
Cycles: 29296. Passed: 28275. Failed: 1021. Score: 96.5%.
Self-mods: 1170. Lessons: 50. Provisions: 32. Goals: 20.
Best prompt: direct. LLM accuracy: 76.8%.

Domains: math 1319/1381 (95.5%); logic 1139/1384 (82.3%); string 1573/1640 (95.9%); compare 3061/3159 (96.9%); alphasort 1262/1279 (98.7%); temporal 1243/1271 (97.8%); causal 1255/1261 (99.5%); spatial 1267/1268 (99.9%); creative 1255/1279 (98.1%).
Last run: 2026-11-24T09:40:43.688Z.
Transfer probe: spatial -> revlex delta 0.4 (base 0.6 / transfer 1).
Driver: armed.


Architecture map: https://github.com/didicola/eon-opencode-cloud/blob/main/ARCHITECTURE.md
Known gaps: termux2 .3 last up 2026-10-21, LAN unverified 2026-10-27; ubuntu .72 phone-unreachable; Vercel read-only. /health is a 200-for-all stub; this card uses /self + /state + /driver.
No secrets in this card.