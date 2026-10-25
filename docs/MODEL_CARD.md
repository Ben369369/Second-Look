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
