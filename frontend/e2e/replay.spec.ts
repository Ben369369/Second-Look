import { expect, test, type Page } from "@playwright/test";

const seqTime = async (page: Page) => {
  const text = (await page.getByTestId("seq-time").textContent()) ?? "";
  return Number(/t = ([\d.]+)/.exec(text)?.[1]);
};

const ready = async (page: Page) => {
  await page.goto("/");
  await expect(page.getByTestId("pitch-canvas")).toBeVisible();
};

test("replay loads with synthetic and offline labels", async ({ page }) => {
  await ready(page);
  await expect(page.getByTestId("synthetic-badge")).toContainText("Synthetic match");
  await expect(page.getByTestId("provider-status")).toContainText("no language model connected");
  await expect(page.getByTestId("match-clock")).toHaveText("63:12");
});

test("play, pause, scrub, reset and event seek", async ({ page }) => {
  await ready(page);
  await page.getByTestId("play-toggle").click();
  await expect.poll(() => seqTime(page), { timeout: 5000 }).toBeGreaterThan(1);

  await page.getByTestId("play-toggle").click();
  const paused = await seqTime(page);
  await page.waitForTimeout(500);
  expect(await seqTime(page)).toBe(paused);

  await page.getByTestId("scrubber").fill("13.7");
  expect(await seqTime(page)).toBeCloseTo(13.7, 1);
  await expect(page.getByTestId("caption")).toHaveText("F137");

  await page.getByTestId("reset").click();
  expect(await seqTime(page)).toBe(0);
  await expect(page.getByTestId("caption")).toHaveText("F000");

  await page.getByTestId("nav-events").click();
  await page.getByTestId("event-rb_press_hero-e013").click();
  expect(await seqTime(page)).toBeCloseTo(13.1, 1);
  await expect(page.getByTestId("play-toggle")).toHaveAccessibleName("Play");
});

test("keyboard controls step frames", async ({ page }) => {
  await ready(page);
  await page.locator("body").press("ArrowRight");
  await page.locator("body").press("ArrowRight");
  expect(await seqTime(page)).toBeCloseTo(0.2, 1);
  await page.locator("body").press("Shift+ArrowRight");
  expect(await seqTime(page)).toBeCloseTo(1.2, 1);
  await page.locator("body").press("Home");
  expect(await seqTime(page)).toBe(0);
});

test("hero question: evidence cards seek to the measured moment", async ({ page }) => {
  await ready(page);
  await page.getByTestId("suggest-press_timing").click();
  const answer = page.getByTestId("answer");
  // The pressing answer also runs the simulator (a few seconds on a cold cache).
  await expect(answer).toContainText("Answered", { timeout: 30_000 });
  await expect(answer).toContainText("Halvorsen");
  // Offline mode is labelled, simulated claims are labelled, and the trace shows how the answer was made.
  await expect(page.getByTestId("answer-provider")).toHaveText("Rule-matched");
  await expect(answer).toContainText(/simulated/i);
  await page.getByTestId("trace-toggle").click();
  await expect(page.getByTestId("trace")).toContainText("keyword rules matched intent: press_timing");
  await expect(page.getByTestId("trace")).toContainText("claims approved");

  // Defender distance when the ball arrived: recorded at 11.4 s (Rossi's reception).
  await page.getByTestId("fact-defender_distance").first().click();
  expect(await seqTime(page)).toBeCloseTo(11.4, 1);
  await expect(page.getByTestId("caption")).toHaveText("F114");
  await expect(page.getByTestId("selected-fact")).toContainText(/observed/i);
  await expect(page.getByTestId("selected-fact")).toContainText("8.5 m");

  // The estimated lane fact is labelled as such.
  await page.getByTestId("fact-lane_access").click();
  await expect(page.getByTestId("selected-fact")).toContainText(/estimated/i);
  expect(await seqTime(page)).toBeCloseTo(13.7, 1);
});

test("unsupported and ambiguous questions are not answered", async ({ page }) => {
  await ready(page);
  await page.getByTestId("question-input").fill("Who will win the league?");
  await page.getByTestId("ask").click();
  await expect(page.getByTestId("answer")).toContainText("Unsupported");
  await page.getByTestId("question-input").fill("How far did #2 run?");
  await page.getByTestId("ask").click();
  await expect(page.getByTestId("answer")).toContainText("Needs clarification");
});

test("answers computed past the replay position are flagged", async ({ page }) => {
  await ready(page);
  await page.getByTestId("cutoff-mode").getByText("Up to replay").click();
  await page.getByTestId("scrubber").fill("17");
  await page.getByTestId("suggest-pass_completion").click();
  await expect(page.getByTestId("answer")).toContainText("Data to 63:29");
  await expect(page.getByTestId("stale-warning")).toHaveCount(0);
  await page.getByTestId("scrubber").fill("5");
  await expect(page.getByTestId("stale-warning")).toBeVisible();
});

test("pages, header search, stat cards and chart clicks are interactive", async ({ page }) => {
  await ready(page);
  // A stat card is a real fact: clicking it seeks and draws it.
  await page.getByTestId("stat-pass_distance").click();
  await expect(page.getByTestId("selected-fact")).toContainText("17.7 m");
  expect(await seqTime(page)).toBeCloseTo(16.3, 1);

  // Clicking the pressure chart seeks the replay (Recharts needs a hover to pick the point, as with a real mouse).
  const chart = page.locator(".recharts-surface").first();
  await chart.hover({ position: { x: 200, y: 100 } });
  await chart.click({ position: { x: 200, y: 100 } });
  await expect.poll(() => seqTime(page)).not.toBeCloseTo(16.3, 1);

  // Header search asks the question and opens the Ask page.
  await page.getByTestId("header-search").fill("How far did Halvorsen run?");
  await page.getByTestId("header-search").press("Enter");
  await expect(page).toHaveURL(/#\/investigate$/);
  await expect(page.getByTestId("answer")).toContainText("Halvorsen covered");

  // Players page: selecting a player highlights them and shows their speed chart.
  await page.getByTestId("nav-players").click();
  await page.getByTestId("player-CED-02").click();
  await expect(page.getByText("Speed: #2 R. Halvorsen")).toBeVisible();

  await page.getByTestId("nav-methods").click();
  await expect(page.getByText("lane_access/1").first()).toBeVisible();
});

test("stacked layout at narrow width has no horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
