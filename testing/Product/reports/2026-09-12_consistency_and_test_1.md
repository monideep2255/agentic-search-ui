# Consistency across questions, and test 1

Written 2026-09-12 for the product owner, in answer to two things raised while starting `Product_workflows.md`. Nothing here has been built or changed yet.

## 1. Do all questions perform at the same level?

Short answer: no check does that today. Testing with one question tells you about that one question, and today showed that even one question does not behave the same way twice.

### What exists

| Check | What it does | Does it prove consistency? |
|---|---|---|
| Golden dataset, `eval/golden/golden_dataset.json` | 50 questions with expected outcomes and required citations: 24 simple lookups, 20 multi-step questions, 6 open-ended discovery questions | No. It is a list of questions. Nothing runs it against the live product |
| The grader that scores answers against those 50 | Built in build phase 5.2 | No. It is parked because it does not work, and it refuses to run |
| Local automated tests, 60 passing | Check that the screens and buttons work | No. The AI model is faked, so no real answer is ever produced |
| Today's browser walkthrough | Real searches on develop | Only a sample, and it showed the problem: 7 of 12 real questions were refused |

The clearest evidence: "Which diseases are associated with BRCA1?" answered 5 times and was refused 3 times, at different depths, minutes apart. Full report with screenshots: `../Developer/reports/2026-09-12_walkthrough/index.html`.

### How to make sure

A proposal, in order. The first step needs no new grader, just counting.

1. Consistency run, done by the assistant on the developer side. Ask each of the 50 golden questions 3 times on develop, signed in, and record for each run: answered or refused, how long it took, and how many sources and layers it used. That is 150 real searches, roughly an hour and a few dollars.
2. A one-page result per question, for example "BRCA1 diseases: answered 2 of 3". Anything below 3 of 3 is inconsistent.
3. Fix the biggest causes first. Today that is the flagship question refusing about one time in three, and follow-up questions being refused every time.
4. Re-run the same 150 searches after each fix, so the result is a number that goes up, not an impression.
5. Only once questions answer reliably, judge answer quality: the grader, or a domain expert reading the answers.

Until step 1 has run, a good answer on one question should not be read as the product working.

## 2. Test 1, basic search

### What you saw, in your words

"I go onto the website. I click the disclaimer, otherwise I can't continue. Then I type in the question, diseases linked to BRCA1, and click Search. It tells me to sign in to keep searching, because this browser's guest session was moved into an account. This is a really bad experience, and it needs to be consistent. One thing we need to change for now is to get away with the five search concept, keep the login, and allow people to search, because this is just a prototype. I haven't been able to even do the basic search."

### Why it happened

- A browser that has ever created an account remembers that, and the memory survives signing out and reloading.
- Reloading the page already signs you out.
- Together, any browser used to sign up can never search as a guest again, even with free searches left. It shows "This browser's guest session was moved into an account" instead.

So the wall blocks you before your first search, which is why test 1 could not even start.

### Your decision

Remove the five-search guest limit for the prototype, keep sign-in available, and let people search.

What that removes:

- The five free searches and their counter.
- The "You have used your free searches" wall.
- The "moved into an account" wall.
- The ten-attempt ceiling, and tests 4, 16 and 20 in `Product_workflows.md` with it.

What should stay, because it bounds real cost rather than guest behaviour, and is not the thing blocking you:

- The per-search cost cap.
- The system-wide daily spending cap.
- The daily cap on anonymous searches across all visitors.

Changing a cost cap needs your explicit approval under this repository's rules, so those three are listed here rather than removed silently.

## 3. Test 1, second try

### What you saw on the second try, in your words

"I was able to do the search this time. One thing I want kept consistent is the box size. Right now it starts smaller and becomes bigger and bigger. The white box should stay the size it is when the answer is actually shown. I also thought we were going to stream the answer, and I don't see streaming. It just shows the answer, and it is very sparse. This was in researcher mode, so I don't know if that was done on purpose. And then there is 'Single source, not independently confirmed'."

### What each one is

| What you saw | Why it happens | Already known? | Fix |
|---|---|---|---|
| The white box grows | The progress card is about 570px wide and the answer card about 850px, measured from today's screenshots. The screen swaps one card for the other | Seen in the walkthrough, not yet written down | Make the progress card the same width as the answer card, so the box never changes size |
| The answer does not stream | The answer is split into sentences, but all of them are sent to the browser in a single burst at the end, so it arrives all at once. Recorded in `Developer_workflows.md` as W-thread-12 | Yes, on the developer side only | Send each sentence as soon as it is ready, so it builds up on screen |
| The answer is very sparse | Researcher depth is supposed to give standard scientific wording with full detail. What came back is one sentence listing four diseases. Not on purpose | Partly: your first-impressions note, point 3 | Part of the answer quality work: richer writing at researcher depth, formatted to be easy to read |
| "Single source, not independently confirmed" | The label appears when only one independent source backs the answer. Today the search only ever reaches one live source, so almost every answer will show it. This is the same root cause as your first-impressions point 5, where most search layers never run | Yes, on the developer side as finding F-3.4-A-04 | Search more layers, so an answer can be confirmed by a second source. The label is honest; the search behind it is too narrow |

## 4. Go deeper, depths, transitions and follow-ups

### What you saw, in your words

"When it asks me 'do you want me to go deeper?', I clicked on it and it completely refused. What was the purpose? Have you not set up the context that gets fed into it? For a researcher we're showing two or three lines. That is not enough. How have we set the limits for the three types of search? A researcher can understand complex language, but it should still be easy to understand. We could have a mode where things are put into simple terms, using first principles, so that a high school student could follow. We need to define the appropriate length someone needs to see. Clinical brief, researcher and deep technical need their limits fixed, and we should discuss it."

