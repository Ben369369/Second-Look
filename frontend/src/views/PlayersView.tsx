import { Badge, Card, Grid, Group, SegmentedControl, Table, Text } from "@mantine/core";
import { useMemo, useState } from "react";
import { SpeedChart } from "../components/Charts";
import { PitchCard } from "../components/PitchCard";
import { speedSeries } from "../features/series";
import { useStudio } from "../features/studio";

type Sort = "distance" | "speed" | "number";

export function PlayersView() {
  const { bundle, packet, selection, selectPlayer } = useStudio();
  const [team, setTeam] = useState("all");
  const [sort, setSort] = useState<Sort>("distance");
  const selected = selection?.kind === "player" ? selection.playerId : null;

  const rows = useMemo(() => {
    const dist = new Map((packet?.facts ?? []).filter((f) => f.metric === "tracked_running").map((f) => [f.subject_ids[0], f.value ?? 0]));
    return bundle.manifest.teams.flatMap((t) =>
      t.players.map((p) => ({
        ...p,
        team: t,
        distance: dist.get(p.player_id),
        topSpeed: Math.max(0, ...speedSeries(bundle, p.player_id).map((s) => s.speed)),
      })),
    );
  }, [bundle, packet]);

  const shown = rows
    .filter((r) => team === "all" || r.team_id === team)
    .sort((a, b) => (sort === "number" ? a.number - b.number : sort === "speed" ? b.topSpeed - a.topSpeed : (b.distance ?? 0) - (a.distance ?? 0)));
  const focus = rows.find((r) => r.player_id === selected);

  return (
    <Grid>
      <Grid.Col span={{ base: 12, lg: 6 }}>
        <Card>
          <Group justify="space-between" mb="sm" wrap="wrap">
            <div>
              <Text fw={600}>Players</Text>
              <Text fz="sm" c="dimmed">
                Click a player to trace their run on the pitch.
              </Text>
            </div>
            <Group gap="xs">
              <SegmentedControl
                size="xs"
                value={team}
                onChange={setTeam}
                data={[{ value: "all", label: "All" }, ...bundle.manifest.teams.map((t) => ({ value: t.team_id, label: t.short_name }))]}
                aria-label="Team filter"
              />
              <SegmentedControl
                size="xs"
                value={sort}
                onChange={(v) => setSort(v as Sort)}
                data={[
                  { value: "distance", label: "Distance" },
                  { value: "speed", label: "Speed" },
                  { value: "number", label: "No." },
                ]}
                aria-label="Sort by"
              />
            </Group>
          </Group>
          <Table.ScrollContainer minWidth={440} maxHeight={560}>
            <Table highlightOnHover stickyHeader verticalSpacing={6}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={64}>No.</Table.Th>
                  <Table.Th>Player</Table.Th>
                  <Table.Th w={76}>Role</Table.Th>
                  <Table.Th ta="right">Distance</Table.Th>
                  <Table.Th ta="right">Top speed</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {shown.map((r) => (
                  <Table.Tr
                    key={r.player_id}
                    className={`clickable${r.player_id === selected ? " row-selected" : ""}`}
                    onClick={() => selectPlayer(r.player_id === selected ? null : r.player_id)}
                    tabIndex={0}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), selectPlayer(r.player_id))}
                    data-testid={`player-${r.player_id}`}
                  >
                    <Table.Td style={{ whiteSpace: "nowrap" }}>
                      <span className={`swatch${r.team.marker_shape === "circle" ? " shape-circle" : ""}`} style={{ background: r.team.color }} /> {r.number}
                    </Table.Td>
                    <Table.Td fw={500}>
                      {r.name} <Text span c="dimmed" fz="xs">{r.team.short_name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge size="sm" variant="light" color="gray" radius="sm">
                        {r.role}
                      </Badge>
                    </Table.Td>
                    <Table.Td ta="right" className="tabular">
                      {r.distance !== undefined ? `${r.distance.toFixed(1)} m` : "—"}
                    </Table.Td>
                    <Table.Td ta="right" className="tabular">
                      {r.topSpeed.toFixed(1)} m/s
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Text fz="xs" c="dimmed" mt="xs">
            Observed from synthetic tracking at 10 Hz. Distance is the sum of frame-to-frame displacement; speed is per 0.1 s interval.
          </Text>
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, lg: 6 }}>
        <PitchCard title={focus ? `${focus.name}'s run` : "Replay"} compact />
        <Card mt="md">
          <Text fw={600}>{focus ? `Speed: #${focus.number} ${focus.name}` : "Speed"}</Text>
          <Text fz="sm" c="dimmed" mb="md">
            {focus ? "Click the chart to jump to that moment." : "Select a player to see their speed over the sequence."}
          </Text>
          {focus ? <SpeedChart playerId={focus.player_id} /> : <div className="chart-placeholder" />}
        </Card>
      </Grid.Col>
    </Grid>
  );
}
