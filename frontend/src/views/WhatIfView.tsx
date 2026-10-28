import {
  Accordion,
  Button,
  Card,
  Group,
  List,
  Loader,
  SegmentedControl,
  SimpleGrid,
  Slider,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { AttackerPolicy, ChallengeCell, ChallengeResult, ComparisonResult, SimAction, TrackingFrame } from "../api/types";
import { PlaybackControlsBare } from "../components/PlaybackControls";
import { useStudio } from "../features/studio";
import { formatClock, playerLabel, shortPlayer, stateAt } from "../replay/model";
import { PitchCanvas } from "../replay/PitchCanvas";
import { usePlayback } from "../replay/usePlayback";

const ACTION_LABEL: Record<SimAction, string> = { hold: "Hold position", press_earlier: "Press earlier", press_with_cover: "Press with cover" };
const SHORT: Record<SimAction, string> = { hold: "Hold", press_earlier: "Press", press_with_cover: "Press + cover" };
const pct = (x: number) => `${(x * 100).toFixed(0)}%`;

export function WhatIfView() {
  const { bundle, lookup, scenarioId } = useStudio();
  const [coverDelay, setCoverDelay] = useState(0.6);
  const [policy, setPolicy] = useState<AttackerPolicy>("patient");
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<SimAction>("press_with_cover");
  const [stress, setStress] = useState<ChallengeResult | null>(null);
  const [stressPending, setStressPending] = useState(false);
  const ctl = useRef<AbortController | null>(null);

  // Debounced request; a newer setting aborts the older request, so late results are never shown as current.
  useEffect(() => {
    setPending(true);
    const timer = window.setTimeout(() => {
      ctl.current?.abort();
      const c = new AbortController();
      ctl.current = c;
      setError(null);
      api
        .compare(scenarioId, { cover_delay_s: coverDelay, attacker_policy: policy }, c.signal)
        .then((r) => {
          setResult(r);
          setPending(false);
        })
        .catch((err) => {
          if (err.name === "AbortError") return;
          setError(err instanceof ApiError ? err.message : String(err));
          setPending(false);
        });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [scenarioId, coverDelay, policy]);

  const stale = result !== null && (result.config.cover_delay_s !== coverDelay || result.config.attacker_policy !== policy);
  const sample = result?.samples.find((s) => s.action === view) ?? null;
  const horizon = result?.config.horizon_s ?? 8;
  const simPlayback = usePlayback(horizon);

  // The sampled rollout as a replay bundle (same pitch, orientation and scale as the recording).
  const simBundle = useMemo(() => {
    if (!sample) return null;
    const team = new Map(bundle.manifest.teams.flatMap((t) => t.players.map((p) => [p.player_id, t.team_id] as const)));
    const frames: TrackingFrame[] = sample.frames.map((f, i) => ({
      frame_id: i,
      time_s: f.t,
      ball: { x: f.ball.x, y: f.ball.y, z: 0, vx: 0, vy: 0, possession_player_id: f.holder },
      players: f.players.map((p) => ({ ...p, team_id: team.get(p.player_id) ?? "", vx: 0, vy: 0, observed_fields: [] })),
    }));
    return { ...bundle, frames, events: [] };
  }, [sample, bundle]);

  const branchT = result?.branch.time_s ?? 0;
  const ghost = useMemo(() => ({ frames: bundle.frames, t: branchT + simPlayback.t }), [bundle.frames, branchT, simPlayback.t]);
  const highlight = useMemo(
    () => new Set(result ? [result.branch.presser, result.branch.carrier, ...(view === "press_with_cover" ? [result.branch.cover] : [])] : []),
    [result, view],
  );

  const runStress = () => {
    setStressPending(true);
    api
      .challenge(scenarioId, { baseline_cover_delay_s: coverDelay, baseline_attacker_policy: policy })
      .then(setStress)
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)))
      .finally(() => setStressPending(false));
  };

  const b = result?.branch;
  const offset = bundle.manifest.match_clock_offset_s;
  const simState = simBundle ? stateAt(simBundle.frames, simPlayback.t) : null;

  return (
    <Stack gap="xl">
      <section>
        <Text className="kicker kicker-sim" mb={8}>
          Simulated · {result ? `${result.config.rollouts} rollouts per choice` : "running"} · lower is safer
        </Text>
        <Finding result={result} stale={stale || pending} error={error} />
        <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="xl" mt="lg" className={stale || pending ? "is-stale" : undefined}>
          {result?.actions.map((a) => {
            const rec = result.recommendation;
            // The navy rule marks the choice the predeclared rule supports: the recommendation, or the
            // safest choice wherever it clearly beats another one.
            const clearBest = result.diffs.find((d) => d.metric === "danger" && d.diff >= 0.05 && d.ci95[0] > 0)?.better;
            const best = (rec.status === "recommend" ? rec.action : clearBest) === a.action;
            return (
              <div key={a.action} className={`choice${best ? " choice-mark" : ""}`} data-testid={`action-${a.action}`}>
                <Group justify="space-between" align="baseline" wrap="nowrap">
                  <Text fw={600} c="navy.9" fz="lg">
                    {a.label}
                  </Text>
                  <Text className="kicker kicker-sim" fz={11}>
                    simulated
                  </Text>
                </Group>
                <Text className="big-number" mt={6} style={best ? undefined : { color: "#9aa3b5" }}>
                  {a.danger.count} <span style={{ fontSize: "0.45em", fontWeight: 500 }}>of {a.danger.n}</span>
                </Text>
                <Text className="finding" fz={17} mt={2}>
                  rollouts reach a dangerous position
                </Text>
                <Text fz="xs" c="dimmed" mt={6} className="tabular">
                  {a.danger.count} of {a.danger.n} rollouts · {pct(a.danger.rate)} (95% {pct(a.danger.ci95[0])}–{pct(a.danger.ci95[1])}) · Cedar win it back in{" "}
                  {a.regain.count}
                  {a.median_regain_s !== null && `, median ${a.median_regain_s.toFixed(1)} s`}
                </Text>
                <button
                  type="button"
                  className="text-link"
                  style={{ marginTop: 8 }}
                  onClick={() => {
                    setView(a.action);
                    simPlayback.reset();
                    simPlayback.play();
                  }}
                >
                  Watch an example
                </button>
              </div>
            );
          })}
        </SimpleGrid>
      </section>

      <Group gap="xl" align="flex-end" wrap="wrap" style={{ borderTop: "1px solid var(--sheet-rule)" }} pt="lg">
        <div style={{ flex: "1 1 320px", minWidth: 0 }}>
          <Group gap="xs" mb={4}>
            <Text fz="sm" fw={600}>
              Cover delay: <span className="tabular">{coverDelay.toFixed(1)} s</span>
            </Text>
            {(pending || stale) && (
              <Group gap={6} data-testid="sim-pending">
                <Loader size={12} />
                <Text fz="xs" c="dimmed">
                  updating
                </Text>
              </Group>
            )}
          </Group>
          <Text fz="xs" c="dimmed" mb="sm">
            How long after the pass {b ? playerLabel(lookup, b.cover) : "the cover player"} starts moving to screen the inside lane.
          </Text>
          <Slider
            value={coverDelay}
            onChange={setCoverDelay}
            min={0}
            max={2}
            step={0.1}
            marks={[0, 0.5, 1, 1.5, 2].map((v) => ({ value: v, label: `${v}s` }))}
            label={(v) => `${v.toFixed(1)} s`}
            mb="lg"
            aria-label="Cover delay in seconds"
            data-testid="cover-delay"
          />
        </div>
        <div style={{ flex: "0 1 360px" }}>
          <Text fz="sm" fw={600} mb={6}>
            Attackers
          </Text>
          <SegmentedControl
            fullWidth
            value={policy}
            onChange={(v) => setPolicy(v as AttackerPolicy)}
            data={[
              { value: "patient", label: "Patient (keeps the ball)" },
              { value: "direct", label: "Direct (takes risks)" },
            ]}
            aria-label="Attacker response policy"
            data-testid="attacker-policy"
          />
        </div>
      </Group>

      <Card>
        <Group justify="space-between" mb="xs" wrap="wrap">
          <div>
            <Text fw={600}>Watch one replay</Text>
            <Text fz="xs" c="dimmed">
              One example rollout with the most common outcome for that choice. Examples are illustrations, not the same trial replayed.
            </Text>
          </div>
          <SegmentedControl
            size="xs"
            value={view}
            onChange={(v) => {
              setView(v as SimAction);
              simPlayback.reset();
            }}
            data={(Object.keys(ACTION_LABEL) as SimAction[]).map((a) => ({ value: a, label: ACTION_LABEL[a] }))}
            aria-label="Which simulated choice to watch"
            data-testid="sim-view"
          />
        </Group>
        {simBundle ? (
          <>
            <PitchCanvas
              bundle={simBundle}
              lookup={lookup}
              t={simPlayback.t}
              highlight={highlight}
              annotation={null}
              showGrid={false}
              variant="simulated"
              ghost={ghost}
              label={`Simulated rollout ${sample?.rollout_index} for "${ACTION_LABEL[view]}", ${simPlayback.t.toFixed(1)} s after the branch. ${
                simState?.possession ? `${playerLabel(lookup, simState.possession)} on the ball.` : "Ball loose or travelling."
              } Dashed outlines show the recorded positions at the same moment.`}
            />
            <Group gap="lg" mt={6}>
              <Text fz="xs" c="dimmed">
                <span className="legend-solid" /> simulated players
              </Text>
              <Text fz="xs" c="dimmed">
                <span className="legend-ghost" /> recorded positions, same moment
              </Text>
              {sample && (
                <Text fz="xs" c="dimmed">
                  This example {sample.outcome === "danger" ? "ends in danger" : sample.outcome === "regain" ? "ends with Cedar winning the ball" : "ends with neither"}
                </Text>
              )}
              <Text fz="xs" c="dimmed">
                Highlighted: {b ? [b.presser, b.carrier].map((id) => shortPlayer(lookup, id)).join(", ") : ""}
                {view === "press_with_cover" && b ? `, cover ${shortPlayer(lookup, b.cover)}` : ""}
              </Text>
            </Group>
            <PlaybackControlsBare playback={simPlayback} duration={horizon} clockLabel={`+${simPlayback.t.toFixed(1)} s`} />
          </>
        ) : (
          <Group justify="center" h={300}>
            <Loader size="sm" />
          </Group>
        )}
      </Card>

      <Card>
        <Group justify="space-between" wrap="wrap" mb="xs">
          <div>
            <Text fw={600}>Try to flip it</Text>
            <Text fz="sm" c="dimmed">
              The challenger re-runs the comparison across a fixed grid of cover delays and attacker styles and looks for settings where the
              answer changes.
            </Text>
          </div>
          <Button onClick={runStress} loading={stressPending} variant="default" data-testid="run-stress">
            Run stress test
          </Button>
        </Group>
        {stress && <StressGrid stress={stress} coverDelay={coverDelay} policy={policy} />}
      </Card>

      {result && (
        <Accordion variant="default" chevronPosition="left">
          <Accordion.Item value="assumptions" style={{ borderTop: "1px solid var(--sheet-rule)" }}>
            <Accordion.Control>
              <Text fw={600}>Model assumptions and run details</Text>
            </Accordion.Control>
            <Accordion.Panel>
              {b && (
                <Text fz="sm" mb="sm">
                  Starting from the recorded moment the pass to {playerLabel(lookup, b.carrier)} leaves the passer's foot ({formatClock(offset + b.time_s)}), a
                  rule-based model replays the next {horizon} s {result.config.rollouts} times for each choice by {playerLabel(lookup, b.presser)}. Results are
                  counts inside this simulator, not real-world probabilities.
                </Text>
              )}
              <Text fz="sm" mb="sm">
                Decision rule, fixed before running: {result.recommendation.rule}
              </Text>
              <List fz="sm" spacing={4} mb="sm">
                {result.assumptions.map((x) => (
                  <List.Item key={x}>{x}</List.Item>
                ))}
              </List>
              <Text fz="xs" c="dimmed" className="tabular">
                run {result.run_id} · policy {result.policy_version} · seed {result.config.seed} · {result.config.rollouts} rollouts per action ·
                horizon {result.config.horizon_s} s · branch frame {result.branch.frame_id} · {result.cached ? "cached" : `${result.compute_ms} ms`}
              </Text>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      )}
    </Stack>
  );
}

const VERB: Record<SimAction, string> = { hold: "Holding position", press_earlier: "Pressing earlier", press_with_cover: "Pressing with cover" };
const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

/** The predeclared rule's answer as sentences: what is clear, what is unresolved. */
function Finding({ result, stale, error }: { result: ComparisonResult | null; stale: boolean; error: string | null }) {
  if (error) {
    return (
      <Text c="red.8" role="alert">
        The simulation failed: {error}
      </Text>
    );
  }
  if (!result) return <Loader size="sm" />;
  const rec = result.recommendation;
  const pairs = result.diffs.filter((d) => d.metric === "danger");
  const clear = pairs.filter((d) => d.diff >= 0.05 && d.ci95[0] > 0);
  const open = pairs.filter((d) => !clear.includes(d));
  const head =
    rec.status === "recommend" && rec.action
      ? `${VERB[rec.action]} is the clear call under these assumptions.`
      : rec.status === "no_clear_winner"
        ? "No single choice is clearly best under these assumptions."
        : "Not enough simulated evidence to decide.";
  const detail = [
    ...(rec.status === "recommend" ? [] : clear.map((d) => `${VERB[d.better]} is clearly safer than ${lower(VERB[d.other])}.`)),
    ...open.map((d) => `${VERB[d.better]} versus ${lower(VERB[d.other])} is too close to call.`),
  ];
  return (
    <div className={stale ? "is-stale" : undefined} data-testid="recommendation">
      <Title order={2} c="navy.9" className="page-title" fz={{ base: 24, sm: 28 }}>
        {head}
      </Title>
      {detail.length > 0 && (
        <Text className="finding" mt={6}>
          {detail.join(" ")}
        </Text>
      )}
      <Text fz="xs" c="dimmed" mt={6} maw={760}>
        {stale ? "Showing the previous settings while the new ones run. " : ""}Lower is safer. A choice wins only if it leads by 5 points
        and the 95% interval clears zero, a rule fixed before any run.
      </Text>
    </div>
  );
}

function StressGrid({ stress, coverDelay, policy }: { stress: ChallengeResult; coverDelay: number; policy: AttackerPolicy }) {
  const delays = [...new Set(stress.cells.map((c) => c.cover_delay_s))];
  const policies = [...new Set(stress.cells.map((c) => c.attacker_policy))];
  const at = (d: number, p: AttackerPolicy) => stress.cells.find((c) => c.cover_delay_s === d && c.attacker_policy === p);
  const label = (c: ChallengeCell | undefined) => (!c ? "—" : c.status === "recommend" && c.action ? SHORT[c.action] : c.status === "no_clear_winner" ? "No clear winner" : "Inconclusive");
  return (
    <>
      <Text className="finding" fz={18} mb="sm" data-testid="stress-conclusion">
        {stress.conclusion}
      </Text>
      <Table.ScrollContainer minWidth={560}>
        <Table withTableBorder withColumnBorders ta="center" fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Attacker / cover delay</Table.Th>
              {delays.map((d) => (
                <Table.Th key={d} ta="center">
                  {d.toFixed(1)} s
                </Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {policies.map((p) => (
              <Table.Tr key={p}>
                <Table.Td fw={600}>{p}</Table.Td>
                {delays.map((d) => {
                  const c = at(d, p);
                  const isBase = Math.abs(d - coverDelay) < 1e-9 && p === policy;
                  return (
                    <Table.Td
                      key={d}
                      className={`stress-cell ${c?.status === "recommend" ? `rec-${c.action}` : "rec-none"}${isBase ? " stress-base" : ""}`}
                      title={c ? Object.entries(c.danger).map(([a, v]) => `${ACTION_LABEL[a as SimAction]}: ${pct(v)} danger`).join("\n") : ""}
                    >
                      {label(c)}
                    </Table.Td>
                  );
                })}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      <Text fz="xs" c="dimmed" mt="xs">
        Tested: {stress.tested_domain}. Finding a change shows the answer is not robust across this grid; finding none would not prove
        robustness beyond it. Hover a cell for the danger rates. Outlined cell = your current settings.
      </Text>
    </>
  );
}
