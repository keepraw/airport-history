# Architecture

`data/airports.json` contains the formal dataset. Schema 4.0.0 describes three
collections. [JSON Schema](../schema/dataset.schema.json)

| Collection | Role |
| --- | --- |
| `airports` | Permanent physical-site IDs, names, locations, timezones, and external identity mappings |
| `assignments` | Dated IATA and ICAO assignments keyed to physical-site IDs |
| `names` | Dated official names, aliases, and translations keyed to physical-site IDs |

`schemaVersion` identifies the format. `dataVersion` identifies the dataset
revision. Airport attribute status describes the quality of the individual
value. A `reference` coordinate or timezone can be useful during a resolved
code assignment. An `unknown` attribute carries a null value.

## Resolution

`src/index.ts` exposes `resolveAirport(dataset, code, date, scheme)` and
`resolveAirportName(dataset, airportId, date)`. IATA is the default scheme.
Dates are local Gregorian calendar dates. Both public entry points enforce
`[2000-01-01, 2026-11-19)`. [Query horizon](../src/query-horizon.json)

Intervals are half-open. The earliest possible start and latest possible end
bound possible coverage. The latest possible start and earliest possible end
bound certain coverage. A certain match covers the entire local day.
A transfer dated to day precision can leave that date uncertain.

Code resolution selects a site when an assignment covers the whole date and
every candidate belongs to that site. Whole-day assignments at different
sites produce `conflict`. Partial coverage or a competing possible site
produces `uncertain`. A date with no candidate produces `not_found`. A
malformed code or date produces `invalid_input`.

Name resolution uses canonical `official` records. When none apply to a known
site, it returns the site's display label as `reference`. The
`historicallyVerified` result indicates whole-day official-name resolution.

## Validation and build

Validation checks the schema, unique IDs, foreign keys, date precision,
attribute quality, and interval consistency. It rejects conflicting certain
intervals and reports possible overlaps. The build writes canonical JSON and
file checksums. [Release process](release-process.md)
