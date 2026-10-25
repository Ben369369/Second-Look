import { Badge, Card, Group, Switch, Text } from "@mantine/core";
import { useStudio } from "../features/studio";
import { formatClock, playerLabel, shortPlayer, stateAt } from "../replay/model";
import { PitchCanvas } from "../replay/PitchCanvas";
import { PlaybackControls } from "./PlaybackControls";

export function PitchCard({ title = "Replay", compact = false }: { title?: string; compact?: boolean }) {
  const { bundle, lookup, playback, highlight, annotation, selection, showGrid, setShowGrid } = useStudio();
  const { manifest, frames } = bundle;
  const [home, away] = manifest.teams;
  const offset = manifest.match_clock_offset_s;
  const state = stateAt(frames, playback.t);
  const frame = frames[state.frameIndex];
  const caption = `${formatClock(offset + playback.t)}, ${state.possession ? `${playerLabel(lookup, state.possession)} on the ball` : "ball in play, no player in possession"}`;
  const label = `Synthetic replay, frame ${frame.frame_id} of ${manifest.frame_count - 1}. ${caption}. ${home.name} (circles) defend the right-hand goal; ${away.name} (squares) attack it.${selection?.kind === "fact" ? ` Showing: ${selection.fact.statement}` : ""}`;

  return (
    <Card className="pitch-card">
      <Group justify="space-between" mb="xs" wrap="nowrap">
        <Group gap="sm" wrap="nowrap">
          <Text fw={600}>{title}</Text>
          <Badge variant="light" color="gray" radius="sm" className="tabular" data-testid="caption">
            F{String(frame.frame_id).padStart(3, "0")}
          </Badge>
          <Text fz="sm" c="dimmed" visibleFrom="sm">
            {state.possession ? `${shortPlayer(lookup, state.possession)} on the ball` : "Ball in play"}
          </Text>
        </Group>
        <Group gap="md" wrap="nowrap">
          <Group gap={6} visibleFrom="sm">
            <span className="swatch shape-circle" style={{ background: home.color }} />
            <Text fz="sm">{home.name}</Text>
            <span className="swatch" style={{ background: away.color }} />
            <Text fz="sm">{away.name}</Text>
          </Group>
          <Switch size="xs" label="Grid" checked={showGrid} onChange={(e) => setShowGrid(e.currentTarget.checked)} />
        </Group>
      </Group>
      <PitchCanvas bundle={bundle} lookup={lookup} t={playback.t} highlight={highlight} annotation={annotation} showGrid={showGrid} label={label} />
      <p className="sr-only" aria-live="polite">
        {playback.playing ? "" : caption}
      </p>
      {selection?.kind === "fact" && (
        <Group gap="xs" mt="xs" wrap="nowrap" align="flex-start" data-testid="selected-fact" className="telestration">
          <Badge variant="light" color={selection.fact.evidence_class === "observed" ? "navy" : "grape"} radius="sm" style={{ flex: "none" }}>
            {selection.fact.evidence_class}
          </Badge>
          <Text fz="sm">{selection.fact.statement}</Text>
        </Group>
      )}
      <PlaybackControls compact={compact} />
    </Card>
  );
}
