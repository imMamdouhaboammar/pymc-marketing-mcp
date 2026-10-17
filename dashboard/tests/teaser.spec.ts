import { mkdir } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("the sample CTA reaches setup without opening authentication", async ({
  page,
}) => {
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Put evidence behind your next marketing decision.",
  );
  await page
    .getByRole("link", { name: "Try the sample workflow", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/#quickstart$/);
  await expect(
    page.getByRole("heading", {
      name: "Try one question before using your own data.",
    }),
  ).toBeInViewport();
  await expect(
    page.getByRole("heading", { name: "Sign in to dashboard" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Illustrative workflow", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Advanced beta", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("Server Gate Verdict")).toHaveCount(0);
});

test("every role supplies distinct context that carries into setup", async ({
  page,
}) => {
  const roles = [
    [
      "Digital Marketer",
      "Which channels should I examine before changing spend?",
    ],
    [
      "Business Owner",
      "What could a different budget allocation mean for the business?",
    ],
    [
      "E-commerce Manager",
      "What might customers be worth beyond their first order?",
    ],
    [
      "Agency Strategist",
      "How can I explain a budget recommendation to a client?",
    ],
    [
      "Marketing Analyst",
      "Can this fitted model support the proposed decision?",
    ],
  ];
  for (const [role, question] of roles) {
    await page.getByRole("tab", { name: role, exact: true }).click();
    await expect(page.getByRole("tabpanel")).toContainText(question);
    await expect(page.getByRole("tabpanel")).toContainText("What you bring");
    await expect(page.getByRole("tabpanel")).toContainText(
      "What you can review",
    );
    await page
      .getByRole("link", { name: `Try this as a ${role}`, exact: true })
      .click();
    await expect(page.locator("#first-question")).toContainText(role);
    await expect(page.locator("#first-question .copy-text")).toHaveText(
      await page.getByRole("tabpanel").locator(".copy-text").innerText(),
    );
  }
});

test("tabs and disclosures support keyboard use", async ({ page }) => {
  const first = page.getByRole("tab", {
    name: "Digital Marketer",
    exact: true,
  });
  await first.focus();
  await page.keyboard.press("ArrowDown");
  await expect(
    page.getByRole("tab", { name: "Business Owner", exact: true }),
  ).toBeFocused();
  await expect(
    page.getByRole("tab", { name: "Business Owner", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  const question = page.getByRole("button", {
    name: "Does it change my live campaigns?",
  });
  await question.focus();
  await page.keyboard.press("Enter");
  await expect(question).toHaveAttribute("aria-expanded", "true");
  await expect(
    page.getByText(
      "You review recommendations and decide what to do. This MCP does not change live ad campaigns.",
    ),
  ).toBeVisible();
});

test("clipboard reports success only after the write succeeds", async ({
  page,
}) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const setup = page.locator("#sample-commands");
  await setup.getByRole("button", { name: "Copy commands" }).click();
  await expect(setup.getByRole("status")).toHaveText("Copied");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain(
    "uv run marketing-mcp-demo --fast",
  );
});

test("clipboard denial exposes a manual fallback without false success", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: () =>
          Promise.reject(new DOMException("Denied", "NotAllowedError")),
      },
    });
  });
  await page.reload();
  const setup = page.locator("#sample-commands");
  await setup.getByRole("button", { name: "Copy commands" }).click();
  await expect(setup.getByRole("status")).toContainText(
    "Select the text below and copy it manually.",
  );
  await expect(setup.getByRole("status")).not.toHaveText("Copied");
  await expect(setup.locator(".copy-text")).toHaveAttribute("tabindex", "0");
});

test("setup has valid local config and the sign-in entry still returns to the teaser", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Claude Desktop: local connection" })
    .click();
  const config = JSON.parse(
    await page.locator("#local-client-config .copy-text").innerText(),
  );
  expect(config.mcpServers["pymc-marketing"].command).toBe("uv");
  expect(config.mcpServers["pymc-marketing"].args).toEqual([
    "run",
    "--directory",
    "/ABSOLUTE/PATH/TO/pymc-marketing-mcp",
    "marketing-mcp",
    "--transport",
    "stdio",
  ]);
  expect(config.mcpServers["pymc-marketing"].env).toEqual({
    MARKETING_MCP_DATA_DIR: ".demo-runtime/data",
    MARKETING_MCP_INGEST_DIR: ".demo-runtime",
    MARKETING_MCP_ARTIFACT_DIR: ".demo-runtime/artifacts",
    MARKETING_MCP_METADATA_DB: ".demo-runtime/metadata.db",
  });
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Sign in to dashboard" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Back to platform overview" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("landing has no automated WCAG AA violations, including selected role and open FAQ", async ({
  page,
}) => {
  await page
    .getByRole("tab", { name: "E-commerce Manager", exact: true })
    .click();
  await page.getByRole("button", { name: "What data do I need?" }).click();
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(result.violations).toEqual([]);
});

for (const width of [320, 390, 720, 1440]) {
  test(`content and navigation remain usable at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    if (width < 760) {
      await page.getByRole("button", { name: "Menu", exact: true }).click();
    }
    await page
      .getByRole("navigation", { name: "Public navigation" })
      .getByRole("link", { name: "Your work" })
      .click();
    await expect(page).toHaveURL(/#your-work$/);
    await page
      .getByRole("tab", { name: "Marketing Analyst", exact: true })
      .click();
    await expect(page.getByRole("tabpanel")).toContainText(
      "Can this fitted model support the proposed decision?",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  });
}

test("capture responsive review evidence and check runtime health", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const dir = process.env.TEASER_SCREENSHOT_DIR ?? "test-results/review";
  await mkdir(dir, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await page.evaluate(async () => {
    await document.fonts.load("800 40px Outfit");
    await document.fonts.load("400 16px Inter");
    await document.fonts.ready;
  });
  console.log(
    await page.evaluate(() => ({
      faces: [...document.fonts].map((f) => ({
        family: f.family,
        status: f.status,
      })),
      heading: getComputedStyle(document.querySelector("h1")!).fontFamily,
    })),
  );
  expect(
    await page.evaluate(() =>
      [...document.fonts].some(
        (face) => face.family.includes("Outfit") && face.status === "loaded",
      ),
    ),
  ).toBe(true);
  expect(
    await page.evaluate(() =>
      [...document.fonts].some(
        (face) => face.family.includes("Inter") && face.status === "loaded",
      ),
    ),
  ).toBe(true);
  await page.screenshot({ path: `${dir}/desktop.png`, fullPage: true });
  await page.screenshot({ path: `${dir}/hero.png` });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: `${dir}/mobile.png`, fullPage: true });
  await page.screenshot({ path: `${dir}/mobile-hero.png` });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => {
    document.body.style.zoom = "2";
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => {
    document.body.style.zoom = "1";
  });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(errors).toEqual([]);
  console.log(
    JSON.stringify({
      words: (await page.locator("body").innerText()).split(/\s+/).length,
      fontsLoaded: await page.evaluate(() =>
        [...document.fonts]
          .filter((face) => face.status === "loaded")
          .map((face) => face.family),
      ),
    }),
  );
});
