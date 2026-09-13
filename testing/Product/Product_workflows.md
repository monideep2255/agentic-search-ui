# Product workflows

Tests to run by hand on the develop app: <https://search-agent-web-develop-2aeb.up.railway.app>

Each test says what it checks, what to do, and what should happen. If something does not match, drop a screenshot in `feedback/inbox/`. Put the test number in the filename if you like.

Tip: use a private or incognito window whenever a test says "as a guest". It gives you a fresh visitor who is not signed in.

## Table of contents

- [1. Basic search](#1-basic-search)
- [2. Follow-up questions](#2-follow-up-questions)
- [3. Log in and log out](#3-log-in-and-log-out)
- [4. Guest limit of 5 searches (removed)](#4-guest-limit-of-5-searches-removed)
- [5. Wrong password](#5-wrong-password)
- [6. Search history](#6-search-history)
- [7. Answer depth](#7-answer-depth)
- [8. Off-topic question](#8-off-topic-question)
- [9. Stop a search](#9-stop-a-search)
- [10. Feedback on an answer](#10-feedback-on-an-answer)
- [11. Other pages and phone width](#11-other-pages-and-phone-width)
- [12. Trust signals and sources](#12-trust-signals-and-sources)
- [13. Suggested next step and missing-information notes](#13-suggested-next-step-and-missing-information-notes)
- [14. The scientist name at the top](#14-the-scientist-name-at-the-top)
- [15. The disclaimer](#15-the-disclaimer)
- [16. Guest searches moving into a new account (removed)](#16-guest-searches-moving-into-a-new-account-removed)
- [17. A page address that does not exist](#17-a-page-address-that-does-not-exist)
- [18. Search limit shown to a signed-in user](#18-search-limit-shown-to-a-signed-in-user)
- [19. A question with no data](#19-a-question-with-no-data)
- [20. Too many guest attempts (removed)](#20-too-many-guest-attempts-removed)
- [21. Feedback when the connection drops](#21-feedback-when-the-connection-drops)
- [What this list does not cover](#what-this-list-does-not-cover)
- [Already known, no need to report](#already-known-no-need-to-report)

## 1. Basic search

Testing: a first-time visitor can ask a question and get a cited answer.

Query: `Which diseases are associated with BRCA1?`

Steps: open the site as a guest → tick "I understand this is a research tool…" → Continue → type the query in the search box, or click the "Diseases linked to BRCA1" chip → Search

Expected:

- A progress screen with five steps and a seconds counter that keeps ticking.
- Then an answer made of sentences, each with a numbered citation chip, plus source cards.
- Diseases named in words, such as "Familial cancer of breast", never codes like `MedGen:C0346153`.
- Clicking a citation or source link opens an ncbi.nlm.nih.gov page for that record.

## 2. Follow-up questions

Testing: the chat keeps context, so "it" means the gene from the last answer.

Query: after test 1, ask `What variants cause it?`

Steps: finish test 1 → type in "Ask a follow-up question", or click the "What variants cause it?" chip → submit → then click "New search"

Expected:

- A second answer about BRCA1, without you typing BRCA1 again.
- Both questions and answers stay visible as one conversation.
- "New search" clears the conversation and returns you to the home page.

## 3. Log in and log out

Testing: one Log in button creates an account for a new email, and logging out goes to the home page.

Steps: click "Log in" at the top right → enter a new email and a password → Log in → reload the page → run test 1's query → click "Integrations" in the top bar → click your email at the top right → Log out → click "Log in" → enter the same email and password → Log in (or press Enter)

Expected:

- A sign-in screen titled "Log in" that says "Use your email and a password. A new email creates your account." It has one button, Log in, and no Sign up button.
- After the first Log in, the top right shows your initials and email instead of "Log in".
- Clicking your email opens a menu with your email, "Signed in", "API key and integrations", "Documentation" and a red "Log out".
- Search and follow-ups work the same as tests 1 and 2.
- Log out, even from the Integrations page, lands on the search home page, with the previous conversation gone.
- Logging back in with the same email and password shows your email at the top right again.
- After a reload you stay signed in: your initials and email are still at the top right, and your searches are still listed on the left.

## 4. Guest limit of 5 searches (removed)

Removed on 2026-09-12. Set 1 took away the guest limit, so there is nothing left to test here. Test 1 now covers searching as a guest, with no count and no sign-in card however many searches you run.

## 5. Wrong password

Testing: a wrong password gives a clear message, and the form still works afterwards.

Steps: click "Log in" → enter your account's email with a wrong password → Log in → fix the password → Log in

Expected:

- A wrong password shows "That password does not match this email. Check it and try again."
- Your email stays filled in, and the corrected password logs you in.
- No raw error codes or technical messages.

## 6. Search history

Testing: a signed-in user can see and re-run earlier searches.

Steps: log in → run 2 different searches → look at "Your searches" on the left → click an older one → click "Hide your searches", then "Show your searches"

Expected:

- Both searches are listed.
- Clicking one runs that question again. It is a fresh run, not a saved copy.
- The panel hides and comes back.
- Guests see no history panel.
- Reload the page: you stay signed in and both searches are still listed, without logging in again.

## 7. Answer depth

Testing: the three depth options change how the answer is written, not what it finds.

Query: `Which diseases are associated with BRCA1?`, asked three times.

Steps: on the home page choose "Clinical brief" → Search → New search → choose "Researcher" → Search → New search → choose "Deep technical" → Search

Expected:

- Clinical brief: short plain sentences, and no diagnosis or treatment advice.
- Researcher: normal scientific wording. This is the default.
- Deep technical: the most detail, with codes like `MedGen:C0346153` shown inline. That is correct at this depth.
- The same diseases appear at all three depths. A shorter answer must not quietly drop one.

## 8. Off-topic question

Testing: the product refuses rather than making something up.

Query: `What is the capital of France?`

Steps: type the query → Search

Expected:

- A refusal box with a calm grey label reading "Outside biomedical research".
- A short sentence explaining the refusal.
- No red "Not verified" or "Not fully grounded" pill.
- No error styling.
- Never an invented answer.

## 9. Stop a search

Testing: a search can be cancelled mid-way.

Query: `Which diseases are associated with BRCA1?`

Steps: Search → press Stop while the progress screen is running

Expected:

- The progress steps disappear.
- A "Search stopped" message appears.
- Two buttons appear: "Run again" and "New search".
- Clicking "Run again" asks the same question again from the start.
- Clicking "New search" returns to the home page.
- No answer appears from the stopped search.

## 10. Feedback on an answer

Testing: a reader can rate an answer and flag a bad source.

Steps: get any answer → click "Not helpful" → pick a reason, such as "Wrong answer" → type a comment → Send feedback → on a source, click "Flag: does not support"

Expected:

- Reasons appear only after "Not helpful", never after "Helpful".
- Sending confirms that it went through.
- The source changes to "Flagged".

## 11. Other pages and phone width

Testing: navigation works, including on a phone.

Steps: click Integrations → About → press the browser back button → on Integrations, click a copy button → make the window phone-narrow, or open the site on your phone → open "More pages" → log in → tap the searches button at the top right

Expected:

- Each page opens, and back returns to the previous page. There is no Docs tab; the top bar shows Search, Integrations and About.
- Integrations shows one title, four chips reading 115M nodes, 693M edges, 3 data layers and 7 tools, then four cards of the same height: REST and SSE, GraphQL, MCP server, and Command line tools. Each card has a round icon, a title, a short description, and buttons lined up along the bottom.
- Below the cards, a short access notice, then an API documentation section.
- The copy button copies the snippet.
- At phone width nothing scrolls sideways, and the other pages are reachable from "More pages".
- At phone width, while logged in, the searches button at the top right opens your searches as a panel sliding in from the left. Tapping outside it, pressing Escape, or its close button closes it.

## 12. Trust signals and sources

Testing: an answer shows how much to trust each claim.

Query: `Which diseases are associated with BRCA1?`

Steps: get the answer → read the trust signals next to the claims → open "Show work"

Expected:

- Each claim shows its trust signals, such as confidence and evidence.
- A claim backed by only one source says "Single source, not independently confirmed".
- Any sentence with no source is shown in grey with no citation chip. It must never look like a cited claim.
- "Show work" shows the steps and tools the search used.

## 13. Suggested next step and missing-information notes

Testing: the answer is honest about what it left out.

Query: `Which diseases are associated with BRCA1?`, then `Variants in GCK causing MODY`

Steps: get each answer → read the end of the answer

Expected:

- Sometimes one suggested next step, which makes sense for your question. Sometimes none, which is also fine.
- If the answer left something out, a plain note says so in everyday words, with no internal jargon.
- If the answer is a refusal instead, it shows a grey label such as "No answer found in NCBI records", and the NCBI search address inside it is a clickable link that opens in a new tab on ncbi.nlm.nih.gov.
- No note ever appears as a normal cited sentence.

## 14. The scientist name at the top

Testing: the "Working as" name is decoration only.

Steps: look at "Working as …" at the top right → run test 1's query in two separate private windows

Expected:

- A scientist's name, which may differ between visits.
- The answer is the same whichever name is shown.

## 15. The disclaimer

Testing: nobody can use the product without accepting the disclaimer.

Steps: open the site as a guest → try to click past the disclaimer, or press Escape, without ticking the box → tick the box → Continue → log in → Log out

Expected:

- The disclaimer is a wide box, about twice the width of the old one, titled "Important medical disclaimer".
- It has a bold opening sentence, a paragraph that says to seek the advice of your physician, and a notice box titled "Prototype".
- The continue button runs the full width of the box and reads "I understand, continue to the research tool". It stays greyed out until the box is ticked.
- Escape does not close it.
- After ticking and Continue, the product opens.
- It does not come back while you use the site, and it appears again after Log out.

## 16. Guest searches moving into a new account (removed)

Removed on 2026-09-12. With no guest limit, there is no guest allowance to move into an account.

## 17. A page address that does not exist

Testing: a mistyped address does not break the site.

Steps: open the site's address with `/nonsense` added to the end

Expected: you land on the Search page, not a blank or error page.

## 18. Search limit shown to a signed-in user

Testing: a signed-in user sees their own search limit, and it is true.

Steps: log in → click your email at the top right → look at the bottom of "Your searches"

Expected:

- The menu reads "Signed in", followed by your search limit.
- The bottom of the history panel names your account and your search limit.
- No "unlimited" claim anywhere.

## 19. A question with no data

Testing: when NCBI has nothing, the product says so instead of inventing an answer.

Query: `Which diseases are associated with the gene FAKEGENE99?`

Steps: type the query → Search

Expected:

- A refusal box with the grey label "No answer found in NCBI records".
- A plain sentence saying nothing was found.
- A clickable NCBI search link.
- No diseases listed.
- No citation chips.
- No red "Not verified" or "Not fully grounded" pill.

## 20. Too many guest attempts (removed)

Removed on 2026-09-12. Set 1 took away the ten-attempt guest limit. Test 8 still covers an off-topic question being refused.

## 21. Feedback when the connection drops

Testing: feedback you wrote is not lost if sending fails.

Steps: get any answer → click "Not helpful" → pick a reason and type a comment → turn off Wi-Fi → Send feedback → turn Wi-Fi back on → Retry

Expected:

- Your reason and comment stay on screen with a Retry button.
- Retry sends it once you are back online.

## What this list does not cover

Three workflows cannot be triggered by hand, so they are tested on the developer side in `../Developer/Developer_workflows.md`:

- A citation that points outside NCBI, which should be refused rather than linked.
- The shared daily limit for all guests on one network.
- How the answer text arrives on screen, sentence by sentence or all at once.
- The GraphQL and MCP integrations, which need a developer's tools to call. They are checked on the developer side after every change to the Integrations page.

## Already known, no need to report

Found by the browser run on 2026-09-12. Full report with screenshots: `../Developer/reports/2026-09-12_walkthrough/index.html`, open it in a browser.

- Follow-up questions get refused, including the suggested "What variants cause it?". Refused 3 times out of 3.
- "Which diseases are associated with BRCA1?" is refused with "I could not find grounded evidence" about one time in three. "Variants in GCK causing MODY" was refused too.
- An answer can open with "These include…" without saying what "these" are, and a "one further gene record" note shows as a grey sentence with no source.
- After sign-up, your guest searches do appear in your history, but no message says so.
- Answers sometimes take more than 25 seconds.
- An answer's first sentence can come out garbled, for example "BRCA1 (gene symbol BRCA1 [1]. These are…". Seen 2026-09-12.
- A returning guest cannot see how many searches are left until they run one.