"The transitions are very weird. The footer moves all over the place. The header and footer should stay consistent, including going from the home page to the search page. It needs to be a much smoother experience. Right now it looks very static and clunky."

"With a different question, I don't see any answers being produced. With diseases linked to BRCA1, I tried the follow-up 'What variants cause it?' and it refuses to answer, which means it is not retaining the previous context. Secondly, it goes to a new page, which it should not. The first answer should minimise and the chat should continue on the same screen. That is one of the most important things."

### What each one is

| What you saw | Why it happens | Fix |
|---|---|---|
| "Yes, go deeper" is refused | The button sends its own offer sentence as the next question, for example "Would you like me to go through the 1 further gene record found for this question?". That sentence never names BRCA1, so it breaks the same way follow-ups do | The button should continue the same search using what the previous answer already found, not start a new search from a sentence |
| Follow-ups are refused | "It" is never connected to BRCA1. In the walkthrough, one try was refused as off-topic in 1.4 seconds, before any search ran. Another did search, but for the literal words "What variants cause it?", which is visible in its NCBI fallback link. Refused 3 of 3 times in the walkthrough, and again in your test. Exactly where the earlier turn gets lost is not yet traced in the code | Carry the previous turn into every step, starting with the on-topic check, and resolve "it" to the gene before searching |
| A follow-up feels like a new page | The earlier answer does collapse, but the new question replaces the whole card and jumps to the top, so it reads as a fresh page rather than a conversation | Keep one conversation on one screen: the earlier answer shrinks above, and the new answer grows below it |
| Header and footer jump around | The header and footer sit around content whose height keeps changing: home page, then a short progress card, then a long answer. The footer follows the bottom of whatever is on screen | Fix the header and footer in place and give the content area a stable height, so only the content changes |
| Screens swap instead of transitioning | Home, progress and answer are separate screens that replace one another with no motion between them | One continuous layout with smooth transitions between states |
| No answer for a different question | Consistent with the walkthrough, where 7 of 12 real questions were refused | The consistency run in section 1, then fixing the biggest causes |

### What the three depths should be, since settled in sections 7 and 10

How they are defined today, in `src/system_03_search_agent/synthesis/findings.py`:

| Depth | The whole instruction today | Length limit |
|---|---|---|
| Clinical brief | For a clinician who needs the evidence fast, plain clinical language, keep it short, complete sentences, never diagnose or recommend treatment | None, only "keep it short" |
| Researcher | For a working researcher, standard biomedical vocabulary, full mechanistic detail | None |
| Deep technical | For a bioinformatician, maximum technical depth, identifiers like `NCBIGene:672` inline | None |

No depth has a length target, and nothing defines what a good answer contains at each depth. That is why researcher mode produced one sentence.

Your proposal at the time, since settled in sections 7 and 10:

- Researcher: complex scientific language, still easy to follow.
- A plain-language mode that explains in simple terms from first principles, readable by a high school student.
- An agreed length and content for each mode.

Questions to settle together:

1. Which modes should exist? Keep the three, replace one with plain language, or have four?
2. For each mode, who is the reader and what must they come away knowing?
3. What length is right for each: a paragraph, a short structured summary, a full page?

## 5. Integrations, Docs and sign-in

### What you saw, in your words

"On the Integrations tab, the REST and SSE formatting and how those things are structured is not uniform. Something's up, something's down. I want it to be very consistent. Are these things working, or did you just put in placeholders? And on the navigation bar I see Docs, and I have no idea what its purpose is. Is it for the integrations, or for streaming?"

"I go to log in and I have never registered. Both the Log in and Sign up buttons show up, and I'm confused about which one to press. The sign-in box is way too close to the header; I would like it much more centred. The header and footer should be the same colour. For simplicity, remove the Sign up button and keep only Log in, so people type in any email address and password they want and go straight in, without the 'we don't recognise your email' process. Then they can easily log out and go back to the home page."

### Are the integrations working or placeholders?

Checked live on develop on 2026-09-12, not read from the page:

| Card | Status | Evidence |
|---|---|---|
| REST and SSE | Works | Used for real searches today. The API reference `/docs` and the schema `/openapi.json` both open |
| GraphQL | Works, but the example on the page is wrong | As printed, the example fails three ways: it is written as a query instead of a mutation, it uses `question` where the field is `text`, and it leaves out a required session id. Corrected, it returned the BRCA1 answer with 5 NCBI citations in 10 seconds, signed in |
| MCP server | Broken on develop | Every request is rejected with "Invalid Host header", signed in or not, so no AI tool can connect to it |
| KGX export | Real, not testable from the site | A command that runs from a computer with this code installed. A website visitor cannot use it from the page. Not tested today |
| Command line | Real, not testable from the site | Same as KGX export |

So nothing on the page is a pure placeholder, but one surface is broken and one example is wrong.

### What each one is

