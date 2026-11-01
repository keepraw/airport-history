# Worldwide historical airport code bulk ingestion

This is a **full-corpus, zero-airport-allowlist import**, not a queue of one-off
airport studies. One command builds a local, indexed SQLite database from **all**
16 published OurAirports source-record shards, all 88,330 existing event review
groups, their original selected source-transition candidates, and the curated
formal physical-site/code assignments. Sources are pinned; no network request,
owner signature, country-specific code change or manual per-airport step is made.

```sh
python3 bulk/worldwide.py build --output work/history-index.sqlite
python3 bulk/worldwide.py lookup --code TAO --date 2018-01-01
python3 bulk/worldwide.py lookup --code LZO --date 2017-01-01
python3 bulk/worldwide.py lookup --code KTI --date 2020-01-01
python3 bulk/worldwide.py lookup --code RKSI --scheme ICAO --date 2025-05-01
```

The **Worldwide historical code bulk ingestion** GitHub Actions job executes
this entire import automatically when the relevant files change, checks a
known verified historic code against an ambiguous reference code, and uploads
`history-index.sqlite.gz` plus machine-readable whole-population metrics as a
build artifact. The generated database can also be rebuilt locally at any time.
The builder writes a temporary database, checks referential/integrity constraints,
then atomically replaces the output; repeated builds are deterministic.

The database has three explicit evidence layers:

1. `formal_assignments`: reviewed `apt_` physical sites, IATA/ICAO and
   conservative `validFrom`/`validTo` uncertainty bounds. Only an unambiguous
   *certain* date range can return `resolved`; an unconfirmed horizon returns
   `uncertain`, even when a source directory contains a current row.
2. `reference_observations`: bulk indexed source-record codes, retained
   before/after revisions, typed namespaces, site coordinates and source
   locators. `loc_` is a physical location **hypothesis**, not a vetted airport.
   A historical change can be joined to a historical location only when the
   original candidate ID explicitly links them; otherwise multiple possible
   sites remain visible and are labeled ambiguous.
3. `lead_groups` / `lead_code_observations`: all selected worldwide transition
   leads; each candidate and source can be queried by code, with an optional
   unverified OurAirports source record crosswalk. They are not silently merged
   into physical sites or official allocation dates.

**This is real batch materialization, not mass fabrication of code-validity
claims.** A source revision time says when an upstream directory revision was
observed; it does *not* establish when a code took effect, stopped being used,
or crossed physical sites. IATA, ICAO, GPS, LOCAL and IDENT stay distinct.
Directory/country/city-code changes are never auto-promoted to `resolved`.
Uncertain source observations are still searchable by any historical date,
with that limitation explicit in the response, rather than dropped entirely.

The pipeline has no airport-count or country-count cap, no repeated Owner approval
cycle, no new `apt_` allocation and no dependency on PR #29's private provenance
recovery. Future official, dated code allocations can be added to the existing
curated layer without changing or deleting the raw bulk evidence. The materialized
index updates automatically from whichever pinned complete input corpus the
repository supplies; it does not pretend that the current global directory scan
is a complete official historical allocation ledger.
