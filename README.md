# airport-history

Historical airport identities, locations, and code assignments.

A small, offline TypeScript resolver and versioned reference dataset for
[Keepraw-Fly](https://github.com/keepraw/Keepraw-Fly). The same airport code can
identify different physical sites over time. This repository preserves those
sites and the evidence behind their code assignments.

**Bootstrap scope:** eight physical airports, eight IATA assignments for TAO,
IST, HKG and DEN, plus two ICAO VHHH assignments. This is a curated history layer,
not a replacement for a worldwide current-airport directory. No server, database,
UI, global crawler or Keepraw-Fly integration is included. This is not a
navigation or operational flight-planning dataset.

## Run

Use Node.js 24 and pnpm 10.14.0 (the package manager is pinned in `package.json`).

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
dist/v0.1.0/
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
| `conflict` | Confirmed intervals for different physical airports overlap on the query date |
| `not_found` | No curated assignment can apply; no current-directory fallback |
| `invalid_input` | Invalid code, scheme or Gregorian date |

Codes are trimmed and uppercased. Dates must be real `YYYY-MM-DD` calendar dates
in the airport's local civil calendar. Timestamps, offsets and partial query
dates are rejected. The resolver does not convert UTC to local time. The four
migration pairs are in the same respective local date systems; cross-timezone
code reuse needs an explicit future policy. ICAO is a separate namespace:
`resolveAirport(data, "VHHH", "1997-06-01", "ICAO")` returns Kai Tak.

## Identity and time model

- `airportId` is an opaque `apt_<UUIDv4>`, assigned once and never reused. Keep
  it when updating names, sources or coordinates. A physical relocation creates
  another entity. A simple rename does not. Keep closed airport entities.
- OurAirports numeric IDs are external cross-references, not our primary IDs.
  The fixture `test/identities.json` freezes the initial identity mapping.
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
  intervals cause uncertainty; overlapping certain intervals for different
  physical sites are a conflict.

An old airport's original code-assignment date is unknown. Its latest-start bound
comes from an earlier dated code observation. This is **not** a claim that the
code began on that observation date. Dates before that evidence remain uncertain;
we do not truncate the actual historical interval to the MVP window. New airports'
end dates are unknown; the fixed 2026-10-25 reference snapshot bounds the checked
continuity horizon. Later queries are uncertain rather than silently extrapolated.

`verified` records are reviewed historical conclusions, including explicitly
recorded continuity inferences between observations and the documented transfer.
They are not an official IATA/ICAO allocation ledger or proof of every intervening
day. `pending`/`disputed` records cannot yield a resolved result. All seeded
names, coordinates and timezone mappings remain `reference` attributes; resolving
a code does not upgrade them into verified historical names or surveyed positions.
The display name is a canonical label, not a historical-name timeline. IANA zone
IDs are not fixed offsets; consumers must use timezone rules for a flight instant.

## First cases and evidence

All source records were reviewed on **2026-10-26**. Full URLs, license scope,
access dates, review status and claim notes are in `data/airports.json`.
The [evidence notes](docs/evidence.md) explain the historical and licensing limits.

| Code | Physical change | Supported boundary | Date-only behavior |
| --- | --- | --- | --- |
| TAO | Qingdao Liuting → Qingdao Jiaodong | 2021-08-12 local midnight | 2017: Liuting; 2024: Jiaodong; transfer date resolves to Jiaodong |
| IST | Istanbul Atatürk → Istanbul Airport | 2019-04-06, within the day | 2017: Atatürk; 2024: Istanbul; transfer date uncertain |
| HKG / VHHH | Kai Tak → Chek Lap Kok | 1998-07-06, within the day | 1997: Kai Tak; 2024: Chek Lap Kok; transfer date uncertain |
| DEN | Stapleton → Denver International | 1995-02-28, day precision | 1994: Stapleton; 2024: Denver; transfer date uncertain |

The validator intentionally reports four possible-overlap warnings (IST, HKG,
VHHH, DEN). They express unresolved boundary-day attribution, not definite data
conflicts. No historic code start was inferred from an airport opening date.

## Repository layout

```text
.github/workflows/ci.yml      # install, types, data validation, tests, build
src/
  types.ts                   # physical entities, boundaries, assignments, results
  time.ts                    # civil-date and interval operations
  resolve.ts                 # pure offline resolution
  validate.ts                # JSON Schema plus semantic validation
  index.ts                   # dependency-free resolver entry point
schema/dataset.schema.json   # strict draft-07 schema
data/airports.json           # eight sites, ten assignments, source registry
scripts/{load,validate,build}.ts
test/{resolve,validate,build}.test.ts
test/identities.json          # permanent initial ID mapping
docs/evidence.md
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
code conflicts. Possible temporal conflicts are warnings. Tests cover historical
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

Add a few well-sourced transitions at a time. Review licenses and preserve source
URLs, access/review dates and uncertainty. Never generate IDs from airport codes
or regenerate existing IDs. New factual evidence should update the dataset
version and regression expectations deliberately, leaving closed entities intact.
Clients should retain the original code/date alongside `airportId`, status and
`dataVersion` so they can re-resolve after a data update.

Next priorities: archive more primary allocation/AIP evidence (especially DEN
and HKG), establish earlier first-assignment bounds, verify historical airport
reference points and names, add carefully sourced ICAO transfers, and design
instant-level disambiguation only when there is supporting evidence. Cross-version
ID retirement/alias review should precede larger contributions. No automatic
current-data fallback, global import system or main-project integration is planned
in this bootstrap.

## License

Code and documentation: [MIT](LICENSE). Original dataset arrangement, IDs and
annotations: [CC0 1.0](LICENSE-DATA), only to the extent contributors hold rights.
OurAirports and the selected IANA data retain their upstream **public domain**
designation; Wikidata structured statements are **CC0**. Copyrighted references
are cited as evidence and are not redistributed or relicensed. See
[third-party notices](THIRD_PARTY_NOTICES.md) and each source's license record.