| What you saw | Why it happens | Fix |
|---|---|---|
| Integrations cards are uneven | Five cards in a grid, each with a different amount of text, and only the REST card has links. Their code boxes and buttons land at different heights | Give every card the same parts in the same order and the same height, so titles, examples and buttons line up |
| No idea what Docs is for | Docs is a short technical reference for the integrations: access, the event stream, citations, limits. Nothing says so, it sits in the main navigation as if it were for everyone, and it is out of date. Its example event stream uses event names and fields the real stream does not have, and it still describes the free guest searches | To discuss: fold it into Integrations as "API documentation", or keep it and say who it is for. Either way, correct the example |
| Both Log in and Sign up show | The form offers two separate paths, so a first-time visitor has to know which one applies to them | Your decision below |
| Sign-in box too close to the header | The box sits about 28px below the header instead of in the middle of the screen | Centre it vertically in the space between header and footer |
| Header and footer are different colours | The header uses the lighter NCBI blue and the footer the dark navy, both from the design system | Use one colour for both. Which of the two is a quick choice for you |

### Your decision: one Log in button

- Remove the Sign up button.
- One form: type an email and a password, press Log in.
- A new email creates the account and signs you in straight away.
- Log out returns to the home page.

One consequence to know before it is built. An email that already has an account must still require its own password, or anyone could sign in as anyone. So a wrong password on an existing email will say so, which tells the person that the email is registered. The current design hides that. For a prototype that is a reasonable trade, but it changes two tests in `Product_workflows.md`: test 5 (wrong password and duplicate account) and the sign-up steps in test 3.

## 6. Tests 4 to 6, and two pages to copy from the reference site

### Decisions confirmed

- Test 4, the five-search guest limit: remove it, so it does not confuse people while they search.
- Test 5, wrong password and duplicate account: replace with a single Log in, so people just log in without the basics getting in the way.

### Test 6, search history, in your words

"I signed in with my email address. The good news is that it retains all the threads. When I click on one, it does the search again. Is that the expected behaviour, or are we storing the search we ran previously? I am confused. As far as the UI is concerned, it shows the whole search happening and the whole environment comes up, which I like, and the side menu gets populated, which is good. Again, I want the white search box to be consistent across all searches. And it is still not able to get to the whole question, which is the big problem here."

### What each one is

| What you saw | Why it happens | Fix |
|---|---|---|
| History keeps every thread | Working as intended | Nothing to fix |
| Clicking a history item searches again | Deliberate, not a bug. A history entry stores only the question, never the answer, so clicking it re-asks the question and gets a fresh answer. Recorded as W-identity-5 in `Developer_workflows.md` | Your choice, below |
| The white box changes size | Same as section 3: the progress box is narrower than the answer box | Same fix as section 3 |
| It does not get to the whole question | Consistent with the refusals in sections 1 and 4 | The consistency run in section 1, then fixing the biggest causes |

A choice for you on history:

- Keep re-running. Every answer is fresh, but a click costs a new search and takes 10 to 25 seconds.
- Store the answer and show it instantly, with an option to run it again. Faster, but the saved answer can go out of date.

### Integrations page: copy the reference layout

Your instruction: the Integrations page formatting is horrible, so learn from, and copy if needed, the Integrations page on <https://ncbi-kg-frontend-production.up.railway.app/integrations>. Its code is in `reference/ncbi_ai_agents-ncbi-kg/frontend/src/components/IntegrationHub.tsx`.

What the reference does that ours does not:

| Reference | Ours today |
|---|---|
| One title, "Integration Hub", with a one-line description and small summary chips under it | A large title and a two-line description |
| Three cards per row, all the same height | Five cards of different heights, with a gap in the second row |
| Every card has the same parts in the same order: a round icon, title, short description, then buttons | Cards mix descriptions, code boxes and links in different places |
| Buttons are pinned to the bottom of each card, so they line up across the row: a filled main action such as "Copy curl" beside an outlined "API Docs" | A plain Copy button and text links at different heights |
| Only the MCP card shows code, in a tidy box | Every card has a code box, and long lines wrap awkwardly |
| A clear notice at the bottom about access | Nothing about access |

Screenshots side by side: `../../Developer/reports/2026-09-12_reference_comparison/reference-integrations.png` and `ours-integrations.png` in the same folder.

### Disclaimer: make it bigger, like the reference

Your instruction: make the disclaimer as big as the one on <https://ncbi-kg-frontend-production.up.railway.app/>. Its code is in `reference/ncbi_ai_agents-ncbi-kg/frontend/src/App.tsx`.

| | Reference | Ours today |
|---|---|---|
| Width | About 900px | 520px |
| Title | "Important Medical Disclaimer", with a warning icon, large | "Before you start", small |
| Body | A bold opening sentence, then two paragraphs, including "Always seek the advice of your physician" | A bold sentence and one short grey paragraph |
| Notice box | A titled "Testing Environment" box | An untitled one-line box |
| Button | Full width: "I Understand - Continue to Research Tool" | "Continue" |

Screenshots side by side: `reference-disclaimer.png` and `ours-disclaimer.png` in the same Developer folder.

One thing to know: the repository's design rule says new screens follow our own design system rather than a second look. Your instruction overrides that for these two pages, so when they are built the plan is to copy the reference layout while keeping our own colours and typeface, so the product still looks like one app. If you want the reference look exactly, colours included, say so. Settled in section 10, question 2: the reference layout in our own colours.

## 7. Answer depth, and tests 8 to 10

### Answer depth, in your words

"Clinical brief, with short plain sentences, is okay. Researcher, with normal scientific wording, is also good. Do we need deep technical? I don't think so. It should be in more user-friendly terms. The user groups I am going for are, first, any plain audience who just wants to find the information, and second, the researcher. Those are the two big ones. Someone who doesn't understand the papers would want it super simple, in language anyone can understand. The researcher and deep technical modes can be combined into one."

### The direction

This answers the first two questions from section 4.

