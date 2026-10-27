import { Group, Paper, Text, UnstyledButton } from "@mantine/core";
import type { Fact } from "../api/types";
import { useStudio } from "../features/studio";

interface Props {
  title: string;
  fact: Fact | undefined;
  value: string;
  unit?: string;
  caption: string;
}

/** KPI tile backed by a real fact; clicking it shows the fact on the pitch. */
export function StatCard({ title, fact, value, unit, caption }: Props) {
  const { selectFact, selection } = useStudio();
  const active = fact && selection?.kind === "fact" && selection.fact.fact_id === fact.fact_id;
  return (
    <UnstyledButton
      onClick={() => fact && selectFact(fact)}
      disabled={!fact}
      className="stat-button"
      aria-label={fact ? `${title}: ${fact.statement} Show on pitch.` : `${title}: not available`}
      data-testid={`stat-${fact?.metric ?? "missing"}`}
    >
      <Paper py="md" className={`stat-card${active ? " stat-active" : ""}`}>
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Text fz="sm" fw={600} c="navy.9">
            {title}
          </Text>
          {fact && (
            <Text className={`kicker ${fact.evidence_class === "simulated" ? "kicker-sim" : "kicker-obs"}`} fz={11}>
              {fact.evidence_class}
            </Text>
          )}
        </Group>
        <Group gap={6} align="baseline" mt="md">
          <Text fz={28} fw={700} c="navy.9" className="tabular">
            {fact ? value : "—"}
          </Text>
          {unit && fact && (
            <Text fz="sm" c="dimmed">
              {unit}
            </Text>
          )}
        </Group>
        <Text fz="xs" c="dimmed" mt={4} lineClamp={2}>
          {fact ? caption : "Not available for this sequence"}
        </Text>
      </Paper>
    </UnstyledButton>
  );
}
