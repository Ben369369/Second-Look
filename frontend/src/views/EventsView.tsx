import { Card, Grid, Group, SegmentedControl, Text } from "@mantine/core";
import { useState } from "react";
import type { MatchEvent } from "../api/types";
import { EventLog } from "../components/EventLog";
import { PitchCard } from "../components/PitchCard";
import { useStudio } from "../features/studio";

const FILTERS: Record<string, MatchEvent["type"][] | null> = {
  all: null,
  passing: ["pass", "reception", "carry"],
  pressure: ["pressure_start", "pressure_end"],
  shots: ["shot"],
};

export function EventsView() {
  const { bundle } = useStudio();
  const [filter, setFilter] = useState("all");
  const types = FILTERS[filter];
  const events = types ? bundle.events.filter((e) => types.includes(e.type)) : bundle.events;
  return (
    <Grid>
      <Grid.Col span={{ base: 12, lg: 6 }}>
        <Card>
          <Group justify="space-between" mb="sm" wrap="wrap">
            <div>
              <Text fw={600}>Recorded events</Text>
              <Text fz="sm" c="dimmed">
                {events.length} of {bundle.events.length} events. Click one to jump there.
              </Text>
            </div>
            <SegmentedControl
              size="xs"
              value={filter}
              onChange={setFilter}
              data={[
                { value: "all", label: "All" },
                { value: "passing", label: "Passing" },
                { value: "pressure", label: "Pressure" },
                { value: "shots", label: "Shots" },
              ]}
              aria-label="Event filter"
            />
          </Group>
          <EventLog events={events} maxHeight={600} />
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, lg: 6 }}>
        <PitchCard />
      </Grid.Col>
    </Grid>
  );
}
