import { Alert, Badge, Button, Card, Grid, Group, Loader, Stack, Table, Text, Title } from "@mantine/core";
import { IconDownload, IconPlayerPlayFilled } from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ExportBundle, OverlayCue } from "../api/types";
import { PlaybackControls } from "../components/PlaybackControls";
import { useStudio } from "../features/studio";
import { formatClock } from "../replay/model";
import { PitchCanvas } from "../replay/PitchCanvas";

const HERO = "Should the right-back have pressed earlier?";

/** Recap plan and a live preview of the exported overlay cues over the recorded replay. */
export function RecapView() {
  const { bundle, lookup, playback, answer, ask, askPending, showGrid } = useStudio();
  const [exp, setExp] = useState<ExportBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const offset = bundle.manifest.match_clock_offset_s;

  useEffect(() => {
    setExp(null);
    setError(null);
    if (!answer || answer.status !== "complete") return;
    const ctl = new AbortController();
    api
      .exportInvestigation(answer.investigation_id, ctl.signal)
      .then(setExp)
      .catch((err) => err.name !== "AbortError" && setError(err instanceof ApiError ? err.message : String(err)));
    return () => ctl.abort();
  }, [answer]);

  const t = playback.t;
  const active: OverlayCue | undefined = exp?.cues.find((c) => t >= c.start_s && t < c.start_s + c.duration_s);
  const highlight = useMemo(() => new Set(active?.highlighted_player_ids ?? []), [active]);

  const playRecap = () => {
    playback.reset();
    playback.setSpeed(exp?.playback_rate ?? 0.5);
    playback.play();
  };

  const download = () => {
    if (!exp) return;
    const blob = new Blob([JSON.stringify(exp, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `second-look-overlay-${exp.investigation_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!answer) {
    return (
      <Card>
        <Title order={4} c="navy.9" mb="xs">
          No recap yet
        </Title>
        <Text c="dimmed" mb="md">
          A recap is built from an answered question: 2–4 approved insights, each timed to the moment of the replay it describes.
        </Text>
        <Button onClick={() => ask(HERO)} loading={askPending} data-testid="build-recap">
          Build a recap for “{HERO}”
        </Button>
      </Card>
    );
  }

  return (
    <Grid>
      <Grid.Col span={{ base: 12, lg: 8 }}>
        <Card>
          <Group justify="space-between" mb="xs" wrap="wrap">
            <Group gap="xs">
              <Text fw={600}>Overlay preview</Text>
              <Badge variant="light" color="gray" radius="sm">
                synthetic replay + exported cues
              </Badge>
            </Group>
            <Button size="xs" leftSection={<IconPlayerPlayFilled size={14} />} onClick={playRecap} disabled={!exp} data-testid="play-recap">
              Play recap ({exp ? `${exp.recap_duration_s.toFixed(0)} s at ${exp.playback_rate}×` : "…"})
            </Button>
          </Group>
          <div className="overlay-stage">
            <PitchCanvas
              bundle={bundle}
              lookup={lookup}
              t={t}
              highlight={highlight}
              annotation={null}
              showGrid={showGrid}
              label={`Recap preview at ${formatClock(offset + t)}. ${active ? `${active.title}: ${active.body}` : "No overlay on screen."}`}
            />
            {active && (
              <div className={`overlay-card overlay-${active.graphic_type}`} data-testid="active-cue" aria-live="polite">
                <Group gap={6} mb={4}>
                  <Badge size="sm" radius="sm" color={active.branch === "simulated" ? "teal" : "navy"} variant="filled">
                    {active.branch === "simulated" ? "SIMULATION" : active.evidence_class}
                  </Badge>
                  <Text fw={700} fz="sm" c="white">
                    {active.title}
                  </Text>
                </Group>
                {active.body.split("\n").map((line) => (
                  <Text key={line} fz="sm" c="white" lh={1.35} mb={2}>
                    {line}
                  </Text>
                ))}
                {active.branch === "simulated" && active.assumptions_summary && (
                  <Text fz="xs" c="gray.3" mt={4}>
                    {active.assumptions_summary}
                  </Text>
                )}
              </div>
            )}
          </div>
          <PlaybackControls />
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, lg: 4 }}>
        <Card>
          <Text fw={600}>Recap</Text>
          <Text fz="sm" c="dimmed" mb="sm">
            “{answer.question}” · {answer.audience === "casual" ? "fan view" : "analyst view"} · {answer.provider_label}
          </Text>
          {error && <Alert color="red">{error}</Alert>}
          {!exp && !error && <Loader size="sm" />}
          {exp && (
            <Stack gap="sm">
              {exp.insights.map((ins) => {
                const cue = exp.cues.find((c) => c.cue_id === ins.cue_id)!;
                return (
                  <div key={ins.cue_id} className={`recap-item${active?.cue_id === cue.cue_id ? " recap-active" : ""}`}>
                    <Group gap={6} mb={2}>
                      <Badge size="xs" radius="sm" variant="light" color={cue.branch === "simulated" ? "teal" : "navy"}>
                        {ins.order} · {cue.branch === "simulated" ? "simulation" : cue.evidence_class}
                      </Badge>
                      <Text fz="xs" c="dimmed" className="tabular">
                        {formatClock(offset + cue.start_s)}–{formatClock(offset + cue.start_s + cue.duration_s)}
                      </Text>
                    </Group>
                    {ins.claims.map((c) => (
                      <Text key={c.text} fz="sm">
                        {c.text}
                      </Text>
                    ))}
                  </div>
                );
              })}
              <Button variant="light" leftSection={<IconDownload size={16} />} onClick={download} data-testid="download-overlay">
                Download overlay JSON
              </Button>
              <Text fz="xs" c="dimmed">
                {exp.schema_version} · timebase {exp.timebase} · {exp.cues.length} cues · every cue cites approved facts; simulated cards are labelled.
              </Text>
            </Stack>
          )}
        </Card>
      </Grid.Col>
      {exp && (
        <Grid.Col span={12}>
          <Card>
            <Text fw={600} mb="xs">
              Cue timeline (exported)
            </Text>
            <Table.ScrollContainer minWidth={640}>
              <Table verticalSpacing={5} fz="sm" data-testid="cue-table">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Start</Table.Th>
                    <Table.Th>End</Table.Th>
                    <Table.Th>Branch</Table.Th>
                    <Table.Th>Graphic</Table.Th>
                    <Table.Th>Title</Table.Th>
                    <Table.Th>Facts</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {exp.cues.map((c) => (
                    <Table.Tr key={c.cue_id} className={`clickable${active?.cue_id === c.cue_id ? " row-selected" : ""}`} onClick={() => playback.seek(c.start_s + 0.05)}>
                      <Table.Td className="tabular">{c.start_s.toFixed(1)} s</Table.Td>
                      <Table.Td className="tabular">{(c.start_s + c.duration_s).toFixed(1)} s</Table.Td>
                      <Table.Td>{c.branch}</Table.Td>
                      <Table.Td>{c.graphic_type}</Table.Td>
                      <Table.Td>{c.title}</Table.Td>
                      <Table.Td className="tabular">{c.fact_ids.length}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          </Card>
        </Grid.Col>
      )}
    </Grid>
  );
}
