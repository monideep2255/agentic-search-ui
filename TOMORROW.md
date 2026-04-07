# Work computer setup

Read this file first thing. Goal: get Claude Code environment-ready in under 30 minutes, no planning, no pipeline code.

You are not starting the plan. The user will kick off the plan and give all instructions. You are just installing tools and verifying the environment.

---

## 1. Clone and Python environment

```bash
git clone <github-url> agentic-search-data-engineering
cd agentic-search-data-engineering

python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Recreate reference symlinks

These are Confluence-style docs. Read-only context. Do not edit them.

```bash
mkdir -p reference
ln -s <path-to>/ncbi_ai_agents-ncbi-kg reference/ncbi_ai_agents-ncbi-kg
ln -s <path-to>/personal-os-work       reference/personal-os-work
```

## 3. Configure .env

```bash
cp env.example .env
```

Edit `.env` and set:

- `NCBI_API_KEY` - your NCBI API key (required for 10 req/sec rate limit)
- `NCBI_EMAIL` - your NCBI-registered email
- `PG_USER` - output of `whoami`
- `PG_PASSWORD` - leave empty for Homebrew Postgres

## 4. PostgreSQL + Apache AGE

```bash
brew install postgresql@15
brew services start postgresql@15

# Build AGE from source
mkdir -p ~/src && cd ~/src
curl -LO https://github.com/apache/age/archive/refs/tags/PG15/v1.6.0-rc0.tar.gz
tar xzf v1.6.0-rc0.tar.gz
cd age-PG15-v1.6.0-rc0
make PG_CONFIG=$(brew --prefix postgresql@15)/bin/pg_config
make PG_CONFIG=$(brew --prefix postgresql@15)/bin/pg_config install

# Create database and graph
createdb ncbi_kg
psql ncbi_kg -c "CREATE EXTENSION age;"
psql ncbi_kg -c "LOAD 'age'; SET search_path = ag_catalog, '\$user', public; SELECT * FROM ag_catalog.create_graph('ncbi_kg');"
```

## 5. Verify environment

Run both checks. Both must pass before asking Claude to do anything.

### Check 1: Python packages and Postgres+AGE

```bash
python -c "
from dotenv import dotenv_values
import psycopg2, linkml, kgx, biopython
e = dotenv_values('.env')
c = psycopg2.connect(host=e['PG_HOST'], port=e['PG_PORT'],
                     user=e['PG_USER'], dbname=e['PG_DBNAME'])
cur = c.cursor()
cur.execute(\"LOAD 'age'; SET search_path = ag_catalog, '\\$user', public;\")
cur.execute(\"SELECT * FROM ag_catalog.cypher('ncbi_kg', \$\$ RETURN 1 \$\$) AS (n agtype);\")
print('Postgres + AGE: OK', cur.fetchall())
c.close()
"
```

Expected output: `Postgres + AGE: OK [(b'1',)]` or similar.

### Check 2: NCBI API key

```bash
python -c "
from dotenv import dotenv_values
from Bio import Entrez
e = dotenv_values('.env')
Entrez.email = e['NCBI_EMAIL']
Entrez.api_key = e['NCBI_API_KEY']
handle = Entrez.esearch(db='gene', term='BRCA1[Gene Name] AND 9606[Organism]')
rec = Entrez.read(handle)
print('NCBI API: OK, hits =', rec['Count'])
"
```

Expected output: `NCBI API: OK, hits = 1` or similar.

---

Once both checks pass, tell the user. They will kick off the plan.
