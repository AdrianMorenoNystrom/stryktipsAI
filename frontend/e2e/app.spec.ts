import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // Preserve explicit demo regression tests; public provider calls belong to mocked live tests.
  await page.route("**/api/coupon/current", (route) =>
    route.fulfill({
      json: {
        draw: null,
        coupon: null,
        analysis_ready: false,
        available_draws: [],
        health: { status: "Unavailable" },
        stale: false,
        issues: [],
        message: "Ingen livekupong i detta automatiserade demotest.",
      },
    }),
  );
});

test("news evidence survives a failed update without changing the system", async ({
  page,
}) => {
  await page.route("**/api/matches/*/news", (route) =>
    route.fulfill({
      json: {
        configured: true,
        extraction: "rules",
        newsAffectsProbabilities: false,
        last_checked_at: "2026-09-09T12:00:00Z",
        source_count: 1,
        stale: false,
        signals: [
          {
            id: "event",
            team: "Arsenal",
            direction: "negative",
            summary: "Testuppgift: spelare saknas.",
            status_label: "Rapporterad",
            source_count: 1,
            last_confirmed_at: "2026-09-09T11:00:00Z",
            first_published_at: "2026-09-09T11:00:00Z",
            recorded_at: "2026-09-09T12:00:00Z",
            evidence: "Mockad artikel för automatiserat test.",
            source_article_ids: ["version"],
          },
        ],
        sources: [
          {
            id: "article",
            version_id: "version",
            publisher: "BBC Sport",
            title: "Testartikel",
            url: "https://www.bbc.co.uk/sport",
            source_tier: 2,
            published_at: "2026-09-09T11:00:00Z",
          },
        ],
      },
    }),
  );
  await page.route("**/api/news/update", (route) =>
    route.fulfill({ status: 503, json: { detail: "Mocked outage" } }),
  );
  await page.goto("/overview");
  await expect(page.locator(".optimal-cell")).toHaveCount(13);
  const system = await page.locator(".optimal-cell").allTextContents();
  await page.locator(".optimal-cell").first().click();
  await page.getByRole("tab", { name: "Data", exact: true }).click();
  await page.locator(".advanced-news > summary").click();
  await expect(page.locator(".news-signal")).toHaveCount(1);
  await page.getByText("Visa källor och belägg", { exact: true }).click();
  await expect(
    page.getByText("Mockad artikel för automatiserat test."),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /BBC Sport Testartikel/ }).first(),
  ).toHaveAttribute("href", "https://www.bbc.co.uk/sport");
  await page
    .getByRole("button", { name: "Uppdatera kupongens nyheter" })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Senast sparad information visas",
  );
  await expect(page.locator(".news-signal")).toHaveCount(1);
  await page.keyboard.press("Escape");
  expect(await page.locator(".optimal-cell").allTextContents()).toEqual(system);
});

test("real API: overview, budgets, drawer and manual coupon", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/overview");
  await expect(page.locator(".optimal-cell")).toHaveCount(13);
  await expect(page.getByText("DEMO DATA", { exact: true })).toBeVisible();
  await expect(page.locator(".insight-card")).toHaveCount(3);
  await expect(page.locator(".match-card")).toHaveCount(13);
  for (const budget of [64, 128, 256, 512]) {
    const responsePromise = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/coupon/analyze") &&
        r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: `${budget} kr`, exact: true })
      .click();
    const result = await (await responsePromise).json();
    expect(result.system.cost).toBeLessThanOrEqual(budget);
    expect(
      result.matches.every((m: { source: string }) =>
        ["ml", "market_baseline"].includes(m.source),
      ),
    ).toBe(true);
    await expect(page.locator(".loading-state")).toHaveCount(0);
  }
  await page.getByRole("button", { name: "256 kr", exact: true }).click();
  await expect(page.locator(".loading-state")).toHaveCount(0);
  await page.screenshot({
    path: `test-results/overview-${info.project.name}.png`,
    fullPage: true,
  });
  await page.locator(".optimal-cell").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("tab", { name: "Data", exact: true }).click();
  await expect(page.locator(".form-list li")).toHaveCount(10);
  await page.getByRole("tab", { name: "Data", exact: true }).click();
  await expect(
    page.getByText("Hemmalagets Elo", { exact: true }),
  ).toBeVisible();
  await page.locator(".advanced-news > summary").click();
  await expect(
    page.getByText(
      "News Intelligence påverkar ännu inte modellens sannolikheter.",
      {exact:true},
    ),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("link", { name: "Anpassa tecken" }).click();
  await expect(page.locator(".builder-row")).toHaveCount(13);
  const row = page.locator(".builder-row").first();
  const unselected = row
    .locator('.sign-selector button[aria-pressed="false"]')
    .first();
  const costResponse = page.waitForResponse((r) =>
    r.url().endsWith("/api/coupon/cost"),
  );
  await unselected.click();
  const cost = await (await costResponse).json();
  await expect(
    page.getByText("Manuellt ändrad", { exact: false }),
  ).toBeVisible();
  await expect(page.locator(".price-panel h2")).toContainText(
    String(cost.cost),
  );
  await page.getByRole("button", { name: "Återställ modellens val" }).click();
  await expect(
    page.getByRole("button", { name: "Återställ modellens val" }),
  ).toBeDisabled();
  expect(errors).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("coupon input validates crowd and sends real changes to API", async ({
  page,
}) => {
  await page.goto("/coupon");
  await expect(page.locator(".builder-row")).toHaveCount(13);
  await page
    .getByRole("button", { name: "Redigera matcher, odds och streck" })
    .click();
  await page
    .getByRole("spinbutton", { name: "Match 1, Folket 1", exact: true })
    .fill("95");
  await page
    .getByRole("button", { name: "Analysera och generera system" })
    .click();
  await expect(
    page.getByText(
      "Kontrollera lagnamn, datum, alla odds och Svenska Folkets summor.",
    ),
  ).toBeVisible();
  await page
    .getByRole("spinbutton", { name: "Match 1, Folket 1", exact: true })
    .fill("72");
  await page
    .getByRole("spinbutton", { name: "Match 1, odds 1", exact: true })
    .fill("1.75");
  const responsePromise = page.waitForResponse((r) =>
    r.url().endsWith("/api/coupon/analyze"),
  );
  await page
    .getByRole("button", { name: "Analysera och generera system" })
    .click();
  const result = await (await responsePromise).json();
  expect(result.matches[0].marketOdds.home).toBe(1.75);
  expect(result.demo).toBe(true);
  await expect(page.locator(".editor")).toHaveCount(0);
  await page.goto("/analysis");
  await expect(page.locator("tbody tr")).toHaveCount(39);
  await page.goto("/history");
  await page.locator(".advanced-model > summary").click();
  await expect(
    page.getByText("Model v2", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("MARKET ANCHOR · V2", { exact: true }),
  ).toBeVisible();
});

test("API outage is readable and retry recovers", async ({ page }) => {
  await page.route("**/api/config", (route) => route.abort());
  await page.goto("/overview");
  await expect(page.getByRole("alert")).toContainText(
    "Datan kunde inte hämtas",
  );
  await page.unroute("**/api/config");
  await page.getByRole("button", { name: "Försök igen" }).click();
  await expect(page.locator(".optimal-cell")).toHaveCount(13);
});
