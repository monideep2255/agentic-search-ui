# Product check of cards 135 (part 1) and 136 (part 3) on develop, 2026-10-30

A pre-screen before the owner retests. It closes nothing; the owner's verdict closes.

- Target: develop web `https://search-agent-web-develop-2aeb.up.railway.app`, API `/health` read `{"status":"ok","app_env":"develop"}` before the first capture.
- Deployed commit: a21b0b1e (merge of #314, on top of #313), as stated in the brief.
- Signed in with a throwaway develop account created through the app's own log in screen ("A new email creates your account"); no email confirmation was asked for. The research-tool disclaimer was ticked in a fresh automated browser. No golden run, by the brief.
- Capture: Playwright scripts run from `frontend/`; every judgement below names the file it rests on, all in this folder.

## Table of contents

- [Findings](#findings)
- [Summary](#summary)

## Findings

### PR-135-136-01: The OMIM source links to omim.org on the live answer, at 1280 and 390
- Kind: screen
- Verdict: pass
- Card: 135 part 1
- What: query 21 in Researcher answered in 12.3 seconds (meta line "Answered 11.7s · 13 tool calls · 22 sources cited from 2 layers"). Source [8], "omim 138079", shows RECORD `https://omim.org/entry/138079` as a link. No "Not linked" text anywhere on the page at either width. Overflow at 390: 0 px.
- Evidence: `q21_live_1280_omim_row.png`, `q21_live_390_omim_row.png`, `q21_live_1280_full.png`, `q21_live_390_full.png`, `q21_live_log.json`, `q21_live_answer.txt`. The 390 capture is the same live page resized, not a second ask.
- Why a person would care: a clinician checking the glucokinase record can open it from the answer.
- NOT CLOSED
- Correction, same evening: `q21_live_390_omim_row.png` shows the "Your searches" drawer open over the answer after the resize, so the OMIM row is covered there. The 390 half of this finding rests only on the page's link list in `q21_live_log.json` until the 390 re-capture in PR-135-136-04 below.

### PR-135-136-02: The OMIM source links to omim.org on the reopened saved answer at 1280
- Kind: screen
- Verdict: pass
- Card: 135 part 1
- What: query 21 reopened from "Your searches" lists source "8. omim LIVE" with the link `https://omim.org/entry/138079`. No "Not linked" text in the saved answer.
- Evidence: `q21_saved_1280_omim_row.png`, `q21_saved_answer.txt` (lines "8. omimLIVE" and "https://omim.org/entry/138079").
- Why a person would care: the source that used to read "Not linked: this URL is not on a recognised NCBI host." now opens the OMIM entry.
- NOT CLOSED

### PR-135-136-03: On a computer, picking a past search leaves the rail open
- Kind: screen
- Verdict: pass
- Card: 136 part 3
- What: at 1280, after picking "Which diseases are associated with GCK?" in "Your searches", the saved answer shows and the rail stays open beside it, both searches listed.
- Evidence: `q51_1280_after_pick_rail_open.png`, `q21_saved_1280_omim_row.png`.
- Why a person would care: on a computer the list stays where it was, as before.
- NOT CLOSED

### PR-135-136-04 (reserved for the 390 OMIM re-capture, see below)

### PR-135-136-05: Reopened sources still read as raw tool names
- Kind: screen
- Verdict: needs your eye
- Card: earlier (card 135 part 2, diagnosed, not in these slices)
- What: the reopened Sources list reads "4. ncbi_efetch LIVE", "8. omim LIVE", "10. ncbi_gene LITERATURE", "11. clinicaltrials.gov LITERATURE". The live source cards read "omim 138079", "clinvar 4881360", lowercase.
- Evidence: `q21_saved_1280_omim_row.png`, `q21_live_1280_omim_row.png`.
- Why a person would care: "ncbi_efetch" is a tool name, not a database a reader knows.
- NOT CLOSED

### PR-135-136-06: A human GCK answer cites a literature gene record that looks like another species
- Kind: answer
- Verdict: needs your eye
- Card: earlier
- What: query 21's table "Literature entity records found" lists "Gck | @GENE_GCK" [10], and source 10 links to `https://www.ncbi.nlm.nih.gov/gene/24385`. The human GCK record is gene 2645 (source 5). I did not open 24385 to confirm the species; lowercase "Gck" is the rodent symbol style. The second paragraph cites a cardiomyocyte paper: "Recent work describes inhibition of Hmbox1 promoting cardiomyocyte survival through Gck activation in ischemia/reperfusion injury".
- Evidence: `q21_live_answer.txt`, `q21_saved_answer.txt`, `q21_saved_1280_omim_row.png`.
- Why a person would care: a clinician asking about the human gene may follow a citation to a non-human gene record, a confident wrong record.
- NOT CLOSED

### PR-135-136-07: Query 21's first two sentences say the same thing
- Kind: answer
- Verdict: needs your eye
- Card: earlier
- What: "GCK is associated with four diseases: Type 2 diabetes mellitus, Maturity-onset diabetes of the young type 2, Hyperinsulinemic hypoglycemia, familial, 3, and Permanent neonatal diabetes mellitus 1." is followed at once by "Found 4 disease records for GCK: Type 2 diabetes mellitus, Maturity-onset diabetes of the young type 2, Hyperinsulinemic hypoglycemia, familial, 3 and Permanent neonatal diabetes mellitus 1." Rubric line 1 passes: the first sentence answers. OMIM 138079 is among the sources and no other gene's OMIM record appears, as query 21 expects.
- Evidence: `q21_live_answer.txt`.
- Why a person would care: the reader reads the same list twice in the opening lines.
- NOT CLOSED

### PR-135-136-08: Query 51 (search history) at 1280 meets every line
- Kind: screen
- Verdict: pass
- Card: 136 part 3 (no change expected on a computer) and earlier
- What: both searches are listed ("What does GCK do? 18 sources cited · Oct 30" and "Which diseases are associated with GCK? 22 sources cited · Oct 29"). Clicking the older one shows "SAVED ANSWER · ASKED OCT 29, 2026, 11:59 PM" with a Run again button, at once, rail still open. "Hide your searches" leaves the "YOUR SEARCHES 2" strip; clicking it brings the rail back. After a reload the account is still signed in and both searches are still listed. Guests seeing no panel was not re-checked here.
- Evidence: `q51_1280_both_listed.png`, `q51_1280_older_opened.png`, `q51_1280_hidden.png`, `q51_1280_shown.png`, `q51_1280_after_reload.png`, `q51_1280_log.json`. The brief named "query 1202"; no query carries that number, and line 1202 of `testing/Test_queries_and_workflows.md` sits inside query 51, so I ran query 51.
- Why a person would care: the history rail on a computer behaves as before the phone fix.
- NOT CLOSED

### PR-135-136-09: The reopened answer shows citations as plain "[1]" text
- Kind: screen
- Verdict: needs your eye
- Card: earlier (card 135 part 3, diagnosed, not in these slices)
- What: the reopened answer reads "Type 2 diabetes mellitus [1]" and the gene row "GCK [5][9]" as literal text, where the live answer shows superscript markers "1 to 4" (one range marker) and "5, 9".
- Evidence: `q51_1280_older_opened.png`, `q21_live_answer.txt`.
- Why a person would care: the saved copy looks different from the answer they read and the numbers cannot be pressed.
- NOT CLOSED

### PR-135-136-04: The OMIM source links to omim.org at 390, live and reopened
- Kind: screen
- Verdict: pass
- Card: 135 part 1
- What: at 390x844 the reopened query 21 lists "8. omim LIVE" with the link `https://omim.org/entry/138079`. Query 21 asked a second time at 390 (answered in 12.5 seconds, meta "Answered 12.1s · 13 tool calls · 22 sources cited from 2 layers") shows source [8] "omim 138079" with RECORD `https://omim.org/entry/138079`, the drawer closed. No "Not linked" text on either screen. Overflow 0 px on both. I opened the source card, not the citation marker's pop-up card.
- Evidence: `q21_saved_390_omim_row.png`, `q21_saved_390_full.png`, `q21_live_390_second_ask_omim_row.png`, `q21_live_390_second_ask_full.png`, `q21_live_390_second_ask_answer.txt`, `d390_log.json`.
- Why a person would care: on a phone the OMIM record opens from both the fresh and the saved answer.
- NOT CLOSED

### PR-135-136-10: On a phone, picking a past search closes the drawer and shows that answer
- Kind: screen
- Verdict: pass
- Card: 136 part 3
- What: at 390x844, with the drawer open listing "What does GCK do?" and "Which diseases are associated with GCK?", tapping the older one closed the drawer (no "Your searches" dialog on screen, the app bar toggle reads aria-expanded false) and showed "SAVED ANSWER · ASKED OCT 29, 2026, 11:59 PM" with Run again. Overflow 0 px.
- Evidence: `d390_02_drawer_open.png`, `d390_03_after_pick_older.png`, `d390_log.json` ("after_pick_older").
- Why a person would care: the answer they picked is in front of them, not hidden behind the list.
- NOT CLOSED

### PR-135-136-11: On a phone, "+ New search" closes the drawer and shows the question screen
- Kind: screen
- Verdict: pass
- Card: 136 part 3
- What: reopening the drawer over the saved answer and tapping "+ New search" closed it and showed "Ask a biomedical question" with the question box. Overflow 0 px.
- Evidence: `d390_04_drawer_open_again.png`, `d390_05_after_new_search.png`, `d390_log.json` ("after_new_search").
- Why a person would care: they can type the next question at once.
- NOT CLOSED

### PR-135-136-12: The phone drawer for "Your searches" has no design
- Kind: missing design
- Verdict: needs your eye
- Card: earlier (design gap)
- What: `docs/build/design/README.md`'s coverage table marks "History rail and its collapsed strip" as NO design, and the prototype hides the rail below 860px (`prototype/app.html:65`), so nothing says how the phone drawer should look or behave. The drawer was judged only against the brief's "after" lines, not against a design.
- Evidence: `docs/build/design/README.md` line 90, `docs/build/design/design-system/prototype/app.html` line 65, `d390_02_drawer_open.png`.
- Why a person would care: no agreed look exists to hold the phone drawer to.
- NOT CLOSED

### PR-135-136-13: A short grey line runs down the middle of the phone drawer
- Kind: screen
- Verdict: needs your eye
- Card: earlier (the drawer of 2026-09-13), not these slices
- What: in the open drawer the rail's own right border stops just below the account line, about a third of the way down, inside a wider white panel with its own edge, so a short vertical line hangs beside the list.
- Evidence: `d390_02_drawer_open.png`, `d390_04_drawer_open_again.png`, `q21_live_390_omim_row.png`.
- Why a person would care: it reads as a stray rule left over from the computer layout.
- NOT CLOSED

### PR-135-136-14: An opened source card shows internal field values
- Kind: screen
- Verdict: needs your eye
- Card: earlier
- What: every opened live source card reads "TOOL title", "EVIDENCE primary_assertion", "CONFIDENCE asserted", "LICENSE public_domain_us_gov", with a "Flag: does not support" button. My script opened every card at once to read links; a person opens one at a time and sees the same fields.
- Evidence: `q21_live_1280_omim_row.png`, `q21_live_390_second_ask_omim_row.png`.
- Why a person would care: "title" as the tool and underscored codes read as debugging output, not as a source description.
- NOT CLOSED

### PR-135-136-15: "What does GCK do?" opens mid-thought rather than saying what GCK does
- Kind: answer
- Verdict: needs your eye
- Card: earlier (card 147's summaries that open mid-thought is related)
- What: the first sentence is "The enzyme operates in a tissue-specific manner, playing a role in glucose-stimulated insulin secretion in the pancreas and in glucose uptake and conversion to glycogen in the liver." It never first says GCK makes glucokinase, which turns glucose into glucose-6-phosphate; the second sentence is "Found 1 gene record for GCK: glucokinase." Answered in 9.8 seconds by its meta line. This question was asked only to put a second search in the list; one run.
- Evidence: `q2_gck_do_live_answer.txt`, `q2_gck_do_live_1280_full.png`.
- Why a person would care: "the enzyme" arrives before they are told which enzyme.
- NOT CLOSED

## Summary

| Slice | Verdict | Findings |
|---|---|---|
| Card 135 part 1, OMIM links on live and reopened answers | Pass at 1280 and 390 | PR-135-136-01, 02, 04 |
| Card 136 part 3, the drawer closes after a pick on a phone | Pass at 390; the rail unchanged at 1280 | PR-135-136-03, 08, 10, 11 |

Answer times, from the script's clock (submit to the answer's meta line):

| Question | Width | Seconds |
|---|---|---|
| Query 21, Researcher, first ask | 1280 | 12.3 |
| `What does GCK do?` | 1280 | 9.8 by its meta line (the script's own timing was lost when that run stopped on a selector error after the answer) |
| Query 21, Researcher, second ask | 390 | 12.5 |

None over 20 seconds.

What to look at first, ranked: no fails. Needs your eye, in order: PR-135-136-06 (a GCK answer citing what looks like a non-human Gck gene record), 15 and 07 (answer openings), 14 (internal codes on source cards), 05 and 09 (the other two card 135 parts, still open), 13 (a stray line in the drawer), 12 (no design for the phone drawer).

Overflow at 390: 0 px on every screen measured (live answer, saved answer, question screen, with and without the drawer). Surface with no design: the phone drawer for "Your searches" (PR-135-136-12).

What was not captured, and why:

- The citation marker's pop-up card for source 8 was not opened; the OMIM verdicts rest on the source card and the reopened Sources list.
- The prototype was not screenshot beside these screens: it has no phone drawer, and the rail at 1280 is unchanged by these slices.
- Guests seeing no history panel (query 51's last line but one) was not re-checked.
- The screenshots show the throwaway account's address in the account menu and rail footer; the text and log files have it replaced. Check the images before any commit.
- A new browser started from the first run's saved sign-in state came up signed out, so the later scripts signed in again. A reload inside one browser kept the account signed in (`q51_1280_log.json`), which is what query 51 asks.

Every verdict above rests on a screenshot or answer file I read myself, except the "no Not linked text" and overflow numbers, which rest on the scripts' logs (`q21_live_log.json`, `q51_1280_log.json`, `d390_log.json`).
