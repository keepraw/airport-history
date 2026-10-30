# airport-history

Historical airport identities, locations, code assignments, and official names.

An offline TypeScript historical resolver and a worldwide reference database for
[Keepraw-Fly](https://github.com/keepraw/Keepraw-Fly). The same airport code can
identify different physical sites over time. This repository preserves those
sites and the evidence behind their code assignments.

**Worldwide reference 1.0.0:** 86,950 queryable OurAirports source records,
including the entire 86,286-row pinned snapshot and 664 retained historical-only
records. It preserves 13,643 closed records, typed identifiers, source revisions,
location ambiguity and 24,013 reference timezones. These are reference observations;
they do not increase the number of verified historical airports below.

```sh
pnpm reference:lookup --code JFK
pnpm reference:lookup --code KJFK --scheme ICAO
pnpm reference:lookup --code KTI       # ambiguous historical reference observations
pnpm reference:lookup --name Temindung --country ID
pnpm reference:lookup --source-id 12148 # removed, closed, code-less facility
```

The [worldwide reference and bulk-review guide](reference/README.md) documents
reproducible offline builds, eligibility, evidence limits, indexed lookup and
multi-batch admission review. All 1,240,058 existing worldwide transition
candidates are mechanically processed into 88,330 relevant review groups and
explicit excluded/deferred categories. No new upstream history scan is needed.
See [measured before/after coverage and performance](docs/worldwide-reference-pr11.md).

**Curated scope (0.9.0):** thirty-four physical airports, twenty-eight IATA
assignments, twenty-one ICAO assignments and three official-name intervals, with
ninety-five evidence sources. The
original TAO, IST, HKG and DEN examples are joined by five reviewed ISL, ISB,
SXF/BER, TSE/NQZ and KIV/RMO events and, in 0.5.0, by ROV/RVI (Rostov-on-Don /
Platov), YNT (Yantai Laishan / Penglai) and PNH/KTI with VDPP/VDTI (Phnom Penh /
Techo); see the [0.5.0 admission review](docs/curated-admissions-pr8.md).
Version 0.6.0 adds Dakar Yoff / Diass (DKR/DSS, GOOY/GOBD), Samarinda
Temindung / Pranoto (AAP only), and Pranoto's Indonesian official-name interval;
see the [0.6.0 admission review](docs/curated-admissions-pr9.md).
Version 0.7.0 adds six reviewed ICAO histories at existing sites: OPRN/OPIS,
LTBA/LTFM, EDDB and UACC. OPRN coverage stops at the last admitted 2021 AIP
observation; preparatory OPIS/LTFM AIP designations do not certify flights before
commissioning. See [boundaries, source limitations and measured coverage](docs/curated-icao-pr10.md).
Version 0.8.0 admits four explicitly user-approved physical identities and three
ICAO continuity windows (KPFN, KECP, KISN). Williston Basin's physical identity is
admitted without a KXWA assignment. The actual new coverage is 3,780 code/date
queries; see the [authorization, record review and reproduction](research/admissions/0.8.0/README.md).
Version 0.9.0 admits seven approved physical identities and six exact ICAO windows
(VOSR, VOGB, VEKI, VEPY, VOKU and LELC), adding 4,530 actual resolved code/date
queries. The new Murcia identity has no assignment; LEMI, RMU and MJV remain
deferred. See the [0.9.0 authorization and actual coverage](research/admissions/0.9.0/README.md).
This remains the authoritative curated history layer. The worldwide reference
lookup above is separate and never returns resolved historical answers. A separate
[global discovery research layer](research/discovery/README.md) scans pinned
source histories and tracks coverage and unverified candidates. No server,
UI or Keepraw-Fly integration is included. This is not a
navigation or operational flight-planning dataset.

## Run

Use Node.js 24 and pnpm 10.14.0 (the package manager is pinned in `package.json`).
Full admission validation also uses Python 3 and Poppler's `pdftotext` to check
the accepted ECP airport row directly against its original PDF. CI ensures it is available.

```sh
pnpm install --frozen-lockfile
pnpm typecheck
pnpm validate:data
pnpm test
pnpm build
# All four checks:
pnpm check
```

Initial dependency installation needs network access. All subsequent checks,
tests, builds and resolution run offline. `pnpm build` writes:

```text
dist/v0.9.0/
├── airport-history.json
├── dataset.schema.json
├── manifest.json             # SHA-256 hashes of the five other files
├── LICENSE
├── LICENSE-DATA
└── THIRD_PARTY_NOTICES.md
```

Builds validate first, sort keys and identity collections, and omit build-time
clocks. Identical inputs produce identical bytes. Package and data versions must
match. Generated artifacts are ignored by Git. Nothing publishes a Release or
an npm package (`private: true`); a future release can attach this directory.

## Resolve a historical code

From this checkout, run:

```sh
node --input-type=module -e '
import { loadDataset } from "./scripts/load.ts";
import { resolveAirport } from "./src/index.ts";
const data = await loadDataset();
console.log(resolveAirport(data, "TAO", "2017-06-01"));
'
```

The reusable API is `resolveAirport(dataset, code, localDate, scheme = "IATA")`.
It performs no I/O, reads no clock, mutates no caller data, and has no runtime
package dependencies. Validate externally supplied JSON once with
`assertDataset` from `src/validate.ts` before resolution; Ajv is a development
validation dependency, not imported by the resolver entry point.

The returned object includes `dataVersion`, normalized query, `status`,
`airport` (only populated for a unique resolved result), `candidates`, evidence
source records and a reason. Each airport has an ID, display name, WGS84 reference
coordinates and IANA timezone, with independent attribute status and sources.
Unknown attributes have a null value and `unknown` status.

| Status | Meaning |
| --- | --- |
| `resolved` | One verified physical identity covers the entire local date |
| `uncertain` | Possible candidates exist, but a boundary, evidence horizon or verification status prevents a unique answer |
| `conflict` | Two verified assignments with reviewed evidence certainly overlap for different physical airports on the query date |
| `not_found` | No curated assignment can apply; no current-directory fallback |
| `invalid_input` | Invalid code, scheme or Gregorian date |

Codes are trimmed and uppercased. Dates must be real `YYYY-MM-DD` calendar dates
in the airport's local civil calendar. Timestamps, offsets and partial query
dates are rejected. The resolver does not convert UTC to local time. The curated
code-transfer pairs are in the same respective local date systems; cross-timezone
code reuse needs an explicit future policy. ICAO is a separate namespace:
`resolveAirport(data, "VHHH", "1997-06-01", "ICAO")` returns Kai Tak.

## Resolve a historical name

```ts
import { resolveAirportName } from "./src/index.ts";
const astanaId = "apt_99f19660-7609-49c5-b221-ed4a37046566";
resolveAirportName(data, astanaId, "2015-06-01"); // resolved: Международный аэропорт Астана
resolveAirportName(data, astanaId, "2017-06-21"); // uncertain: effective day
resolveAirportName(data, astanaId, "2024-06-01"); // resolved: Международный аэропорт Нурсултан Назарбаев
```

`resolveAirportName(dataset, airportId, localDate)` is a separate pure, offline API.
It never changes code resolution, physical identity, coordinates, or the static
`PhysicalAirport.name` reference label. Its result includes `name`, `language`,
`historicallyVerified`, the unchanged `airport`, candidates, evidence and a reason.

| Name status | Meaning |
| --- | --- |
| `resolved` | A reviewed canonical official name covers the whole date; `historicallyVerified: true` |
| `uncertain` | A possible official-name claim exists, but boundaries, review or evidence coverage prevent selection; `name: null` |
| `conflict` | Different reviewed canonical official names certainly overlap on this date; `name: null` |
| `reference` | No official-name interval can apply; `name` is the static label and **is not historically verified for this date** |
| `not_found` | The permanent airport ID is absent |
| `invalid_input` | Empty ID or invalid Gregorian date |

Every `names[]` record has a stable `nameId`, `airportId`, text, canonical language
tag, `kind`, the existing time boundaries, sources, evidence type and review fields.
Only `kind: "official"` participates in resolution. Historical aliases and
translations have separate `alias` / `translation` kinds; neither establishes an
official rename. City names belong outside this collection. This API selects one
canonical source-language official name per period; it does not negotiate display
languages, translate text, or rank parallel official spellings. The seed uses the
Russian original. Competing canonical records require review, not automatic ranking.

All time and evidence rules below apply to names as well as code assignments.
Even a static name marked `verified` cannot become a verified historical fallback.
Unknown original naming dates and dates beyond the checked evidence horizon stay
uncertain. No contemporary label is copied backward into a historical interval.
See the [Astana name evidence review](docs/historical-names.md) for source scope,
the distinction between signing and publication, and the later corporate amendment.

## Identity and time model

- `airportId` is an opaque `apt_<UUIDv4>`, assigned once and never reused. Keep
  it when updating names, sources or coordinates. A physical relocation creates
  another entity. A simple rename does not. Keep closed airport entities.
- OurAirports numeric IDs are external cross-references, not our primary IDs.
  The fixture `test/identities.json` freezes the initial identity mapping;
  `test/batch-1-identities.json` freezes the five added identities and coordinates.
- Each assignment describes one continuous **left-closed, right-open** interval
  `[validFrom, validTo)`. Each boundary carries `earliest`, `latest`, and
  `precision`: bounds on the unknown actual boundary, not invented event dates.
- `exact` requires equal non-null dates and asserts a local-midnight boundary.
  `day`, `month`, and `year` use the beginning and following beginning of that
  calendar period. These conservative bounds preserve uncertainty within it.
  `unknown` may have either/both bounds null: earliest null means unbounded
  uncertainty to the past; latest null means unbounded uncertainty to the future.
- For start bounds `[sMin,sMax]` and end bounds `[eMin,eMax]`, possible coverage
  is `[sMin,eMax)` and certain coverage is `[sMax,eMin)`. A whole-date query is
  `[day,day+1)` and must fit in certain coverage to resolve. Overlapping possible
  intervals cause uncertainty. Overlapping certain intervals for different
  physical sites are a confirmed conflict only when both assignments and their
  supporting sources have passed review.

An old airport's original code-assignment date is unknown. Its latest-start bound
comes from an earlier dated code observation. This is **not** a claim that the
code began on that observation date. Dates before that evidence remain uncertain;
we do not truncate the actual historical interval to the MVP window. New airports'
end dates are unknown; the fixed 2026-10-25 reference snapshot bounds the checked
continuity horizon. Later queries are uncertain rather than silently extrapolated.

`verified` records are reviewed historical conclusions, including explicitly
recorded continuity inferences between observations and the documented transfer.
They are not an official IATA/ICAO allocation ledger or proof of every intervening
day. `pending`/`disputed` records cannot yield a resolved result. All seeded static
names, coordinates and timezone mappings remain `reference` attributes; resolving
a code does not upgrade them into verified historical names or surveyed positions.
The static display name is a canonical reference label; `names[]` holds the
independently reviewed historical-name timeline. IANA zone
IDs are not fixed offsets; consumers must use timezone rules for a flight instant.

## Evidence provenance and conflicts

Review status, evidence provenance and temporal precision are separate fields:

| Field | Values and meaning |
| --- | --- |
| `Source.sourceType` | `primary`: first-party publication or original institutional record for its own subject; `secondary`: reporting or compilation of other records |
| `CodeAssignment.evidenceType` | `primary_direct`: a first-hand record explicitly supports the asserted code assignment; `indirect`: secondary or indirect corroboration; `continuity_inference`: a continuous assignment inferred between dated observations |
| `AirportName.evidenceType` | The same categories, applied to the entire name interval rather than to code allocation |

`evidenceType` describes the **whole continuous assignment**. When continuity
between observations is inferred, use `continuity_inference` even if a boundary
has primary evidence. All forty curated assignments have this category and remain
`verified`. It is visible through `candidates[].assignment.evidenceType`; source
types are included in candidate and result evidence. See the
[per-assignment classification](docs/evidence.md#assignment-classification).

A primary publication is primary for its own subject. A government airport
opening history can be primary for the opening and indirect for code allocation.
A news report of IATA approval is secondary, even if the quoted decision is
official. Neither publication type nor an exact boundary upgrades an assignment
to `primary_direct`. That category requires explicit code-assignment support in
a primary source; validation requires a primary source reference, while content
review establishes whether it actually supports the claim.

A confirmed conflict requires different physical airports, the same scheme/code,
overlapping **certain** intervals, and reviewed evidence for both assignments.
The shared review gate requires `verified`, a review date, nonempty source
references that exist and are all verified/accessed by that date, and a recognized
evidence category (including a primary source for `primary_direct`). Reviewed
indirect evidence and continuity inferences remain usable; categories do not rank
competing airports or automatically change verification status.

Verified assignments with only possible temporal overlap produce boundary
warnings. Any possible or certain overlap involving `pending`/`disputed` claims
produces an **unconfirmed overlap** warning, not a confirmed-conflict error.
Invalid evidence still produces validation errors independently. The resolver
retains all candidates: an unreviewed competitor on the query date prevents a
unique answer and returns `uncertain`. If a reviewed pair also certainly conflicts
on that date, `conflict` takes precedence and includes the other candidates.
Nonoverlapping historical reuse is accepted normally.

## Format compatibility: 0.9.0
+
+0.9.0 adds seven explicitly owner-approved physical identities, six ICAO
+assignments and eighteen scoped source records. Schema **3.0.0**, resolver
+semantics and all published records remain unchanged. Names/coordinates stay
+reference; timezones stay unknown. The certain windows are limited to the exact
+authorization. Unknown outer dates remain uncertain. Package/data versions
+advance together; output is `dist/v0.9.0/`.
+
+The original admission gate passed before formal replacement and replays in CI.
+Actual production-resolver measurements reproduce 4,530 new resolved queries,
+21,390 outside-window uncertain queries and 146,938 unchanged existing code
+answers. The [admission dossier](research/admissions/0.9.0/README.md) documents
+source rights, exact scopes, boundary checks and immutable research baselines.
+
+## Format compatibility: 0.8.0 (historical)

0.8.0 adds only the seven user-approved records and seven scoped primary sources.
Schema **3.0.0** and resolver/evidence semantics are unchanged. Unknown first
allocation and withdrawal bounds remain null. Names and coordinates remain
reference attributes; all four new timezones remain unknown. Package/data
versions advance together; output is `dist/v0.8.0/`. Every 0.4.0–0.7.0 record
and old query result is preserved, and 0.8.0 has its own reviewed snapshot.

PR11–13 research outputs retain their hash-pinned 0.7.0 input and original
pending states. Reproducing those historical snapshots does not re-admit records
or expand candidates. The separate admission validation runs against the actual
formal 0.8.0 database and is included in `pnpm check` and CI.

## Format compatibility: 0.7.0 (historical)

0.7.0 adds six ICAO intervals and fourteen reviewed sources at existing physical
airports. Schema **3.0.0**, resolver logic, old records and the evidence horizon
remain unchanged. Package/data versions advance together; output is `dist/v0.7.0/`.
Reviewed 0.4.0, 0.5.0 and merged 0.6.0 snapshots are frozen and required unchanged
by tests and research validation. See the [ICAO admission review](docs/curated-icao-pr10.md)
for administrative AIP designations, operational observations and OPRN's earlier
evidence limit.

## Format compatibility: 0.6.0 (historical)

0.6.0 adds four physical identities, five code assignments, one official-name
interval and thirteen sources. Schema **3.0.0** and resolver logic are unchanged.
Package and data versions advance together; output is `dist/v0.6.0/`.
Both reviewed datasets are frozen in `test/curated-0.4.0.json` and
`test/curated-0.5.0.json`; regression tests and `research:validate` require every
earlier record to survive unchanged. Temindung is an identity-only predecessor:
SRI and WALS are not admitted. AAP dates before 2019-08-21 remain uncertain.
DSS resolves from 2017-11-22 because an IATA notice explicitly confirms existing
allocation, separately from the December airport opening. DKR after 2017-12-06
stays uncertain because the announced withdrawal conflicts with later directories.

## Format compatibility: 0.5.0 (historical)

0.5.0 changes data only: schema **3.0.0** is unchanged, package and
`dataVersion` advance from **0.4.0 to 0.5.0**, and the output directory is
`dist/v0.5.0/`. Every 0.4.0 airport, assignment, name and source record is
preserved unchanged (frozen in `test/curated-0.4.0.json` and enforced by tests
and research validation). Six identities, nine assignments and fourteen sources
are added; `resolveAirport` behavior for existing codes is unchanged.

## Format compatibility: 0.4.0 (historical)

The required top-level `names` array is new. Strict schema 2 consumers reject it,
so `schemaVersion` advances from **2.0.0 to 3.0.0**. Package and `dataVersion`
advance from **0.3.0 to 0.4.0**, and the output directory is `dist/v0.4.0/`.
The manifest carries both versions. The static `PhysicalAirport.name` field and
all thirteen physical airport records, twenty code assignments and twenty-six
existing source records are unchanged. `resolveAirport` retains its signature,
result shape, evidence and historical behavior.

Schema 3 rejects schema 2 input. To migrate an external schema 2 dataset, update
its schema version and add `names: []` until name evidence has been reviewed.
Do not generate historical names from static labels or city/code changes. An empty
timeline yields explicitly unverified reference-name results. Consumers must update
their schema/types and artifact path; no runtime migration is performed. Preserve
the existing provenance fields introduced by schema 2 (`Source.sourceType` and
`CodeAssignment.evidenceType`). The build remains deterministic and offline and
ships the existing license files and SHA-256 checksums.

## First cases and evidence

Source records retain their individual access and review dates. Full URLs, license scope,
access dates, review status and claim notes are in `data/airports.json`.
The [evidence notes](docs/evidence.md) explain the historical and licensing limits.
The [batch-1 review](docs/batch-1-evidence.md) and
[candidate register](docs/batch-1-candidates.md) document new cases, uncertainty
and deferred leads. The [historical-name review](docs/historical-names.md) documents
the two Astana name intervals added in 0.4.0.

| Code | Physical change | Supported boundary | Date-only behavior |
| --- | --- | --- | --- |
| TAO | Qingdao Liuting → Qingdao Jiaodong | 2021-08-12 local midnight | 2017: Liuting; 2024: Jiaodong; transfer date resolves to Jiaodong |
| IST | Istanbul Atatürk → Istanbul Airport | 2019-04-06, within the day | 2017: Atatürk; 2024: Istanbul; transfer date uncertain |
| HKG / VHHH | Kai Tak → Chek Lap Kok | 1998-07-06, within the day | 1997: Kai Tak; 2024: Chek Lap Kok; transfer date uncertain |
| DEN | Stapleton → Denver International | 1995-02-28, day precision | 1994: Stapleton; 2024: Denver; transfer date uncertain |
| ISL | Istanbul Airport → Atatürk (inverse of IST) | 2019-04-06, within the day | 2018-12: Istanbul; 2024: Atatürk; exchange day uncertain |
| ISB | Benazir Bhutto → new Islamabad | May 2018, month precision | 2017: old field; 2019: new field; all May dates uncertain, including May 3 flight move |
| SXF → BER | Same expanded Schönefeld/Brandenburg airfield | 2020-10-25, day precision | One identity; earlier BER city code excluded; October 31 T1 opening is separate |
| TSE → NQZ | Same Astana airfield | 2020-06-08, day precision | One identity; change day uncertain; TSE unavailable afterward |
| KIV → RMO | Same Chișinău airfield | 2024-01-18, day precision | One identity; secondary code evidence; KIV unavailable afterward |
| ROV / RVI | Old Rostov-on-Don → Platov; old field gets temporary RVI | 2017-11-27, day precision | 2016: old field; 2017-11-28 onward: Platov; switch day uncertain; RVI always uncertain (end unknown) |
| YNT | Yantai Laishan → Yantai Penglai | between 2014-11-10 and 2015-05-28 | Before 2014-11-11: uncertain (start unknown); window uncertain; 2015-05-28 onward: Penglai |
| PNH / VDPP | Phnom Penh (Pochentong), replaced by Techo | earliest end 2025-09-09 (PNH) / 2025-09-08 (VDPP); withdrawal unknown | 2015: Pochentong; after the move: uncertain, not reassigned |
| KTI / VDTI | Techo (greenfield; Kratie history not admitted) | latest start 2025-09-10 (KTI; 2025-09-09 transfer day uncertain) / 2025-09-04 (VDTI) | After those dates: Techo; earlier: uncertain |
| DKR / DSS | Dakar Yoff → separate Diass | DKR end ≥2017-12-07, latest unknown; DSS start ≤2017-11-22 | 2016 DKR: Yoff; later DKR uncertain; DSS: Diass from explicit allocation observation, not booking |
| GOOY / GOBD | Separate Dakar airfields | GOOY start ≤2013-03-30; GOBD start ≤2017-12-07 | GOOY continues at Yoff after passenger move; GOBD resolves Diass |
| AAP | Pranoto at Sungai Siring, replacing Temindung | start ≤2019-08-21; earlier allocation unknown | 2018 opening/inauguration uncertain; 2019-08-21 onward: Pranoto; SRI/WALS not admitted |

The validator intentionally reports eight code-overlap warnings (IST, HKG,
VHHH, DEN, ISL, ISB, ROV and YNT) plus one Astana official-name boundary warning. These
express unresolved boundary attribution, not confirmed conflicts. No historic
code start was inferred from an airport opening date. Version 0.3.0 added the five
code-history events; 0.4.0 preserves those facts and adds name history separately.

## Repository layout

```text
.github/workflows/ci.yml      # install, types, data validation, tests, build
src/
  types.ts                   # physical entities, boundaries, assignments, results
  time.ts                    # civil-date and interval operations
  evidence.ts                # shared evidence review gate
  resolve.ts                 # pure offline resolution
  names.ts                   # pure historical official-name resolution
  validate.ts                # JSON Schema plus semantic validation
  index.ts                   # dependency-free resolver entry point
schema/dataset.schema.json   # strict draft-07 schema
data/airports.json           # 34 sites, 49 assignments, 3 names, 95 sources
scripts/{load,validate,build}.ts
test/{resolve,validate,build,evidence,conflicts,batch-1,names}.test.ts
test/identities.json          # permanent initial ID mapping
test/batch-1-identities.json  # five added IDs and reference coordinates
docs/evidence.md
docs/batch-1-{candidates,evidence}.md
docs/historical-names.md
docs/global-verification-batch-{1,2}.md
docs/curated-admissions-pr{8,9}.md
README.md
LICENSE                      # MIT for code
LICENSE-DATA                 # CC0 legal text; scope below
THIRD_PARTY_NOTICES.md
package.json
pnpm-lock.yaml
tsconfig.json
.nvmrc / .npmrc / .gitignore
```

Schema and semantic checks reject duplicate IDs/external identities, missing
references or evidence, unknown fields, malformed codes, impossible dates,
invalid coordinates/timezones, null/status mismatches, unreviewed evidence behind
verified records, inconsistent precision, reversed/empty intervals and confirmed
code/name conflicts. Possible temporal and unconfirmed overlaps are warnings.
Tests cover historical
examples, boundary days, unknown bounds, partial precision, conflicts, pending
claims, invalid inputs, identity stability and reproducible exported artifacts.
CI runs the same gates; it does not publish or merge anything.

## Relationship to Keepraw-Fly

Reviewed `keepraw/Keepraw-Fly` main at
[`0407d77`](https://github.com/keepraw/Keepraw-Fly/tree/0407d77de1a7260256c0209a8f743e5e6a6d68f9):
README, root package configuration, airport update/search/loading scripts,
`reference-data.ts` and data source metadata. It uses Node 24, pnpm 10.14,
TypeScript and Vitest. `update-airports.mjs` builds current IATA-keyed rows
`[iata,name,city,country,latitude,longitude,timezone]` from `mborsetti/airportsdata`;
the web loader installs them in the core directory. That model has no historical
assignment intervals. This project uses matching basic tooling but stays wholly
independent; no Keepraw-Fly files, import behavior or PR #106 were modified.

## Contribute and next steps

Use the worldwide reference baseline and deterministic bulk triage to process
historical leads systematically. Supported admissions may span many compatible
review batches; each preserves the existing 20-event validation rule, with no
arbitrary ceiling on total progress. Review licenses and preserve source
URLs, access/review dates and uncertainty. Never generate IDs from airport codes
or regenerate existing IDs. New factual evidence should update the dataset
version and regression expectations deliberately, leaving closed entities intact.
Clients should retain the original code/date alongside `airportId`, status and
`dataVersion` so they can re-resolve after a data update.

Next priorities: archive more primary allocation/AIP evidence (especially DEN
and HKG), establish earlier first-assignment bounds, verify historical airport
reference points and names, add carefully sourced ICAO transfers, and design
instant-level disambiguation only when there is supporting evidence. Cross-version
ID retirement/alias review should precede larger contributions. The separate
[global discovery workflow](research/discovery/README.md) now produces a worldwide
verification queue; candidate counts do not limit future coverage. No automatic
current-data fallback or main-project integration is included.

## Direct historical evidence proposals (PR13)

The [direct-source demonstration](research/evidence/direct/README.md) acquires
15 useful official historical publications plus one rejected policy sample,
assesses four physical-history cases, and prepares six physical-airport/six ICAO
interval proposals with exact original citations. Two Cleveland drafts remain
blocked; the KSGU pair still needs transfer bounds. All proposals require real
human review in that original snapshot. The separately recorded user approval
now admits only the seven records documented in the [0.8.0 admission](research/admissions/0.8.0/README.md).
KXWA, KSGU, KDXZ and Cleveland intervals remain unadmitted; the original pending
dataset, dossiers, evidence and blocked drafts are preserved.

## Versioned evidence policy review

The [offline policy workflow](research/policy/README.md) evaluates existing
research candidates against hard evidence predicates, prepares fixed medium-risk
batches and measures the actual resolver effect. Its initial AAI ICAO policy is
**draft**: no new policy or batch authorization exists and formal 0.9.0 is unchanged.
Policy execution records an engine audit with no human reviewer; exact owner
authorization is validated separately through the existing admission gate.
Run `pnpm policy:validate` or read the [Chinese dry-run report](research/policy/generated/审核报告.zh-CN.md).

## License

Code and documentation: [MIT](LICENSE). Original dataset arrangement, IDs and
annotations: [CC0 1.0](LICENSE-DATA), only to the extent contributors hold rights.
OurAirports and the selected IANA data retain their upstream **public domain**
designation; Wikidata structured statements are **CC0**. Copyrighted references
are cited as evidence and are not redistributed or relicensed. See
[third-party notices](THIRD_PARTY_NOTICES.md) and each source's license record.
