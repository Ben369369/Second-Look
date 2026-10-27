import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Fact, FactPacket, InvestigationState, MatchEvent, QuestionOption, ReplayBundle } from "../api/types";
import { buildLookup, eventPlayers, type Lookup } from "../replay/model";
import type { Annotation } from "../replay/PitchCanvas";
import { type Playback, usePlayback } from "../replay/usePlayback";
import { factAnnotation } from "./evidence";

export type CutoffMode = "sequence" | "replay";
export type Audience = "casual" | "analyst";
export type Selection =
  | { kind: "fact"; fact: Fact }
  | { kind: "event"; event: MatchEvent }
  | { kind: "player"; playerId: string }
  | null;

interface Studio {
  bundle: ReplayBundle;
  scenarioId: string;
  lookup: Lookup;
  playback: Playback;
  selection: Selection;
  highlight: ReadonlySet<string>;
  annotation: Annotation | null;
  selectFact: (f: Fact) => void;
  selectEvent: (e: MatchEvent) => void;
  selectPlayer: (id: string | null) => void;
  clearSelection: () => void;
  questions: QuestionOption[];
  answer: InvestigationState | null;
  askPending: boolean;
  askError: string | null;
  ask: (q: string) => void;
  cutoffMode: CutoffMode;
  setCutoffMode: (m: CutoffMode) => void;
  audience: Audience;
  setAudience: (a: Audience) => void;
  packet: FactPacket | null;
  showGrid: boolean;
  setShowGrid: (v: boolean) => void;
}

const StudioContext = createContext<Studio | null>(null);

export function useStudio(): Studio {
  const s = useContext(StudioContext);
  if (!s) throw new Error("useStudio outside StudioProvider");
  return s;
}

const errText = (err: unknown) => (err instanceof ApiError ? err.message : String(err));

export function StudioProvider(props: { bundle: ReplayBundle; scenarioId: string; questions: QuestionOption[]; children: ReactNode }) {
  const { bundle, scenarioId, questions } = props;
  const lookup = useMemo(() => buildLookup(bundle), [bundle]);
  const raw = usePlayback(bundle.manifest.duration_s);
  const [selection, setSelection] = useState<Selection>(null);
  const [answer, setAnswer] = useState<InvestigationState | null>(null);
  const [askPending, setAskPending] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [cutoffMode, setCutoffMode] = useState<CutoffMode>("sequence");
  const [audience, setAudienceState] = useState<Audience>("analyst");
  const audienceRef = useRef<Audience>("analyst");
  const [packet, setPacket] = useState<FactPacket | null>(null);
  const [showGrid, setShowGrid] = useState(false);
  const askCtl = useRef<AbortController | null>(null);
  const rawRef = useRef(raw);
  rawRef.current = raw;

  useEffect(() => {
    const ctl = new AbortController();
    api.facts(scenarioId, null, ctl.signal).then(setPacket).catch(() => undefined);
    return () => ctl.abort();
  }, [scenarioId]);

  // Starting playback clears the telestration: it describes one frozen moment.
  const toggle = useCallback(() => {
    if (!rawRef.current.playing) setSelection((s) => (s?.kind === "player" ? s : null));
    rawRef.current.toggle();
  }, []);
  const playback = useMemo(() => ({ ...raw, toggle }), [raw, toggle]);

  const ask = useCallback(
    (q: string) => {
      askCtl.current?.abort(); // a newer question supersedes any in flight
      const ctl = new AbortController();
      askCtl.current = ctl;
      setAskPending(true);
      setAskError(null);
      const done = (s: InvestigationState) => s.status === "complete" || s.status === "failed";
      const poll = async (s: InvestigationState): Promise<InvestigationState> => {
        // Model-backed investigations run in the background; poll until finished (bounded).
        const until = Date.now() + 330_000; // on-device models can take a few minutes; the server enforces its own budget
        let cur = s;
        while (!done(cur) && Date.now() < until) {
          setAnswer(cur);
          await new Promise((r) => setTimeout(r, 800));
          if (ctl.signal.aborted) throw new DOMException("aborted", "AbortError");
          cur = await api.getInvestigation(cur.investigation_id, ctl.signal);
        }
        return cur;
      };
      api
        .startInvestigation(scenarioId, q, cutoffMode === "replay" ? rawRef.current.t : null, audienceRef.current, ctl.signal)
        .then(poll)
        .then((res) => {
          setAnswer(res);
          setSelection(null);
        })
        .catch((err) => err.name !== "AbortError" && setAskError(errText(err)))
        .finally(() => askCtl.current === ctl && setAskPending(false));
    },
    [scenarioId, cutoffMode],
  );

  // Switching audience changes only the presentation: each investigation carries both views of the same facts,
  // so nothing is re-run and the data cutoff cannot move.
  const setAudience = useCallback((a: Audience) => {
    audienceRef.current = a;
    setAudienceState(a);
  }, []);

  const selectFact = useCallback((f: Fact) => {
    rawRef.current.pause();
    rawRef.current.seek(f.focus_time_s);
    setSelection({ kind: "fact", fact: f });
  }, []);
  const selectEvent = useCallback((e: MatchEvent) => {
    rawRef.current.pause();
    rawRef.current.seek(e.time_s);
    setSelection({ kind: "event", event: e });
  }, []);
  const selectPlayer = useCallback((id: string | null) => setSelection(id ? { kind: "player", playerId: id } : null), []);
  const clearSelection = useCallback(() => setSelection(null), []);

  const highlight = useMemo(() => {
    if (!selection) return new Set<string>();
    if (selection.kind === "fact") return new Set(selection.fact.subject_ids.filter((id) => lookup.players.has(id)));
    if (selection.kind === "event") return new Set(eventPlayers(selection.event));
    return new Set([selection.playerId]);
  }, [selection, lookup]);

  const annotation = useMemo<Annotation | null>(() => {
    if (selection?.kind === "fact") return factAnnotation(selection.fact, bundle);
    if (selection?.kind === "player") return { lines: [], paths: [{ player_id: selection.playerId, start_s: 0, end_s: bundle.manifest.duration_s }] };
    return null;
  }, [selection, bundle]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      const pb = rawRef.current;
      const step = 1 / bundle.manifest.frame_rate_hz;
      if (ev.key === " " && tag !== "BUTTON") {
        ev.preventDefault();
        toggle();
      } else if (ev.key === "ArrowRight") {
        pb.pause();
        pb.seek(pb.t + (ev.shiftKey ? 1 : step));
      } else if (ev.key === "ArrowLeft") {
        pb.pause();
        pb.seek(pb.t - (ev.shiftKey ? 1 : step));
      } else if (ev.key === "Home") {
        pb.reset();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bundle.manifest.frame_rate_hz, toggle]);

  const value: Studio = {
    bundle,
    scenarioId,
    lookup,
    playback,
    selection,
    highlight,
    annotation,
    selectFact,
    selectEvent,
    selectPlayer,
    clearSelection,
    questions,
    answer,
    askPending,
    askError,
    ask,
    cutoffMode,
    setCutoffMode,
    audience,
    setAudience,
    packet,
    showGrid,
    setShowGrid,
  };
  return <StudioContext.Provider value={value}>{props.children}</StudioContext.Provider>;
}
