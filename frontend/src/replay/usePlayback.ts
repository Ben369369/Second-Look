import { useCallback, useEffect, useRef, useState } from "react";

export const SPEEDS = [0.25, 0.5, 1, 2] as const;

export interface Playback {
  t: number;
  playing: boolean;
  speed: number;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  seek: (t: number) => void;
  reset: () => void;
  setSpeed: (s: number) => void;
}

/** Wall-clock driven playback over [0, duration]; stops at the end. */
export function usePlayback(duration: number): Playback {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const tRef = useRef(0);
  const speedRef = useRef(1);
  speedRef.current = speed;

  const seek = useCallback(
    (next: number) => {
      const clamped = Math.min(Math.max(next, 0), duration);
      tRef.current = clamped;
      setT(clamped);
    },
    [duration],
  );

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = ((now - last) / 1000) * speedRef.current;
      last = now;
      const next = Math.min(tRef.current + dt, duration);
      tRef.current = next;
      setT(next);
      if (next >= duration) {
        setPlaying(false);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, duration]);

  // A new scenario starts from the beginning, paused.
  useEffect(() => {
    tRef.current = 0;
    setT(0);
    setPlaying(false);
  }, [duration]);

  const play = useCallback(() => {
    if (tRef.current >= duration) seek(0);
    setPlaying(true);
  }, [duration, seek]);
  const pause = useCallback(() => setPlaying(false), []);
  const toggle = useCallback(() => (playing ? pause() : play()), [playing, play, pause]);
  const reset = useCallback(() => {
    setPlaying(false);
    seek(0);
  }, [seek]);

  return { t, playing, speed, play, pause, toggle, seek, reset, setSpeed };
}
