import { expect, test } from "@playwright/test";

test("what-if: simulated comparison, assumption change, stress test", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/#/whatif");
  const rec = page.getByTestId("recommendation");
  await expect(rec).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("action-hold")).toContainText("of 200 rollouts");
  await expect(page.getByTestId("action-press_with_cover")).toContainText(/simulated/i);
  // At the default assumptions hold clearly beats pressing earlier, so it carries the mark.
  await expect(page.getByTestId("action-hold")).toHaveClass(/choice-mark/);
  await expect(page.getByTestId("action-press_earlier")).not.toHaveClass(/choice-mark/);
  // The simulated pitch is clearly labelled.
  await expect(page.getByTestId("pitch-canvas")).toHaveAttribute("aria-label", /Simulated rollout/);

  // Changing an assumption marks results as updating, then shows results for the new setting.
  const before = await page.getByTestId("action-press_with_cover").textContent();
  await page.getByTestId("attacker-policy").getByText("Direct (takes risks)").click();
  await expect(page.getByTestId("sim-pending")).toBeVisible();
  await expect(page.getByTestId("sim-pending")).toBeHidden({ timeout: 30_000 });
  await expect(page.getByTestId("action-press_with_cover")).not.toHaveText(before ?? "");

  // Play the sampled rollout.
  await page.getByTestId("sim-play").click();
  await expect.poll(async () => Number((await page.getByTestId("sim-clock").textContent())?.replace(/[^\d.]/g, "")), { timeout: 5000 }).toBeGreaterThan(0.5);

  // Stress test reports what it tested and whether the finding changes.
  await page.getByTestId("run-stress").click();
  await expect(page.getByTestId("stress-conclusion")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Tested: cover delay/)).toBeVisible();
});
