# Priority-market correction for PR #15

This stage follows the actual user priority: historical passenger-flight
geolocation, physical replacements, typed code relationships, and major airports
in mainland China, Japan, Korea, the USA, the UK and continental Europe.
It continues the same PR branch. It neither approves nor admits historical facts.

Read the [Chinese measured results](generated/RESULTS.zh-CN.md),
[per-airport and per-record review list](generated/待审核清单.zh-CN.md),
[chain classifications](generated/chains.json), and
[country/year/namespace matrix](generated/country-year-namespace.json).
The matrix records **inspected years**, separately from any proven event date.

Two independent queues live in [generated/queues.json](generated/queues.json):

- A: actual-change leads, including replacements, service closure, code changes
  and carefully labelled future projects. China has an explicitly larger share
  because the user prioritized its real relocation cases.
- B: scoped continuity checks at major airports. Terminal/runway work and corporate
  changes do not create a new physical airport. A missing source never removes
  an important lead; unfinished years and unavailable originals remain gaps.

These 60 investigations are not 60 new historical changes. The manual leads are
explicitly labelled and do not masquerade as newly discovered directory transitions.
No additional Indian publication or investigation is used in this stage.
The earlier [global snapshot](../global/README.md) and its effective Indian,
Philippine and other judgments remain independently reproducible.

## Reproduce

```sh
pnpm evidence:markets verify
pnpm evidence:markets build
pnpm evidence:markets validate
pnpm check
```

Builds run the real TypeScript resolver for every whole local date in
2015-01-01–2026-10-29. Review assumptions exist in memory only. The combined
pending dataset reuses the preceding global proposal and enriches only its four
pending Murcia assignments; all published 0.8.0 records remain identical.
New Chinese identities are independent permanent UUIDs. Their coordinates are
reference attributes, and the actual admission gate continues to reject them.
The three <=20-event review packets disclose manual candidate origins. Murcia's
earlier candidate retains its original owner; its four enrichment dossiers do not
map that candidate again.

The important remaining gap is **zero complete same-IATA cross-site transfer
chains**. Murcia is a different-code replacement (MJV/RMU), with both physical
sites and both IATA/ICAO namespaces resolving within the evidence-supported
review hypothesis. Do not present it as a same-code transfer or a precise
allocation/withdrawal chronology. The Chinese association-only records add no
resolved days. KSGU, KDXZ and KXWA remain unapproved.

## Evidence custody and rights

The catalog is claim-specific and records the original endpoint, issuer and
expected exact short quotations. `source-lock.json` preserves original-byte
SHA-256, original extraction SHA-256, access date, known publication/effective
dates, dependence on older publications, and rights assessments. Missing precise
publication dates stay null; a guide's edition year is not an allocation date.
The public `excerpts/` files retain only necessary factual spans, original PDF
pages and normalized-character offsets, with independent excerpt hashes.

**Offline verification authenticates retained excerpts and deterministic builds.**
It cannot reproduce a whole protected publication from an excerpt. Full raw
copies used in the investigation stay under ignored `work/`, and their original
hashes were checked locally. `fetch --recover --source ID` can separately recover
an accessible original into ignored work storage and reject changed bytes; it
does not overwrite the committed evidence or infer publication permission.

The [legacy rights audit](legacy-rights-audit.json) also covers PR15's older
global raw copies: 92 full response/extraction pairs with no established full
redistribution grant are withheld from the current tree. Original hashes,
judgments and minimal cited spans remain. Earlier Git commit objects still
contain the old bytes; no history rewrite was attempted. PR11–13 frozen FAA,
NOAA, BTS and Federal Register snapshots retain their US-government factual-work
rights metadata and remain untouched. No permission is inferred for third-party
photos, commercial ledgers, charts or attachments.

All fact judgments and record dossiers remain `pending`, `reviewer: null`.
PR14 approval does not extend to this work. Keep PR15 open and unmerged; do not
enable auto-merge, write main, create another PR, tag or release.
