# EON Cloud AGI State

Updated: 2026-11-22T19:31:36Z
Worker: agi-cloud-v10 (v10); store=do-storage.
Cycles: 28176. Passed: 27199. Failed: 977. Score: 96.5%.
Self-mods: 1126. Lessons: 50. Provisions: 32. Goals: 20.
Best prompt: direct. LLM accuracy: 76.4%.

Domains: math 1267/1329 (95.3%); logic 1100/1334 (82.5%); string 1520/1586 (95.8%); compare 3012/3110 (96.8%); alphasort 1214/1228 (98.9%); temporal 1194/1222 (97.7%); causal 1203/1209 (99.5%); spatial 1217/1218 (99.9%); creative 1207/1231 (98.1%).
Last run: 2026-11-22T19:26:25.326Z.
Transfer probe: spatial -> revlex delta 0.4 (base 0.2 / transfer 0.6).
Driver: armed.


Architecture map: https://github.com/didicola/eon-opencode-cloud/blob/main/ARCHITECTURE.md
Known gaps: termux2 .3 last up 2026-10-21, LAN unverified 2026-10-27; ubuntu .72 phone-unreachable; Vercel read-only. /health is a 200-for-all stub; this card uses /self + /state + /driver.
No secrets in this card.