# Keepraw-Fly historical resolver experiment

Actual read-only target: `keepraw/Keepraw-Fly` main at
**50a00d9d2b4fede6595b008d211167ef020eedbd**. Airport History base is
`d520136e82a348ff6f3429f9c879672ad1dfa5b8`, reviewed data **0.7.0**.
The source/hash lock is `scripts/compat/fly-source-lock.json`; measured results
are in `scripts/compat/results.json`. No Fly tracked or untracked file was
changed, and no Fly PR, release or archive migration was made.

## Reproduce the actual experiment

The regular Airport History tests run the committed adapter and real history
without fetching another repository. Cross-repository tests require an explicit
clean checkout at the pinned SHA, never a moving main:

```sh
pnpm build
pnpm exec vitest run test/compat/fly-adapter.test.ts test/conflicts.test.ts
# Supply a clean Fly checkout at the exact SHA above.
pnpm compat:fly --checkout /path/to/Keepraw-Fly
# Optional actual D3 map tests: install only into Airport History's ignored work/.
npm install --prefix work/compat/runtime --ignore-scripts --no-audit --no-fund d3-geo@3.1.1
pnpm compat:fly --checkout /path/to/Keepraw-Fly --maps
```

The final run passed **182 tests / 7 files**, including actual Fly `core`,
`routes`, `time-display`, `flight-editor`, `csv-import` and `map-geometry` tests,
plus four cross-repository experiments using the real built historical JSON.
It uses Airport History's Vitest/AJV dependencies, and optional D3 3.1.1, not a
full Fly dependency installation or full web-app CI. Only eight authentic
directory sample rows and their MIT notice are retained as fixtures; the whole
Fly project is never copied into this repository.

## Findings and proposed adapter

Keep the existing **7,884-entry** current IATA directory for search and reference
display. `AirportReference` requires non-null city/country, numeric coordinates
and an IANA timezone; historical `PhysicalAirport` does not provide city/country
and permits null attributes with separate `reference`/`verified`/`unknown` status.
Replacing `airportByIata` directly would erase dates and these type/quality
distinctions. A read adapter is necessary.

The experimental `scripts/compat/fly-adapter.ts` accepts a code and local date,
calls `resolveAirport()`, and returns the historical result, immutable physical
`airportId`, nullable attributes with their existing fact status, current-directory
fallback separately, and calculation capability. Resolving the code/site does
not certify historical display name, coordinates, timezone, city or country.
This prototype deliberately does not force missing values into `AirportReference`.

| Historical status | Display and calculation policy |
| --- | --- |
| `resolved` | Prefer the selected historical physical site; preserve each attribute's quality. Compute only with valid available coordinates. |
| `not_found` | A current reference label may be shown with an explicit unverified badge. It supplies no historically verified route. |
| `uncertain` | Expose all candidate sites and boundary uncertainty; withhold historical coordinates until a site/date is established. |
| `conflict` | Require review; expose the conflict and withhold historical coordinates. |
| `invalid_input` | Surface the input problem; do not hide it behind directory fallback. |

If the product elects to show approximate current-reference map/statistics for
unresolved history, that must be a separately labelled opt-in policy. It must not
be silently counted as verified historical coverage or mixed with a resolved old
site's missing timezone/coordinates.

Real-data tests cover TAO before/after relocation, HKG's old site and uncertain
1998-07-06 day, absent JFK coverage, and KTI's uncertain historical boundary.
The existing reference tests exercise KTI's multiple reference IDs and Samarinda's
multiple location hypotheses without importing them into history. Production
history contains no confirmed overlapping conflict; the existing resolver conflict
regressions cover that status, while the adapter policy test ensures review is
required. No assignments were invented to manufacture a production conflict.
The missing-coordinate/timezone projection test uses the existing missing-attribute
regression condition and changes no assignment or interval.

The actual Fly route function aggregates by `originIata-destinationIata` before
lookup. Two TAO flights on 2021-08-11 and 2021-08-13 therefore produce one route,
although their physical origins are **27.799 km apart**. Using Fly's actual
distance function on the historical TAO/HKG points yields **1,672.151 km**, versus
**1,672.853 km** with its current map: a **0.702 km** difference for this route.
Other route directions can have different effects. Feeding the historical points
into Fly's actual D3 projection and great-circle path produces distinct paths
without nonfinite coordinates. Thus runtime behavior, not only TypeScript shape,
demonstrates the need to resolve before aggregation.

