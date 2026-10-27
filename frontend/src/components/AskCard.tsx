import { Accordion, Alert, Badge, Button, Card, Group, Loader, SegmentedControl, Stack, Text, TextInput, UnstyledButton } from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import type { ClaimType, InvestigationState, TraceStep } from "../api/types";
import { type Audience, type CutoffMode, useStudio } from "../features/studio";
import { formatClock } from "../replay/model";

const STATUS: Record<NonNullable<InvestigationState["outcome"]>, { label: string; color: string }> = {
  answered: { label: "Answered", color: "teal" },
  unsupported: { label: "Unsupported", color: "red" },
  clarify: { label: "Needs clarification", color: "orange" },
  insufficient_data: { label: "Insufficient data", color: "red" },
};

/** Ask box, suggestions and the answer. `seed` pre-fills the box (e.g. from the header search). */
export function AskCard({ seed, showSuggestions = true }: { seed?: string; showSuggestions?: boolean }) {
  const { bundle, questions, answer: a, askPending, askError, ask, cutoffMode, setCutoffMode, audience, setAudience, playback, selectFact } =
    useStudio();
  const [text, setText] = useState(seed ?? "");
  useEffect(() => {
    if (seed) setText(seed);
  }, [seed]);
  const offset = bundle.manifest.match_clock_offset_s;
  const submit = (q: string) => q.trim() && ask(q.trim());
  const factIndex = new Map(a?.facts.map((f, i) => [f.fact_id, i]) ?? []);
  const stale = a !== null && cutoffMode === "replay" && playback.t + 0.05 < a.cursor_s;
  const casual = audience === "casual";
  // Both views come from the same investigation; switching never re-runs it.
  const shown = a ? (casual && a.casual_claims?.length ? a.casual_claims : a.claims) : [];

  return (
    <Card>
      <Group justify="space-between" mb="sm" gap="xs">
        <Text fw={600}>Ask Second Look</Text>
        <SegmentedControl
          size="xs"
          value={audience}
          onChange={(v) => setAudience(v as Audience)}
          data={[
            { value: "casual", label: "Fan view" },
            { value: "analyst", label: "Analyst view" },
          ]}
          aria-label="Audience"
          data-testid="audience"
        />
      </Group>
      <Group justify="flex-end" mb="sm">
        <SegmentedControl
          size="xs"
          value={cutoffMode}
          onChange={(v) => setCutoffMode(v as CutoffMode)}
          data={[
            { value: "sequence", label: "Whole sequence" },
            { value: "replay", label: "Up to replay" },
          ]}
          aria-label="Data cutoff"
          data-testid="cutoff-mode"
        />
      </Group>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(text);
        }}
      >
        <Group gap="xs" wrap="nowrap">
          <TextInput
            value={text}
            onChange={(e) => setText(e.currentTarget.value)}
            placeholder="e.g. Should the right-back have pressed earlier?"
            aria-label="Question"
            maxLength={300}
            leftSection={<IconSearch size={16} />}
            style={{ flex: 1 }}
            data-testid="question-input"
          />
          <Button type="submit" loading={askPending} data-testid="ask">
            Ask
          </Button>
        </Group>
      </form>
      {showSuggestions && (
        <Group gap={6} mt="sm">
          {questions.map((q) => (
            <Button
              key={q.intent}
              size="compact-xs"
              variant="light"
              radius="xl"
              onClick={() => {
                setText(q.example);
                submit(q.example);
              }}
              data-testid={`suggest-${q.intent}`}
            >
              {q.label}
            </Button>
          ))}
        </Group>
      )}

      {askError && (
        <Alert color="red" mt="md" title="Could not answer">
          {askError}
        </Alert>
      )}
      {a && (
        <Stack gap="xs" mt="md" className="answer" aria-live="polite" data-testid="answer">
          <Group gap={8} wrap="wrap">
            {a.outcome ? (
              <Text fz="sm" fw={600} c={STATUS[a.outcome].color === "teal" ? "navy.9" : `${STATUS[a.outcome].color}.8`}>
                {STATUS[a.outcome].label}
              </Text>
            ) : (
              <Group gap={6}>
                <Loader size={12} />
                <Text fz="sm" fw={600} c="navy.9">
                  {a.status}…
                </Text>
              </Group>
            )}
            <Text fz="sm" c="dimmed" className="tabular">
              {[a.intent_label, `data to ${formatClock(offset + a.cursor_s)}`].filter(Boolean).join(" · ")}
            </Text>
            <ProviderBadge a={a} />
          </Group>
          <Text fz="sm" c="dimmed" fs="italic">
            “{a.question}”
          </Text>
          {stale && (
            <Alert color="orange" variant="light" p="xs" data-testid="stale-warning">
              Computed with data up to {formatClock(offset + a.cursor_s)}, after the current replay position. Ask again to update.
            </Alert>
          )}
          {shown.length > 0 && casual && (
            <Stack gap={8} className="casual" data-testid="casual-claims">
              {shown
                .filter((c) => c.claim_type !== "interpretation")
                .map((s, i) => {
                  const f = s.fact_ids.map((id) => a.facts.find((x) => x.fact_id === id)).find(Boolean);
                  return (
                    <Text key={i} fz="md" lh={1.45}>
                      <span className="kicker" style={{ fontSize: 10.5, marginRight: 6, color: `var(--mantine-color-${CLAIM_COLOR[s.claim_type]}-8)` }}>
                        {PLAIN_KIND[s.claim_type]}
                      </span>
                      {s.text}{" "}
                      {f && (
                        <UnstyledButton className="ref" onClick={() => selectFact(f)}>
                          show me
                        </UnstyledButton>
                      )}
                    </Text>
                  );
                })}
              {shown
                .filter((c) => c.claim_type === "interpretation")
                .map((s, i) => (
                  <Text key={`i${i}`} fz="sm" c="dimmed" fs="italic">
                    {s.text}
                  </Text>
                ))}
            </Stack>
          )}
          {shown.length > 0 && !casual && (
            <ol className="sentences">
              {shown.map((s, i) => (
                <li key={i} className={`claim claim-${s.claim_type}`}>
                  <span className="kicker" style={{ fontSize: 10.5, marginRight: 6, color: `var(--mantine-color-${CLAIM_COLOR[s.claim_type]}-8)` }}>
                    {s.claim_type.replace("_", " ")}
                  </span>
                  {s.text}{" "}
                  {s.fact_ids.map((id) => {
                    const idx = factIndex.get(id);
                    return idx === undefined ? null : (
                      <UnstyledButton key={id} className="ref" onClick={() => selectFact(a.facts[idx])} aria-label={`Show fact ${idx + 1} on the pitch`}>
                        [{idx + 1}]
                      </UnstyledButton>
                    );
                  })}
                </li>
              ))}
            </ol>
          )}
          {a.notes.map((n) => (
            <Text key={n} fz="sm" c="dimmed">
              {n}
            </Text>
          ))}
          {a.challenge_summary && (
            <Text fz="sm">
              <Text span fw={600} c="navy.9">
                Challenger:{" "}
              </Text>
              {a.challenge_summary}
            </Text>
          )}
          <Trace a={a} />
        </Stack>
      )}
    </Card>
  );
}

