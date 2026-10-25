import type { AskResponse, Capabilities, FactPacket, QuestionOption, ReplayBundle, ScenarioSummary } from "./types";

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
  ask: (id: string, question: string, cursorS: number | null, signal?: AbortSignal) =>
    request<AskResponse>(`/api/scenarios/${sid(id)}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, cursor_s: cursorS }),
      signal,
    }),
};
