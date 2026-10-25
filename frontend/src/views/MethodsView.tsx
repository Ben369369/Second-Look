import { Badge, Card, Code, Grid, List, Table, Text, Title } from "@mantine/core";
import { useStudio } from "../features/studio";

const METRICS: [string, string][] = [
  ["pass_distance/1", "Straight line between a pass's recorded start and end points."],
  ["pass_completion/1", "Completed ÷ passes with a known outcome. Passes still in the air at the cutoff are excluded and reported."],
  ["possession_duration/1", "From the first frame a team holds the ball until an opponent holds it. A spell in this sequence, not match possession."],
  ["tracked_running/1", "Sum of frame-to-frame movement. Gaps are not bridged; event-only data is refused."],
  ["defender_distance/1", "Distance between two players on one recorded frame."],
  ["response_time/1", "Time from the carrier's reception until a defender is within 3 m."],
  ["final_third_share/1", "Share of a team's on-ball events starting beyond 70 m in its attacking direction."],
  ["lane_access/1", "Estimate. Can any defender reach a straight passing lane before the ball? See the formula below."],
  ["open_lanes/1", "Estimate. Teammates whose lanes no defender can reach first."],
];

export function MethodsView() {
  const { bundle } = useStudio();
  const m = bundle.manifest;
  return (
    <Grid>
      <Grid.Col span={{ base: 12, lg: 7 }}>
        <Card>
          <Title order={4} c="navy.9" mb="xs">
            How every number is made
          </Title>
          <Text fz="sm" c="dimmed" mb="md">
            Numbers come from code, never from a language model. Each one is labelled by how it was produced.
          </Text>
          <Grid mb="md">
            {[
              ["observed", "navy", "Computed directly from the synthetic recording."],
              ["estimated", "grape", "Output of a stated rule of thumb. Not a measurement, not a probability."],
              ["simulated", "teal", "Results of alternative rollouts (coming in the next stage)."],
            ].map(([k, c, d]) => (
              <Grid.Col key={k} span={{ base: 12, sm: 4 }}>
                <Badge color={c} variant="light" radius="sm" mb={4}>
                  {k}
                </Badge>
                <Text fz="sm">{d}</Text>
              </Grid.Col>
            ))}
          </Grid>
          <Table verticalSpacing={6}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={180}>Method</Table.Th>
                <Table.Th>Definition</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {METRICS.map(([k, d]) => (
                <Table.Tr key={k}>
                  <Table.Td>
                    <Code>{k}</Code>
                  </Table.Td>
                  <Table.Td fz="sm">{d}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Title order={5} c="navy.9" mt="lg" mb="xs">
            Lane-access estimate
          </Title>
          <Code block>
            {`defender_time = 0.25 s + max(0, distance_to_lane − 1.0 m) / 7.0 m/s
ball_time     = distance along lane / 14.0 m/s
margin        = ball_time − defender_time   (> 0: defender gets there first)`}
          </Code>
          <Text fz="sm" c="dimmed" mt="xs">
            The constants are prototype assumptions, not fitted. Margins within about ±0.1 s are effectively a toss-up.
          </Text>
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, lg: 5 }}>
        <Card>
          <Title order={4} c="navy.9" mb="xs">
            This sequence
          </Title>
          <Table verticalSpacing={4} fz="sm">
            <Table.Tbody>
              {[
                ["Scenario", m.scenario_id],
                ["Seed", String(m.seed)],
                ["Tracking", `${m.frame_rate_hz} Hz · ${m.frame_count} frames · ${m.duration_s} s`],
                ["Availability", m.availability],
                ["Generator", m.generator_version],
                ["Dataset hash", m.dataset_hash.slice(0, 23) + "…"],
              ].map(([k, v]) => (
                <Table.Tr key={k}>
                  <Table.Td c="dimmed" w={120}>
                    {k}
                  </Table.Td>
                  <Table.Td className="tabular">{v}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Title order={5} c="navy.9" mt="lg" mb="xs">
            Known limitations
          </Title>
          <List fz="sm" spacing={4}>
            {m.known_limitations.map((l) => (
              <List.Item key={l}>{l}</List.Item>
            ))}
          </List>
        </Card>
      </Grid.Col>
    </Grid>
  );
}
