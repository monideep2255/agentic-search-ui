/**
 * Journey 5: every affordance on the integrations page.
 *
 * `docs/build/UI_feedback.md` complaint 4. The page names KGX, MCP, GraphQL, REST and
 * SSE, and what it does not do is let anyone use them. The document's own
 * table is blunt about the worst of it: the KGX control is described in this
 * repository's own `stubs/registry.ts` as "a request button that
 * acknowledges and does nothing", and there is no KGX HTTP endpoint at all,
 * the export existing only as the `s3-kgx-export` command-line tool.
 *
 * So this journey clicks EVERY control on the page and films what happens,
 * which is the evidence T-6.2-09 needs. That ticket is blocked on a product
 * decision, build the endpoint or stop advertising it, and a strip showing
 * exactly what a visitor gets today is what the decision should be made
 * against.
 *
 * Spends NO guest answer: it never asks a question.
 */

import { expect, test } from "@playwright/test";

import { Filmstrip, JOURNEYS_ENABLED, enterApp, outputDir } from "./_capture";

test.describe(
  JOURNEYS_ENABLED ? "journey 5: integrations" : "journey 5 (skipped: RUN_LIVE_JOURNEYS=1)",
  () => {
    test.skip(!JOURNEYS_ENABLED, "reaches the deployed app");
    test.describe.configure({ timeout: 180_000 });

    test("click everything on the integrations page", async ({ page }) => {
      const strip = new Filmstrip(page, outputDir("journey5_integrations"), "Journey 5: integrations affordances");
      await strip.begin();
      await page.setViewportSize({ width: 1440, height: 1000 });

      await enterApp(page);
      await page
        .getByRole("navigation", { name: /main/i })
        .getByRole("link", { name: /integrations/i })
        .click({ timeout: 10_000 })
        .catch(async () => {
          await page.getByRole("button", { name: /integrations/i }).click({ timeout: 10_000 }).catch(() => undefined);
        });
      await strip.capture("integrations page");

      // Enumerate rather than name them: a hardcoded list of controls would
      // go stale silently, and the point of this journey is to find what is
      // there rather than to confirm what someone remembered.
      const controls = page.getByRole("main").getByRole("button");
      const count = await controls.count().catch(() => 0);
      strip.note(`buttons on the page: ${count}`);

      for (let index = 0; index < count; index += 1) {
        const control = controls.nth(index);
        const name = (await control.textContent().catch(() => null))?.trim() || `#${index}`;
        const before = await page.evaluate(() => document.body.innerText.length).catch(() => 0);

        await control.click({ timeout: 5_000 }).catch(() => undefined);
        await page.waitForTimeout(700);
        await strip.capture(`clicked ${name}`);

        const after = await page.evaluate(() => document.body.innerText.length).catch(() => 0);
        // The crude discriminator between a control that did something and
        // one that did nothing. Crude is fine here: the strip carries the
        // screenshots, and this line only tells a reader which frames to
        // look at first.
        strip.note(`  "${name}" -> page text ${before} to ${after}${before === after ? "  (NO VISIBLE CHANGE)" : ""}`);
      }

      strip.write();
      // `>= 1`, not `> 1`. This journey captures one frame per control plus
      // the page itself, so a page with NO controls legitimately produces a
      // single frame, and that single frame is a real finding rather than a
      // failure. The first version used `> 1` copied from journey 2, and it
      // turned "the page has no dead buttons" into a red test.
      expect(strip.frames, "the journey captured no frames at all").toBeGreaterThanOrEqual(1);
    });
  },
);
