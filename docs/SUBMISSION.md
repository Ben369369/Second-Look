# Submission draft: Innovation Studio

Project page: https://innovationstudio.microsoft.com/hackathons/insidethegamedeveloperhackathon/project/127073

Recheck the organiser's current rules before submitting. Deadline as reviewed: **27 Oct 2026, 11:59 pm Pacific**. Saving a draft may not count as submitting; confirm the final status in the portal.

## Tagline (paste-ready)

The football argument, with its assumptions on the pitch.

## Description (paste-ready)

*Should the right-back have pressed earlier?* Fans argue about decisions like this every week, with no way to check who's right. Second Look settles one with evidence you can inspect.

In this move the answer is **no: holding was safer.** Replaying the next eight seconds 200 times for each choice, the opponent reaches a dangerous position in 30 of 200 replays when the right-back holds, against 71 when he presses earlier. With a teammate covering it's too close to call, until that cover arrives 0.6 seconds later and holding becomes the clear call. The answer depends on that assumption, and Second Look shows it instead of hiding it.

**How it works**
- **Measured, then simulated, always labelled.** Distances, timings and passing lanes are computed by code and drawn on the pitch when you click them. A transparent simulator compares hold, press earlier and press with cover, with confidence intervals and a decision rule fixed before any run.
- **A challenger that tries to flip the answer.** It searches a grid of assumptions (cover timing, attacker style) for settings that change the verdict.
- **AI agents that can't invent the match.** Four Microsoft Agent Framework agents (planner, evidence analyst, challenger, producer) run on-device with Foundry Local. They choose and order the evidence; code writes every factual sentence, and a validator rejects any claim the numbers don't support. Unknown players and what-ifs the simulator doesn't model are refused, not answered.
- **One moment, three audiences.** A fan view in plain words, an analyst view with every number and the agents' trace, and timed broadcast cards where every card cites a fact.

**Tested:** 12 of 12 held-out scenarios behaved as predeclared, 139 of 139 planted fabrications were rejected, 60 of 60 off-catalogue questions were refused, and 4 of 4 live on-device runs completed.

**Microsoft technology:** Microsoft Agent Framework (four agents, tool calls, typed handoffs) and Foundry Local (`qwen3-8b` on-device). A Microsoft Foundry cloud project was provisioned, but model deployment was blocked on our subscription (Azure error 715-123420), so the live agents run on the laptop. The hosted demo runs the same tools and validator without a model.

All data is synthetic; the teams and players are fictional. The simulator is illustrative, not a prediction.

**Links:** Demo: https://second-look-dusky.vercel.app · Code: https://github.com/Ben369369/Second-Look · Video: [YouTube link]

If the form has a character limit, keep the first two paragraphs, the Microsoft technology paragraph and the links.

## Microsoft technology (actual use)

| Technology | Status |
|---|---|
| **Microsoft Agent Framework (Python)** | **Used.** `agent-framework-core` 1.23.0 and `agent-framework-foundry` 1.15.0: four `Agent` roles with function tools, typed structured outputs and `FunctionInvocationConfiguration` limits, tested through the real framework loop. |
| **Foundry Local** | **Used, live.** The four Agent Framework agents call `qwen3-8b` running on-device through Foundry Local (CLI 0.12.1), via Agent Framework's `OpenAIChatCompletionClient` (`agent-framework-openai` 1.17.0) pointed at the local server. Live: in a small benchmark of the current workflow, 4 of 4 fresh runs of the pressing question completed with the live agents (no fallback), 70–196 s each on an RTX 5070 laptop GPU, with the reversal search run and the validator rejecting 12 model interpretations (docs/EVALUATION.md). Verified in the UI with the trace shown. Runs on the developer's machine only; the public Vercel demo stays offline. |
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
