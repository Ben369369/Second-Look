import { Card, Grid, SimpleGrid, Text } from "@mantine/core";
import { AskCard } from "../components/AskCard";
import { PressureChart } from "../components/Charts";
import { FactList } from "../components/FactList";
import { PitchCard } from "../components/PitchCard";
import { StatCard } from "../components/StatCard";
import { useStudio } from "../features/studio";
import { shortPlayer } from "../replay/model";

export function OverviewView() {
  const { packet, lookup, answer } = useStudio();
  const facts = packet?.facts ?? [];
  const max = (metric: string) =>
    facts.filter((f) => f.metric === metric).reduce<(typeof facts)[number] | undefined>((best, f) => (!best || (f.value ?? 0) > (best.value ?? 0) ? f : best), undefined);
  const possession = facts.find((f) => f.metric === "possession_duration");
  const completion = max("pass_completion");
  const longest = max("pass_distance");
  const runner = max("tracked_running");
  const teamName = (id?: string) => (id ? (lookup.teams.get(id)?.name ?? id) : "");
  const ratioDen = completion ? /^of (\d+)/.exec(completion.unit)?.[1] : undefined;

  return (
    <>
      <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }} spacing="md" mb="md">
        <StatCard
          title="Possession spell"
          fact={possession}
          value={possession?.value?.toFixed(1) ?? ""}
          unit="s"
          caption={`${teamName(possession?.subject_ids[0])} kept the ball until the opponent won it`}
        />
        <StatCard
          title="Passes completed"
          fact={completion}
          value={`${completion?.value ?? ""}/${ratioDen ?? ""}`}
          caption={`${teamName(completion?.subject_ids[0])}, whole sequence`}
        />
        <StatCard
          title="Longest pass"
          fact={longest}
          value={longest?.value?.toFixed(1) ?? ""}
          unit="m"
          caption={longest ? `${shortPlayer(lookup, longest.subject_ids[0])} → ${shortPlayer(lookup, longest.subject_ids[1])}` : ""}
        />
        <StatCard
          title="Most ground covered"
          fact={runner}
          value={runner?.value?.toFixed(1) ?? ""}
          unit="m"
          caption={runner ? `${shortPlayer(lookup, runner.subject_ids[0])} over the whole sequence` : ""}
        />
      </SimpleGrid>

      <Grid>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <PitchCard />
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <AskCard />
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Card>
            <Text fw={600}>Pressure distance</Text>
            <Text fz="sm" c="dimmed" mb="md">
              Distance between each presser and the player they closed down, from the recorded tracking. Click the chart to jump
              to that moment.
            </Text>
            <PressureChart />
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 5 }}>
          <Card>
            <Text fw={600}>Evidence</Text>
            <Text fz="sm" c="dimmed" mb="xs">
              {answer ? "Facts behind the current answer. Click a row to see it on the pitch." : "Ask a question to see the facts behind the answer."}
            </Text>
            <FactList facts={answer?.facts ?? []} refused={answer?.refused} empty="No question asked yet." maxHeight={300} />
          </Card>
        </Grid.Col>
      </Grid>
    </>
  );
}
