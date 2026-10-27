import { ActionIcon, Group, SegmentedControl, Text, Tooltip } from "@mantine/core";
import { IconChevronLeft, IconChevronRight, IconPlayerPauseFilled, IconPlayerPlayFilled, IconPlayerSkipBack } from "@tabler/icons-react";
import type { MatchEvent } from "../api/types";
import { useStudio } from "../features/studio";
import { describeEvent, eventTypeLabel, formatClock } from "../replay/model";
import { type Playback, SPEEDS } from "../replay/usePlayback";

const MARKED: ReadonlySet<MatchEvent["type"]> = new Set(["pass", "pressure_start", "shot"]);

export function PlaybackControls({ compact = false }: { compact?: boolean }) {
  const { bundle, lookup, playback, answer, selectEvent } = useStudio();
  const { manifest, events } = bundle;
  const { t, playing, speed } = playback;
  const duration = manifest.duration_s;
  const offset = manifest.match_clock_offset_s;
  const step = 1 / manifest.frame_rate_hz;
  const pct = (s: number) => `${(s / duration) * 100}%`;

  return (
    <div className="transport">
      <Group gap="sm" wrap="wrap">
        <ActionIcon.Group>
          <ActionIcon size="lg" variant="filled" onClick={playback.toggle} aria-label={playing ? "Pause" : "Play"} data-testid="play-toggle">
            {playing ? <IconPlayerPauseFilled size={16} /> : <IconPlayerPlayFilled size={16} />}
          </ActionIcon>
          <ActionIcon size="lg" variant="default" onClick={() => playback.seek(t - step)} aria-label="Back one frame">
            <IconChevronLeft size={16} />
          </ActionIcon>
          <ActionIcon size="lg" variant="default" onClick={() => playback.seek(t + step)} aria-label="Forward one frame">
            <IconChevronRight size={16} />
          </ActionIcon>
          <ActionIcon size="lg" variant="default" onClick={playback.reset} aria-label="Reset to start" data-testid="reset">
            <IconPlayerSkipBack size={16} />
          </ActionIcon>
        </ActionIcon.Group>
        {!compact && (
          <SegmentedControl
            size="xs"
            value={String(speed)}
            onChange={(v) => playback.setSpeed(Number(v))}
            data={SPEEDS.map((s) => ({ value: String(s), label: `${s}×` }))}
            aria-label="Playback speed"
            data-testid="speed"
          />
        )}
        <Group gap={10} ml="auto" align="baseline">
          <Text fw={700} fz={22} c="navy.9" className="tabular" data-testid="match-clock">
            {formatClock(offset + t)}
          </Text>
          <Text fz="sm" c="dimmed" className="tabular" data-testid="seq-time">
            t = {t.toFixed(1)} s / {duration.toFixed(1)} s
          </Text>
        </Group>
      </Group>
      <div className="scrub">
        <input
          type="range"
          min={0}
          max={duration}
          step={step}
          value={t}
          onChange={(e) => {
            playback.pause();
            playback.seek(Number(e.target.value));
          }}
          aria-label="Replay position"
          aria-valuetext={`${formatClock(offset + t)}, ${t.toFixed(1)} seconds into the sequence`}
          data-testid="scrubber"
        />
        <div className="ticks">
          {answer && <div className="cutoff" style={{ left: pct(answer.cursor_s) }} title="Data cutoff of the current answer" />}
          {events
            .filter((e) => MARKED.has(e.type))
            .map((e) => (
              <Tooltip key={e.event_id} label={`${formatClock(offset + e.time_s)} · ${eventTypeLabel(e)}: ${describeEvent(lookup, e)}`}>
                <button
                  type="button"
                  className={`tick tick-${e.type}`}
                  style={{ left: pct(e.time_s) }}
                  onClick={() => selectEvent(e)}
                  aria-label={`Jump to ${eventTypeLabel(e)} at ${formatClock(offset + e.time_s)}: ${describeEvent(lookup, e)}`}
                />
              </Tooltip>
            ))}
        </div>
      </div>
    </div>
  );
}

/** Minimal transport for a playback that is not the recorded replay (e.g. a simulated rollout). */
export function PlaybackControlsBare({ playback, duration, clockLabel }: { playback: Playback; duration: number; clockLabel: string }) {
  const step = 0.1;
  return (
    <div className="transport">
      <Group gap="sm">
        <ActionIcon.Group>
          <ActionIcon
            size="lg"
            variant="filled"
            color="teal.7"
            onClick={playback.toggle}
            aria-label={playback.playing ? "Pause simulation" : "Play simulation"}
            data-testid="sim-play"
          >
            {playback.playing ? <IconPlayerPauseFilled size={16} /> : <IconPlayerPlayFilled size={16} />}
          </ActionIcon>
          <ActionIcon size="lg" variant="default" onClick={() => playback.seek(playback.t - step)} aria-label="Back one step">
            <IconChevronLeft size={16} />
          </ActionIcon>
          <ActionIcon size="lg" variant="default" onClick={() => playback.seek(playback.t + step)} aria-label="Forward one step">
            <IconChevronRight size={16} />
          </ActionIcon>
          <ActionIcon size="lg" variant="default" onClick={playback.reset} aria-label="Restart simulation">
            <IconPlayerSkipBack size={16} />
          </ActionIcon>
        </ActionIcon.Group>
        <Text ml="auto" fw={700} c="teal.8" className="tabular" data-testid="sim-clock">
          {clockLabel}
        </Text>
      </Group>
      <div className="scrub sim-scrub">
        <input
          type="range"
          min={0}
          max={duration}
          step={step}
          value={playback.t}
          onChange={(e) => {
            playback.pause();
            playback.seek(Number(e.target.value));
          }}
          aria-label="Simulated replay position"
        />
      </div>
    </div>
  );
}
