import { AreaChart, LineChart } from "@mantine/charts";
import { useMemo } from "react";
import { pairDistanceSeries, pressurePairs, speedSeries } from "../features/series";
import { useStudio } from "../features/studio";
import { formatClock, shortPlayer } from "../replay/model";

const SERIES_COLORS = ["navy.8", "red.7", "teal.7", "grape.6"];

/** Recharts click state → sequence time, using the active row's own `t`. */
function clickedTime(state: unknown, data: { t: number }[]): number | null {
  const s = state as { activeTooltipIndex?: number | string | null; activeLabel?: number | string } | null;
  if (s?.activeTooltipIndex !== undefined && s.activeTooltipIndex !== null) {
    const row = data[Number(s.activeTooltipIndex)];
    if (row) return row.t;
  }
  return s?.activeLabel !== undefined ? Number(s.activeLabel) : null;
}

function useTimeAxis() {
  const { bundle } = useStudio();
  const offset = bundle.manifest.match_clock_offset_s;
  return {
    type: "number" as const,
    dataKey: "t",
    domain: [0, bundle.manifest.duration_s],
    tickFormatter: (v: number) => formatClock(offset + v),
    allowDecimals: false,
  };
}

export function PressureChart({ height = 260 }: { height?: number }) {
  const { bundle, lookup, playback } = useStudio();
  const pairs = useMemo(() => pressurePairs(bundle, (id) => shortPlayer(lookup, id)), [bundle, lookup]);
  const data = useMemo(() => pairDistanceSeries(bundle, pairs), [bundle, pairs]);
  const xAxis = useTimeAxis();
  return (
    <LineChart
      h={height}
      data={data}
      dataKey="t"
      series={pairs.map((p, i) => ({ name: p.key, color: SERIES_COLORS[i % SERIES_COLORS.length] }))}
      withDots={false}
      curveType="linear"
      unit=" m"
      withLegend
      legendProps={{ verticalAlign: "bottom" }}
      xAxisProps={xAxis}
      yAxisProps={{ domain: [0, "auto"] }}
      referenceLines={[
        { y: 3, label: "Pressure threshold 3 m", color: "orange.6" },
        { x: playback.t, color: "navy.9", label: formatClock(bundle.manifest.match_clock_offset_s + playback.t) },
      ]}
      tooltipAnimationDuration={0}
      lineChartProps={{
        onClick: (state: unknown) => {
          const t = clickedTime(state, data as { t: number }[]);
          if (t !== null) {
            playback.pause();
            playback.seek(t);
          }
        },
        style: { cursor: "pointer" },
      }}
    />
  );
}

export function SpeedChart({ playerId, height = 220 }: { playerId: string; height?: number }) {
  const { bundle, playback } = useStudio();
  const data = useMemo(() => speedSeries(bundle, playerId), [bundle, playerId]);
  const xAxis = useTimeAxis();
  return (
    <AreaChart
      h={height}
      data={data}
      dataKey="t"
      series={[{ name: "speed", label: "Speed", color: "navy.7" }]}
      withDots={false}
      curveType="linear"
      unit=" m/s"
      xAxisProps={xAxis}
      referenceLines={[{ x: playback.t, color: "navy.9" }]}
      tooltipAnimationDuration={0}
      areaChartProps={{
        onClick: (state: unknown) => {
          const t = clickedTime(state, data);
          if (t !== null) {
            playback.pause();
            playback.seek(t);
          }
        },
        style: { cursor: "pointer" },
      }}
    />
  );
}
