# Workstream scout brief, shared by all six scouts

You are a read-only planning scout for the agentic-search-ui repository (System 3, a biomedical search agent: a person types a question in natural language and must get one answer with citations). The owner's paramount test: a person types a question and gets an answer. Rank everything against that.

Rules:
- Do not dispatch agents, ever. Do not edit any file except your own output file. No git commands that change state. No code changes.
- Read each card's row in `testing/UI_fix_plan.md` (To do table) and follow its pointers: reports under `testing/Developer/reports/`, ledgers under `tracker/`, `testing/UI_fixes_done.md` (grep, it is large), `testing/Test_queries_and_workflows.md` (grep by query number), and the code under `src/system_03_search_agent/` and `frontend/src/`.
- A diagnosis written on 2026-10-05 exists for cards 86, 87, 88, 89, 91, 92 and 94 under `testing/Developer/reports/2026-10-05_*`; use it rather than redoing it. Cards 88 and 89 are being built now.
- Live checks only where a card's status is genuinely unclear: develop API https://search-agent-api-develop-43b3.up.railway.app as a GUEST (see `testing/Developer/scripts/flagship_measure.py` for the guest session pattern; write scripts with the Write tool into `testing/Developer/reports/2026-10-05_board_plan/scripts_wN/` and run them by path). At most 6 live questions for your workstream. Never sign in or create an account. Never save tokens.
- Public repository: no local absolute paths, credentials or tokens in anything you write; use `<repo-root>`. House style: no em dashes, no bold, sentence-case headings.

For each card in your workstream, one row in a table with these columns:
1. Card number and the feature in plain words (a person's words, one line).
2. Impact on the person: blocks an answer / wrong or degraded answer / slow / screen or wording only / not seen by a user.
3. Status today: still happens (with evidence and date), already fixed (evidence), stale or superseded (by what), or unknown.
4. Root cause: known (one line, file:function) or unknown.
5. Shared cause: other card numbers, in any workstream, that the same fix would close or change.
6. Code it touches: files and functions. Two cards touching the same function must be built in sequence.
7. Size: S (under half a day), M (one to two days), L (more), or "discussion first" for architecture items.
8. Depends on: cards that must land first, and why. Blocks: cards waiting on this one.
9. Needs the owner: no, or the decision as one plain question with a recommendation.

After the table:
- Root causes shared by several cards: each cause, the cards it covers, and the one fix that would close them together. This is the most valuable part; look hard for it.
- Suggested order inside the workstream, with one line of reasoning per step.
- What you did not check.

Output: `testing/Developer/reports/2026-10-05_board_plan/wN_<short_name>.md` (your N and name are in your prompt). Done when every card in your list has a full row. Return about 300 words: the shared causes, the order, the owner decisions, and the file path.
