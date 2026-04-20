# Local setup (Windows laptop)

One-time setup guide for running this repo on your personal Windows laptop C: drive instead of the shared NCBI `/export` volume. Gate 2 and all subsequent local work runs from here.

See `DECISIONS.md` (2026-04-16 entry) for the rationale.

## Table of contents

- [Current state on the server (what you are migrating from)](#current-state-on-the-server-what-you-are-migrating-from)
- [What you need on the laptop](#what-you-need-on-the-laptop)
- [Step 1: Download data from server (~51 GB)](#step-1-download-data-from-server-51-gb)
- [Step 2: Clone the main repo](#step-2-clone-the-main-repo)
- [Step 3: Clone the two reference repos](#step-3-clone-the-two-reference-repos)
- [Step 4: Create `.env`](#step-4-create-env)
- [Step 5: Python environment](#step-5-python-environment)
- [Step 6: Verify the migration](#step-6-verify-the-migration)
- [Step 7: Delete data from `/export` (AFTER Step 6 passes)](#step-7-delete-data-from-export-after-step-6-passes)
- [Gotchas](#gotchas)
- [Where this leaves you](#where-this-leaves-you)

---

## Current state on the server (what you are migrating from)

```
/home/chakrabortim2/agentic-search-data-engineering/     <- repo (on NFS home)
  |-- data -> /export/home/chakrabortim2/data            <- symlink
  |-- .env                                               <- gitignored, has API key
  |-- env.example                                        <- checked in template
  |-- reference-repos/ncbi_ai_agents -> /home/chakrabortim2/ncbi_ai_agents
  |-- reference-repos/personal-os -> /home/chakrabortim2/personal-os-work

/export/home/chakrabortim2/data/
  |-- ftp_cache/   5.0 GB   raw NCBI FTP downloads (skip re-downloads)
  |-- kgx/        46 GB     Gate 1 KGX output (Gene + ClinVar + MedGen)
  |-- raw/         empty
Total: ~51 GB
```

---

## What you need on the laptop

| Piece | Source | Notes |
|-------|--------|-------|
| 1. Repo clone | `git@github.com:monideep2255/agentic-search-data-engineering.git` | Main repo (System 1 + System 2) |
| 2. Reference repo: ncbi_ai_agents | `git@github.com:monideep2255/ncbi_ai_agents.git` | Canonical BioLink pipeline. Referenced throughout CLAUDE.md and rules. |
| 3. Reference repo: personal-os-work | `git@github.com:monideep2255/personal-os-work.git` | Source for skills and agents adapted into `.claude/`. |
| 4. `.env` file | Copy from server via scp, or regenerate from `env.example` | Contains NCBI_API_KEY — treat as secret |
| 5. Data directory | Rsync from server (~51 GB) | FTP cache + Gate 1 KGX |
| 6. Python 3.11+ | python.org or via conda | |
| 7. Docker Desktop | docker.com | Needed for Phase 3.0 fixture smoke test (PostgreSQL + AGE Linux container) |

---

## Step 1: Download data from server (~51 GB)

You confirmed this is in progress. Target location on laptop:

```
C:/Users/<you>/agentic-search-data-engineering/data/
  ├── ftp_cache/
  ├── kgx/
  └── raw/
```

Use the repo-local `data/` directory as the canonical storage root. On the laptop, `.env` should point `DATA_DIR` at `C:/Users/<you>/agentic-search-data-engineering/data`.

If the rsync gets interrupted, rerun the same `rsync -avP` command and it resumes.

---

## Step 2: Clone the main repo

```powershell
cd C:\Users\<you>\
git config --global core.autocrlf input    # MUST do before cloning (prevents CRLF corruption)
git clone git@github.com:monideep2255/agentic-search-data-engineering.git
cd agentic-search-data-engineering
```

---

## Step 3: Clone the two reference repos

These are separate git repos that the main repo reads as read-only context. They live inside `reference-repos/`, which is gitignored, so each machine sets up its own.

Clone them somewhere convenient on disk (HTTPS shown; SSH works too if you have a key set up):

```powershell
cd C:\Users\<you>\
git clone https://github.com/monideep2255/ncbi_ai_agents.git
git clone https://github.com/monideep2255/personal-os-work.git
```

Check out the right branch for `ncbi_ai_agents`:

```powershell
cd C:\Users\<you>\ncbi_ai_agents
git checkout ncbi-kg
```

Then create junction points inside the main repo. Junctions work on any Windows account, no admin or Developer Mode needed:

```powershell
cd C:\Users\<you>\agentic-search-data-engineering
mkdir reference-repos
cmd /c mklink /J reference-repos\ncbi_ai_agents C:\Users\<you>\ncbi_ai_agents
cmd /c mklink /J reference-repos\personal-os C:\Users\<you>\personal-os-work
```

If the source folder names differ on your machine (for example you cloned personal-os-work into a folder called `Personal OS` with a space), the junction target is the only path that matters. Point the junction at whatever local path actually holds the clone.

If you prefer full Windows symlinks (requires admin PowerShell or Developer Mode), substitute `New-Item -ItemType SymbolicLink -Path <junction-name> -Target <source>` for each `mklink` line. Copying the folder contents directly into `reference-repos/` also works if you do not plan to pull updates into the reference repos.

---

## Step 4: Create `.env`

The `.env` file is gitignored (see `.gitignore:9`). You have two options:

**Option A: Pull the current `.env` from the server via scp:**

```bash
scp chakrabortim2@<SERVER>:/home/chakrabortim2/agentic-search-data-engineering/.env .
```

Then edit the paths for Windows.

**Option B: Start from the template:**

```powershell
copy env.example .env
```

Then fill in values. Required fields:

```ini
# NCBI API (for FTP downloads and EUtils)
NCBI_API_KEY=<your_key_from_ncbi.nlm.nih.gov/account/>
NCBI_EMAIL=<your_email>

# PostgreSQL + Apache AGE — only needed for Phase 3.0 smoke test (Docker)
PG_HOST=localhost
PG_PORT=5432
PG_USER=<your_pg_user>
PG_PASSWORD=<your_pg_password_or_empty>
PG_DBNAME=ncbi_kg

# Storage paths — use forward slashes on Windows, pathlib handles both
DATA_DIR=C:/Users/<you>/agentic-search-data-engineering/data
FTP_CACHE_DIR=C:/Users/<you>/agentic-search-data-engineering/data/ftp_cache
KGX_OUTPUT_DIR=C:/Users/<you>/agentic-search-data-engineering/data/kgx
RAW_DATA_DIR=C:/Users/<you>/agentic-search-data-engineering/data/raw
```

**Why forward slashes:** Python's `pathlib.Path` handles both separators on Windows, but forward slashes avoid backslash escaping in the `.env` parser.

---

## Step 5: Python environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1        # PowerShell
# or: .venv\Scripts\activate.bat  # cmd

pip install --upgrade pip
pip install -e .
```

---

## Step 6: Verify the migration

Four checks in order:

```powershell
# 1. Tests pass (180 tests, all use inline fixtures, no disk data needed)
pytest -q

# 2. Config reads from .env and resolves to C: drive
python -c "from system_01_data_pipelines.shared.config import PipelineConfig; c=PipelineConfig.from_env(); print(c.data_dir, c.ftp_cache_dir)"
#    Expected: paths starting with C:/Users/<you>/... not /export/...

# 3. FTP cache is accessible
ls "$env:DATA_DIR\ftp_cache"
#    Expected: see ClinVar, Gene, MedGen cache subdirs

# 4. One pipeline runs end-to-end from cache (does NOT re-download)
gene-etl
#    Expected: reads ftp_cache, writes kgx/gene/nodes.tsv + edges.tsv, no FTP traffic
#    If this triggers an FTP download, your FTP_CACHE_DIR path is wrong.
```

All four must pass before proceeding to Step 7.

---

## Step 7: Delete data from `/export` (AFTER Step 6 passes)

```bash
# SSH to the server
ssh chakrabortim2@<SERVER>

# Delete the data (keep the parent dir so the symlink target is still valid)
rm -rf /export/home/chakrabortim2/data/kgx
rm -rf /export/home/chakrabortim2/data/ftp_cache
rm -rf /export/home/chakrabortim2/data/raw

# Optional: delete the repo clone on server if you are not coming back
# rm -rf /home/chakrabortim2/agentic-search-data-engineering
```

You can keep the server repo clone as a fallback SSH dev environment. It costs ~50 MB on `/home` (NFS) and nothing on `/export`.

---

## Gotchas

| Issue | Action |
|-------|--------|
| NCBI_API_KEY in `.env` | Transfer via scp only. Never paste into chat, email, or screenshots. If exposed, rotate at [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/). |
| Git line endings on Windows | `git config --global core.autocrlf input` BEFORE first clone. Otherwise shell scripts get CRLF and break when rsync'd to the Linux VPS in Phase 4. |
| PostgreSQL + AGE | Do NOT install natively on Windows. Use Docker Desktop with a Linux `apache/age:latest` container for the Phase 3.0 fixture smoke test. |
| Laptop sleep during long jobs | PubMed ETL is ~8 hours. Power settings → "never sleep when plugged in". Pause Windows Update during Gate 2. |
| Phase 4 rsync to Hetzner VPS | 140 GB upload from home Wi-Fi: 6-16 hrs. Schedule as overnight/weekend. rsync resumes cleanly on drop. |
| `<SERVER>` placeholder in this doc | Replace with your SSH hostname for the NCBI Linux box (whatever you type after `ssh`). |
| Reference repos get updates | If you update the main repo's reference to a rule/skill, also push the matching change to the personal-os repo (see `.claude/skills/skill-adapt-verify`). |

---

## Where this leaves you

- Repo on `C:/Users/<you>/agentic-search-data-engineering/`
- Data on `C:/Users/<you>/agentic-search-data-engineering/data/`
- Reference repos at `C:/Users/<you>/ncbi_ai_agents/` and `C:/Users/<you>/personal-os-work/`
- Server `/export` footprint: 0 GB
- Ready to run Gate 2 (PubMed + Taxonomy + merge) on the laptop
