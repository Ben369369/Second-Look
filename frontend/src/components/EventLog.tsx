import { Badge, Table } from "@mantine/core";
import { useEffect, useRef } from "react";
import type { MatchEvent } from "../api/types";
import { useStudio } from "../features/studio";
import { eventTypeLabel, formatClock, type Lookup, shortPlayer } from "../replay/model";

const TYPE_COLOR: Partial<Record<MatchEvent["type"], string>> = {
  pass: "navy",
  reception: "gray",
  carry: "gray",
  shot: "red",
  pressure_start: "orange",
  pressure_end: "orange",
};

function detail(lookup: Lookup, e: MatchEvent): string {
  const who = shortPlayer(lookup, e.player_id);
  if (e.type === "pass") return `${who} → ${shortPlayer(lookup, e.recipient_id)}`;
  if (e.type.startsWith("pressure")) return `${who} on ${shortPlayer(lookup, e.related_player_ids[0] ?? null)}`;
  return who;
}

export function EventLog({ events, maxHeight }: { events: MatchEvent[]; maxHeight?: number }) {
  const { bundle, lookup, playback, selection, selectEvent } = useStudio();
  const offset = bundle.manifest.match_clock_offset_s;
  const ref = useRef<HTMLDivElement>(null);
  const current = events.reduce((acc, e, i) => (e.time_s <= playback.t + 1e-6 ? i : acc), -1);
  const selectedId = selection?.kind === "event" ? selection.event.event_id : null;

  useEffect(() => {
    ref.current?.querySelector<HTMLElement>("[data-current='true']")?.scrollIntoView({ block: "nearest" });
  }, [current]);

  return (
    <Table.ScrollContainer minWidth={460} maxHeight={maxHeight} ref={ref}>
      <Table highlightOnHover verticalSpacing={5} stickyHeader>
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={64}>Clock</Table.Th>
            <Table.Th w={110}>Type</Table.Th>
            <Table.Th>Players</Table.Th>
            <Table.Th w={90}>Outcome</Table.Th>
            <Table.Th w={64}>ID</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {events.map((e, i) => {
            const team = lookup.teams.get(e.team_id);
            return (
              <Table.Tr
                key={e.event_id}
                className={`clickable${e.event_id === selectedId ? " row-selected" : ""}${i > current ? " row-future" : ""}`}
                data-current={i === current}
                onClick={() => selectEvent(e)}
                tabIndex={0}
                onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && (ev.preventDefault(), selectEvent(e))}
                data-testid={`event-${e.event_id}`}
              >
                <Table.Td className="tabular">{formatClock(offset + e.time_s)}</Table.Td>
                <Table.Td>
                  <Badge size="sm" radius="sm" variant="light" color={TYPE_COLOR[e.type] ?? "gray"}>
                    {eventTypeLabel(e)}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <span className={`swatch${team?.marker_shape === "circle" ? " shape-circle" : ""}`} style={{ background: team?.color }} />{" "}
                  {detail(lookup, e)}
                </Table.Td>
                <Table.Td c="dimmed">{e.outcome ?? ""}</Table.Td>
                <Table.Td c="dimmed" className="tabular">
                  {e.event_id.slice(-4)}
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
