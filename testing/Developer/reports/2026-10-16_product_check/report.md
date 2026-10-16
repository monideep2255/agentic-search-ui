# Product check, 2026-10-16: cards 115, 17 and 94 on develop (851125c1)

Pre-screen by the product reviewer; nothing here closes a card. /health read app_env develop before the first capture. Captures: `.claude/skills/verify/scripts/capture.mjs`, spec `spec.json` into `run1/` (1280 and 390), `spec_q33.json` into `q33/` (1280 only, asked once). Golden run: not run (not in the brief, no accounts, $1.50 cap).

## Findings

### PR-1016-01: the read-only reply does not say what the app can show
- Kind: answer. Verdict: needs your eye
- What: query 111 says the change request is told "the graph is read-only and what it can show". The reply says only "This system only reads from NCBI records. It cannot add, change, or remove data." under "Read-only system", with no next thing to ask. Otherwise correct at both widths, 0.6 s and 0.7 s, 0 tool calls.
- Evidence: `run1/q111_write_followup_1280.png`, `run1/q111_write_followup_390.png` and their `.txt`.
- Why a person would care: a refusal says what to type next; this one does not.
- NOT CLOSED

### PR-1016-02: one GERD ask showed no answer within 150 s, with no capture of why
- Kind: answer. Verdict: needs your eye. NOT CLOSED
- What: my first try of the link-check script (`run2_links/`, Researcher, 1280) timed out waiting for the answer line at 150 s and saved no screenshot; the same script's retry answered in 9.9 s. A script fault is not ruled out. It failed at about 09:32 UTC; the API log for that minute would say which.

### PR-1016-03: GERD run 1 took 38.2 s and lost the knowledge graph search
- Kind: answer. Verdict: needs your eye. NOT CLOSED
- Evidence: `run1/q113_gerd_researcher_1280.png`: "? Answered 38.2s", and "The background search of the knowledge graph did not finish because it took too long". Runs 2 and 3: 7.0 s and 8.9 s.

### PR-1016-04: no GERD answer names a risk factor the question asked for
- Kind: answer (rubric lines 1 and 2, not card 17's change). Verdict: needs your eye. NOT CLOSED
- What: run 1 gives symptoms, PPI harms and a children paper; runs 2 and 3 give pathogenesis ("Pathogenic factors include abnormal transient relaxations of the lower esophageal sphincter ..."). None says obesity, smoking or pregnancy; a general chatbot would. The count line "Found 5 pubmed records, ..." sits inside the first paragraph in all three.

### PR-1016-05: query 33 took 34.2 s, over 25 s
- Kind: answer. Verdict: needs your eye. NOT CLOSED
- Evidence: `q33/q33_isolates_1280.png`, "Answered 34.2s". Earlier: 20.0 s (2026-10-05), 27.4 s (2026-10-09). One sample.

## Per card
- Card 115, query 111: PASS, wording aside (PR-1016-01). Read-only reply at 0.6 s (1280) and 0.7 s (390), never the off-topic line. `run1/q111_write_followup_*`.
- Card 17, query 113: PASS on what I could check. Lead-ins appeared in runs 1 and 3, none wrongly. Run 3: the lead-in "From the paper "Gastroesophageal reflux disease in children: What's new right now?":" cites [14], whose link opens pubmed 37034973, the table's row of that title (`run2_links/q113_gerd_researcher_links.json`). Run 1's lead-in cites [15]; its link was not captured. Run 2's move from [13] to [14] has no lead-in, but GERD is its only link, the known open case. Seconds: 38.2, 7.0, 9.9 (3 answered, 1 timed out at 150 s).
- Card 94, query 33: PASS. The answer arrived whole: 20 rows across two pages, the 141,578 count and the blaCTX-M note, no crash and no console errors, 34.2 s. The timeout path itself was not exercised. "Not recorded" in Collected matches the BioSamples (2026-10-09 check).

## Screens, overflow and design
- Overflow at 390: 0 px on all four screens. Axe serious or critical: 0. Console errors: 0.
- No design: the follow-up field and its refusal (`docs/build/design/README.md`, "Follow-up field | NO").

## Not captured, and what rests on what
- Query 33 at 390 (asked once, as briefed). The link for run 1's [15]. Golden run: no accounts, cap. Spend not metered: 7 questions asked (1 never answered), plus 2 follow-up refusals with 0 tool calls.
- Read myself: every `.txt` above, the q111 PNGs at both widths, GERD fold PNGs at both widths, the q33 fold PNG, and the links JSON. Prototype pairs: not read.
