import { Alert, Badge, Button, Card, Group, SegmentedControl, Stack, Text, TextInput, UnstyledButton } from "@mantine/core";
import { IconInfoCircle, IconSearch } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import type { AskResponse } from "../api/types";
import { type CutoffMode, useStudio } from "../features/studio";
import { formatClock } from "../replay/model";

const STATUS: Record<AskResponse["status"], { label: string; color: string }> = {
  answered: { label: "Answered", color: "teal" },
  unsupported: { label: "Unsupported", color: "red" },
  clarify: { label: "Needs clarification", color: "orange" },
  insufficient_data: { label: "Insufficient data", color: "red" },
};

/** Ask box, suggestions and the answer. `seed` pre-fills the box (e.g. from the header search). */
export function AskCard({ seed, showSuggestions = true }: { seed?: string; showSuggestions?: boolean }) {
  const { bundle, questions, answer: a, askPending, askError, ask, cutoffMode, setCutoffMode, playback, selectFact } = useStudio();
  const [text, setText] = useState(seed ?? "");
  useEffect(() => {
    if (seed) setText(seed);
  }, [seed]);
  const offset = bundle.manifest.match_clock_offset_s;
  const submit = (q: string) => q.trim() && ask(q.trim());
  const factIndex = new Map(a?.facts.map((f, i) => [f.fact_id, i]) ?? []);
  const stale = a !== null && cutoffMode === "replay" && playback.t + 0.05 < a.cursor_s;

  return (
    <Card>
      <Group justify="space-between" mb="sm">
        <Text fw={600}>Ask Second Look</Text>
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
          <Group gap={6}>
            <Badge color={STATUS[a.status].color} variant="light" radius="sm">
              {STATUS[a.status].label}
            </Badge>
            {a.intent_label && (
              <Badge color="gray" variant="outline" radius="sm">
                {a.intent_label}
              </Badge>
            )}
            <Badge color="gray" variant="outline" radius="sm" title="Offline mode: matched by fixed keyword rules, not a language model">
              Rule-matched
            </Badge>
            <Badge color="gray" variant="outline" radius="sm" className="tabular">
              Data to {formatClock(offset + a.cursor_s)}
            </Badge>
          </Group>
          <Text fz="sm" c="dimmed" fs="italic">
            “{a.question}”
          </Text>
          {stale && (
            <Alert color="orange" variant="light" p="xs" data-testid="stale-warning">
              Computed with data up to {formatClock(offset + a.cursor_s)}, after the current replay position. Ask again to update.
            </Alert>
          )}
          {a.answer.length > 0 && (
            <ol className="sentences">
              {a.answer.map((s, i) => (
                <li key={i}>
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
            <Alert key={n} color="navy" variant="light" p="xs" icon={<IconInfoCircle size={16} />}>
              <Text fz="sm">{n}</Text>
            </Alert>
          ))}
        </Stack>
      )}
    </Card>
  );
}
