# communication-style: full text

The complete text of `.claude/rules/communication-style.md` as it stood on 2026-10-04, before that rule was cut to a short summary to lower the context every session loads. Nothing was dropped: every clause the summary leaves out is here, word for word. This file is never loaded automatically. Read it when the summary points here.

## Communication style

- Ask ONE question at a time. Never batch. Wait for the answer before asking the next.
- Think from first principles. Short sentences, active voice, no buzzwords.
- Do not use corporate jargon or vague suggestions ("consider", "look into").

## Before major interactions

Always read these skills first:

- `.claude/skills/first-principles/SKILL.md`
- `.claude/skills/socratic-questioning/SKILL.md`
- `.claude/skills/objective-review/SKILL.md`, for review and feedback tasks

## Why this rule sits here rather than in CLAUDE.md

It was briefly merged into CLAUDE.md on 2026-08-02 during a consolidation pass, and moved back the same day. The consolidation existed to cut always-loaded context, and CLAUDE.md is loaded on every turn exactly as `.claude/rules/` is, so the move saved nothing while pushing CLAUDE.md past its roughly 200 line budget. It also contradicted CLAUDE.md's own line stating that rules load automatically and need no duplication there.

The general form, worth keeping: moving content between two always-loaded surfaces is not an optimization. Only removing it, or making it load conditionally, is.
