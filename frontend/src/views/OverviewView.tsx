import { Accordion, Button, Grid, Group, SimpleGrid, Skeleton, Stack, Text, Title } from "@mantine/core";
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ComparisonResult, SimAction } from "../api/types";
import { PressureChart } from "../components/Charts";
import { PitchCard } from "../components/PitchCard";
import { StatCard } from "../components/StatCard";
import { useStudio } from "../features/studio";
import { shortPlayer } from "../replay/model";

const QUESTION = "Should the right-back have pressed earlier?";
const VERB: Record<SimAction, string> = { hold: "holding position", press_earlier: "pressing earlier", press_with_cover: "pressing with cover" };
// The decision rule's per-pair test (same as the backend): a 5-point margin with the paired 95% interval above zero.
const clearPair = (d: ComparisonResult["diffs"][number]) => d.diff >= 0.05 && d.ci95[0] > 0;

/** The press: the disputed decision, the finding in numbers, and the assumption that flips it. */
export function OverviewView({ go }: { go: (v: "investigate" | "whatif") => void }) {
  const { packet, lookup, scenarioId, ask, selectFact, selection } = useStudio();
  const [base, setBase] = useState<ComparisonResult | null>(null);
  const [late, setLate] = useState<ComparisonResult | null>(null);
  const framed = useRef(false);

  // Default assumptions, and the same comparison with the cover arriving late: the flip the page leads with.
  useEffect(() => {
    const ctl = new AbortController();
    api.compare(scenarioId, { cover_delay_s: 0.6, attacker_policy: "patient" }, ctl.signal).then(setBase).catch(() => undefined);
    api.compare(scenarioId, { cover_delay_s: 1.2, attacker_policy: "patient" }, ctl.signal).then(setLate).catch(() => undefined);
    return () => ctl.abort();
  }, [scenarioId]);

  // Open frozen on the moment the ball reached the carrier, with the right-back's measured gap drawn.
  useEffect(() => {
    if (framed.current || selection) return;
    const ctl = new AbortController();
    api
      .ask(scenarioId, QUESTION, null, ctl.signal)
      .then((res) => {
        const gap = res.facts.find((f) => f.metric === "defender_distance");
        if (gap && !framed.current) {
          framed.current = true;
          selectFact(gap);
        }
      })
      .catch(() => undefined);
    return () => ctl.abort();
    // Runs once per page visit; a user's own selection wins.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarioId]);

  const facts = packet?.facts ?? [];
  const max = (metric: string) =>
    facts.filter((f) => f.metric === metric).reduce<(typeof facts)[number] | undefined>((best, f) => (!best || (f.value ?? 0) > (best.value ?? 0) ? f : best), undefined);
  const possession = facts.find((f) => f.metric === "possession_duration");
  const completion = max("pass_completion");
  const longest = max("pass_distance");
  const runner = max("tracked_running");
  const teamName = (id?: string) => (id ? (lookup.teams.get(id)?.name ?? id) : "");
  const ratioDen = completion ? /^of (\d+)/.exec(completion.unit)?.[1] : undefined;

  const count = (r: ComparisonResult, a: SimAction) => r.actions.find((x) => x.action === a)?.danger;
  const early = base && count(base, "press_earlier");
  const hold = base && count(base, "hold");
  const presser = base ? shortPlayer(lookup, base.branch.presser) : "";
  const pairs = base?.diffs.filter((d) => d.metric === "danger") ?? [];
  const open = pairs.filter((d) => !clearPair(d));
  const lateRec = late?.recommendation;
  const holdVsEarly = pairs.find((d) => new Set([d.better, d.other]).has("hold") && new Set([d.better, d.other]).has("press_earlier"));
  // Only a pair that clears the predeclared rule gets the mark.
  const safer = holdVsEarly && clearPair(holdVsEarly) ? holdVsEarly.better : null;

  return (
    <Stack gap="xl">
      <Grid gap={{ base: "lg", lg: 40 }} align="flex-start">
        <Grid.Col span={{ base: 12, lg: 5 }} data-testid="hero">
          <Text className="kicker kicker-sim" mb={10}>
            Simulated · {base ? `${base.config.rollouts} replays per choice` : "replaying the next 8 seconds"} · lower is safer
          </Text>
          <Title order={1} c="navy.9" className="page-title" mb="lg">
            {QUESTION}
          </Title>
          {base && late && early && hold ? (
            <>
              <Text className="verdict" data-testid="hero-verdict">
                {holdVsEarly && clearPair(holdVsEarly)
                  ? holdVsEarly.better === "hold"
                    ? "No. Holding was safer."
                    : "Yes. Pressing earlier was safer."
                  : "Too close to call."}
              </Text>
              <Group gap={28} align="flex-end" mt="md" wrap="nowrap" data-testid="hero-number">
                <div className={`duel${safer === "hold" ? " duel-safe" : ""}`}>
                  <div className="big-number">{hold.count}</div>
                  <Text fz="sm" fw={600} c={safer === "hold" ? "navy.9" : "dimmed"}>
                    holds position
                  </Text>
                </div>
                <Text fz="lg" c="dimmed" pb={22}>
                  vs
                </Text>
                <div className={`duel${safer === "press_earlier" ? " duel-safe" : ""}`}>
                  <div className="big-number">{early.count}</div>
                  <Text fz="sm" fw={600} c={safer === "press_earlier" ? "navy.9" : "dimmed"}>
                    presses earlier
                  </Text>
                </div>
              </Group>
              <Text className="finding" mt="md">
                Harbor reach a dangerous position in {hold.count} of {hold.n} replays when {presser} holds, and in {early.count} when he presses
                earlier.
              </Text>
              <Text className="finding" mt="md" data-testid="hero-flip">
                {open.length
                  ? `With a teammate covering at ${base.config.cover_delay_s.toFixed(1)} s, ${open
                      .map((d) => `${VERB[d.better]} versus ${VERB[d.other]}`)
                      .join(" and ")} is too close to call.`
                  : base.recommendation.status === "recommend" && base.recommendation.action
                    ? `At a ${base.config.cover_delay_s.toFixed(1)} s cover delay the rule picks ${VERB[base.recommendation.action]}.`
                    : ""}{" "}
                {lateRec && late
                  ? lateRec.status === "recommend" && lateRec.action
                    ? `Make the cover arrive at ${late.config.cover_delay_s.toFixed(1)} s and ${VERB[lateRec.action]} becomes the clear call.`
                    : `With the cover at ${late.config.cover_delay_s.toFixed(1)} s there is still no clear call.`
                  : ""}
              </Text>
              <Text fz="xs" c="dimmed" mt="md" maw={460}>
                Counts from a rule-based simulator of this synthetic move, not a prediction. A choice wins only if it leads by 5 points and the
                95% interval clears zero.
              </Text>
            </>
          ) : (
            <Stack gap="sm">
              <Skeleton h={56} w={220} />
              <Skeleton h={18} />
              <Skeleton h={18} w="80%" />
            </Stack>
          )}
          <Group gap="sm" mt="xl">
            <Button
              onClick={() => {
                ask(QUESTION);
                go("investigate");
              }}
              data-testid="hero-investigate"
            >
              Investigate this decision
            </Button>
            <Button variant="default" onClick={() => go("whatif")} data-testid="hero-choices">
              Change the assumptions
            </Button>
          </Group>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <PitchCard title="The moment" />
        </Grid.Col>
      </Grid>

      <Accordion variant="default" chevronPosition="left">
        <Accordion.Item value="more" style={{ borderTop: "1px solid var(--sheet-rule)" }}>
          <Accordion.Control data-testid="more-toggle">
            <Text fw={600}>Also in this passage</Text>
          </Accordion.Control>
          <Accordion.Panel>
            <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }} spacing="lg" mb="xl">
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
            <Text fw={600}>Pressure distance</Text>
            <Text fz="sm" c="dimmed" mb="md">
              Distance between each presser and the player they closed down, from the recorded tracking. Click the chart to jump to that
              moment.
            </Text>
            <PressureChart />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}