| Question from section 4 | Your answer |
|---|---|
| Which modes should exist? | Two, not three. A plain-language mode, and a researcher mode that absorbs deep technical |
| Who reads each mode? | Plain language: anyone who wants the information and does not read papers. Researcher: someone comfortable with scientific wording |

Proposed shape, to agree before building:

| Mode | Replaces | Reader | Language |
|---|---|---|---|
| Plain language | Clinical brief | Anyone | Simple everyday words that anyone can understand, no jargon |
| Researcher | Researcher and deep technical, merged | A researcher | Standard scientific wording with full detail, identifiers available |

Settled later, in section 10:

- The buttons read "Plain language" and "Researcher", question A5.
- Plain language answers are about 250 words in three short paragraphs, question A3.
- Researcher answers are a full page, question A4, with short topic headings, section 12 U2.

### Tests 8 to 10, in your words

"Off-topic is the only thing that works fine. Stop: everything just stops. The New search and Stop buttons are the same colour. New search should be a different colour, a blue background with white text, so it looks distinct. Feedback is one of the things that is working, so number ten works."

| Test | Result | Fix |
|---|---|---|
| 8. Off-topic question | Works | None |
| 9. Stop a search | Works: the search stops | New search should be a filled blue button with white text, so it no longer looks like Stop |
| 10. Feedback | Works | None |

## 8. Tests 11 to 16

### In your words

"No idea what the purpose of number eleven, navigation, is. I see it working, but it's very funky. I hate how the Integrations page is designed, and I don't know what the Docs page will do."

"Number twelve: what is the purpose of trust signals? Half the time you're refusing to do the search. The answer depth is horrible and it is hard to navigate. I can see Show work, which is a good thing. I can click on the links. The provenance is present, which is not a bad idea."

"Number thirteen: when I test Variants in GCK causing MODY, nothing shows. The answer is refused. The messaging is there, telling me to try something, but it should be a clickable link."

"Number fourteen, the scientist: I like it, it is working. The disclaimer, number fifteen, is working really well. Number sixteen: we already said the guest searches go away, so it's okay."

### What each test result means

| Test | Result | What it means |
|---|---|---|
| 11. Other pages and navigation | Works, but feels funky | The test checks that every page opens, back works, and phone width is usable. The feel is the problem, not the function: the header and footer jumping in section 4, the Integrations page in section 6, and Docs having no clear purpose in section 5 |
| 12. Trust signals and sources | Partly good | Show work, clickable source links and provenance work and are worth keeping. The trust signals themselves are not earning their place, see below |
| 13. Suggested next step | Refused | "Variants in GCK causing MODY" was refused, as it was in the walkthrough. The refusal does suggest NCBI's search, but the address cannot be clicked. Already recorded in section 5 and the walkthrough |
| 14. Scientist name | Works, and you like it | Separate from your first-impressions point that the scientist has no character in the writing |
| 15. Disclaimer | Works well | Still to be made bigger, as in section 6 |
| 16. Guest searches moving into an account | No longer applies | The guest limit is being removed, section 6 |

### What trust signals are for, and why they are not landing

They are there to tell the reader how far to trust an answer before acting on it, without reading every source:

- "Grounded · every claim cited": every sentence traces back to an NCBI record.
- "Single source, not independently confirmed": only one source backs it.
- "High risk claim": the topic is one where a wrong answer could matter clinically.
- "Not fully grounded" and "Not verified": shown on refusals.

Why they are not landing today:

- About half of real questions are refused, so the signal most people see is a red pill on a refusal, which reads as an error rather than a guide.
- On answers, the labels contradict each other side by side: "Grounded · every claim cited" next to a red "High risk claim".
- Almost every answer says "Single source", because the search only reaches one live source, section 3.
- Nothing on screen explains what any of them mean.

Settled in section 12, U1: one plain line on real answers only, with an info icon that explains it, and a neutral grey reason label on refusals, U6.

## 9. Tests 17 to 21

### In your words

"Number seventeen is working fine. It just shows the home page, which is okay. For number eighteen, if we get rid of the search limit, are we limiting the searches a user can do, or how is this happening? For no data, Which diseases are associated with FAKEGENE99: it works extremely well. For too many guest attempts, number twenty, I said just remove it. Number twenty-one, feedback when the connection drops, I don't think I need to test. I am done with that initial feedback."

| Test | Result | Note |
|---|---|---|
| 17. Mistyped address | Works | None |
| 18. Search limit for signed-in users | Question, answered below | None |
| 19. A question with no data | Works extremely well | None |
| 20. Too many guest attempts | Remove | Goes with the guest limit, section 6 |
| 21. Feedback when the connection drops | Not needed | None |

### Is there a search limit for signed-in users?

Not in practice today, and the menu says so honestly.

- The code has a limit of 100 searches a day per account.
- It counts searches from a record that is not being counted for signed-in accounts yet, so the limit never triggers. That is why the account menu reads "Signed in · no search limit in effect yet".
- Two spending caps do still apply to everyone: a maximum cost per search, and a maximum total spend per day for the whole system.
- Removing the guest limit does not change any of this for signed-in users.

This was read from the code and the account menu, not tested by running 100 searches.

## Summary of this testing round

### Decisions you made

1. Remove the five-search guest limit, the "used your free searches" and "moved into an account" walls, and the ten-attempt limit. Tests 4, 16 and 20.
2. One Log in button: any email and password, and a new email creates the account. Tests 3 and 5.
3. Two answer modes instead of three: plain language for anyone, and researcher with deep technical merged in. Section 7.
4. The loading screen names the scientist doing each step, such as "Franklin is searching…". First impressions, point 2.
5. Copy the reference site's layout for the Integrations page, and its size for the disclaimer. Section 6.
6. New search becomes a filled blue button with white text. Section 7.
7. Test 21 is not needed.

