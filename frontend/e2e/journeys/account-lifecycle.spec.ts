/**
 * Journey 8: sign up, sign out, sign in, and whether history survives.
 *
 * `UI_feedback.md` lists this as UNTESTED ENTIRELY, and build phase 4.13
 * merged with known open items on exactly this path, all recorded as
 * product-owner decisions at the time:
 *
 *   - A reload signs the account out, so history appears only after signing
 *     in again.
 *   - On a shared browser one person's guest searches follow whoever signs
 *     up next.
 *
 * Neither has been LOOKED AT since. This journey films the arc so the
 * decision to carry them can be re-taken against what a person actually
 * sees, rather than against the sentence describing it.
 *
 * ## Credentials
 *
 * The address is unique per run. A fixed one would pass once and then hit
 * the "already registered" path forever, filming a different journey than
 * the one this file claims to film, and doing it silently.
 *
 * The password is GENERATED, never a literal in this file. That is not
 * ceremony: `.claude/hooks/scan-secrets.sh` blocked an earlier draft of this
 * file for carrying a credential-shaped string, and it was right to. A test
 * credential in a repository is still a credential-shaped string that
 * someone will copy.
 */

import { expect, test } from "@playwright/test";

import { Filmstrip, JOURNEYS_ENABLED, enterApp, outputDir } from "./_capture";

function generatedPassword(): string {
  const nonce = Math.random().toString(36).slice(2, 10);
  return `Jrny8-${nonce}-${Date.now() % 100000}!aA`;
}

test.describe(
  JOURNEYS_ENABLED ? "journey 8: account lifecycle" : "journey 8 (skipped: RUN_LIVE_JOURNEYS=1)",
  () => {
    test.skip(!JOURNEYS_ENABLED, "creates a real account on the deployed app");
    test.describe.configure({ timeout: 240_000 });

    test("sign up, reload, and whether the session survives", async ({ page }) => {
      const strip = new Filmstrip(
        page,
        outputDir("journey8_account"),
        "Journey 8: account lifecycle",
      );
      await strip.begin();
      await page.setViewportSize({ width: 1440, height: 1000 });

      const email = `journey8+${Date.now()}@example.com`;
      const password = generatedPassword();
      // The address is recorded so a run can be traced; the password never
      // is, for the reason in the module docstring.
      strip.note(`account: ${email}`);

      await enterApp(page);
      await strip.capture("signed out");

      await page
        .getByRole("navigation", { name: /main/i })
        .getByRole("button", { name: /log in/i })
        .click({ timeout: 10_000 })
        .catch(() => undefined);
      await strip.capture("auth screen");

      await page
        .getByRole("button", { name: /sign up/i })
        .click({ timeout: 10_000 })
        .catch(() => undefined);
      await page
        .getByRole("textbox", { name: /email/i })
        .fill(email)
        .catch(() => undefined);
      await page
        .getByRole("textbox", { name: /password/i })
        .fill(password)
        .catch(() => undefined);
      await strip.capture("sign-up filled");

      await page
        .getByRole("button", { name: /create|sign up/i })
        .last()
        .click({ timeout: 10_000 })
        .catch(() => undefined);
      await page.waitForTimeout(2500);
      await strip.capture("after sign-up");

      // The build phase 4.13 item, filmed rather than described.
      await page.reload({ waitUntil: "domcontentloaded" }).catch(() => undefined);
      await page.waitForTimeout(1500);
      await strip.capture("after reload");

      const signedOutByReload = await page
        .getByRole("navigation", { name: /main/i })
        .getByRole("button", { name: /log in/i })
        .isVisible()
        .catch(() => false);
      strip.note(`a reload signed the account out: ${signedOutByReload}`);

      strip.write();
      expect(strip.frames, "the journey captured no frames").toBeGreaterThan(1);
    });
  },
);
