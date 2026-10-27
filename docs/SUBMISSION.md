# Submission draft: Innovation Studio

Project page: https://innovationstudio.microsoft.com/hackathons/insidethegamedeveloperhackathon/project/127073

Recheck the organiser's current rules before submitting. Deadline as reviewed: **27 Oct 2026, 11:59 pm Pacific**. Saving a draft may not count as submitting; confirm the final status in the portal.

## Short description (paste-ready)

**Second Look — the football argument, with the assumptions pulled out where they can be wrong.**

*Should the right-back have pressed earlier?* In this move, Second Look replays the next eight seconds 200 times for each choice. Pressing earlier lets the opponent into a dangerous position in 71 of 200 replays, against 30 when he holds his position: holding is clearly safer. Pressing with a teammate covering (37 of 200) is too close to call against holding. Make the cover arrive at 1.2 s instead of 0.6 s and the rule's verdict becomes "hold". The answer depends on that assumption, and the app shows it.

- **Measured, then simulated, always labelled.** Distances, timings and passing lanes are computed by code and drawn on the pitch when you click them. Simulated results are always labelled as simulations, with intervals and a decision rule fixed before any result was seen.
- **A challenger that tries to flip the answer.** It searches a grid of assumptions (cover timing, attacker style) for settings that change the finding.
- **Agents that cannot invent the match.** Planner, evidence analyst, challenger and producer agents built with Microsoft Agent Framework call the same tools. Agents choose which facts to show; code writes every factual sentence. The only free text the model writes is short interpretations, which may not contain numbers, certainty or causal wording, invented events, or comparisons between choices, and are rejected otherwise. Questions it cannot answer, such as an unknown player or a what-if the simulator does not model, are refused instead of answered.
- **One moment, three audiences.** A fan view in plain words, an analyst view with every number and the agents' trace, and a timed broadcast overlay where every card cites a fact.

On 12 held-out synthetic variants it met its predeclared behaviour in 12 of 12, rejected all 139 injected fabricated claims across 14 kinds of fabrication, and refused all 36 off-catalogue questions. All data is synthetic, and the simulator is illustrative, not a prediction. The public site runs the same tools and validator without a model, so it never depends on one being up. The live agents run on-device with Foundry Local, because cloud model deployment was blocked on our subscription (Azure error 715-123420).

## Microsoft technology (actual use)

| Technology | Status |
|---|---|
| **Microsoft Agent Framework (Python)** | **Used.** `agent-framework-core` 1.23.0 and `agent-framework-foundry` 1.15.0: four `Agent` roles with function tools, typed structured outputs and `FunctionInvocationConfiguration` limits, tested through the real framework loop. |
| **Foundry Local** | **Used, live.** The four Agent Framework agents call `qwen3-8b` running on-device through Foundry Local (CLI 0.12.1), via Agent Framework's `OpenAIChatCompletionClient` (`agent-framework-openai` 1.17.0) pointed at the local server. Live test: 4 model calls, 3 tool calls, 4 claims approved, 0 rejected, about 83 s on an RTX 5070 laptop GPU. Verified in the UI with the trace shown. Runs on the developer's machine only; the public Vercel demo stays offline. |
| **Microsoft Foundry (cloud)** | **Provisioned, model not connected.** A Foundry resource and project (`second-look`, Switzerland North) were created. Every model deployment (gpt-5-mini, gpt-oss-120b, within quota) was blocked by Azure error 715-123420 on the Azure for Students subscription. The cloud path is implemented and tested with scripted replies only; the hosted demo runs in clearly labelled offline mode. |
| **Microsoft Entra ID / azure-identity** | Used for Foundry authentication (CLI and service-principal credentials, no API keys). |
| Azure AI Speech, Container Apps | Not used. |

Hosting is Vercel (not Microsoft).

## Category

Best Multi-Agent Orchestration is the natural fit: distinct agent roles with typed handoffs, a challenger whose verdict reaches the producer, code-rendered facts with a deterministic validator and a bounded repair, and a labelled fallback. Describe it as a fixed pipeline in which the model cannot mint numbers, not as agents debating. Live-model results come from Foundry Local on one laptop (one live smoke run plus UI checks), not a full live evaluation; the cloud model was blocked by the Azure hold. Say so.

## Checklist

- [x] README explains the problem and what is actually implemented.
- [x] Reproducible setup, tested dependency locks, fixture generator, tests; no secrets in the repository (`.env*` ignored and checked before the push).
- [x] Microsoft technology list reflects actual use (above).
- [x] Data card, model card, architecture, evaluation with real counts and omitted checks.
- [ ] Demo video: public, under 2 minutes, permitted assets only (`docs/DEMO_SCRIPT.md`).
- [ ] GitHub repository set to **public** and the final code pushed.
- [ ] Innovation Studio page updated with the description, repository link, video link and live demo link.
- [ ] Links checked while signed out.
- [ ] Final submission status confirmed in the portal.
