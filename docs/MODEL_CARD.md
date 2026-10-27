# Model card: Second Look metrics and estimates

This card covers the numerical methods behind every fact the app shows. Every fact carries its `method_version`; when a definition changes, its version is bumped.

## Evidence classes

| Class | Meaning | Examples |
|---|---|---|
| **Observed** | Computed directly from the synthetic recording | Pass distance, defender distance, distance covered |
| **Estimated** | Output of a stated heuristic; not a measurement and not a probability | Lane access, open passing lanes |
| **Simulated** | Aggregates from alternative rollouts | None yet (Stage 3) |

## Observed metrics

| Method | Definition | Notes |
|---|---|---|
| `pass_distance/1` | Straight line between the pass event's recorded start and end positions | Refused if the end is unknown at the cutoff |
| `pass_completion/1` | Completed ÷ passes with a known outcome, for one team and window | Passes without an outcome are excluded from the denominator and reported. A zero denominator is refused |
| `possession_duration/1` | Team spell from the first frame a player holds the ball to the first frame an opponent holds it. Loose-ball frames stay with the previous team | Spell within this sequence, not a match possession share. Marked as a lower bound if still running at the cutoff |
| `transitions/1` | Count of possession spells after the first, in the window | Descriptive only |
| `tracked_running/1` | Sum of frame-to-frame displacements, plus top speed over 0.1 s intervals | Refused for event-only data. Rejects non-increasing timestamps. Gaps longer than 1.5 sample periods are not bridged, and coverage is reported |
| `defender_distance/1` | Distance between two players on one recorded frame | |
| `response_time/1` | Time from the carrier's reception to the presser's `pressure_start` event | Pressure begins within 3 m (recording convention) |
| `final_third_share/1` | Count of a team's pass, reception, carry and shot events starting beyond 70 m in that team's attacking direction ÷ all such events | Final-third *event* share, not touches |

## Estimated: lane-access heuristic (`lane_access/1`, `open_lanes/1`)

For a straight ground pass from passer P to receiver R, every outfield opponent D is checked:

```
defender_time = 0.25 s reaction + max(0, distance(D, lane) − 1.0 m reach) / 7.0 m/s
ball_time     = distance(P, closest lane point to D) / 14.0 m/s
margin        = ball_time − defender_time      (> 0: defender can get there first)
```

A lane is **open** when every opponent's margin is negative. `lane_access` reports the opponent with the largest margin. `open_lanes` counts teammates with open lanes.

Limitations: the constants are prototype assumptions, not fitted. The heuristic ignores body orientation, anticipation, pass weight and curve, offside, and pressure on the receiver. A defender standing next to the passer has a ball time near zero, so they never count as cutting the lane, even though they might block the pass. Margins within about ±0.1 s are effectively a toss-up. The hero sequence's Rossi → Kiprono lane has a margin of +0.03 s, so the heuristic calls it "reachable", but only just. **This is not a calibrated probability** and is never displayed as one.

## Question routing (offline mode)

In offline mode, questions are routed by fixed keyword rules (`backend/app/investigations/questions.py`) to one of 8 supported intents. Questions that match no rule are answered "unsupported", with the list of supported questions. Ambiguous player references (such as "#2", which exists on both teams) produce a clarification request. The router only selects which facts to compute; every sentence is a fact statement rendered by code. The UI labels this "ROUTED: RULES". A model-backed planner replaces the router in Stage 5.

## Data cutoff

Every answer is computed from a cutoff view (`backend/app/metrics/view.py`). Frames after the cutoff are dropped. Passes and shots that complete after the cutoff lose their outcome and end position, and unfinished carries lose their end. Tests check that no fact references a later event or frame.

## Simulated: short-horizon intervention model (`rules/1`)

Code: `backend/app/simulation/engine.py` (rollouts), `compare.py` (decision rule, challenger), `stats.py` (intervals).

**What it answers.** Starting from a recorded frame, what tends to happen in the next 8 s if the defending presser **holds** (contains about 6 m goal-side), **presses earlier** (starts closing 0.3 s after the branch), or **presses with cover** (presses earlier while a designated teammate screens the midpoint of the carrier → inside-option lane after a *cover delay*)?

