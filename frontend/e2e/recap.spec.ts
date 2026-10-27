import { expect, test } from "@playwright/test";

test("fan view and analyst view answer from the same facts", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/#/investigate");
  await page.getByTestId("suggest-press_timing").click();
  await expect(page.getByTestId("answer")).toContainText("Answered", { timeout: 30_000 });
  const analystFacts = await page.getByRole("tab", { name: /Evidence/ }).textContent();

  await page.getByTestId("audience").getByText("Fan view").click();
  await expect(page.getByTestId("casual-claims")).toContainText("In the simulation", { timeout: 30_000 });
  await expect(page.getByTestId("casual-claims")).toContainText("made-up match");
  // Same evidence count behind both presentations, and switching does not re-run the question.
  await expect(page.getByRole("tab", { name: /Evidence/ })).toHaveText(analystFacts ?? "");
  await expect(page.getByTestId("ask")).not.toHaveAttribute("data-loading", "true");
  await page.getByTestId("audience").getByText("Analyst view").click();
  await expect(page.getByTestId("answer")).toContainText(/predeclared rule/);
});

test("recap overlay preview matches the exported cue timing", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/#/recap");
  await page.getByTestId("build-recap").click();
  await expect(page.getByTestId("cue-table")).toBeVisible({ timeout: 30_000 });

  // For every exported cue, seeking into its window must show exactly that cue over the replay.
  const rows = page.getByTestId("cue-table").locator("tbody tr");
  const n = await rows.count();
  expect(n).toBeGreaterThanOrEqual(2);
  for (let i = 0; i < n; i++) {
    const title = (await rows.nth(i).locator("td").nth(4).textContent()) ?? "";
    await rows.nth(i).click(); // seeks just inside the cue's window
    await expect(page.getByTestId("active-cue")).toContainText(title);
  }
  // The closing card is the simulation, and it says so.
  await rows.nth(n - 1).click();
  await expect(page.getByTestId("active-cue")).toContainText("SIMULATION");

  const download = page.waitForEvent("download");
  await page.getByTestId("download-overlay").click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^second-look-overlay-.*\.json$/);
});
