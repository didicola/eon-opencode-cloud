# EON Cloud AGI State

Updated: 2026-11-02T15:41:09Z
Worker: agi-cloud-v10 (v10); store=do-storage.
Cycles: 14486. Passed: 13813. Failed: 673. Score: 95.4%.
Self-mods: 578. Lessons: 50. Provisions: 32. Goals: 20.
Best prompt: direct. LLM accuracy: 77.2%.

Domains: math 659/708 (93.1%); logic 585/710 (82.4%); string 911/963 (94.6%); compare 2407/2492 (96.6%); alphasort 596/606 (98.3%); temporal 576/600 (96.0%); causal 586/590 (99.3%); spatial 600/601 (99.8%); creative 589/609 (96.7%).
Last run: 2026-11-02T15:39:56.172Z.
Transfer probe: spatial -> revwordz delta -0.2 (base 0.8 / transfer 0.6).
Driver: armed.


Architecture map: https://github.com/didicola/eon-opencode-cloud/blob/main/ARCHITECTURE.md
Known gaps: termux2 .3 last up 2026-10-21, LAN unverified 2026-10-27; ubuntu .72 phone-unreachable; Vercel read-only. /health is a 200-for-all stub; this card uses /self + /state + /driver.
No secrets in this card.