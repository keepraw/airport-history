# User-approved historical admission: 0.8.0

Four physical identities and three ICAO continuity windows were explicitly
approved by the user `keepraw` in the task instruction on 2026-10-28. Formal data
now contains **27 airports, 43 assignments, 3 names and 77 sources**. No IATA or
historical official-name interval is added. The PR remains subject to the user's
separate merge decision.

## Authorization and evidence

[approval.json](approval.json) records the exact seven authorized IDs, windows
and exclusions. [dossier.json](dossier.json) contains seven `accepted` decisions
with reviewer `keepraw`, the approving user. Codex recorded the instruction and
checked the originals; this is not a second human review, GitHub approval,
signature, or assertion that the user personally read a PDF.

[source-review.json](source-review.json) records seven actual fresh online accesses,
original hashes, publication/edition dates, exact citations and scoped verification.
All originals match the existing PR13 archives. The FAA rules and airport rows
in one directory are one publication; the two FAA editions share register lineage.
NWS supplies its own TAF notice, not independent proof of an FAA allocation
instant or execution of an announced airport opening/closure.

The KPFN dossier uses the **printed numeric issue date 2010-04-28**, retaining
the contradictory weekday, rather than the prospective TAF date. The ECP row is
read in original PDF row order: the PR13 layout extraction interleaves an unrelated
Nottingham row. Both original proposal observations remain attached for comparison.
The KISN admission omits the 2019 closure notice: it is not needed to support the
approved interval ending in 2014. No original research evidence is removed.

| Physical airport | Permanent airport ID |
| --- | --- |
| Panama City–Bay County International | `apt_d3a329f9-73d0-43f5-90c2-0ba0a0a2e5be` |
| Northwest Florida Beaches International | `apt_74a05fd5-53fa-40f8-a3a6-de8cfd7d5e99` |
| Sloulin Field International | `apt_ba1f9f8c-1849-4092-9e91-d641bddb6bc6` |
| Williston Basin International | `apt_661b72ea-f84d-4cec-ae34-fddd5e579b3d` |

Names and coordinates remain `reference`. Timezones remain null/`unknown`.
These records do not establish historical runway footprints, official-name
validity periods or operational event dates. Williston Basin has **no KXWA assignment**.

| Assignment ID | Code | Certain half-open coverage | Resolved local dates |
| --- | --- | --- | ---: |
| `proposal-icao-pfn` | KPFN | `[2009-05-08, 2010-04-28)` | 355 |
| `proposal-icao-ecp` | KECP | `[2010-05-24, 2014-07-24)` | 1,522 |
| `proposal-icao-isn` | KISN | `[2009-05-08, 2014-07-24)` | 1,903 |
| Total | | | **3,780** |

The stable proposal assignment IDs are retained for traceability. Each formal
record remains `ICAO` / `continuity_inference`, with `validFrom.earliest = null`,
`validTo.latest = null`, and unknown boundary precision. The displayed window
does not claim first allocation or final withdrawal. Dates outside it are uncertain.
These counts describe code/date query combinations, not independent facts or global coverage.
The [actual coverage measurement](coverage.json) binds these results to the
formal dataset hash and includes boundary query outcomes.

## Admission validation and preservation

The [two existing owner events](batches/approved-historical-1.json) map exactly
the seven approved records. Event readiness is restricted to those listed IDs;
it does not approve every claim in the original candidate group. The separate
PR13 research packet and all unapproved records remain unchanged and pending.

[review-manifest.json](review-manifest.json) binds the actual formal dataset,
review files and unchanged original proposal inputs. The prior local audit and
coverage files existed and were read; their hashes are recorded as advisory
history, not as authorization or invented published documents.

```sh
# Requires Node 24, Python 3 and Poppler (pdftotext).
pnpm validate:admission
pnpm reference:review validate \
  --base-dataset test/curated-0.7.0.json \
  --batches research/admissions/0.8.0/batches \
  --dataset data/airports.json \
  --dossier research/admissions/0.8.0/dossier.json \
  --output work/validated-0.8.0.json
pnpm check
```

The replay option accepts only the hash-pinned reviewed baseline. It keeps the
same record mapping, explicit reviewer, dated original observation, boundary,
source review and schema gates. It cannot write directly to formal data.
The approved candidate passed the original default gate before formal data was
updated; replay now validates the actual admitted database and runs in CI.
The final local `pnpm check` passed: 411 TypeScript tests, 50 discovery tests,
15 reference tests and 22 evidence tests, plus schema, admission, hash,
frozen-history and deterministic-build validation.

PR11–13 builders use their frozen 0.7.0 input so existing observations, pending
judgments and deterministic outputs survive later formal additions. Their
manifests are rebuilt with the explicit frozen input and current tool hashes;
no upstream history scan or candidate expansion is performed.

KXWA, both KSGU intervals, KDXZ and Cleveland/Hardwick remain blocked. No exact
opening/closure date, additional candidate, IATA interval, name interval or timezone
upgrade is admitted. No resolver, schema, overlap rule or evidence gate is relaxed.
