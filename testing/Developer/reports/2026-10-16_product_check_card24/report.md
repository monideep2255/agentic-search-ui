# Product check, card 24 (#245), deployed develop

This is a pre-screen by the product reviewer, and nothing here closes a card. Before the first capture, /health read app_env develop. Captures came from `.claude/skills/verify/scripts/capture.mjs`, using `spec.json`, into `run1/`, at 1280 and 390, with --no-prototype because of the deadline. Guest flow only, 8 live questions (6 BRCA1, 2 weather). The golden run was not run because it was not in the brief.

- Step 1, Plain language answer with the switch beside Show work: PASS. In `run1/q112_s1_s2_confirm_line_390_fold.png`, which I read myself, "Plain language | Researcher" sits beside "Show work" and Plain language is lit. 1280 and 390 reached in 9.7 s and 7.9 s (question to confirm line).
- Step 2, confirm line: PASS. `run1/q112_s1_s2_confirm_line_1280.txt` reads "Ask this question again in Researcher? It runs as one new search." with "Ask again" and "Cancel". The 390 screenshot shows the same, with the line on its own row under the switch.
- Step 2, Cancel and Escape run nothing: PASS. After each, the line closed (waited for detach) and a 3 s wait followed. The final page text holds the question exactly twice, the folded answer plus the one Ask again run (`run1/q112_s2_s3_cancel_escape_then_ask_again_1280.txt` and `_390.txt`), so neither Cancel nor Escape started a search.
- Step 3, Ask again: PASS. `previous-turn-0-mode` appeared and the text reads "Plain language" above the new answer, which reads "Plain language / Researcher" in its switch. After a 5 s wait there was no third search (question count 2). Whole screen, first answer plus three clicks plus the second answer: 35.4 s at 1280, 28.9 s at 390. The capture does not time the second search on its own.
- Step 4, weather refusal: PASS. `run1/q112_s4_weather_refusal_1280.txt` reads "Outside biomedical research ... I can help with a gene, variant, pathogen, or paper question." and has no "Plain language" or "Researcher" text, so it shows no switch. Reached in 4.9 s and 5.3 s.
- Overflow at 390: 0 px on all three screens. Axe serious or critical: 0 on all six. Console errors: 0 on all six (`run1/results.json`).
- Needs your eye: the status line in the 390 screenshot reads "? Answered 6.5s · 13 tool calls · 21 sources cited", with what looks like a "?" glyph before Answered.
- Missing design: the confirm line has no design (the component's own comment says so), so it was not judged against one.
- Card 117 known items: I did not measure the 19 px blank strip, and I did not try to reproduce the raw "clinical_brief" label.
- Not captured: focus return and Tab order, a click on the lit mode, the follow-up after the switch, and the prototype pairs.
- What rests on what: I read the 390 confirm-line screenshot and every page text cited above myself. The 1280 screenshots and the other 390 screenshots I did not open; their pass rests on the script's checks and the saved text.
