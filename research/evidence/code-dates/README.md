# Historical code dates and relocation boundaries (PR23 follow-up)

This research starts from merged PR22, main
`80df6f95143c33e861b74243637e8e4a7ff92172`. Its post-merge
[CI run 41018240556](https://github.com/keepraw/airport-history/actions/runs/41018240556)
succeeded in both jobs before branch creation. Complete baseline `pnpm check`
also passed before the branch was created.

Read the [Chinese handoff](HANDOFF.zh-CN.md),
[case-by-case evidence matrix](MATRIX.zh-CN.md),
[typed assessments](assessments.json), and
[Korean amendment, SUP and NOTAM screening](korea-screening.json).

The substantive additions are pre-relocation Chinese directory captures with
explicit codes, issuing-body IATA results naming the replacement sites, Japanese
meteorological service schedules, a dated Williston booking-system statement,
a direct CAA certificate-surrender date, and further historical European sources.
These are carefully typed observations. No capture, opening, project, weather,
certificate or current-lookup date is promoted into an administrative allocation
or withdrawal date.

The IATA public search is fuzzy: ENY also returns ENI and DAX also returns PKX.
Only exact code rows are used. NGO has separate airport and metropolitan-area
rows. The current DAX/Heshi row is retained as a counterexample to inferring code
withdrawal from closure of passenger operations. The archived Yibin page's
incorrect Gaoping heading and Ankang's possibly stale flight claims remain
explicit evidence limitations. Sina credits Qunar and others; its six pages are
one syndicated source family, not six independent allocation authorities.

Korean screening examines all 1,061 returned server records, including 158
records in the focused issue-date query. One duplicated number has two server
IDs but identical full text. Three apparent identifier-change hits concern ICAO
aircraft reference codes C/D, not airport location indicators. Three amendment
originals and 51 selected supplement URLs (49 distinct byte streams) were
recovered and screened. Issue-date searches, the archive's earliest returned
date and unresolved notice lifecycles prevent an archive-completeness claim.
Independent human physical-site review is still pending.

The existing Korean `[2025-04-18, 2025-05-15)` hypothesis still represents
54 unauthorized hypothetical queries. Its increment is zero. Formal new resolved
queries and approved new windows are both zero. All seven market policies remain
draft; the Indian policy, all production grants, the published 0.10.0 dataset,
Schema 3.0.0 and permanent physical IDs are unchanged. No new policy adapter or
admission executor is introduced.

## Reproduce and custody

```sh
python3 scripts/evidence/code_dates.py validate
python3 scripts/evidence/priority_markets.py validate
pnpm check
python3 scripts/evidence/code_dates.py rights
```

The source lock retains publisher identity, original/retrieval URLs, archive
capture timestamps, publication/effective-date limits, response-byte and
extraction SHA-256 values, encoding, rights assessments and exact minimal
citation spans. PDF pages are physical one-based pages. Normalized text collapses
Unicode whitespace; JSON citations specify a JSON Pointer and character span
within that decoded field. URL dates and HTTP Last-Modified dates do not establish
code validity.

`validate` checks committed evidence and the separately labelled local original
verification receipt. It does **not** freshly acquire original bytes. Actual
original verification uses the private ignored cache:

```sh
python3 scripts/evidence/code_dates.py originals
```

That command re-extracts every locked original and checks all citation spans,
physical PDF pages, reused PR22 hashes and per-NOTAM full-text fingerprints.
Complete HTML/PDF/JSON responses, full text extractions and source diagrams remain
under ignored `work/pr23/originals/`. They are not public redistribution artifacts.
The [discovery log](discovery-log.json) records failures and retrieval metadata;
404 responses, empty indexes and query misses are not evidence of historical
absence. Exact-byte matches to prior originals are labelled as reuse, including
the already known Sichuan Airlines Dazhou notice.

The standalone validator also protects every existing main file with the
[772-file baseline lock](baseline-lock.json). Corpus tests run under the existing
evidence test suite, including inside the disposable admission rehearsal where
formal and grant files are intentionally replaced. The latter tests therefore
validate the research corpus without treating that fixture as the real baseline.
