# User-approved historical admission: 0.9.0

This admission adds exactly **seven physical identities, six ICAO continuity
assignments and eighteen source records** to merged PR #16 main
`f43e172d8833317086a94d0c23302b42f509dcee`. Formal data is now **0.9.0 / schema
3.0.0 / 34 airports / 49 assignments / 3 names / 95 sources**.

[approval.json](approval.json) transcribes the owner's explicit instruction on
2026-10-29. Each permanent ID and `exactAuthorization` is copied from PR #16's
unchanged [selection](../../evidence/first-admission/selection.json). The thirteen
[accepted dossier decisions](dossier.json) identify `keepraw` as the approving
user and Codex as the recorder/content checker. They do not assert a GitHub
approval, independent human review or that the owner personally read originals.
The PR awaits a separate human merge decision.

| ICAO | Permanent airport ID | Certain half-open window | New resolved queries |
| --- | --- | --- | ---: |
| VOSR | `apt_9e24d5d7-5e1a-4489-b936-2737c438921e` | `[2024-02-23, 2026-07-09)` | 867 |
| VOGB | `apt_66034969-b902-4ede-8011-cc87a23070b7` | `[2024-02-23, 2026-07-09)` | 867 |
| VEKI | `apt_0342f79b-a035-43b6-88bf-52b9a5e9622f` | `[2024-02-23, 2026-07-09)` | 867 |
| VEPY | `apt_162c7dfd-e70b-48c7-bbe5-282ede0a5cc9` | `[2024-02-23, 2026-07-09)` | 867 |
| VOKU | `apt_5d260013-75b3-4ec4-8915-7c5ff2a47fc3` | `[2024-02-23, 2026-07-09)` | 867 |
| LELC | `apt_a456f7d0-80f7-48b2-81b0-0d762d5d4b12` | `[2026-04-17, 2026-10-29)` | 195 |

The new Murcia site `apt_f50aecf6-9778-4db7-9027-0e751ffab63a` is admitted as
a physical identity without an assignment. **LEMI, RMU and MJV remain deferred**.
No other pending claim is accepted. Display names and coordinates retain the
exact authorized `reference` records; timezones remain null/`unknown`. The
physical records retain the proposal's reference-note wording as required by the
exact authorization; their acceptance is recorded separately in the dossier.
No operational date or historical official-name interval is admitted.

## Evidence and rights

All nineteen PR #16 components were freshly fetched during this task. Original
SHA-256, independent extraction SHA-256 and every retained citation position
matched. The [source reviews](source-review.json) include the eighteen components
actually cited by admitted records; the parliamentary component is unused and
is not added to the formal source registry. Eighteen source records are not
eighteen independent publications: they represent six publication keys and two
issuers, AAI and ENAIRE. AAI editions share issuer lineage, and repeated Kurnool
bytes do not add independent evidence.

Archive edition, chapter amendment/publication and retrieval dates remain
distinct. Same-archive AIRAC metadata anchors the AAI editions. Specimen labels
and the stale July GEN 0.2 component are not date evidence. The ENAIRE current
index's October 29 retrieval is an observation, not a withdrawal. LELC's earlier
2019 proposal is not adopted. Kurnool's 2020/2021 opening-year conflict remains
outside this admission. Continuity between scoped observations is an explicitly
owner-approved inference, not a complete allocation ledger.

Only links, provenance hashes, independent factual notes and necessary short
citations are public. Full originals/extractions remain in ignored `work/`.
AAI/ENAIRE rights remain reserved; public access and content verification do not
establish full redistribution permission or relicense publications under CC0/MIT.
Offline CI authenticates retained minimal citations/provenance; it does not
claim a fresh online download.

## Admission and actual resolver measurements

Before replacing formal data, the candidate passed the original default
`reference:review validate` command against current 0.8.0. The admission gate's
claim, reviewer, original-primary-observation, event mapping, boundary, schema
and permanent-record checks are unchanged. Replay adds only the exact
hash-pinned 0.8.0 baseline alongside the existing 0.7.0 baseline; arbitrary
caller-supplied baselines remain rejected.

[coverage.json](coverage.json) is recomputed using production `resolveAirport()`
against the **actual formal database**, not the review hypothesis or its counts.
It covers every whole local date from 2015-01-01 through 2026-10-29 inclusive:

- **4,530** `not_found → resolved` code/date queries, all ICAO.
- **21,390** `not_found → uncertain` queries outside the approved windows,
  disclosed separately and excluded from resolved coverage.
- **146,938** existing complete code answers unchanged, including all existing
  boundaries and adjacent days; **116,721** existing name answers unchanged.
- **0** changed published resolved identities/statuses; **0/0** new/removed
  conflicts. **12,960** deferred LEMI/RMU/MJV answers remain unchanged.

Version metadata is excluded when comparing complete answers. These counts are
unique scheme/code/local-date queries, not independent facts or worldwide
coverage. Open unknown first-allocation/final-withdrawal bounds remain uncertain.

```sh
pnpm validate:admission
node scripts/evidence/admission_090_coverage.ts validate
pnpm reference:review validate \
  --base-dataset test/curated-0.8.0.json \
  --batches research/admissions/0.9.0/batches \
  --dataset data/airports.json \
  --dossier research/admissions/0.9.0/dossier.json \
  --output work/validated-0.9.0.json
pnpm check

# Optional independent re-extraction from privately obtained originals:
pnpm evidence:first-admission verify-originals work/first-admission-originals
```

[review-manifest.json](review-manifest.json) binds the admitted data, acceptance
files, actual measurements and original pending inputs. Prior 0.8.0 admission
replay remains enforced against its frozen snapshot and preservation in current
formal data. Global/market/transfer/first-admission research builders now read
their original hash-pinned 0.8.0 snapshot. Rebuilt manifests reflect the explicit
input paths/tool hashes; all research facts, pending decisions and payload bytes
remain unchanged. No resolver, schema or evidence eligibility rule is relaxed.
