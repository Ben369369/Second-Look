import { ActionIcon, Badge, Table, Text } from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import { Fragment, useState } from "react";
import type { Fact, RefusedMetric } from "../api/types";
import { formatValue, METRIC_LABEL } from "../features/evidence";
import { useStudio } from "../features/studio";
import { formatClock } from "../replay/model";

export const CLASS_COLOR: Record<Fact["evidence_class"], string> = { observed: "navy", estimated: "grape", simulated: "teal" };

interface Props {
  facts: Fact[];
  refused?: RefusedMetric[];
  empty: string;
  maxHeight?: number;
}

export function FactList({ facts, refused = [], empty, maxHeight }: Props) {
  const { bundle, selection, selectFact } = useStudio();
  const [open, setOpen] = useState<string | null>(null);
  const offset = bundle.manifest.match_clock_offset_s;
  const selectedId = selection?.kind === "fact" ? selection.fact.fact_id : null;
  if (facts.length === 0 && refused.length === 0) {
    return (
      <Text c="dimmed" fz="sm" py="md">
        {empty}
      </Text>
    );
  }
  return (
    <Table.ScrollContainer minWidth={420} maxHeight={maxHeight}>
      <Table highlightOnHover verticalSpacing={6} stickyHeader>
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={28}>#</Table.Th>
            <Table.Th>Metric</Table.Th>
            <Table.Th w={96}>Class</Table.Th>
            <Table.Th ta="right">Value</Table.Th>
            <Table.Th ta="right" w={60}>
              At
            </Table.Th>
            <Table.Th w={36} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {facts.map((f, i) => {
            const expanded = open === f.fact_id;
            return (
              <Fragment key={f.fact_id}>
                <Table.Tr
                  className={`clickable${f.fact_id === selectedId ? " row-selected" : ""}`}
                  onClick={() => selectFact(f)}
                  data-testid={`fact-${f.metric}`}
                  tabIndex={0}
                  onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), selectFact(f))}
                  aria-label={`Show on pitch: ${f.statement}`}
                >
                  <Table.Td c="dimmed">{i + 1}</Table.Td>
                  <Table.Td fw={500}>{METRIC_LABEL[f.metric] ?? f.metric}</Table.Td>
                  <Table.Td>
                    <Badge size="sm" radius="sm" variant="light" color={CLASS_COLOR[f.evidence_class]}>
                      {f.evidence_class}
                    </Badge>
                  </Table.Td>
                  <Table.Td ta="right" fw={600} className="tabular">
                    {formatValue(f)}
                  </Table.Td>
                  <Table.Td ta="right" c="dimmed" className="tabular">
                    {formatClock(offset + f.focus_time_s)}
                  </Table.Td>
                  <Table.Td>
                    <ActionIcon
                      variant="subtle"
                      color="gray"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpen(expanded ? null : f.fact_id);
                      }}
                      aria-expanded={expanded}
                      aria-label={expanded ? "Hide method details" : "Show method details"}
                    >
                      {expanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
                {expanded && (
                  <Table.Tr className="detail-row">
                    <Table.Td colSpan={6}>
                      <dl className="fact-detail">
                        <dt>Statement</dt>
                        <dd>{f.statement}</dd>
                        <dt>Method</dt>
                        <dd className="tabular">{f.method_version}</dd>
                        <dt>Window</dt>
                        <dd className="tabular">
                          {f.time_window.start_s.toFixed(1)}–{f.time_window.end_s.toFixed(1)} s
                          {f.source_frame_range && ` · frames ${f.source_frame_range[0]}–${f.source_frame_range[1]}`}
                        </dd>
                        <dt>Sources</dt>
                        <dd className="tabular">{f.source_event_ids.join(", ") || "tracking frames"}</dd>
                        <dt>Coverage</dt>
                        <dd>
                          {f.coverage.availability}
                          {f.coverage.frames_expected > 0 && ` · ${f.coverage.frames_used}/${f.coverage.frames_expected} intervals`}
                          {f.coverage.note && ` · ${f.coverage.note}`}
                        </dd>
                        <dt>Limits</dt>
                        <dd>
                          <ul>
                            {f.limitations.map((l) => (
                              <li key={l}>{l}</li>
                            ))}
                          </ul>
                        </dd>
                      </dl>
                    </Table.Td>
                  </Table.Tr>
                )}
              </Fragment>
            );
          })}
          {refused.map((r) => (
            <Table.Tr key={r.metric + r.subject_ids.join()}>
              <Table.Td c="dimmed">—</Table.Td>
              <Table.Td fw={500}>{METRIC_LABEL[r.metric] ?? r.metric}</Table.Td>
              <Table.Td>
                <Badge size="sm" radius="sm" variant="outline" color="gray">
                  not available
                </Badge>
              </Table.Td>
              <Table.Td colSpan={3} c="dimmed" fz="sm">
                {r.reason}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
