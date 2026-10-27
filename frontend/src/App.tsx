import { Container, Group, Loader, Select, Stack, Text, Title } from "@mantine/core";
import { useEffect, useState } from "react";
import { api, ApiError } from "./api/client";
import type { Capabilities, QuestionOption, ReplayBundle, ScenarioSummary } from "./api/types";
import { BrandLogo } from "./components/BrandLogo";
import { StudioProvider, useStudio } from "./features/studio";
import { EventsView } from "./views/EventsView";
import { InvestigateView } from "./views/InvestigateView";
import { MethodsView } from "./views/MethodsView";
import { OverviewView } from "./views/OverviewView";
import { PlayersView } from "./views/PlayersView";
import { RecapView } from "./views/RecapView";
import { WhatIfView } from "./views/WhatIfView";

type View = "overview" | "investigate" | "whatif" | "recap" | "players" | "events" | "methods";

// The demo path, in the order a viewer walks it. Data pages are text links, not equal tabs.
const MAIN: { view: View; label: string }[] = [
  { view: "overview", label: "The press" },
  { view: "investigate", label: "The argument" },
  { view: "whatif", label: "Three choices" },
  { view: "recap", label: "On air" },
];
const DATA: { view: View; label: string }[] = [
  { view: "players", label: "Players" },
  { view: "events", label: "Events" },
  { view: "methods", label: "Methods & data" },
];

const TITLES: Record<View, string> = {
  overview: "The press",
  investigate: "The argument",
  whatif: "Three choices",
  recap: "On air",
  players: "Players",
  events: "Events",
  methods: "Methods & data",
};

const SUBTITLES: Partial<Record<View, string>> = {
  investigate: "Ask a question about this move. Every number comes from code; the agents only choose and explain.",
  whatif: "Counts from this simulator, not a prediction.",
  recap: "The answer as timed broadcast cards. Every card cites a fact; simulations stay labelled.",
};

const VIEWS = Object.keys(TITLES) as View[];
const viewFromHash = (): View => {
  const v = window.location.hash.replace(/^#\/?/, "") as View;
  return VIEWS.includes(v) ? v : "overview";
};

const errText = (err: unknown) => (err instanceof ApiError ? err.message : String(err));

export function App() {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [questions, setQuestions] = useState<QuestionOption[]>([]);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [bundle, setBundle] = useState<ReplayBundle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    Promise.all([api.capabilities(ctl.signal), api.scenarios(ctl.signal), api.questions(ctl.signal)])
      .then(([c, s, q]) => {
        setCaps(c);
        setScenarios(s);
        setQuestions(q);
        setScenarioId((cur) => cur ?? s[0]?.scenario_id ?? null);
      })
      .catch((err) => err.name !== "AbortError" && setError(errText(err)));
    return () => ctl.abort();
  }, []);

  useEffect(() => {
    if (!scenarioId) return;
    const ctl = new AbortController();
    setBundle(null);
    api
      .replay(scenarioId, ctl.signal)
      .then(setBundle)
      .catch((err) => err.name !== "AbortError" && setError(errText(err)));
    return () => ctl.abort();
  }, [scenarioId]);

  if (error) {
    return (
      <Stack align="center" justify="center" h="100vh" p="md">
        <BrandLogo size={56} />
        <Text c="red" role="alert">
          {error}
        </Text>
      </Stack>
    );
  }
  if (!bundle || !scenarioId || !caps) {
    return (
      <Stack align="center" justify="center" h="100vh" gap="sm">
        <BrandLogo size={56} />
        <Loader size="sm" />
      </Stack>
    );
  }
  return (
    <StudioProvider key={bundle.manifest.dataset_hash} bundle={bundle} scenarioId={scenarioId} questions={questions}>
      <Shell caps={caps} scenarios={scenarios} scenarioId={scenarioId} onScenario={setScenarioId} />
    </StudioProvider>
  );
}

function Shell(props: { caps: Capabilities; scenarios: ScenarioSummary[]; scenarioId: string; onScenario: (id: string) => void }) {
  const { bundle } = useStudio();
  const [view, setView] = useState<View>(viewFromHash);

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const go = (v: View) => {
    window.location.hash = `/${v}`;
    setView(v);
    window.scrollTo({ top: 0 });
  };

  return (
    <>
      <header className="topbar">
        <Container size="xl" py="sm">
          <Group justify="space-between" wrap="wrap" gap="sm">
            <Group gap="lg" wrap="wrap" style={{ minWidth: 0, rowGap: 4 }}>
              <Group gap="xs" wrap="nowrap">
                <BrandLogo size={34} />
                <Text fw={700} c="navy.9" fz="lg" className="serif" style={{ whiteSpace: "nowrap" }}>
                  Second Look
                </Text>
              </Group>
              <nav className="topnav" aria-label="Main">
                {MAIN.map((it) => (
                  <button key={it.view} type="button" aria-current={view === it.view ? "page" : undefined} onClick={() => go(it.view)} data-testid={`nav-${it.view}`}>
                    {it.label}
                  </button>
                ))}
              </nav>
            </Group>
            <Group gap={6} wrap="wrap" fz="xs">
              <Text fz="xs" fw={600} c="orange.9" data-testid="synthetic-badge" title="All data is generated by a simulator. Teams and players are fictional.">
                Synthetic match
              </Text>
              <Text fz="xs" c="dimmed">
                ·
              </Text>
              <Text fz="xs" c="dimmed" data-testid="provider-status">
                {props.caps.provider_label}
              </Text>
            </Group>
          </Group>
        </Container>
      </header>

      <Container size="xl" py="lg" component="main">
        {view !== "overview" && (
          <Group justify="space-between" align="flex-end" wrap="wrap" gap="sm" mb="lg">
            <div>
              <Title order={1} c="navy.9" className="page-title">
                {TITLES[view]}
              </Title>
              {SUBTITLES[view] && (
                <Text c="dimmed" fz="sm" mt={6}>
                  {SUBTITLES[view]}
                </Text>
              )}
            </div>
            {props.scenarios.length > 1 && (
              <Select
                value={props.scenarioId}
                onChange={(v) => v && props.onScenario(v)}
                data={props.scenarios.map((s) => ({ value: s.scenario_id, label: s.title }))}
                allowDeselect={false}
                aria-label="Sequence"
                w={280}
                data-testid="scenario-select"
              />
            )}
          </Group>
        )}
        {view === "overview" && <OverviewView go={go} />}
        {view === "investigate" && <InvestigateView />}
        {view === "whatif" && <WhatIfView />}
        {view === "recap" && <RecapView />}
        {view === "players" && <PlayersView />}
        {view === "events" && <EventsView />}
        {view === "methods" && <MethodsView />}

        <Group justify="space-between" wrap="wrap" gap="sm" mt={48} pt="md" style={{ borderTop: "1px solid var(--sheet-rule)" }}>
          <Group gap="md" wrap="wrap">
            <Text fz="xs" c="dimmed">
              Data behind this move:
            </Text>
            {DATA.map((it) => (
              <button key={it.view} type="button" className="text-link" onClick={() => go(it.view)} data-testid={`nav-${it.view}`}>
                {it.label}
              </button>
            ))}
          </Group>
          <Text fz="xs" c="dimmed">
            Second Look by Chui Labs · {bundle.manifest.description} · Synthetic data; Cedar FC and Harbor FC are fictional · Space play · ←/→ frame
          </Text>
        </Group>
      </Container>
    </>
  );
}