**Branch.** The default branch is the first frame after the pass that triggered the recorded press is released; for the hero sequence, frame 101 at 63:22. The pass's intended receiver is the passing team's outfielder closest to the ball's observed direction of travel. Only that frame (positions, velocities, ball velocity) and earlier possession are read. A test corrupts every later frame and confirms identical results.

**Roles from geometry, not names.**
- *Inside option:* the most advanced teammate within 25 m who is more central than the carrier.
- *Overlap runner:* the nearest same-flank teammate behind the ball.
- *Striker:* the most advanced other teammate.
- *Cover:* the defending midfielder or defender (forwards excluded) nearest the inside option.
- Team-shape anchors are inferred from the branch positions.

**Behaviour.**
- **Movement:** steering with 4.5 m/s² acceleration, top speed 7.5 m/s (carrier 6 m/s, goalkeepers 6 m/s).
- **Carrier decisions:** every 0.3 s (after holding at least 0.5 s), the carrier picks pass to any teammate, carry, or hold.
  - Option value = (1 − risk) × gain − risk × loss cost. Gain combines progress, dangerous-zone value and receiver space.
  - Risk combines lane interception (lane-access margin through a logistic curve: margin 0 gives 30%, +0.1 s gives 70%) and misplacement (pressure-dependent perpendicular error beyond 1.6 m).
  - The choice is made by Gumbel-max sampling. "Patient" and "direct" attackers differ in gain weights and loss cost.
- **Passes:** played at 14 m/s, leading the receiver by up to 6 m. The intended receiver controls an arriving ball within 2 m; otherwise it is loose.
- **Defending:** the nearest outfield defender closes a new carrier after 0.4 s. A defender within 1 m wins a tackle with 7% chance per 0.1 s.
- **Support play:** the inside option and striker take the nearby spot furthest from defenders. The overlap starts when the presser engages (closer than 4 m).

**Outcomes per rollout.**
- *Dangerous possession:* the attacking team controls the ball within 30 m of goal and inside penalty-area width.
- *Regain:* the defending team controls the ball.
- *Retained:* the attacking team still has it at 8 s.

**Randomness and pairing.** Draws are keyed by (seed, step, rollout, player), so all three actions use identical random conditions. Differences are measured on paired trials.

**Statistics.**
- Wilson 95% intervals for single rates; 95% paired percentile bootstrap (2,000 resamples) for differences.
- These describe Monte Carlo sampling uncertainty only, not whether the model represents football well.

**Decision rule (fixed before running).** Recommend an action only if its dangerous-possession rate is at least 5 points below every other action's, with each paired 95% interval excluding zero, from at least 64 rollouts per action. Otherwise: "no clear winner" (or "inconclusive" below 64 rollouts). Regain rates stay visible as a secondary outcome.

**Challenger.** A fixed grid: cover delay {0, 0.3, 0.6, 0.9, 1.2, 1.8} s × attacker policy {patient, direct}, 128 rollouts per action. It reports every setting where the finding differs from the user's current setting, plus a tally. Finding a change shows the answer is not robust across the grid; finding none would not prove robustness beyond it.

**How it was calibrated, honestly.** The constants were hand-set during development. The targets were face validity on this sequence: passes usually reach their receivers, carriers don't run into defenders, and an unpressured winger usually finds the inside option. Calibration problems found and fixed through diagnostics:
- Long passes were nearly always intercepted. The choice rule became expected-value based and the interception curve was recalibrated.
- Carriers dribbled into defenders. Avoidance was added.
- Passes aimed at receivers' current positions were collected by opponents (122 of 238 under "hold"). Passes now lead the receiver and the intended receiver gets first-touch priority.
- The cover could never arrive when branching at the reception (13.6 m away against a pass about 1.4 s later). The branch moved to the pass trigger, and the cover now screens the lane instead of marking goal-side.

No constant was tuned to produce a particular recommendation, but the model has **not** been validated against real football. Results on the hero sequence at default assumptions (patient, cover delay 0.6 s, 200 rollouts):

| Choice | Dangerous possession | Regain |
|---|---|---|
| Hold | 30/200 (15%) | 80/200 (40%) |
| Press earlier | 71/200 (36%) | 66/200 (33%) |
| Press with cover | 37/200 (19%) | 94/200 (47%) |

Rule outcome: no clear winner. Hold vs press with cover differs by 3.5 points (interval −4.0 to +10.5). Press earlier is clearly worse than hold (+20.5 points, interval 12.5 to 28.5).
