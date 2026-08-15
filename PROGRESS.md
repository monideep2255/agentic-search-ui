# Progress

A plain-language update on what this project is, what works today, and what comes next. No jargon. If you have never seen the code, start here.

Last updated: 2026-08-14.

## Table of contents

- [What we are building, in one paragraph](#what-we-are-building-in-one-paragraph)
- [What works today](#what-works-today)
- [What does not work yet](#what-does-not-work-yet)
- [The story so far, sprint by sprint](#the-story-so-far-sprint-by-sprint)
- [What is next](#what-is-next)
- [Problems we know about and are tracking](#problems-we-know-about-and-are-tracking)
- [How we work](#how-we-work)
- [Where to look for more detail](#where-to-look-for-more-detail)

## What we are building, in one paragraph

A search tool for biomedical researchers. You ask a question in ordinary English, like "which diseases are associated with the BRCA1 gene?", and it answers you in ordinary English, with a link next to every fact showing exactly which official record that fact came from. The links are the point. Anyone can build something that sounds confident; the hard part is being able to prove every sentence, and refusing to answer when you cannot.

It searches three kinds of source. A large database we built in advance and hold ourselves, which is fast. Live government APIs at the US National Center for Biotechnology Information, which are always current. And a set of extra enrichment services that add context. The system decides which of the three to use for each question.

Here is the whole thing as a picture. Every question takes this path, and the parts in the middle are what the sprints below have been building one at a time.

```mermaid
flowchart LR
    Q[Your question] --> G{Allowed in?}
    G -->|no| R[Refused, with a reason]
    G -->|yes| U[Work out what is asked]
    U --> P[Decide where to look]
    P --> F[Fetch the records]
    F --> S1[(Our own database)]
    F --> S2[(Live NCBI records)]
    F --> S3[(Extra context services)]
    S1 --> W[Write the answer]
    S2 --> W
    S3 --> W
    W --> A[Answer, one link per fact]
```

The two ends are the ones worth noticing. On the left, a question can be turned away before anything is spent on it. On the right, nothing reaches you without a link attached, and if there is no link to attach, you get told so instead of being told something invented.

## What works today

You can ask a question and get a real, cited answer back, streamed to a web page as it is written.

Concretely:

- You can sign in. Accounts, passwords, and sessions all work.
- You can type a question into a chat window and watch the answer appear word by word, with a stop button.
- The system asks a real question against our own biomedical database and gets real results.
- Every factual sentence in the answer carries a numbered link to the official record it came from.
- If the system cannot find support for something, it says so and points you somewhere else, instead of making something up.
- Questions that are off topic, that ask for medical advice, or that try to manipulate the system are turned away before they cost anything.
- The system can look up any gene name against the live NCBI databases, not just the one it knew about before. This was the single biggest gap, and it is now closed.
- A dangerous kind of automatic question, one that once crashed our own database and took it offline for everyone, is now stopped before it can ever reach the database at all.
- The system can now look up a genetic variant by its standard identifier (an "rs number", the way scientists refer to a specific spot in the genome) and get back its normalized coordinates, how clinically significant it is, and how common it is across different population groups.
- The system can now look up what a published research paper says about a gene, disease, or chemical, and separately look up what has been written in the scientific literature about a specific genetic variant.
- The system can now look up a bacterial sample (a "biosample", the way labs track which food-poisoning outbreak a sample came from) and get back its lab metadata, which antibiotics it resists, and which other samples belong to the same outbreak cluster and how closely related they are genetically.
- The system can now search for clinical trials by disease or condition and get back real trial identifiers, their recruitment status, and a bounded summary of who can enroll.

All six live-government-API connections the plan called for are now built. That is every planned data source.

- For the first time, a question about a gene can pull an answer from BOTH our own database and a live government record at once, in the same answer, each fact carrying its own separate link back to where it came from. This is the first time the system has ever combined two sources in one answer.
- Every citation, from any of the seven sources, now carries the same four pieces of trust information: what kind of evidence it is, how confident the source itself is in the claim, what population the data covers if relevant, and what usage rights apply to it. Previously only our own database's citations carried this.
- The system's highest-stakes example question, "which diseases are associated with BRCA1?", is now correctly flagged as needing extra scrutiny. Before this sprint, a quirk in how the answer was assembled meant this exact question, the one the whole trust system is built around, was being waved through as routine instead.
- If a live government record and our own database disagree about the same fact, the system now notices and says so, rather than silently picking one and hiding the disagreement.
- If a piece of information from our own database is old enough to be worth double-checking, the system is now built to automatically verify it against the live government record before repeating it as current. This machinery is real and tested, but our own database does not yet store the specific kind of detail it needs to check against, so it has nothing to actually fire on yet (see below).
- If your internet drops mid-answer and you reconnect, the system now picks up exactly where you left off, no repeated sentences, no missed ones. Before this sprint, a reconnect just started the whole answer over from the beginning.
- Two people, or two browser tabs, can now watch the same answer being written at the same time. Before this sprint, only the first one got anything; the second one saw nothing at all.
- A conversation nobody is actually watching now stops itself after a short wait, instead of quietly running to completion and burning resources on an answer nobody will ever read. This closes a real gap found earlier: an abandoned browser tab used to let the system keep working, unseen, until it finished on its own.
- You can now ask for the full list of sources behind a finished answer as a single request, rather than only ever seeing them appear one at a time while the answer streams.
- The web page now looks like a finished product rather than an unstyled form. There is a proper landing page, a live view of the five thinking steps as they happen, an answer page where every sentence sits beside a coloured stripe showing which of the three data sources backed it, expandable source cards, a page explaining how answers are built, and developer documentation. A grey stripe means a sentence nobody could back with a source, which is visible before you read a word.
- You can now try the system without an account. You get five free searches before being asked to sign in, and the page tells you plainly how many you have left.
- Every answer now carries the name of a historical scientist working on your question, shown as a plain label rather than a cartoon, and a control that lets you ask for a clinical summary, a researcher-level answer, or a deeply technical one.
- You can rate an answer, say what was wrong with it from a list drawn from mistakes this system has genuinely made before, and flag an individual source as not supporting the sentence it is attached to. That last one is the most useful thing a person can tell us, because it identifies exactly which link was wrong rather than just that the answer felt off.
- Every screen was checked against the international accessibility standard by an automated tool, and four real problems it found were fixed, including text that was too faint to read against its own background and code examples a keyboard user could not scroll.
- The system now has a first outbound door for other computer programs and AI agents to ask it questions directly, the same protocol other AI tools already speak to each other. It answers with one complete, cited result rather than a stream, and it never hands out a cost figure or lets a caller reach any of the seven lookup tools directly, only the one question-answering door. Nothing outside this project uses it yet, so there is no visible change if you are using the web page.

## What does not work yet

The newest work, the redesigned web page, has now been through two independent reviews and both found serious problems. That is the system working, but it is worth being blunt about what they found, because the worst one goes to the heart of what this product is for.

The first reviewer discovered that a visitor without an account, asking any question at all, was shown a confident answer with real-looking official source links attached. Asked "what is the capital of the USA?", the page produced a fully sourced answer about a breast cancer gene. Nothing about it was true, and nothing on screen said so. That has been removed entirely: a visitor without an account is now asked to sign in rather than shown anything invented.

The second reviewer found the deeper cause of a whole family of related problems. When the system writes an answer, it also sends along an exact record of which sentence came from which source. The web page ignored that record and tried to work it out for itself by matching text. That guesswork attached a real source to sentences it had never supported, including one reading "every patient with this cancer should stop chemotherapy immediately". The page now uses the exact record the system provides, which fixed five separate problems at once.

A third review then ran specifically on the repairs, because in this project the repair is historically where the next problem hides, and it was right again: the fix for the second problem had introduced a new one, skipping the progress screen for every question after the first, which meant the Stop button was unreachable on a runaway search. That is fixed too. All three reviews failed the work, 56 problems were found between them, 48 are fixed and 8 are written down with a named owner each.

Then a fourth check found two more, and it was not a review at all: somebody opened the page and looked at it. The whole application was drawing itself into a narrow strip down the middle of the screen with empty grey either side, and the product's own name was wrapped onto three lines. Separately, the coloured bar that runs down the left of an answer, the one that tells you at a glance which sentence came from where, had drifted out of line with the sentences, so by the third sentence it was pointing at the wrong one. A bar that points at the wrong sentence is worse than no bar, because it claims a source that is not there.

Both were fixed the same day, and both are worth being blunt about: 147 automated checks, 19 browser checks, a clean build and a full accessibility pass were ALL passing while both were true. Every one of those checks asks what is on the screen and none of them asks where it is. Nothing in this project looks at the finished page. Until something does, opening it and looking is a real step, not a nicety.

The honest headline, found today by actually asking the finished system real questions and reading the answers by hand, not by reviewing code: the step that is supposed to understand what a question is actually asking has never been built past a placeholder. Right now, the system mostly just scans your question for something that looks like a gene name. If it finds a real one, it looks that up and stops there, even if your question asked for much more. If it finds something that LOOKS like a gene name but is not (a database name mentioned in passing, like "GTR" or "SRA"), it tries to look that up, fails, and gives up on the whole question, "I could not identify that gene," instead of noticing what the question was actually about. Asking the system's own seven showcase questions directly today, 4 came back this way, and a 5th came back with only one bare word as its whole answer, for the same underlying reason. This was a known, deliberate shortcut from the very first sprint that built the thinking loop, written down at the time with a plan to come back and build the real version later. Two weeks and twelve completed sprints have gone by since, and nobody has come back to it.

Separately, one of the six newer lookup tools, gene lookup, can now be used together with our own database to answer a question. The other five, genetic variants, research literature (two tools), disease outbreaks, and clinical trials, still cannot: they can each translate a name or identifier into real, verified data, but nothing yet connects them to the actual question-answering pipeline.

The web page now looks like a real product, and as of today it matches the approved design almost everywhere. Sources fold away until you click them, each one says in words which of the three data layers it came from rather than making you decode "L1", the record of how an answer was found can be reopened after the fact, and the little numbered markers in the text now say what they point at instead of just showing a number.

Two things from that design still cannot be built, and the reason is worth stating plainly: the system does not send them. A source card is supposed to show the date our own database snapshot was taken, which is the single field that lets a reader tell a stored value from a freshly fetched one, and it is supposed to name the thing it is about ("NCBI Gene 672, BRCA1") rather than just its number. Neither piece of information currently leaves the back end at all, so no amount of front-end work can display it. Both are now part of the next sprint, which is already changing the back end for other reasons.

Also not built yet: saved history, the other ways to access the system besides the web page and the new outbound door, and anything to do with hosting it somewhere other than a laptop.

## The story so far, sprint by sprint

Each of these is a completed, reviewed, merged piece of work.

| Sprint | In plain terms | Done |
|--------|----------------|------|
| 1.0 | The skeleton of the service, and the fixed format every answer travels in | 2026-07-27 |
| 1.1 | Sign-in, accounts, and the database that holds user information | 2026-07-28 |
| 2.0 | The five-step thinking loop the system follows for every question, and the machinery that picks which AI model does which step | 2026-07-28 |
| 1.2 | The web page: a chat window, answers appearing as they are written, and a stop button | 2026-07-28 |
| 2.1 | The first real connection to our biomedical database | 2026-08-01 |
| 2.2 | The rule that every sentence must be backed by a source, or the system refuses to answer | 2026-08-03 |
| 3.0 | The gatekeeper that decides which questions are allowed in at all | 2026-08-04 |
| 3.1 | The first live government API connection, and gene name lookup | 2026-08-05 |
| Database safety fix | Stopped a specific kind of automatic question that had previously crashed our own database | 2026-08-07 |
| 3.2 | The second live government API connection: genetic variant lookup by rs number | 2026-08-08 |
| 3.3 | The third and fourth live government API connections: published research literature lookup, and research-literature lookup for a specific genetic variant | 2026-08-08 |
| 3.5 | The fifth and sixth live government API connections: disease outbreak lookup and clinical trials search, completing every planned data source | 2026-08-08 |
| 3.4 | Extended the trust-and-citation rules to cover all six newer lookup tools, and connected gene lookup to the answer pipeline for real, the first tool to be wired all the way through | 2026-08-10 |
| Specification pause | Brought the written plans in line with everything learned building the six tools; cleared a backlog of small real bugs and mismatches; swept a folder of outside reading material; then, for the first time, actually asked the finished system real questions and read the answers by hand, which is what found today's headline problem | 2026-08-10 |
| 4.0 | Finished the front door to the whole system: reconnecting after a dropped connection, two people watching the same answer at once, a stalled conversation stopping itself, and a way to fetch a finished answer's full source list in one request | 2026-08-11 |
| 4.1 | Built the first back door: a way for other computer programs and AI agents, not just a person typing into the web page, to ask the system a question and get one complete, cited answer back | 2026-08-11 |
| 4.8 | Gave the web page a real design, and found that no browser test in this project had actually run for five sprints | 2026-08-13 |
| 4.9 | Brought the answer page in line with the approved design, and found three serious problems by putting the two side by side | 2026-08-14 |
| Design system repair | Fixed the design's own colour and keyboard problems at source, after working around them three separate times | 2026-08-14 |

Nine of these are worth understanding, because they explain how this project works.

Sprint 2.1, the expensive lesson. We asked "which diseases are associated with BRCA1?" and got back twenty-five results. All twenty-five had real, working links to official records. Every automated test passed. And every single result was wrong: they were not diseases at all, they were similar genes in other animals. The tests could not see this, because they were checking that the plumbing worked rather than that the answer was true. Finding it took four rounds of review over four days. Everything we do now is shaped by that: before writing any new feature, we now write a test that asks whether the ANSWER is right, and we watch it fail first, so we know the test is capable of catching a lie.

Sprint 3.0, the gatekeeper, and why it has two halves. A gatekeeper that refuses everything is perfectly secure and completely useless. So the tests check both directions: that bad questions get turned away, and just as importantly that good questions get through. That second half caught a real problem. An early version refused the single most important question in the whole product, "which diseases are associated with BRCA1?", because our list of biomedical words contained "disease" and the question said "diseases". One letter. No security test would ever have found that.

Sprint 3.1, the check that paid for itself twice over. Gene name lookup shipped, got checked, and the check found two serious problems: the lookup was completely broken for every gene (a leftover from an unrelated fix), and a search-scoping fix was quietly returning the wrong results instead of the right ones. Both got fixed. Then, because the same team had just spent a whole day learning not to trust a fix that graded its own homework, we paid for one more check on the fix for those two problems. That last check found something worse than either original bug: for a handful of gene names, the government database was matching on a nickname instead of the real name and handing back a real gene that was simply the wrong one. Confidently, with a real-looking source link attached. That is the exact failure this whole project exists to prevent, and it was three checks deep before anyone caught it.

The database safety fix, the same lesson learned twice in one afternoon. A week and a half earlier, one automatically written question had a shape our database could not handle, and it crashed the whole database for everyone using it at the time. This sprint closed that gap: the system now recognises that dangerous shape and refuses to even try running it. But the first attempt at writing that fix had a bug of its own, an obscure one, and a reviewer caught it before it ever shipped. The fix was rewritten, and a second, completely separate reviewer checked the rewrite and confirmed it actually closed the gap. The team had already learned once, on sprint 3.1, that a fix should never be trusted just because the person who wrote it says it works. This sprint proved that lesson applies even to the fix for a problem the team already understood well: knowing exactly what is wrong is not the same as writing a correct fix on the first try.

Sprint 3.2, the variant lookup tool, and the fix that broke something new twice. Building this tool found two serious problems early: it silently cut off values that were too long instead of saying so (imagine a lab report where a long diagnosis just gets chopped off mid-word with no note that anything is missing), and if you typed in a plain number instead of a real variant identifier, the system would confidently return real information about a completely different, unrelated variant. Both got fixed. Then, exactly as happened on sprint 3.1, a separate check on the fix itself found the fix had its own problems: the "stop cutting things off" fix turned out to reject roughly one in ten real, clinically important variants outright, including some of the most well known ones in medicine, because the fix refused the whole answer rather than just leaving out the one piece that was too long. And a second fix, meant to correctly tell the system "this failure is temporary, try again" versus "this input is simply wrong, do not retry," was doing the opposite of what it claimed for one common kind of failure. Both were fixed a second time and checked a third time before anyone trusted them. The lesson, now proven on two sprints in a row: a fix for a bug deserves MORE scrutiny than new code, not less, because the fix is the newest, least-tested thing in the whole system.

Sprint 3.3, the literature lookup tools, and the confidently wrong answer that both tools gave at once. Both new tools ask a government search service for a match and hand back whatever comes back as a real result. Late in review, someone tried typing in a bare number, "334", instead of a real identifier. Both tools cheerfully returned real, official-looking, fully cited answers about five completely unrelated things. Separately, typing in an ordinary word like "the" returned ten confidently matched, real medical terms that had nothing to do with the word "the". Nothing was broken about the individual records returned. Both were real entries from the government's own database. The problem was that the government service itself already flags a weak, "closest guess" style match differently from an exact one, and our tools were throwing that flag away before anyone downstream ever saw it. It is now kept and passed along. This is the single most important find of this sprint, because it is exactly the failure this whole project exists to prevent: not a crash, not an error message, a fully cited, entirely wrong answer delivered with total confidence. It was also found by deliberately typing hostile and strange things into the finished tools, not by any planned test, which is why that kind of adversarial poking is now a standing step for every tool going forward, not an occasional extra.

Sprint 3.5, the last two data tools, and the fix that broke the thing it just fixed, twice. This sprint's outbreak-cluster lookup reads a government file that turned out to be about 400 times bigger than a normal file its own size class: roughly 411 gigabytes, for one bacterial species. The tool has to read that file a little at a time and give up gracefully if it runs out of time, rather than trying to load the whole thing. The first version had a real, serious bug: it stopped reading after finding just the FIRST matching entry, then confidently reported that as the complete answer, when a real outbreak cluster of four related samples was quietly reported as having only two. That got caught and fixed, checked, and passed a full re-test. Then a second, deliberately hostile round of testing found something worse: the FIX ITSELF had broken the tool a different way. In closing the "stops too early and lies" bug, the fix removed the only thing that let the tool stop at all, so now it could never successfully finish AT ALL, not even on the exact same real outbreak cluster it had gotten wrong before. It failed silently, reporting "nothing found" instead of a wrong answer, which is safer but still wrong. That got fixed too, and a live re-check on that same real outbreak cluster still came back empty. It took a THIRD look to find the actual remaining problem: the fix that made the tool patient enough to find every real match had also made it so patient it ran out of time before ever getting to the last, quick step that turns the matches into a proper labeled result. A dedicated slice of time was reserved for that last step no matter how long the earlier steps take, and only then did a live check on the real outbreak cluster come back with the exact right answer: four related samples, with the exact genetic distances a human reviewer had worked out by hand as the ground truth to check against. Three real bugs, each one only found by actually running the finished tool against the real government service and checking the ANSWER, not by trusting that the tests still said "green".

Sprint 3.4, the trust system's own final exam, and the two-gene question that gave a confidently incomplete answer. This was the sprint that connected everything: extending the trust-and-citation rules to all six lookup tools, teaching the system to notice when two sources disagree, and, for the first time, actually letting gene lookup contribute to a real answer alongside our own database. Building and checking it in the ordinary way went well: two rounds of review, a handful of real bugs found and fixed, all closed cleanly. Then a deliberately hostile round of testing tried something nobody had tried before: asking about two different genes in a single question. Two times out of three, the system answered fluently, cited its one source correctly, and never mentioned the second gene at all, reporting itself as a complete, trustworthy answer the whole time. Nothing was technically wrong with the sentence it wrote. It simply never tried to cover the rest of the question, and said nothing about that. This is exactly the failure this whole project exists to prevent: not a crash, not a wrong fact, a confident answer that quietly does less than it claims. It is fixed now: the system checks whether every named subject in a multi-part question actually got an answer, and if not, it downgrades its own confidence and says plainly which part it could not cover. Fixing that turned up a second problem in the same area: the check meant to catch our own database and a live government record disagreeing about the same gene had never actually been able to compare them in practice, because the two sources describe a gene's identity slightly differently (a full name versus a short symbol) and the check required an exact match. It now understands that the two are the same kind of fact. A few smaller, lower-priority gaps were found and deliberately left for later, each with a written reason why leaving it was the right call for now, not an oversight.

Sprint 4.0, the front door, and the reconnect trick that quietly defeated its own fix. This sprint finished the one door every future way of reaching the system, a phone app, a command-line tool, another program, will eventually walk through. Building the ordinary version went the usual way: build it, review finds real problems (the reconnect feature was silently unusable by any standard tool, because of one missing line), fix them, a second reviewer confirms. Then a deliberately hostile round of testing found something nobody had tried: quickly disconnecting and reconnecting on a fast, repeating cycle, never actually reading anything. This exact trick defeated the "stop an abandoned conversation" fix from three sprints ago, keeping a conversation nobody is reading alive forever, as long as the reconnects came fast enough. It also found that a conversation someone deliberately stops now needs to say so clearly rather than just going silent, and that a partial list of sources needs to say plainly that it is partial, not look identical to a complete one. Fourteen real problems were found this way in one sitting; ten were fixed and independently re-confirmed by a fourth review, and four were deliberately left for a specific later sprint each, with the reason written down for each one rather than left unowned. The reviewer's own closing note is the throughline worth keeping: fixing one loophole is exactly when a new one is easiest to introduce, because attention is on the loophole just closed, not on every other door shaped the same way.

Sprint 4.1, the back door, and the check that could never fail. This sprint built the first way for another computer program, not a person on the web page, to ask the system a question directly and get one complete answer back. Before any of that code was written, a check was written to prove it worked, the usual practice by now. The first reviewer found something worse than a missing feature: two of the check's own tests had been written in a way that could never fail, no matter what the real code did, because the test compared the wrong two things to each other. A check that cannot fail is worse than no check, because it looks like proof when it proves nothing. That got rewritten and fixed. Then a deliberately hostile round of testing against the real, running door found sixteen problems, two of them serious, and both shared the same shape as the front-door problems found the sprint before: the system could tell another program "here is a confident, trustworthy answer" in exactly the moment that was least true, when the underlying work had failed, been cut off partway through, or produced nothing worth trusting. Both are fixed now: a failed or stopped answer can never again present itself as a complete, trustworthy one. Two smaller, genuine judgment calls were found and deliberately left open rather than guessed at: whether content copied in from an outside source should be visibly marked as such before being handed to another AI program, since a hostile instruction hidden inside an outside document is invisible to a person reading it but not necessarily to a program blindly following it; and a small identity check that is currently unused and harmless today, but will need attention the moment a future sprint gives it something real to check against.

Sprint 4.9, the design comparison nobody had run, and the check that could not fail. Somebody finally opened the built page and the approved design side by side, in the same states, and compared them. That had never been done in this project. It found nine differences, and a live bug: a visitor with no account was being shown the whole panel of saved searches that is supposed to appear only after signing in.

Fixing the nine went the usual way, and then three separate reviews took it apart. The first, a deliberately hostile one, found the worst thing on the page: when a search failed partway through, the page printed the system's own internal error text, including how much money the search had cost, directly underneath a green badge saying "Grounded, every claim cited". A crashed search was wearing the badge of a successful one. It also found that a refused question was shown with a green tick beside the word "Refused", which at a glance reads as "done, fine".

The second review found something more uncomfortable: the check written to prove all this worked could not fail. Deleting the little number badge that says how many sources an answer has left the check passing, because the check was looking at the whole box rather than the badge, and one of the source identifiers in the test data happened to contain the digit it was looking for. Sixteen deliberate attempts to break the code had missed it, because the person who wrote them chose where to look, and chose where they were already looking.

The third review looked only at the repairs, and found that three of the four most serious fixes were themselves wrong. One had moved a nonsense message rather than removing it. One had collapsed every kind of failure onto a single sentence, so a search the user stopped on purpose was told "this could not be completed, try again", which is both untrue and faintly accusing. The third had been checked in a way that tested a hidden marker rather than either of the two things a real person would notice.

All of those are fixed. The number worth keeping is that the page was fully passing its own checks at the moment each of these was found.

## What is next

Where the finished work sits against what is still ahead:

```mermaid
flowchart LR
    subgraph Built["Built, reviewed, merged"]
        direction LR
        A[Service skeleton] --> B[Sign in]
        B --> C[The thinking loop]
        C --> D[The web page]
        D --> E[Our database, connected]
        E --> F[Every fact cited]
        F --> G[The gatekeeper]
        G --> H[Gene name lookup]
        H --> I[Database safety fix]
        I --> Iv[Variant lookup]
        Iv --> Lit[Literature lookup, two tools]
        Lit --> Out[Outbreak + trials lookup]
        Out --> Tr[Trust rules cover all tools, gene lookup wired in]
        Tr --> Sp[Specification pause, found the question-understanding gap]
        Sp --> Door[Front door finished: reconnect, watch together, self-stopping]
        Door --> MCP[Back door: other programs can now ask questions too]
    MCP --> Style[The web page redesigned and built]
    end
    Style --> Dec[Question-understanding gap: given a home, a later sprint, not fixed yet]
    Dec --> Wire[Wire the other five tools into the answer pipeline]
    Wire --> Other[Other ways in: command line, saved history]
    Other --> L[Everything else]
```

Every planned data lookup tool, all six live-API connections, is now built AND independently checked, and the trust-and-citation rules now cover all of them. Each tool went through the same pattern: build it, find real problems in review, fix them, and find MORE problems in the fix itself before trusting it. Sprint 3.4 held that pattern too, and pushed it one step further: its hostile testing round found a real problem (the two-gene question, see the story above) that no planned test had ever thought to try, only deliberate, adversarial poking at the finished system. Sprint 4.0 repeated the pattern once more on the front door itself, and its own reviewer flagged something worth remembering going forward: a fix round is exactly where the next problem is most likely to hide, because attention is on the one loophole just closed. Sprint 4.1 repeated it a third time on the new back door, and its own hostile testing round found the identical shape of problem the front door had: a failed or cut-off answer that could still present itself as complete and trustworthy.

The planned specification pause (updating the written plans with everything learned from building all six tools and the trust system) ran and finished on 2026-08-10. It also swept a folder of outside reading material collected during the build, and it is the pause that found the question-understanding gap below, by actually asking the system real questions for the first time rather than only reviewing code.

In order, now:

1. Letting somebody try it without signing up first. Right now the very first thing a visitor meets is a demand for an account, and there is no way around it: the back end refuses to run a search for anyone it does not recognise. The approved design gives a visitor five free searches before asking, which is the difference between showing this to someone and asking them to commit to it sight unseen. This is the next sprint, and it is back-end work, not a web-page change.

   It also carries the two missing pieces of information the answer page cannot currently show, the snapshot date and the name of the thing a source is about, since it is already changing the back end. And it fixes a small lie: the account menu currently says "unlimited searches" when there is a real limit of a hundred a day.
2. The question-understanding gap now has a home: a specific future sprint, later than the next several, will build the real fix. It is not being rushed in early, and nothing else in the next few sprints depends on it being fixed first.
3. Wiring the other five lookup tools (genetic variants, both literature tools, disease outbreaks, clinical trials) into the answer pipeline the same way gene lookup was wired in an earlier sprint.
4. Then the remaining work: the other ways to access the system, saved history and personalisation, measurement and quality scoring, and finally hardening it for real use.

## Problems we know about and are tracking

Nothing here is hidden or forgotten. Each one is written down with a decision about when it gets fixed.

| Problem, in plain terms | When it gets fixed |
|-------------------------|--------------------|
| Almost nothing in this project looks at the finished web page. Most checks ask what is on the screen, never where it is, which is how a page that drew itself into a narrow strip passed everything. There are now a handful of checks that measure where things actually land, and one that checks the design pages themselves, but they cover a few specific things rather than the page as a whole | Partly addressed. Full coverage needs a deliberate visual-checking approach that does not exist yet |
| The answer page cannot show two things the design calls for, because the system does not send them: the date our stored database snapshot was taken, and the name of the thing a source is about rather than just its number. A reader therefore cannot tell a stored value from a freshly fetched one | The next sprint, which is already changing the back end |
| Sources now fold away until you click them, which is what the design asks for, but it also folded away a warning that appears when a source link points somewhere other than an official government site. A security warning is now two clicks deep instead of visible | Needs a decision: whether a warning of that kind may sit behind a fold at all |
| A search you stop on purpose never says clearly that it stopped. The little label for the tool it was running says "running" for ever, because the page hangs up on the connection before the system's own "cancelled" message can arrive | A sprint that owns how searches start and stop |
| Parts of the design itself failed the accessibility standard the product is held to: a green used for success was unreadable on two of the backgrounds it sits on, a label was near-black on a dark blue panel, and a button was placed inside another clickable element. The code had worked around three of these one at a time before anyone checked the design itself | Fixed at source on 2026-08-14, and there is now an automatic check over all 21 design pages so it cannot come back |
| A web page address does not identify what you are looking at, so no answer can be shared by sending someone a link, bookmarked, or reached with the browser's Back button, and reloading loses the answer | Needs a decision from the product owner first, since the approved design does not cover it |
| Parts of the old web page are now unused but still have tests passing against them. Roughly a quarter of the web page's automated checks are testing screens nobody can reach any more, which makes the number of passing tests look better than it is | Needs a decision on whether to delete them. Not deleted yet, because deleting work is not a call to make quietly |
| An automated accessibility checker reported the new web page as completely clean while the single most important thing on it, the coloured marker showing which source backed each sentence, was invisible to anyone using a screen reader. The tool cannot tell whether the thing a product exists to communicate is actually communicated | Fixed this sprint. The lesson is the durable part: a green automated check is evidence about what the tool measures, not about whether the product works for a person |
| For five sprints, no browser test in this project actually ran. Two separate faults were stacked: one made the tests unable to start, which hid the fact that the other had already broken them. Both are fixed and browser tests run again, but it means five sprints of work were signed off without that check ever passing | Fixed this sprint. Worth remembering: a check that cannot run is worse than a check that fails, because a failure is visible |
| The step that is supposed to understand what a question is actually asking has never been built past a placeholder (see "What does not work yet" above). The single biggest known problem right now | Given a home: a specific future sprint, later than the next several. It will not be rushed in early, and nothing else waits on it |
| One of the two small leftover gaps in the gene lookup tool (a missing length limit on one nested list) turned out to be real and already reachable by a real question, once this sprint's specification pause looked again; it is fixed. The other (an unusual input shape inside a different lookup path) is still not reachable by anything today, so it was left alone | Fixed |
| Five of the six lookup tools (genetic variants, both research-literature tools, disease outbreaks, and clinical trials) are still not connected to the answer pipeline. Each can look up real data but cannot yet use that lookup to answer a question. Gene lookup is the one exception, connected in an earlier sprint | A later sprint |
| If two live sources describe the same fact in genuinely different words for the same fact, not just a different name for the same gene, the system has one narrow safety check for the one specific case found so far (a real value versus a wildly wrong one for the same field) but has not been tested against every way two sources might phrase the same fact differently | Whenever a future check finds a new case |
| The system is now built to automatically double-check an old, possibly-outdated fact from our own database against the live government record before repeating it as current, but our own database does not yet store the specific kind of detail (how old a particular fact is, field by field) this check needs to know when to fire, so in practice it never runs yet. This is a gap in the earlier database-building work, not in this system, confirmed still true by this sprint's specification pause | Whenever the earlier database-building work stores that detail |
| One narrow path in the gatekeeper, if it ever hit a specific rare internal error, showed a generic "something went wrong" message instead of the real reason. Found by accident in an earlier sprint | Fixed |
| The two new literature lookup tools disagree with each other about whether to tell you when they had to hide part of an answer for being too long. One says so, the other stays quiet. Neither is wrong exactly, they were built by different people making a reasonable call about the same open question, but having two different answers to the same question in one product needs a single decision | Whenever the product owner decides |
| One of the two literature lookup tools used to give you a name-lookup result with no link back to where the confirmation came from. Now it links every result its sibling mode already did | Fixed |
| The variant-literature tool's link for a specific variant used to point only to a general search page. Now every individual match gets its own real record-page link when one exists, and every related paper in a list gets its own link too, not just the tool's one overall link | Fixed |
| One advanced way of asking the literature-lookup tool "how are this chemical and this disease related to each other" has not yet been confirmed to actually work against the real government service, so it is not offered yet | A future add-on, once verified |
| Nobody has been assigned yet to double-check that the expected answers for our future quality-testing question set are actually correct. A wrong expected answer would make a wrong system answer look like a pass | Whenever the quality-scoring sprint begins |
| A handful of smaller, lower-priority gaps from an earlier sprint: two places where a very long list gets quietly shortened with no note that anything was cut (not yet seen in real use); one narrow input shape that could still slip past a should-refuse-if-empty check (not yet seen in real use); and one inconsistency in how the two literature tools handle a single bad entry inside an otherwise-good batch request | Whenever the product owner decides, or whenever real use actually produces one of these shapes |
| A separate, smaller flake: about one time in ten, an automatically written question comes out slightly malformed in a way our database rejects outright, with no second attempt. Not dangerous, just occasionally a wasted question | Whenever we next have a working connection to measure it properly |
| Two open questions about how the gene lookup tool should handle ambiguous input: should a handful of medical abbreviations that are also real gene names stay blocked, and what should happen when someone types a gene name in lowercase. Neither is a bug, both are genuine judgment calls with real tradeoffs either way | Whenever the product owner decides |
| Similarly, if you type in a plain number that happens to belong to something else (say, a gene's own catalog number) formatted to look like a variant identifier, the variant tool will honestly report which identifier it actually looked up, but that identifier is still the wrong one for what you meant | Whenever the product owner decides it needs closing |
| One government lookup the variant tool relies on has been broken on the government's own side since before we started building against it, for every input we have tried. We found a working substitute, but have not yet proven the substitute behaves identically for every case | Whenever someone verifies it live |
| The written specification set a length limit on one clinical field that is too short for real medical terms. The tool already says plainly "some information was left out because it was too long to fit" rather than silently cutting terms off. Raising the limit itself is still an open product decision | Whenever the product owner decides |
| The clinical trials search tool understands its search box as a small command language, not plain text, so a real medical term containing the word "NOT" (a standard way doctors write "not otherwise specified") could silently search for the exact OPPOSITE of what was typed. The tool now tells the system asking the question about this risk directly, rather than staying silent about it; the underlying command-language behavior itself is unchanged | Escaping the risk away entirely is a future decision, if the current disclosure turns out not to be enough |
| The clinical trials search tool has the same weak-match problem the literature tools had in an earlier sprint: a bare number or a common word like "the" can return confident, real-looking, but essentially meaningless results. The tool now asks for its best matches first, which helps, but unlike the literature tools it still has no way to tell you a match was weak, since the government service behind it does not offer that signal the same way | Whenever that government service starts offering a usable signal |
| The clinical trials search tool used to reject a status word (like "withdrawn" or "suspended") that the same government service could hand back as a real answer, because our own written specification listed fewer status words than the service actually uses. Checked directly against the government service and widened to match all of them | Fixed |
| Three smaller gaps in the gatekeeper, where a backup layer currently covers for them | The hardening sprint near the end |
| One narrow way of sneaking an instruction into a question, hidden as a clause inside an otherwise ordinary question, still slips past detection in one specific grammatical shape. A test is in place that will fail loudly the moment the real fix is attempted, so this cannot silently regress | Whenever picked up as a dedicated task |
| Three places where the written specification and the working code used to disagree, including one written plan that described a piece of work as still needed when it had actually already been finished in an earlier sprint | Fixed |
| One test is switched off because checking it needs a connection to our server that we cannot open from the current setup | Whenever that connection is available, about ten minutes of work |
| A full security review of the whole codebase has never been run. It is paused on cost | Before this is ever shown to anyone outside the team, or put on the internet |
| Nothing yet stops one person from starting an enormous number of conversations very quickly. A test run started over nine thousand in under a minute with none rejected. Each one is still cleaned up properly after a while, but nothing limits how many pile up before that happens | A dedicated future sprint whose whole job is exactly this kind of speed limiting |
| When a conversation is deliberately stopped partway through, the answer given so far is real, but there is currently no clean, general way for a future tool (like a phone app or a command-line client) to tell "this is a complete answer" apart from "this is all we got before it was cut off", beyond a plain marker on the wire | Whichever future sprint next touches how the final answer summary is put together |
| A conversation that is watched by a connection that never actually reads anything (as opposed to one that disconnects, which is already handled) can still be kept alive indefinitely. Different from the fast-reconnect trick above, and not yet closed | A future sprint revisiting how the system decides whether anyone is still watching |
| When another computer program asks the system a question through the new back door and gets back cited source text pulled from an outside document, nothing currently marks that text as "copied from an outside source" versus "written by our own system." A person reading an answer would never be fooled by a hidden instruction sitting inside a quoted source; whether an automated program reading the same text needs that distinction marked explicitly is a real, open product question, not a bug with an obvious fix | Whenever the product owner decides, or the hardening sprint near the end |
| A conversation id that the new back door accepts from a calling program is not yet checked against who that program actually is. Harmless today, since nothing reads it yet, but it will need a real ownership check the moment a future sprint starts using it to remember someone's conversation history | Whichever future sprint first starts using that id for real |
| One narrow error message on the new back door still describes a real internal failure in developer-facing terms rather than fully plain language, though nothing sensitive leaks through it today by coincidence rather than by design | The hardening sprint near the end, or whichever sprint next touches that error-handling code |
| The new back door's honesty signal, for the rare case where nothing at all could be confirmed one way or the other, currently always reports itself as "low risk" rather than "we do not know." Every other case is handled correctly; only reaches this narrow case with no attempted answer at all | Whenever the product owner decides, or whichever sprint next revisits how that signal is set |

That last row is the important one. None of these can affect a real person while the project runs only on a laptop with no outside users. The moment that changes, several of them stop being optional.

## How we work

Every sprint follows the same loop, and it is deliberately slower than just writing the code.

1. Write down what "finished" means, as a test that checks whether the ANSWER is right rather than whether the code ran.
2. Watch that test fail, to prove it is capable of failing.
3. Build the thing.
4. Hand it to a separate reviewer that did not write it, whose job is to decide if it is correct.
5. Hand it to a second reviewer whose job is to actively try to break it.
6. Fix what they find, and re-run everything.
7. Only then, a human reviews and approves it.

The reason for steps 4 and 5 is that the person who wrote something is the worst person to check it. On sprint 3.0, everything passed the checklist, and the reviewer still failed it, because it turned out you could ask "what is the capital of the USA?" and get let straight through. On the same sprint, the second reviewer found that a doctor asking "should this patient be started on tamoxifen?" also got through, which is exactly the kind of question this system must never answer.

Both of those were found after every test was green. That is why both steps exist.

## Where to look for more detail

| If you want | Read |
|-------------|------|
| The current state of every sprint, as a visual board | `tracker/board.html`, open it in a browser |
| What went wrong and what fixed it, written at the time | `LEARNINGS.md` |
| Every decision we made and why, including the ones we rejected | `DECISIONS.md` |
| The technical picture | `README.md` |
| The full plan | `requirements/Plan.md` |
