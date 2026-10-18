# Card 8 re-attempt build report

Change: the trust line's info card now says "When an answer rests on two or more databases and the values behind one of its high-stakes facts could not be compared, the line adds "their values could not be compared"." It no longer says how a fact was checked.

Diff:
- `frontend/src/components/screens/AnswerScreen.tsx`: sentence in `TRUST_LINE_EXPLAINER` and its doc comment.
- `frontend/src/components/screens/AnswerScreen.card22.test.tsx`: the pinned sentence updated. The old wording is gone, so the test fails on the previous text.

Commands:
- `npx vitest run src/components/screens/AnswerScreen.card22.test.tsx`: 24 passed.
- `npx tsc --noEmit`: clean.
- Python synthesis, test_tiers, test_write_answer_structure: 956 passed, 10 skipped, 1 xfailed.
- `ruff check` and `isort --check-only src tests services tracker alembic .claude .github`: clean.

No code condition or `synthesis/trust.py` wording changed.