## Endpoint dates and unchanged archives

Arrival date cannot be copied from `serviceDate`. The prototype interprets each
stored timestamp in that endpoint's timezone. For travelled origin/destination
it prefers actual timestamps when present, otherwise scheduled ones. The planned
destination uses scheduled arrival. Diversion identity uses the actual diversion
airport **and actual arrival**; when that timestamp is absent, its historical date
remains unknown instead of borrowing the planned arrival. Tests include UTC
timestamps, explicit offsets, distinct departure/planned-arrival/diversion dates,
and a date crossing the TAO transfer.

When all sites for a code share a known timezone, it seeds date conversion;
otherwise the current reference timezone is only a provisional seed. After
resolution, the adapter converts again with the selected site's timezone and
requeries until stable, rejecting cycles or missing/invalid timezone conversion.
The `dateBasis` and the timezone Fact status must be exposed: even a selected
site's timezone can be reference-level, not historically verified. Historical
timezone changes and same-day transfer instants remain outside this date-only
resolver's guarantees. Import/editor writes would need their own product review;
this experiment only reads and derives views.

All code strings, `serviceDate`, timestamps and endpoint records remain unchanged.
There is no need to alter the Keepraw Fly JSON 0.1.0 format or migrate IndexedDB:
compute the view at read time. A derived cache can key by endpoint code, actual
local query date, historical dataVersion, and directory version; never persist a
new inferred airport identity into the user's original archive automatically.

## Reading paths needing a future Fly PR

* `packages/core/src/routes.ts`: resolve each flight endpoint first; aggregate by
  physical IDs, with explicit separate current-reference fallback keys.
* `packages/core/src/statistics.ts`: `distanceForFlight`, country counts, physical
  airport counts, longest/shortest and yearly distance/route totals need the same
  endpoint views. Decide whether product airport counts mean codes or physical sites.
* `packages/core/src/formatting.ts` and `time-display.ts`: make time formatting
  use the selected endpoint/date timezone; preserve stored instants and uncertainty.
* `airport-search.ts`, `search.ts`, web directory loading: keep current search,
  optionally annotate historical choices; do not mutate the global IATA map per flight.
* Web `flight-editor.ts`, CSV/Flighty/Umetrip import paths: review local time
  conversion and candidate selection separately. Existing UTC/default timezone
  behavior cannot certify historical site identity. The actual editor/CSV tests
  passed, including diversion-time handling, without integrating new write behavior.
* `map-geometry.ts`, globe route builders, flight-detail/passport views, map
  labels and shared poster/share models must receive the same selected coordinates
  and quality labels; changing core statistics alone cannot fix every display.

## Size, latency and limits

| Actual artifact/measurement | Result |
| --- | ---: |
| Reviewed history JSON from `pnpm build` | 137,440 bytes / 23,495 gzip |
| Existing Fly directory JSON | 683,392 bytes / 233,321 gzip |
| All 86,950 reference-record shards | 16,660,987 compressed / 139,542,135 expanded bytes |
| 10,000 historical endpoint resolutions | 197.69 ms, about 19.77 microseconds each |

Timing is a warm Node worker benchmark of the real 23-airport/40-assignment
dataset, not a cold browser benchmark or a projection to a worldwide reviewed
history. No whole-browser JavaScript bundle or Fly web build size is claimed.
The real historical data build is small enough for a separate static asset now.
The worldwide research reference layer should **not** be loaded wholesale into
the browser: retain Fly's filtered current IATA directory; load reviewed history
separately; use code/country shards or a server-side lookup for reference research.
Include dataVersion and preserve quality markers in any browser projection.

An independent Fly integration PR is technically justified after user approval.
It still needs agreed unresolved-history UX, physical-site aggregation semantics,
nullable attribute/timezone policy, a full Fly web build, browser/E2E checks,
derived-cache invalidation and audits of all listed read paths. These are future
integration tasks; this Airport History PR does not claim Fly is fully integrated.
