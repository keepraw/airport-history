# Global public-data airport-history enrichment

Research baseline: `bb1046455e949c6c0bf3a18769464cb232bec19e`, data 0.12.0, Schema 3.0.0. Research/query horizon: 1970-01-01 through 2026-11-10. Formal data remains 46 identities, 55 assignments and 112 sources.

## Measured results

| Measure | Result |
| --- | ---: |
| Existing reference records reused | 86,950 |
| Historical event groups joined | 88,330 |
| Existing code-linked candidates processed | 2,484 (2,012 IATA; 472 ICAO) |
| Existing geographic reuse leads processed | 493 |
| High-value event groups processed | 1,198 |
| Wikidata entities enumerated, including all-rank-only entities | 21,477 |
| Wikidata entities with coordinate-supported reference matches | 10,466 |
| OSM coded airport objects acquired | 16,231 |
| OSM objects with coordinate-supported reference matches | 10,492 |
| Matched Wikidata / OSM country buckets | 218 / 234 |
| Wikidata code-statement relationships, deduplicated | 30,442 |
| Wikidata structured code revisions actually compared | 2,446 |
| OSM code-tag changes actually compared | 1,645 |
| Existing reuse leads with distant distinct Wikidata entities | 41 |
| Additional distant-entity shared-code leads | 181 |
| New verified real-world code-change events / solved cross-site reuse | 0 / 0 |
| New evidence-ready bounded ICAO proposals | 2,458 |
| New physical-airport proposals in that batch | 2,456 |
| New IATA admission proposals | 0 |
| Currently Owner-authorized new admissions | 0 |
| Conditional newly resolved code/date queries | 63,908 |
| uncertain → resolved / not_found → resolved | 0 / 63,908 |
| Existing resolved answers changed / new resolver conflicts | 0 / 0 |

The global entity, revision and reuse counts are research results. They do not certify an airport's physical continuity or code effective dates. Code-tag/edit timestamps remain observations. Matched entities can have multiple candidate reference associations; no code-only identity is admitted.

## Consolidated FAA admission proposal

The October 1 and October 29, 2026 FAA NASR `APT_BASE.csv` editions provide primary observations at stable FAA site numbers. The batch requires unchanged four-letter ICAO, open status in both editions, coordinate variation no greater than 100 m, a unique existing US reference match within 500 m, agreement on local FAA identifier and ICAO, the same state, and an existing pinned timezone reference. Shared-code collisions and ambiguous matches are withheld. Two dated editions are temporal observations from one issuer, not two independent source families.

The proposed certain whole-date core is **2026-10-02 through 2026-10-27**. The extra guard before the second civil edition date avoids assuming an effective UTC instant or treating an edition date as an airport-local timestamp. Outer allocation/withdrawal bounds remain unknown. This is a bounded continuity inference, not an assertion that the code was allocated on October 1. These are US supplementary gains; they do not constitute global historical completeness.

`proposed-data.json` is a native Schema 3.0.0 **pending research proposal**. New source and assignment states remain pending. Existing airports, assignments, source records and IDs are preserved byte-for-byte as JSON values. New UUIDv4 IDs are reserved in `proposed-airport-id-bindings.json` for this proposal only. `faa-admission-candidates.jsonl.gz` supplies per-site evidence, exact projected rows, row hashes and scoped claims. `faa-source-lock.json` pins both official ZIP archives and CSV member hashes. No OSM material enters the proposal.

Applicable Owner source/claim authorization and the existing admission path remain required. Existing AAI, Korean or other grants are not extended. No new approval system, policy, executor or schema is introduced. The proposal is prepared for one consolidated review; it has not been executed as a formal admission.

## Resolver measurement

The actual production `resolveAirport` ran 67,868 times on assignment-boundary partitions across 28,903 namespace/code keys. Exact day weights cover the full requested horizon. The 63,908 gained query cells equal the 26-day core across the 2,458 proposed ICAO relationships. Only the simulation marks new scoped records reviewed in memory. There are **zero published production gains until admission**. The hypothetical unknown outer bounds also change 50,983,836 not_found cells to uncertain; these are explicitly excluded from coverage gains. These synthetic query cells are not historical flights. No real flight corpus was acquired, and affected-flight counts are unknown.

## Exact source gaps and uncertainty

- Wikidata: 1,453/1,453 targeted entity histories complete; 0 pending. `complete` checkpoint records per-entity counts. Initial HTTP 429 responses were followed by paced resumable retrieval. Other entities have statement enrichment without targeted revision retrieval. Property-comment selection can miss uncommented/bulk-import edits; this is not an exhaustive content diff of every entity revision.
- OSM: 1,366/1,366 targeted object histories complete; 0 pending. Failed discovery tiles: `[[22.5, 67.5, 45.0, 90.0]]`. API failures and exact URLs are in the source lock. Current-object discovery does not enumerate all deleted airports; codeless objects remain outside the coded-airport acquisition scope.
- Three Wikidata relationships have both start/end qualifiers. They are secondary assertions, not new admitted intervals. ISL is deprecated and conflicts with treating inauguration as allocation; EDDB includes year/month precision and conflicts with interpreting a Wikidata entity's end as physical/code withdrawal. The Bicol LGP claim needs primary source authority and effective-date verification. Raw precision and review notes are preserved.
- BTS lookup acquisition links 560 US references on airport name, city and state. AirportSeqID prefix links are leads without effective chronology; lookup rows are not flights.
- FAA coverage is limited to the two pinned October 2026 editions. Earlier historical NASR epochs and actual flight validation remain gaps. Country and state distributions, all exclusions and pending claims are explicit in the JSON reports.

## Licensing and reproducibility

JSONL names below are logical dataset names. Resolve them through `jsonl-shards.json`; oversized datasets use sequential `.000.jsonl.gz` shards, each at most 8 MiB uncompressed. Concatenating decompressed shards in manifest order exactly reconstructs the original serialized records. Both manifests include hashes, compressed/uncompressed sizes and record counts.

See `LICENSES.md`. OSM databases and combined OSM-derived research joins retain ODbL obligations and attribution. Restricted source documents are not redistributed. FAA projections omit contact fields and third-party PDFs. The source lock contains exact URLs, acquisition outcomes, hashes, reused-input hashes and scoped citations.

Fresh acquisition commands (successful responses cache by URL; failed requests remain resumable):

```sh
python3 scripts/evidence/public_data.py acquire
python3 scripts/evidence/public_data.py statements
python3 scripts/evidence/public_data.py complete_entities
python3 scripts/evidence/public_data.py osm_acquire
python3 scripts/evidence/public_data.py bts
python3 scripts/evidence/public_data.py history
```

Rebuild from the delivered locked research snapshots, without repeating the worldwide scan or downloading OurAirports:

```sh
python3 scripts/evidence/public_data.py build
python3 scripts/evidence/public_data.py faa
node scripts/evidence/public_data_coverage.ts
python3 scripts/evidence/public_data.py finalize
python3 scripts/evidence/public_data.py validate
```

FAA can rebuild from the delivered field projections when original ZIPs are not cached. Original downloads remain reproducible from the pinned official URLs and hashes. Do not run fresh acquisition to reproduce a frozen snapshot against today's mutable source state.

Validation: native schema validation of pending and simulated datasets; production resolver differential; the public-data identity and sharding regression suite (`pnpm test:public-data`, explicitly executed by CI); existing TypeScript checks, formal data validation and 444 repository tests. Formal data, Keepraw-Fly and PR #114 are unchanged. Research-only merge does not admit the FAA proposals; no release or auto-merge is requested.