### What needs fixing, most important first

Answers, which are the product's reason to exist:

- Follow-up questions and "Yes, go deeper" lose the earlier context and get refused. Section 4.
- The flagship questions are refused about one time in three, and the GCK question every time. Sections 1 and 2.
- The search reaches only one live source, and the literature and trials layer never runs, so nearly every answer says "Single source". First impressions point 5, and section 3.
- Answers are sparse and poorly formatted, and do not stream. First impressions point 3, and section 3.
- Nothing yet proves that all questions perform at the same level: the consistency run. Section 1.

How the screens behave:

- The white box changes size between progress and answer.
- The header and footer jump, and screens swap with no transition.
- A follow-up should continue on the same screen, with the earlier answer shrinking above.

Sections 3, 4 and 6.

Individual pages:

- Integrations page: redesign from the reference, fix the broken MCP server, and correct the GraphQL example. Sections 5 and 6.
- Disclaimer: make it bigger. Section 6.
- Sign-in box: centre it. Section 5.
- Refusals: drop the red pill, and make the NCBI search address clickable. Sections 5 and 8.
- Trust signals: fewer, plainer, and explained. Section 8.
- Docs page: give it a clear purpose. Section 5.

### Still open for you

None. All five were settled in section 10.

## 10. Fix order

Decided 2026-09-12. The product owner left the order to the assistant.

### The order

1. Batch 1, screens and pages. Quick fixes, each shippable within hours.
2. Batch 2, answers. The deeper work: follow-ups, refusals, search layers, answer length and formatting, streaming, and the consistency run.

### Why this order

- The guest limit, the two sign-in buttons and the changing box size interrupt every test. Fixing them first means batch 2 gets tested on a screen that no longer gets in the way.
- Batch 2 depended on open questions: the answer mode names and lengths. All are now settled below.
- Most of batch 1 needs no decision at all.

### Batch 1

No decision needed:

- Remove the guest limit, both walls and the ten-attempt limit.
- One Log in button, where a new email creates the account.
- One box width from progress to answer.
- Header and footer fixed in place, with smooth transitions between screens.
- New search as a filled blue button with white text.
- Sign-in box centred.
- Refusals: drop the red pill, and make the NCBI search address a clickable link.
- Correct the GraphQL example, and fix the MCP server rejecting every request.

Needed your answer first, now all answered in the tables below:

- Header and footer colour.
- The reference pages, meaning the Integrations layout and the disclaimer size: our colours or theirs.
- The Docs page.

### Questions, asked one at a time

Answers are recorded here as they come.

| # | Question | For | Answer |
|---|---|---|---|
| 1 | Header and footer colour: the lighter NCBI blue or the dark navy? | Batch 1 | Lighter NCBI blue, for both |
| 2 | The reference pages: copy their layout with our colours, or copy them exactly? | Batch 1 | DECIDED: copy the reference layout and sizes, keep our own colours and typeface |
| 3 | Docs: fold it into Integrations, or keep it and say who it is for? | Batch 1 | DECIDED: fold it into Integrations as an "API documentation" section, corrected to match the real event stream, and remove the Docs tab |

The product owner then asked for all the questions about answers first. They are asked next, one at a time:

| # | Question | For | Answer |
|---|---|---|---|
| A1 | Search layers: run all three layers for every question, or only the layers that fit the question? | Batch 2 | "Ideally all 3. Can we not have the 3 different searches being spawned? Will it be a lot of work? What we can show is some fun work: one scientist picks up the question and asks 3 different scientists every time to help find the answer, and then the original scientist synthesizes the answer." DECIDED: search all three layers at the same time, and show the three scientists on screen, with one coordinator underneath. See "A1 in detail" below |
| A2 | Answer format: short paragraphs, or a structured layout with a one-line summary, a list of findings and the sources? | Batch 2 | DECIDED: short paragraphs of flowing prose, with citations inline |
| A3 | Plain language mode: how long should an answer be? | Batch 2 | DECIDED: three short paragraphs, about 250 words: the answer, what it means, and background from first principles for a reader starting from zero |
| A4 | Researcher mode: how long should an answer be? | Batch 2 | DECIDED: a full page, about 700 words or more: everything the three layers returned, organised by topic, for someone doing a deep review |
| A5 | The names on the two answer mode buttons | Batch 2 | DECIDED: "Plain language" and "Researcher" |
| A6 | Search history: re-run the question, or show the saved answer instantly with an option to run it again? | Batch 2 | DECIDED: show the saved answer instantly, with a "Run again" button for a fresh one |

### A1 in detail: all three layers, and the three scientists

What the code does today, read from `src/system_03_search_agent/core/graph.py`:

- Only two of the seven search tools are ever used: the knowledge graph search and one live NCBI record lookup.
- The other five are built and tested but never picked: variant lookup, the literature tools, pathogen data and clinical trials. So the literature and trials layer never runs.
- The two searches that do run happen one after the other, not at the same time.

Can the three searches run at the same time, and is it a lot of work?

| Part | Effort |
|---|---|
| Running one search per layer at the same time, so the wait is about the slowest layer rather than the sum of all three | Small |
| Wiring in the five unused tools, so the planning step picks them and the written answer can use and cite what they return | The bulk of the work. Days rather than weeks, but not a firm estimate until it is traced properly |
| Keeping within the existing limits: at most 20 outside calls per question, and each tool's own time limit | Already built |

