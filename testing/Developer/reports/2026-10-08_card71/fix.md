# Card 71 fix round

Pull request 203. The saved table lives in `frontend/src/components/screens/savedAnswerMarkdown.tsx`, with its tests in the matching card 71 test file.

## V-71-04: column names on a phone

- Changed: each stacked value now reads "Column name: value". An empty cell shows its column name and an en-style dash instead of vanishing. A table with no header shows the bare value. Sizes, colours and wrapping are unchanged, so the row stays close to the live phone row.
- Test: "labels each stacked value with its column name, empty cells included". It failed on the old code and passes now.

## V-71-03: page reset on different content

- Changed: the table component is keyed by its position plus its header and rows, so a different table or a different saved answer mounts fresh and opens on page 1, with no help from the parent.
- Test: "opens on page 1 when given a different table or answer, without unmounting" rerenders with new content after paging to page 2. It failed on the old code and passes now.

## V-71-05: test gaps

- Added "shows no bar for exactly ten rows" (desktop and phone). With the boundary changed to `>=` it goes red; seen.
- Added "lets long values wrap inside the stacked phone row". With the wrap rule deleted it goes red; seen.

## Gates

- Card 71 test file: 7 of 7 pass, exit 0.
- `npm run build` exit 0; answer and saved markdown suites 48 of 48, exit 0; doc drift check exit 0.
