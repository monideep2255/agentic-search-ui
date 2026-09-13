# Testing

Two folders, one per person doing the testing.

| Folder | Who | What is in it |
|---|---|---|
| `Product/` | The product owner, testing by hand | `Product_workflows.md` to test against, and `feedback/inbox/` for screenshots and notes |
| `Developer/` | The assistant, testing with automated tests and a real browser | `Developer_workflows.md` with the full specification and run commands, and `reports/` with each browser run and its screenshots |

## Testing by hand

1. Open the develop app in a browser: <https://search-agent-web-develop-2aeb.up.railway.app>
2. Check it against `Product/Product_workflows.md`. Any order, skip anything.
3. When something looks wrong, drop a screenshot or a `.md` note into `Product/feedback/inbox/`.
4. Say "check the inbox".
