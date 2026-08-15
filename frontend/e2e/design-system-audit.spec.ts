/**
 * An accessibility audit of the DESIGN SYSTEM itself, not the app.
 *
 * Added 2026-08-14 after the same defect was hit three separate times in two
 * build phases: a token or a markup pattern taken faithfully from the design
 * turned out to fail WCAG 2.1 AA, so "matches the design" and "passes the
 * accessibility gate" disagreed and the code had to deviate. Each time the
 * deviation was filed and worked around at one call site.
 *
 * Pointing axe at the cards ends that: the design system is now held to the
 * same bar as the app, and a contrast or focus-nesting defect is caught in the
 * card rather than three phases later in a component built from it.
 *
 * It found seven violations on its first run, four of them one token, and the
 * design system is at zero now.
 *
 * WHAT IT CANNOT SEE, stated so the gap is arguable rather than discovered:
 * the prototype card renders ONE screen. Its other six screens are `hidden`,
 * so nothing here scans the answer screen, the account menu or the source
 * cards as the prototype draws them. Two of the three defects above were found
 * by driving the running app into those states, not by this file.
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { writeFileSync, readdirSync } from "node:fs";
import path from "node:path";

const DS = "/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/docs/build/design/design-system";
const OUT = "/private/tmp/claude-501/-Users-anuradhachakraborti-Desktop-Tech-Skills-agentic-search-ui/5071737f-3fc1-4077-8bbc-f22e1383fa74/scratchpad/ds-audit.json";

function cards(): string[] {
  const out: string[] = [];
  for (const dir of ["brand", "components", "flows", "foundations", "identity", "prototype", "screens"]) {
    for (const f of readdirSync(path.join(DS, dir))) {
      if (f.endsWith(".html")) out.push(`${dir}/${f}`);
    }
  }
  return out.sort();
}

test("audit the design system itself", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1200, height: 900 });
  const results: Record<string, unknown[]> = {};
  for (const rel of cards()) {
    await page.goto("file://" + path.join(DS, rel));
    await page.waitForTimeout(250);
    const r = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    results[rel] = r.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      nodes: v.nodes.map((n) => ({
        html: n.html.slice(0, 160),
        summary: (n.failureSummary ?? "").replace(/\s+/g, " ").slice(0, 220),
      })),
    }));
  }
  writeFileSync(OUT, JSON.stringify(results, null, 1));

  /*
   * THE ASSERTION. An earlier version of this file only wrote the JSON and
   * asserted nothing, so it passed unconditionally; a mutation restoring the
   * old failing green left it green, which is how that was caught.
   *
   * Compared as a list of "card: rule" strings rather than a count, so a
   * failure names the card and the rule in its own message.
   */
  const offenders = Object.entries(results)
    .filter(([, violations]) => violations.length > 0)
    .map(([card, violations]) =>
      `${card}: ${violations.map((v) => (v as { id: string }).id).join(", ")}`,
    );
  expect(offenders).toEqual([]);
});
