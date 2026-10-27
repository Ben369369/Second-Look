import {
  Accordion,
  Alert,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  List,
  Loader,
  Paper,
  Progress,
  SegmentedControl,
  SimpleGrid,
  Slider,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconAlertTriangle, IconFlask } from "@tabler/icons-react";
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
    <Stack gap="md">
      <Alert color="teal" variant="light" icon={<IconFlask size={18} />} title="Simulated alternatives">
        <Text fz="sm">
          {b ? (
            <>
              Starting from the recorded moment the pass to {playerLabel(lookup, b.carrier)} leaves the passer's foot (
              {formatClock(offset + b.time_s)}), a rule-based model replays the next {horizon} s many times for each choice by{" "}
              {playerLabel(lookup, b.presser)}. Results are counts inside this simulator, not real-world probabilities.
            </>
          ) : (
            "Running the simulator…"
          )}
        </Text>
      </Alert>

      <Grid>
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Card>
            <Group justify="space-between" mb="xs" wrap="wrap">
              <Group gap="sm">
                <Text fw={600}>Simulated replay</Text>
                {sample && (
                  <Badge variant="light" color={sample.outcome === "danger" ? "red" : sample.outcome === "regain" ? "teal" : "gray"} radius="sm">
                    {sample.outcome === "danger" ? "ends in danger" : sample.outcome === "regain" ? "Cedar regain" : "no danger, no regain"}
                  </Badge>
                )}
              </Group>
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
                <Group gap="lg" mt={6} fz="xs" c="dimmed">
                  <Text fz="xs" c="dimmed">
                    <span className="legend-solid" /> simulated players
                  </Text>
                  <Text fz="xs" c="dimmed">
                    <span className="legend-ghost" /> recorded positions, same moment
                  </Text>
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
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 5 }}>
          <Stack gap="md">
            <Card>
              <Group justify="space-between" mb="sm">
                <Text fw={600}>Assumptions</Text>
                {(pending || stale) && (
                  <Badge color="orange" variant="light" radius="sm" leftSection={<Loader size={10} color="orange" />} data-testid="sim-pending">
                    updating
                  </Badge>
                )}
              </Group>
              <Text fz="sm" fw={500} mb={4}>
                Cover delay: {coverDelay.toFixed(1)} s
              </Text>
              <Text fz="xs" c="dimmed" mb="sm">
                How long after the branch {b ? playerLabel(lookup, b.cover) : "the cover player"} starts moving to screen the inside lane.
              </Text>
              <Slider
                value={coverDelay}
                onChange={setCoverDelay}
                min={0}
                max={2}
                step={0.1}
                marks={[0, 0.5, 1, 1.5, 2].map((v) => ({ value: v, label: `${v}s` }))}
                label={(v) => `${v.toFixed(1)} s`}
                mb="xl"
                aria-label="Cover delay in seconds"
                data-testid="cover-delay"
              />
              <Text fz="sm" fw={500} mt="md" mb={4}>
                Attacker response
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
            </Card>

            <RecommendationCard result={result} stale={stale || pending} error={error} />
          </Stack>
        </Grid.Col>
      </Grid>

      <SimpleGrid cols={{ base: 1, md: 3 }} className={stale || pending ? "is-stale" : undefined}>
        {result?.actions.map((a) => {
          const rec = result.recommendation;
          const best = rec.status === "recommend" && rec.action === a.action;
          return (
            <Paper key={a.action} p="lg" className={`action-card${best ? " action-best" : ""}`} data-testid={`action-${a.action}`}>
              <Group justify="space-between" mb="sm">
                <Text fw={700} c="navy.9">
                  {a.label}
                </Text>
                <Badge color="teal" variant="light" radius="sm">
                  simulated
                </Badge>
              </Group>
              <Text fz="xs" c="dimmed" tt="uppercase" fw={600}>
                Harbor dangerous possession
              </Text>
              <Group gap={6} align="baseline">
                <Text fz={28} fw={700} c="red.8" className="tabular">
                  {pct(a.danger.rate)}
                </Text>
                <Text fz="sm" c="dimmed" className="tabular">
                  {a.danger.count} of {a.danger.n} rollouts · 95% {pct(a.danger.ci95[0])}–{pct(a.danger.ci95[1])}
                </Text>
              </Group>
              <Progress value={a.danger.rate * 100} color="red.7" size="sm" mb="sm" aria-hidden />
              <Text fz="xs" c="dimmed" tt="uppercase" fw={600}>
                Cedar win the ball back
              </Text>
              <Group gap={6} align="baseline">
                <Text fz={22} fw={700} c="teal.8" className="tabular">
                  {pct(a.regain.rate)}
                </Text>
                <Text fz="sm" c="dimmed" className="tabular">
                  {a.regain.count} of {a.regain.n}
                  {a.median_regain_s !== null && ` · median ${a.median_regain_s.toFixed(1)} s`}
                </Text>
              </Group>
              <Progress value={a.regain.rate * 100} color="teal.7" size="sm" aria-hidden />
              <Button
                variant="subtle"
                size="compact-sm"
                mt="sm"
                onClick={() => {
                  setView(a.action);
                  simPlayback.reset();
                  simPlayback.play();
                }}
              >
                Watch a sample rollout
              </Button>
            </Paper>
          );
        })}
      </SimpleGrid>

      <Card>
        <Group justify="space-between" wrap="wrap" mb="xs">
          <div>
            <Text fw={600}>Stress test</Text>
            <Text fz="sm" c="dimmed">
              The challenger re-runs the comparison across a fixed grid of assumptions and looks for settings where the answer changes.
            </Text>
          </div>
          <Button onClick={runStress} loading={stressPending} variant="light" leftSection={<IconAlertTriangle size={16} />} data-testid="run-stress">
            Run stress test
          </Button>
        </Group>
        {stress && <StressGrid stress={stress} coverDelay={coverDelay} policy={policy} />}
      </Card>

      {result && (
        <Accordion variant="contained" radius="md">
          <Accordion.Item value="assumptions">
            <Accordion.Control>Model assumptions and run details</Accordion.Control>
            <Accordion.Panel>
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

function RecommendationCard({ result, stale, error }: { result: ComparisonResult | null; stale: boolean; error: string | null }) {
  if (error) {
    return (
      <Alert color="red" title="Simulation failed">
        {error}
      </Alert>
    );
  }
  if (!result) {
    return (
      <Card>
        <Loader size="sm" />
      </Card>
    );
  }
  const rec = result.recommendation;
  return (
    <Card className={stale ? "is-stale" : undefined} data-testid="recommendation">
      <Group gap="xs" mb="xs">
        <Text fw={600}>Finding</Text>
        <Badge color={rec.status === "recommend" ? "navy" : "orange"} variant="light" radius="sm">
          {rec.status === "recommend" ? "recommendation" : rec.status === "no_clear_winner" ? "no clear winner" : "inconclusive"}
        </Badge>
        {stale && (
          <Badge color="gray" variant="outline" radius="sm">
            for previous settings
          </Badge>
        )}
      </Group>
      <Title order={4} c="navy.9" mb="xs">
        {rec.status === "recommend" && rec.action
          ? `${ACTION_LABEL[rec.action]} leads to the least danger in this simulator.`
          : rec.status === "no_clear_winner"
            ? "No single choice is clearly best under these assumptions."
            : "Not enough simulated evidence to decide."}
      </Title>
      <List fz="sm" spacing={4}>
        {rec.reasons.map((r) => (
          <List.Item key={r}>{r}</List.Item>
        ))}
      </List>
      <Text fz="xs" c="dimmed" mt="sm">
        Rule, fixed before running: {rec.rule}
      </Text>
    </Card>
  );
}

function StressGrid({ stress, coverDelay, policy }: { stress: ChallengeResult; coverDelay: number; policy: AttackerPolicy }) {
  const delays = [...new Set(stress.cells.map((c) => c.cover_delay_s))];
  const policies = [...new Set(stress.cells.map((c) => c.attacker_policy))];
  const at = (d: number, p: AttackerPolicy) => stress.cells.find((c) => c.cover_delay_s === d && c.attacker_policy === p);
  const label = (c: ChallengeCell | undefined) => (!c ? "—" : c.status === "recommend" && c.action ? SHORT[c.action] : c.status === "no_clear_winner" ? "No clear winner" : "Inconclusive");
  return (
    <>
      <Alert color={stress.changed.length ? "orange" : "teal"} variant="light" mb="sm" data-testid="stress-conclusion">
        {stress.conclusion}
      </Alert>
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
