# Airport History

Airport History resolves historical IATA and ICAO codes to permanent physical
airport identities on a local calendar date. It also resolves historical official
airport names by physical airport ID. Both lookups run offline.

Schema `4.0.0` is the initial production format for this repository. Data
`0.14.0` includes physical sites, dated code assignments, and historical names.

| Data 0.14.0 | Value |
| --- | --- |
| Schema version | `4.0.0` |
| Supported local dates | `[2000-01-01, 2026-11-19)` |
| Physical airport identities | 6,510 |
| IATA assignments | 6,370 |
| ICAO assignments | 6,214 |
| Total code assignments | 12,584 |
| Historical name intervals | 3 |

The production manifest at `data/production-manifest.json` records the immutable
commit and SHA-256 for the published dataset. Releases also include a
deterministic distribution build with its own file checksums.
[Releases](https://github.com/keepraw/airport-history/releases)

## Run locally

Use Node.js 24 and pnpm 10.14.0. For the initial source tree, follow the
validation steps before generating the first production manifest.
[First publication](docs/release-process.md#first-publication)

Once the production manifest is available, run the full check.

```sh
pnpm install --frozen-lockfile
pnpm check
```

`pnpm check` runs type checking, schema and semantic validation, resolver
tests, production manifest verification, and the deterministic build. The
build writes `dist/v0.14.0/`. [Release process](docs/release-process.md)

## Resolve a code or name

```ts
import data from "./data/airports.json" with { type: "json" };
import { resolveAirport, resolveAirportName } from "./src/index.ts";
import { assertDataset } from "./src/validate.ts";

assertDataset(data);

const oldSite = resolveAirport(data, "TAO", "2021-08-11", "IATA");
const newSite = resolveAirport(data, "TAO", "2021-08-12", "IATA");
const icao = resolveAirport(data, "ZSQD", "2026-11-18", "ICAO");
const astana = resolveAirportName(
  data,
  "apt_99f19660-7609-49c5-b221-ed4a37046566",
  "2015-01-01",
);
```

The first two queries resolve to distinct physical sites in Qingdao.
Pass a local Gregorian date in `YYYY-MM-DD` form. Check the result's `status`
before using an airport or name. Candidates include each matching record and its possible or certain coverage. [Architecture](docs/architecture.md)

Maintain physical-site identities, independent code namespaces, and uncertain
boundaries when editing the dataset. [Data policy](docs/data-policy.md)

## Licensing

Code uses MIT. Project-authored data is dedicated under CC0 1.0 to the extent
contributors hold rights. Source-specific terms and attribution apply to
third-party material. [Code license](LICENSE) · [Data license](LICENSE-DATA) ·
[Third-party notices](THIRD_PARTY_NOTICES.md)
