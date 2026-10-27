import { Card, Grid, Tabs, Text } from "@mantine/core";
import { AskCard } from "../components/AskCard";
import { FactList } from "../components/FactList";
import { PitchCard } from "../components/PitchCard";
import { useStudio } from "../features/studio";

export function InvestigateView() {
  const { answer, packet } = useStudio();
  return (
    <Grid>
      <Grid.Col span={{ base: 12, lg: 7 }}>
        <PitchCard />
      </Grid.Col>
      <Grid.Col span={{ base: 12, lg: 5 }}>
        <AskCard />
      </Grid.Col>
      <Grid.Col span={12}>
        <Card>
          <Tabs defaultValue="answer">
            <Tabs.List mb="sm">
              <Tabs.Tab value="answer">Evidence {answer ? `(${answer.facts.length})` : ""}</Tabs.Tab>
              <Tabs.Tab value="all">All facts {packet ? `(${packet.facts.length})` : ""}</Tabs.Tab>
            </Tabs.List>
            <Tabs.Panel value="answer">
              <FactList facts={answer?.facts ?? []} empty="Ask a question to see the evidence behind the answer." />
            </Tabs.Panel>
            <Tabs.Panel value="all">
              <Text fz="sm" c="dimmed" mb="xs">
                Every fact computable from the whole recorded sequence.
              </Text>
              <FactList facts={packet?.facts ?? []} refused={packet?.refused} empty="Loading facts…" maxHeight={480} />
            </Tabs.Panel>
          </Tabs>
        </Card>
      </Grid.Col>
    </Grid>
  );
}