The three scientists:

- Shown as presentation, the idea fits the current scope. One coordinator runs the three layer searches at the same time, and the screen shows a lead scientist handing the question to three named scientists, one per layer, then writing the answer.
- It also fits the rule that a scientist's name changes the wording and never the facts.
- Built as three genuinely separate AI agents that each reason on their own, it crosses a boundary this project deferred past v1: "single orchestrator for v1", and splitting deep research into sub-questions. That would need your explicit go-ahead as a scope exception.
- Decided: shown on screen, with one coordinator underneath.

### Every question is now settled

| Area | Decision |
|---|---|
| Search layers | All three layers searched at the same time for every question |
| Scientists | A lead scientist hands the question to three named scientists, one per layer, on screen, then writes the answer |
| Answer format | Short paragraphs of flowing prose, with citations inline |
| Plain language mode | Three short paragraphs, about 250 words: the answer, what it means, and background from first principles |
| Researcher mode | A full page, about 700 words or more, organised by topic |
| Mode button names | "Plain language" and "Researcher" |
| Search history | Show the saved answer instantly, with a "Run again" button |
| Header and footer | Both in the lighter NCBI blue |
| Integrations and disclaimer | Reference layout and sizes, in our own colours and typeface |
| Docs | Folded into Integrations as "API documentation", and the Docs tab removed |

### Two implementation notes, recorded so they are not rediscovered

- Mode names on the wire: other surfaces such as GraphQL, the command line and MCP send the depth by its internal name. Deleting `clinical_brief` or `deep_technical` would break any caller already using them. So the plan keeps both names working behind the scenes: `clinical_brief` means Plain language, and `deep_technical` is treated as Researcher. Only the buttons and the writing instructions change.
- Cost and time: a full-page answer searched across three layers costs more per question and takes longer to write than today's one-sentence answer. Streaming the answer sentence by sentence keeps the wait from feeling longer.

## 11. Every requirement from this round

The single list to work from. It gathers everything from sections 1 to 10, the first-impressions note in `../feedback/inbox/2026-09-12_first_impressions.md`, and the walkthrough's known issues. Status is updated here as work proceeds.

Four items were not in the summary's fix list and are added here: R24 (a mode info button, first impressions point 4), R32 and R33 (answer text defects from the walkthrough), and R37 (updating the checklist).

### Batch 1: screens and pages

| ID | Requirement | From | Status |
|---|---|---|---|
| R1 | Remove the five-search guest limit and its counter | Sections 2 and 6 | ✅ Built in set 1, not pushed yet |
| R2 | Remove the "You have used your free searches" and "moved into an account" walls | Section 2 | ✅ Built in set 1, not pushed yet |
| R3 | Remove the ten-attempt guest limit | Sections 2 and 9 | ✅ Built in set 1, not pushed yet |
| R4 | Keep the per-search cost cap, and keep the anonymous daily cap raised from 200 to 1,000 searches a day, since it is the only working limit on total anonymous spend. The system-wide daily cap stays configured but does not fire today. Removing the ten-attempt limit in R3 drops one of three abuse bounds; the per-connection daily share stays and still limits any single caller | Section 2, decision X4 | ✅ Caps kept in code in set 1, not pushed yet. Raising the anonymous daily cap to 1,000 on develop waits for your yes at push |
| R5 | One Log in button, with Sign up removed. A new email creates the account and signs in. An existing email still needs its own password | Sections 5 and 6 | ✅ Built in set 1, not pushed yet |
| R6 | Log out returns to the home page | Section 5 | ✅ Built in set 1, not pushed yet |
| R7 | Sign-in box centred between header and footer | Section 5 | Not started |
| R8 | The white box keeps one width from progress to answer, across every search | Sections 3 and 6 | Not started |
| R9 | Header and footer fixed in place, with a stable content area, so the footer no longer jumps | Section 4 | Not started |
| R10 | Smooth transitions between home, progress and answer | Section 4 | Not started |
| R11 | Header and footer both in the lighter NCBI blue | Section 10, question 1 | Not started |
| R12 | New search as a filled blue button with white text, distinct from Stop | Section 7 | Not started |
| R13 | Refusals: remove the red "Not verified" and "Not fully grounded" pills | Sections 5 and 8 | Not started |
| R14 | Refusals: the NCBI search address becomes a clickable link | Section 8 | Not started |
| R15 | Integrations page rebuilt from the reference layout in our own colours and typeface: summary line and chips, equal-height cards, round icon, title, description, buttons pinned to the bottom, and an access notice | Sections 5 and 6, question 2 | Not started |
| R16 | Correct the GraphQL example: a mutation, the `text` field and a session id | Section 5 | Not started |
| R17 | Fix the MCP server rejecting every request with "Invalid Host header" on develop | Section 5 | Not started |
| R18 | Fold Docs into Integrations as "API documentation", correct its event stream example and remove its guest-search text, and remove the Docs tab | Section 5, question 3 | Not started |
| R19 | Disclaimer rebuilt at the reference size in our own colours: about 900px wide, a large titled heading, fuller body text, a titled notice box, and a full-width continue button | Section 6, question 2 | Not started |

### Batch 2: answers

