import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

// Recorded from the real local API, ultimately backed by immutable public responses.
// Only test copies are changed; no public provider is called by these browser tests.
const fixture = JSON.parse(
  readFileSync(join(__dirname, "fixtures/live.json"), "utf8"),
);

test.beforeEach(async ({ page }) => {
  await page.route("**/api/coupon/current", (r) =>
    r.fulfill({ json: fixture.state }),
  );
  await page.route("**/api/coupon/analyze", (r) =>
    r.fulfill({ json: fixture.analysis }),
  );
  await page.route("**/api/stryktipset/draws/4970/matches/*/crowd", (r) =>
    r.fulfill({ json: fixture.crowd }),
  );
  await page.route("**/api/stryktipset/draws/4970/matches/*/market", (r) =>
    r.fulfill({
      json: { market: [], crowd: fixture.crowd.history, predictions: [] },
    }),
  );
  await page.route("**/api/stryktipset/draws", (r) =>
    r.fulfill({ json: fixture.archive }),
  );
  await page.route("**/api/stryktipset/draws/4969**", (r) =>
    r.fulfill({
      json: r.request().url().includes("selection=latest")
        ? fixture.latestHistory
        : fixture.history,
    }),
  );
});

test("automatic live coupon, real labels and recorded crowd history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/overview");
  await expect(page.getByText("LIVE DATA", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("4970");
  await expect(page.locator(".optimal-cell")).toHaveCount(13);
  await expect(page.getByText("DEMO DATA", { exact: true })).toHaveCount(0);
  await page.locator(".optimal-cell").first().click();
  await page.getByRole("tab", { name: "Historik", exact: true }).click();
  await expect(page.locator(".crowd-history tbody tr")).toHaveCount(
    fixture.crowd.history.length,
  );
  await expect(page.locator(".crowd-history")).toContainText(
    "ändrar inte modellens sannolikheter",
  );
  await page.keyboard.press("Escape");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("missing odds prevents an optimal row and manual completion keeps live crowd", async ({
  page,
}) => {
  const incomplete = structuredClone(fixture.state);
  incomplete.coupon = null;
  incomplete.analysis_ready = false;
  incomplete.draw.matches[0].market_odds = null;
  incomplete.issues = ["Match 1: marknadsodds saknas. Ange odds manuellt."];
  await page.route("**/api/coupon/current", (r) =>
    r.fulfill({ json: incomplete }),
  );
  let sent: any;
  await page.route("**/api/stryktipset/draws/4970/odds", (r) => {
    sent = r.request().postDataJSON();
    return r.fulfill({ json: { ...fixture.state, manual_odds_matches: 1 } });
  });
  await page.goto("/overview");
  await expect(page.getByText("LIVE DATA", { exact: true })).toBeVisible();
  await expect(page.locator(".pending-coupon")).toBeVisible();
  await expect(page.locator(".optimal-cell")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Komplettera odds", exact: true })
    .click();
  for (const [sign, value] of [
    ["1", "7.50"],
    ["X", "4.40"],
    ["2", "1.50"],
  ])
    await page
      .getByRole("spinbutton", {
        name: `Match 1, manuella odds ${sign}`,
        exact: true,
      })
      .fill(value);
  await page.getByRole("button", { name: "Spara odds och analysera" }).click();
  await expect(page.locator(".optimal-cell")).toHaveCount(13);
  expect(sent.odds["1"]).toEqual({ home: 7.5, draw: 4.4, away: 1.5 });
  await expect(page.getByText("LIVE DATA", { exact: true })).toBeVisible();
  await expect(page.locator(".live-controls")).toContainText(
    "1 manuellt inmatade matcher",
  );
});

test("stale live observations are labelled and total unavailability falls back to demo", async ({
  page,
}) => {
  await page.route("**/api/coupon/current", (r) =>
    r.fulfill({ json: { ...fixture.state, stale: true } }),
  );
  await page.goto("/overview");
  await expect(page.locator(".live-controls")).toContainText(
    "Visar senast sparad data",
  );
  await expect(page.locator(".optimal-cell")).toHaveCount(13);
  await page.route("**/api/coupon/current", (r) =>
    r.fulfill({
      json: {
        draw: null,
        coupon: null,
        analysis_ready: false,
        issues: [],
        message: "Live-data saknas. Visar tydligt märkt demo.",
        health: { status: "Unavailable" },
        available_draws: [],
      },
    }),
  );
  await page.unroute("**/api/coupon/analyze"); // The existing real local demo analysis API.
  await page.reload();
  await expect(page.getByText("DEMO DATA", { exact: true })).toBeVisible();
  await expect(page.getByText("LIVE DATA", { exact: true })).toHaveCount(0);
  await expect(page.locator(".optimal-cell")).toHaveCount(13);
});

test("historical post-close crowd and payouts do not invent historical predictions", async ({
  page,
}) => {
  await page.goto("/history");
  await page.getByRole("button", { name: "4969", exact: true }).click();
  await expect(page.locator(".archive-detail")).toContainText(
    "Inga observationer registrerades före denna tidpunkt",
  );
  await expect(page.locator(".archive-detail")).toContainText(
    "Ingen sparad prognos",
  );
  await page
    .getByRole("combobox", { name: "Välj historiskt snapshot" })
    .selectOption("latest");
  await expect(page.locator(".archive-detail")).toContainText(
    "De används inte som historisk pre-match-prognos",
  );
  await expect(page.locator(".payout-grid")).toContainText("764");
  await expect(page.locator(".archive-detail tbody tr")).toHaveCount(13);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
