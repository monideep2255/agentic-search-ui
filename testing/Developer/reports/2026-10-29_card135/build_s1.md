# Card 135 slice S1: build report

Defect: on a reopened saved answer, and inside a closed source card on the live screen, an OMIM source read "Not linked: this URL is not on a recognised NCBI host."

## Cause and decision

The web host list in `frontend/src/components/answer/CitationMarkers.tsx` never gained `omim.org`. The server has admitted it since the owner's decision of 2026-09-20 in `DECISIONS.md`: "REVERSES the row above: widen the citation host rule so OMIM can be cited, and dispatch OMIM in the broad search". The server rule (`NCBI_SOURCE_URL_PATTERN` in `src/system_03_search_agent/contracts/events.py`) admits `(?:www\.)?omim.org/`: both `omim.org` and `www.omim.org`, exact hosts only.

## Change

- `frontend/src/components/answer/CitationMarkers.tsx`: added `omim.org` and `www.omim.org` to `ALLOWED_CITATION_HOSTS`. No other host added.
- `frontend/src/components/answer/CitationMarkers.test.tsx`: both OMIM hosts link; `omim.org.evil.example`, `evilomim.org`, `sub.omim.org` and `http://omim.org` do not.
- `tests/system_03_search_agent/contracts/test_citation_host_parity.py`: reads the web list from the component and holds it to the server pattern both ways (every web host is accepted by the server; every literal server host is in the web list).

## Results

| Check | Result |
|---|---|
| `npx vitest run src/components/answer/` | 5 files, 38 tests passed |
| `npx tsc --noEmit -p .` | clean |
| `pytest test_citation_host_parity.py` | 2 passed |
| `ruff check` and `ruff format` on the new file | clean |
| Mutation: remove `www.omim.org` | the Python server-to-web test and the vitest case both go red; restored |

## Disagreements

None beyond OMIM. The server admits every `*.ncbi.nlm.nih.gov` subdomain while the web lists three; the web list is the narrower side and every web host is accepted by the server. Not changed.