| ID | Requirement | From | Status |
|---|---|---|---|
| R20 | Follow-up questions keep the earlier context, so "it" resolves to the gene, from the on-topic check onward | Section 4 | Not started |
| R21 | "Yes, go deeper" continues from what the previous answer found, instead of sending its own sentence as a new question | Section 4 | Not started |
| R22 | A follow-up continues on the same screen, with the earlier answer shrinking above and the new answer growing below | Section 4 | Not started |
| R23 | Two answer modes, "Plain language" replacing clinical brief and "Researcher" absorbing deep technical, with the internal names still accepted by GraphQL, the command line and MCP | Section 7, questions A5 and notes | Not started |
| R24 | A small info button that explains the two modes | First impressions, point 4 | Not started |
| R25 | Plain language answers: three short paragraphs, about 250 words: the answer, what it means, and background from first principles | Question A3 | Not started |
| R26 | Researcher answers: a full page, about 700 words or more, organised by topic | Question A4 | Not started |
| R27 | Answers written as short paragraphs of flowing prose, with citations inline, and easy to read | Question A2, first impressions point 3 | Not started |
| R28 | The answer streams onto the screen sentence by sentence | Section 3 | Not started |
| R29 | Search all three layers at the same time for every question, by wiring in the five tools the plan never picks today | Question A1, first impressions point 5 | Not started |
| R30 | On screen, a lead scientist hands the question to three named scientists, one per layer, then writes the answer. Presentation only, over one coordinator | Question A1 | Not started |
| R31 | Progress steps named for the scientist, such as "Franklin is searching…", replacing the plain loading state. The scientist also gives the writing some character, never changing the facts | First impressions, points 1 and 2 | Not started |
| R32 | Fix answers that open broken or garbled, such as "These include…" with no subject, or "BRCA1 (gene symbol BRCA1 [1]." | Walkthrough | Not started |
| R33 | The "one further gene record was found" note no longer appears as an uncited grey sentence, and disease names read naturally rather than "susceptibility to, 1" | Walkthrough | Not started |
| R34 | Stop refusing the flagship questions: BRCA1 about one time in three, and GCK every time | Sections 1, 2 and 8 | Not started |
| R35 | Search history shows the saved answer instantly, with a "Run again" button | Question A6 | Not started |
| R36 | Trust signals: replace every pill with one plain line on real answers only, such as "Confirmed by 2 independent sources" or "Based on 1 source, not yet confirmed", with an info icon that explains it | Section 8, section 12 U1 | Not started |

### Checking and follow-through

| ID | Requirement | From | Status |
|---|---|---|---|
| R37 | Update `Product_workflows.md` once tests change: tests 4, 16 and 20 removed, tests 3 and 5 rewritten for one Log in, and test 7 rewritten for two modes | Sections 5, 6 and 7 | Partly done: tests 3, 4, 5, 16 and 20 ✅ in set 1, not pushed yet. Test 7 waits for the two modes |
| R38 | Consistency run: each of the 50 golden questions 3 times on develop, with a per-question result, repeated after each fix | Section 1 | Not started |
| R39 | Judge answer quality with the grader or a domain expert, once questions answer reliably | Section 1 | Not started |

### Added from the product UI decisions in section 12

| ID | Requirement | From | Status |
|---|---|---|---|
| R40 | Researcher answers use a few short plain topic headings, each followed by short paragraphs. Plain language answers have no headings | U2 | Not started |
| R41 | Integrations shows four cards: REST and SSE, GraphQL, MCP server, and one "Command line tools" card covering the command line and KGX export. Summary chips show 115M nodes, 693M edges, 3 data layers and 7 tools, with API documentation below the cards | U3 | Not started |
| R42 | Disclaimer wording follows the reference structure, adapted: "Important Medical Disclaimer", a bold opening sentence, the physician paragraph, a "Prototype" notice box, and a full-width continue button | U4 | Not started |
| R43 | Scientists stay random on every visit, with the three helpers also random, as develop does today | U5 | Not started |
| R44 | A refusal shows a neutral grey label matched to its reason, such as "No answer found in NCBI records" or "Outside biomedical research" | U6 | Not started |
| R45 | After Stop, show "Search stopped" with "Run again" and "New search" buttons, instead of a frozen screen | U7 | Not started |
| R46 | Stay signed in across a page reload, and make search history work on phones as a panel that slides in and closes | U8 and U9 | Not started |
| R47 | Plain language answers end with one small grey line, "Research information, not medical advice." Researcher answers do not | Decision X5 | Not started |

### Known, but not asked to fix

Recorded so it is not mistaken for a requirement:

- Signed-in accounts have no daily search limit in practice, section 9.

## 12. Product UI decisions not yet covered

Checked against requirements R1 to R39 and every test note in this report, on 2026-09-12. Each item below is a product UI choice the testing round raised but did not settle. Answers get recorded here.

### Raised by a requirement, but the choice was never made

