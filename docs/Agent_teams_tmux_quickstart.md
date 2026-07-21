# Agent teams in tmux: launch quickstart

How to launch Claude Code so bossman mode shows parallel builders in live tmux panes. Read this when you want the orchestrator-plus-panes view for a build phase.

## Running agent teams in tmux

Why a terminal: the bossman skill spawns parallel builders into tmux panes, and tmux runs only in a terminal. The IDE extension runs Claude in a panel, which cannot host tmux panes. So for agent teams you launch Claude from your IDE's built-in terminal instead of the extension panel. Normal extension use is unaffected. Use this flow only when you want the multi-pane view.

### Every time you want agent teams

1. Open your IDE's integrated terminal:
   - VS Code: View then Terminal, or press Ctrl and backtick
   - JetBrains (PyCharm, IntelliJ): View then Tool Windows then Terminal, or press Alt and F12
2. Start tmux: `tmux`. A green status bar appears at the bottom. You are now inside a tmux session.
3. Launch Claude inside it: `claude`. This starts a new session that picks up `teammateMode: tmux`.
4. Activate: `/bossman`.

When a phase has 2 or more builders, tmux splits the window into panes, one per teammate. Your lead (main session) stays in the top pane and monitors the shared task list.

### tmux keys

| Action | Keys |
|--------|------|
| Switch panes | Ctrl-b, then an arrow key |
| Detach, leave it running | Ctrl-b, then d |
| Reattach later | `tmux attach` |
| Close the current pane | `exit` or Ctrl-d in that pane |
| List sessions | `tmux ls` |

## If something goes wrong

- No panes appear: you are probably not inside tmux. Run `echo $TMUX`. Empty output means you are not in a tmux session. Start `tmux`, then relaunch `claude`.
- teammateMode not applying: it is read when `claude` starts, so make sure you ran `tmux` first and `claude` second, not the other way around.
- "command not found: tmux": reinstall with `brew install tmux`.
- Want to step away: detach with Ctrl-b then d. The session and its agents keep running. Return with `tmux attach`.

Prerequisites already configured on this machine: tmux installed, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, and `teammateMode: tmux` in `~/.claude/settings.json`. The bossman skill also runs a tmux preflight at Step 1, so if you forget and launch outside tmux, it prints these steps before dispatching any builders.