const PLAIN_KIND: Record<ClaimType, string> = {
  observed: "measured",
  estimated: "estimate",
  simulated: "simulation",
  interpretation: "note",
  insufficient_data: "missing data",
};

const CLAIM_COLOR: Record<ClaimType, string> = {
  observed: "navy",
  estimated: "grape",
  simulated: "cyan",
  interpretation: "gray",
  insufficient_data: "orange",
};

function ProviderBadge({ a }: { a: InvestigationState }) {
  if (a.provider_mode === "foundry_local")
    return (
      <Badge color="navy" variant="filled" radius="sm" title={a.provider_label} data-testid="answer-provider">
        AI agents · on-device · {a.model_deployment}
      </Badge>
    );
  if (a.provider_mode === "foundry")
    return (
      <Badge color="navy" variant="filled" radius="sm" title={a.provider_label} data-testid="answer-provider">
        AI agents · {a.model_deployment}
      </Badge>
    );
  if (a.provider_mode === "fallback")
    return (
      <Badge color="orange" variant="filled" radius="sm" title={a.provider_label} data-testid="answer-provider">
        Fallback · templates
      </Badge>
    );
  return (
    <Badge color="gray" variant="outline" radius="sm" title="Offline mode: matched by fixed keyword rules, not a language model" data-testid="answer-provider">
      Rule-matched
    </Badge>
  );
}

const KIND_COLOR: Record<TraceStep["kind"], string> = {
  model: "navy",
  tool: "teal",
  validation: "grape",
  repair: "orange",
  fallback: "orange",
  error: "red",
  rule: "gray",
};

/** How the answer was produced: agent steps, tool calls, validation. No hidden reasoning is shown. */
function Trace({ a }: { a: InvestigationState }) {
  if (a.trace.length === 0) return null;
  const tokens = a.input_tokens !== null || a.output_tokens !== null ? ` · ${a.input_tokens ?? 0} in / ${a.output_tokens ?? 0} out tokens` : "";
  return (
    <Accordion variant="contained" radius="md" mt={4}>
      <Accordion.Item value="trace">
        <Accordion.Control data-testid="trace-toggle">
          <Text fz="sm" fw={600}>
            How this answer was made
          </Text>
          <Text fz="xs" c="dimmed">
            {a.provider_label} · {a.model_calls} model calls · {a.tool_calls} tool calls{tokens} · {(a.elapsed_ms / 1000).toFixed(1)} s
            {a.rejected_claims.length > 0 && ` · ${a.rejected_claims.length} claim(s) rejected by validation`}
          </Text>
        </Accordion.Control>
        <Accordion.Panel>
          <ol className="trace" data-testid="trace">
            {a.trace.map((t, i) => (
              <li key={i}>
                <Badge size="xs" radius="sm" variant="light" color={KIND_COLOR[t.kind]} mr={6}>
                  {t.kind}
                </Badge>
                <Text span fw={600} fz="sm">
                  {t.agent}
                </Text>
                {t.tool && (
                  <Text span fz="sm" c="teal.8" ff="monospace">
                    {" "}
                    {t.tool}()
                  </Text>
                )}
                <Text span fz="sm" c="dimmed">
                  {" "}
                  — {t.summary}
                  {t.duration_ms > 0 && ` (${t.duration_ms} ms)`}
                </Text>
              </li>
            ))}
          </ol>
          {a.rejected_claims.map((r, i) => (
            <Alert key={i} color="red" variant="light" p="xs" mt="xs" title="Rejected claim (not shown in the answer)">
              <Text fz="sm" fs="italic">
                “{r.claim.text}”
              </Text>
              <Text fz="xs">{r.errors.join("; ")}</Text>
            </Alert>
          ))}
          {a.errors.length > 0 && (
            <Text fz="xs" c="red.8" mt="xs">
              {a.errors.join(" · ")}
            </Text>
          )}
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
