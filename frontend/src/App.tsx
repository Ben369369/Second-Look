import { AppShell, Badge, Burger, Group, Loader, NavLink, Paper, ScrollArea, Select, Stack, Text, TextInput, Title, Tooltip } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconArrowsShuffle, IconBallFootball, IconDatabase, IconMovie, IconLayoutDashboard, IconListDetails, IconMessageQuestion, IconSearch, IconUsers } from "@tabler/icons-react";
import { type ReactNode, useEffect, useState } from "react";
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

const NAV: { section: string; items: { view: View; label: string; icon: ReactNode }[] }[] = [
  {
    section: "Investigate",
    items: [
      { view: "overview", label: "Overview", icon: <IconLayoutDashboard size={18} /> },
      { view: "investigate", label: "Ask & evidence", icon: <IconMessageQuestion size={18} /> },
      { view: "whatif", label: "What if?", icon: <IconArrowsShuffle size={18} /> },
      { view: "recap", label: "Recap & overlay", icon: <IconMovie size={18} /> },
    ],
  },
  {
    section: "Data",
    items: [
      { view: "players", label: "Players", icon: <IconUsers size={18} /> },
      { view: "events", label: "Events", icon: <IconListDetails size={18} /> },
    ],
  },
  { section: "About", items: [{ view: "methods", label: "Methods & data", icon: <IconDatabase size={18} /> }] },
];

const TITLES: Record<View, string> = {
  overview: "Sequence overview",
  investigate: "Ask & evidence",
  whatif: "What if the right-back had pressed earlier?",
  recap: "Recap & overlay",
  players: "Players",
  events: "Events",
  methods: "Methods & data",
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
  const { bundle, ask } = useStudio();
  const [opened, { toggle, close }] = useDisclosure();
  const [view, setView] = useState<View>(viewFromHash);
  const [search, setSearch] = useState("");
  const [seed, setSeed] = useState<string | undefined>();

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const go = (v: View) => {
    window.location.hash = `/${v}`;
    setView(v);
    close();
  };

  return (
    <AppShell layout="alt" header={{ height: 64 }} navbar={{ width: 250, breakpoint: "sm", collapsed: { mobile: !opened } }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" gap="md" wrap="nowrap">
          <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Toggle navigation" />
          <Group gap="xs" hiddenFrom="sm" wrap="nowrap">
            <BrandLogo size={30} />
          </Group>
          <form
            className="header-search"
            onSubmit={(e) => {
              e.preventDefault();
              const q = search.trim();
              if (!q) return;
              setSeed(q);
              ask(q);
              setSearch("");
              go("investigate");
            }}
          >
            <TextInput
              value={search}
              onChange={(e) => setSearch(e.currentTarget.value)}
              placeholder="Ask about this sequence…"
              aria-label="Ask about this sequence"
              leftSection={<IconSearch size={16} />}
              maxLength={300}
              data-testid="header-search"
            />
          </form>
          <Group gap="xs" ml="auto" wrap="nowrap" visibleFrom="md">
            <Tooltip label="All data is generated by a simulator. Teams and players are fictional." multiline w={240}>
              <Badge color="orange" variant="light" radius="sm" size="lg" tt="none" data-testid="synthetic-badge">
                Synthetic match
              </Badge>
            </Tooltip>
            <Badge color="gray" variant="light" radius="sm" size="lg" tt="none" fw={500} data-testid="provider-status">
              {props.caps.provider_label}
            </Badge>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <Group gap="sm" mb="lg" wrap="nowrap">
          <BrandLogo size={44} />
          <div>
            <Text fw={700} c="navy.9" lh={1.2}>
              Second Look
            </Text>
            <Text fz="xs" c="dimmed">
              by Chui Labs
            </Text>
          </div>
        </Group>
        <ScrollArea style={{ flex: 1 }}>
          {NAV.map((s) => (
            <div key={s.section}>
              <Text fz="xs" fw={700} c="dimmed" tt="uppercase" lts={0.6} mt="md" mb={6} px={12}>
                {s.section}
              </Text>
              {s.items.map((it) => (
                <NavLink
                  key={it.view}
                  label={it.label}
                  leftSection={it.icon}
                  active={view === it.view}
                  variant="filled"
                  onClick={() => go(it.view)}
                  className="nav-link"
                  data-testid={`nav-${it.view}`}
                />
              ))}
            </div>
          ))}
        </ScrollArea>
        <Paper p="sm" bg="navy.0" withBorder={false} mt="md">
          <Group gap={8} wrap="nowrap" align="flex-start">
            <IconBallFootball size={18} color="var(--mantine-color-navy-9)" style={{ flex: "none", marginTop: 2 }} />
            <Text fz="xs" c="navy.9">
              Synthetic data only. Cedar FC and Harbor FC are fictional.
            </Text>
          </Group>
        </Paper>
      </AppShell.Navbar>

      <AppShell.Main>
        <Paper p="lg" mb="md">
          <Group justify="space-between" align="flex-end" wrap="wrap" gap="sm">
            <div>
              <Title order={2} c="navy.9">
                {TITLES[view]}
              </Title>
              <Text c="dimmed" fz="sm" mt={4}>
                {bundle.manifest.description}
              </Text>
            </div>
            <Select
              value={props.scenarioId}
              onChange={(v) => v && props.onScenario(v)}
              data={props.scenarios.map((s) => ({ value: s.scenario_id, label: s.title }))}
              allowDeselect={false}
              aria-label="Sequence"
              w={280}
              data-testid="scenario-select"
            />
          </Group>
          <Group gap="xs" mt="sm" hiddenFrom="md">
            <Badge color="orange" variant="light" radius="sm" tt="none">
              Synthetic match
            </Badge>
            <Badge color="gray" variant="light" radius="sm" tt="none" fw={500} h="auto" py={3} style={{ whiteSpace: "normal" }}>
              {props.caps.provider_label}
            </Badge>
          </Group>
        </Paper>
        {view === "overview" && <OverviewView />}
        {view === "investigate" && <InvestigateView seed={seed} />}
        {view === "whatif" && <WhatIfView />}
        {view === "recap" && <RecapView />}
        {view === "players" && <PlayersView />}
        {view === "events" && <EventsView />}
        {view === "methods" && <MethodsView />}
        <Text fz="xs" c="dimmed" ta="center" mt="xl">
          Second Look · Chui Labs · {bundle.manifest.scenario_id} · seed {bundle.manifest.seed} · Space play · ←/→ frame · Home reset
        </Text>
      </AppShell.Main>
    </AppShell>
  );
}
