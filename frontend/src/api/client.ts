import type {
  AskResponse,
  Capabilities,
  ChallengeResult,
  CompareRequest,
  ComparisonResult,
  ExportBundle,
  FactPacket,
  InvestigationState,
  QuestionOption,
  ReplayBundle,
  ScenarioSummary,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "network_error", "Could not reach the Second Look server.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.code ?? "http_error", body.message ?? `Request failed (${res.status}).`);
  }
  return (await res.json()) as T;
}

const sid = (id: string) => encodeURIComponent(id);

export const api = {
  capabilities: (signal?: AbortSignal) => request<Capabilities>("/api/capabilities", { signal }),
  scenarios: (signal?: AbortSignal) => request<ScenarioSummary[]>("/api/scenarios", { signal }),
  questions: (signal?: AbortSignal) => request<QuestionOption[]>("/api/questions", { signal }),
  replay: (id: string, signal?: AbortSignal) => request<ReplayBundle>(`/api/scenarios/${sid(id)}/replay`, { signal }),
  facts: (id: string, cursorS: number | null, signal?: AbortSignal) =>
    request<FactPacket>(`/api/scenarios/${sid(id)}/facts${cursorS === null ? "" : `?cursor_s=${cursorS.toFixed(2)}`}`, {
      signal,
    }),
  compare: (id: string, body: CompareRequest, signal?: AbortSignal) =>
    request<ComparisonResult>(`/api/scenarios/${sid(id)}/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }),
  challenge: (id: string, body: { baseline_cover_delay_s: number; baseline_attacker_policy: string }, signal?: AbortSignal) =>
    request<ChallengeResult>(`/api/scenarios/${sid(id)}/challenge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }),
  startInvestigation: (id: string, question: string, cursorS: number | null, audience: "casual" | "analyst", signal?: AbortSignal) =>
    request<InvestigationState>(`/api/investigations?scenario_id=${sid(id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, cursor_s: cursorS, audience }),
      signal,
    }),
  getInvestigation: (investigationId: string, signal?: AbortSignal) =>
    request<InvestigationState>(`/api/investigations/${encodeURIComponent(investigationId)}`, { signal }),
  exportInvestigation: (investigationId: string, audience: "casual" | "analyst", signal?: AbortSignal) =>
    request<ExportBundle>(`/api/investigations/${encodeURIComponent(investigationId)}/export?audience=${audience}`, { signal }),
  ask: (id: string, question: string, cursorS: number | null, signal?: AbortSignal) =>
    request<AskResponse>(`/api/scenarios/${sid(id)}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, cursor_s: cursorS }),
      signal,
    }),
};
