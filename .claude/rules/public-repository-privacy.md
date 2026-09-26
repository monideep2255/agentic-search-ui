---
description: "This repository has been public since 2026-09-24. Never commit secrets, personal data, the owner's work identity, employer-internal material, colleague names, or local machine paths, on any public branch."
scope: portable
alwaysApply: true
---

## Public repository privacy

This repository has been public since 2026-09-24. Everything committed is world-readable and effectively permanent: files, history, commit messages, and author metadata. This holds on every public branch, `develop`, `production`, and every phase branch alike. There is no private branch to relax on.

### Never commit

| Category | What it covers |
|----------|-----------------|
| Secrets | API keys, tokens, passwords, connection strings with credentials. Use environment variables and example files with placeholders. Test fixtures must stay obviously fake. |
| Personal data | Data about anyone, including real user queries or identifiers in eval logs and screenshots. |
| The owner's work identity | Work email addresses, NCBI username. |
| Employer-internal material | Internal proposals, budgets, strategy notes, internal ticket keys, internal issue-tracker, wiki, or code-review hosts, internal IP addresses. |
| Colleague names | Any colleague's name. |
| Local machine paths | Any absolute or home-relative path from the owner's machine. |
| Private repository names or paths | Any pointer to a private repository this one was built from or references. |
| Server addresses with login commands | An address paired with the command to reach it. |

### Placeholders

Use `<repo-root>`, `<user>`, `<server-ip>`, and "the owner's private notes (not published)" in place of the real values above.

Internal NCBI context stays in the gitignored local file `requirements/context/Private_NCBI_context.md`. Never commit it.

### Evidence artifacts are where local paths leaked before

Evidence artifacts, logs, test reports, and screenshots are committed often in this repository, so check them specifically. This is where local paths leaked before, not only in prose documentation.

### Commit identity

Commit with the GitHub noreply address, never a work address.

### Enforcement

A local pre-commit hook enforces most of this on the owner's main machine only. It does not run on any other machine, and it does not run in CI, so this rule still applies in full everywhere else. Never bypass it with `--no-verify`.

The hook's allow marker exempts a specific line from the check. Use it only for information that is genuinely public. Never use it to publish private information.

GitHub secret scanning with push protection is enabled on this repository, as a second layer behind the hook and this rule, not a substitute for either.

### Before a release to production

Confirm the release actually carries the privacy fixes. Production picks up the September 25 fixes at the next release.

### If something slips

- Remove it from the working tree.
- Tell the owner.
- Rotate any exposed secret at once.

Rewriting history is the owner's call, never made unilaterally.
