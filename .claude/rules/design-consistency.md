## Design consistency

Product-owner rule, 2026-09-05: the UI must be beautiful, and the system is ALREADY beautiful. The job is therefore consistency, never invention. Any new or rebuilt surface copies the established visual language rather than producing a second one alongside it.

### The source of truth, in order

1. `docs/build/design/design-system/` is the design system. Foundations (`colors.html`, `type.html`, `spacing.html`), components (search bar, app bar, depth control, feedback, source card, trust pills, pipeline stepper, persona), identity (citation chip, layer badges, provenance spine), screens (home, answer, streaming), flows (disclaimer modal, guest states), and the assembled `prototype/app.html`.
2. `frontend/src/theme.ts` encodes that system as `designTokens` and the MUI theme. Code reads tokens from here, never a hardcoded hex.
3. A shipped component that already matches the system is the working example. `components/guest/GuestAllowance.tsx` is the reference for a centred card.

When 1 and 2 disagree, 1 is the design intent and the disagreement is a defect worth reporting rather than silently resolving.

### Before styling anything, find its design

Open the design system first and look for the surface you are about to build. Most of them are there. Build phases 4.8 and 4.9 delivered the visual design and a nine-gap fidelity pass against it, so a surface that looks wrong today is usually a drift from something already specified.

CHECKING ONE FILE IS NOT CHECKING THE DESIGN SYSTEM. Added 2026-09-05, hours after this rule was written and broken by its own author. `components/app-bar.html` carries no responsive rule, and that was read as "the app bar has no mobile design". It has one, in `prototype/app.html`: line 403 hides every non-current nav item at 720px and line 404 tightens the bar. A two-row wrapping bar was invented, shipped, and reverted.

So the search is at least three places, in this order:

- `design-system/prototype/app.html`, the ASSEMBLED product. It is the only file that answers "what happens at 390px", because every media query lives there and nowhere else.
- The relevant card under `components/`, `screens/`, `identity/` or `flows/`.
- `foundations/`, for any value the first two do not settle.

`docs/build/design/README.md` carries a coverage table naming every surface that has a design and every one that does not. Read it before concluding that a design is missing. A missing design and a design you did not find look identical from the browser, and only one of them licenses invention.

### When a surface has no design, say so

Measured 2026-09-05: the sign-in and sign-up screen is not in the design system at all. `flows/guest-states.html` designs the wall a guest hits and contains zero input fields, and no other file carries an email or password field. That is why the screen shipped unstyled: it was never part of the design pass, so there was nothing to implement.

A missing design is a different problem from a drifted one, and conflating them produces invention. So:

- Name the gap out loud rather than filling it silently.
- Build from the foundations plus the nearest designed neighbour. For a form, the search bar is the precedent for a text input; for a centred card, the guest-states wall is the precedent.
- Report which token supplied each value, so the next reader can check the derivation instead of trusting it.

### Consistency beats idiom

Where the design system and a component library's defaults disagree, the design system wins. A default MUI outline is one pixel; the search bar specifies two, deliberately, so the control holds its own. Override the library rather than let the surface drift.

### Three-state permissions

Allow:
- Read the design system freely, and build a new surface from its foundations and nearest neighbour, without asking.
- Override a component library default so a surface matches the design system.

Ask:
- Before introducing a visual value that no foundation supplies: a new colour, a new radius, a new type size.
- Before changing anything in `frontend/src/theme.ts`, since every surface reads from it.

Deny:
- Never hardcode a hex, radius or type size that a design token already carries.
- Never invent a look for a surface that already has one in the design system.
- Never fill a missing design silently. Name the gap, then build from the foundations.

The test: did I open the design system, and can I name the token or the designed neighbour behind every visual value I just wrote?
