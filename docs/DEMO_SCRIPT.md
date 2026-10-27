# Demo script (target ~110 s, under 2 minutes)

Record the live site (https://second-look-dusky.vercel.app) or the local app, in a browser window about 1600×1000. Everything shown is real, working software. The app runs in **offline mode**: say so, and don't imply a live AI model.

**Before recording:**
- Open the Overview page.
- Make sure the replay is at 63:12.
- Check that "Synthetic match" and "Offline demonstration — no language model connected" are visible in the header.

| Time | On screen | Say (suggested) |
|---|---|---|
| 0–12 s | **Overview.** Press play; let the move run for a few seconds. | "Football arguments hide their assumptions. *Should the right-back have pressed earlier?* Second Look puts that argument on the pitch. This is a synthetic match: fictional teams, simulated data." |
| 12–30 s | Click the **Pressing decision** chip in *Ask Second Look*. Click the first evidence row (8.5 m) to show the measurement drawn on the pitch. | "It finds the moment: Halvorsen was 8.5 metres off Rossi when the ball arrived and took 1.7 seconds to close Rossi down. Every number comes from code and is labelled measured, estimated or simulated, and clicking it shows it on the pitch." |
| 30–50 s | **What if?** page. Show the three action cards, then play the simulated replay ("Press earlier"), pointing at the dashed recorded ghosts. | "From the pass that triggered the press, a transparent simulator replays the next eight seconds 200 times for each choice. Pressing earlier without cover let Harbor into danger in 71 of 200 runs, against 30 with the right-back holding position: pressing early leaves space behind." |
| 50–72 s | Drag **Cover delay** from 0.6 s to 1.2 s. Wait for "updating" to clear and show the Finding change. | "Add a teammate covering the inside pass and it's close to holding: no clear winner under a rule we fixed in advance. Make the cover arrive late and holding becomes the clear recommendation. The answer depends on that assumption, and the app shows it." |
| 72–88 s | Click **Run stress test** and show the grid. Then open **Ask & evidence**, expand **How this answer was made**, and switch to **Analyst view** if needed. | "A challenger searches a fixed grid of assumptions for settings that flip the finding. The answer comes from Microsoft Agent Framework roles — planner, evidence analyst, challenger, producer — and a validator that rejects any claim whose numbers aren't in the evidence. Here it's running offline, with rule-based routing, and it says so." |
| 88–102 s | Switch to **Fan view**. | "Same facts, different presentation: plain language for a fan, with the caveat attached." |
| 102–110 s | **Recap & overlay.** Click a cue row so the overlay appears on the pitch, then **Download overlay JSON**. | "And a timed overlay a broadcaster can render: every card cites its evidence, and simulations are labelled. Evidence you can inspect, alternatives labelled as simulations." |

**Don't:**
- claim a live model, real players, or real-match accuracy;
- use club logos, real footage or copyrighted music;
- speed the video up in a way that hides the "updating" state.

If the Foundry model becomes available before recording, show one live answer with the trace (model calls, tool calls) instead of the offline badge, and say "live Foundry model".