| # | Decision | Where it comes from | Answer |
|---|---|---|---|
| U1 | Trust signals: which labels to keep, what to call them, and how to explain them | R36, section 8. Left for discussion | DECIDED: replace all the pills with one plain line on real answers only, such as "Confirmed by 2 independent sources" or "Based on 1 source, not yet confirmed", with an info icon that explains it. No trust label on refusals, and no contradicting labels |
| U2 | Researcher answers are a full page organised by topic, but answers are also meant to be short paragraphs. May a researcher answer use topic headings, or stay as paragraphs only? | R26 and R27, questions A2 and A4 | DECIDED: a few short plain topic headings, each followed by short paragraphs of prose with citations inline. Plain language answers stay without headings |
| U3 | Integrations page: the reference shows three surfaces, while ours has five, two of which (KGX export and command line) cannot be used from the website. Keep all five cards, or show fewer? And what should the summary chips under the title show? | R15, section 6 | DECIDED: four cards: REST and SSE, GraphQL, MCP server, and one "Command line tools" card covering both the command line and KGX export. Summary chips show real figures: 115M nodes, 693M edges, 3 data layers, 7 tools. API documentation sits below the cards |
| U4 | Disclaimer wording: the reference size with our current wording, or the reference wording too ("Important Medical Disclaimer", the paragraph about seeking your physician's advice, and "I Understand - Continue to Research Tool")? | R19, section 6 | DECIDED: the reference structure, rewritten for this product: an "Important Medical Disclaimer" title, a bold opening sentence, the paragraph about seeking your physician's advice, a notice box titled "Prototype" in place of the reference's glucose-metabolism "Testing Environment" text, and a full-width continue button |
| U5 | The scientist: should the same scientist stay with a person on every visit, as the specification says, or change on every visit, as develop does today? And who are the three helper scientists: picked at random, or a fixed team? | R30 and R31, section 8 test 14 | DECIDED: random every visit, as develop does today, with the three helpers also picked at random. This departs from technical specification Section 14.2, which keeps one scientist per person; the product owner's choice stands |
| U6 | Refusals without the red pill: show a neutral label instead, or no label at all? | R13, sections 5 and 8 | DECIDED: a neutral grey label matched to the reason, such as "No answer found in NCBI records" or "Outside biomedical research", so nothing looks like an error |

### Known issues you have not yet been asked about

Seen during testing, and recorded as known but not asked to fix in section 11:

| # | Decision | Answer |
|---|---|---|
| U7 | Stop gives no confirmation. Add a short "Search stopped" message, or leave it as it is, since Stop works? | DECIDED: replace the frozen progress screen with "Search stopped" and two buttons, "Run again" and "New search" |
| U8 | Reloading the page signs you out. Keep people signed in across a reload? | DECIDED: stay signed in across a reload, with history and the conversation where they were, until Log out or the session expires |
| U9 | On a phone, the button that shows or hides your searches does nothing. Hide the button, or make search history reachable on a phone? | DECIDED: make history work on phones, as a panel that slides in over the page and closes again |

All nine are settled. Each is added to the requirement list in section 11 as R36 and R40 to R46.

### Remaining decisions, outside the testing round

These are about the build, spending, housekeeping, and two older UI items that predate this round. Blockers for batch 1 come first. Each is asked one at a time with a recommendation.

| # | Decision | Answer |
|---|---|---|
| X1 | Commit and push today's work to `develop` | DECIDED: commit and push now. Done as `08f4576`, 107 files, confirmed on the remote |
| X2 | The go-ahead to start batch 1 | Asked for a plan first: one ordered list of UI work built from everything in `testing/Developer/` and `testing/Product/`, before any fix starts |
| X3 | Accept that one Log in button reveals whether an email is registered, R5 | DECIDED: accepted for the prototype |
| X4 | Keep the three spending caps while the guest limit goes, R4 | Re-asked. The first answer, remove the anonymous daily cap, was given on a wrong description from the assistant: it said the whole-system daily cap would still apply. The code says it cannot. `SYSTEM_DAILY_CAP_USD` sums a record that is not being written, so it reads $0.00 and never fires, and `ANON_DAILY_RUN_CAP`, 200 a day, is the only bound on total anonymous spend (`harness/cost_control.py`, `anon_daily_run_cap`). An earlier adversary round used all 200 in 1.84 seconds. DECIDED after the correction: keep the anonymous daily cap and raise it from 200 to 1,000 searches a day. The per-search cost cap also stays. Setting the new value on develop changes an environment variable, so it is confirmed at the time it is applied |
| X5 | Whether answers carry a medical-advice notice, now that the warning band is gone. Older UI item | DECIDED: one small grey line under Plain language answers only, "Research information, not medical advice." Researcher answers do not show it. Added as R47 |
| X6 | Whether hiding the navigation below 720px is right, now that "More pages" exists. Older UI item | DECIDED: keep it as develop does today, the current page plus a "More pages" button. With Docs folded into Integrations, the menu holds only Integrations and About |
| X7 | Approve the consistency run of about 150 real searches, R38 | DECIDED: run a baseline now, before any answer fix, then again after sets 7, 8 and 9, so each fix shows as a change in the number. Results go to `testing/Developer/reports/` |
| X8 | Raise the per-search cost cap, only if full-page answers start getting cut short | Not yet asked |
| X9 | Add the three missing on-navy layer colours to the theme file | DECIDED: fix it in set 2. When the header turns the lighter NCBI blue, add three approved logo colours to `frontend/src/theme.ts`, checked for contrast against that blue, so the design token check reports zero problems. This is the product owner's approval to change the theme file |
| X10 | Keep or delete the test account on develop, and the online copy of the walkthrough report | DECIDED: keep the test account, which the consistency runs and browser checks use. Delete the online copy of the walkthrough report, since `testing/Developer/reports/2026-09-12_walkthrough/` is the one source |

All ten are settled except X8, raising the per-search cost cap, which is only asked if full-page answers start getting cut short.

## 13. The fix plan

Written 2026-09-12 at the product owner's request, and stored at `../../UI_fix_plan.md`. It turns requirements R1 to R46, plus four open items found only in `Developer_workflows.md`, into ten ordered fix sets: five for screens and pages, then five for answers. Each set lists what you will see, the requirements it closes, the likely files, the checks before push, and which tests to redo. Its status table is the place to see progress.
