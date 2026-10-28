# Worldwide reference 1.0.0: measured scope and evidence boundaries

Base: merged PR #10, `4b3e80fc47c18a9a39f8716a0c2caf83c624351a`.
Historical data stays **0.7.0**, schema **3.0.0**. The entire merged 0.7.0 dataset
is frozen in `test/curated-0.7.0.json`, SHA-256
`31c5735b333881d7afdd527fe4af1db8e28413d5bba114fbf88a4aad0809cff7`.
Earlier 0.4.0, 0.5.0 and 0.6.0 freezes and all resolver safeguards remain enforced.

## Before and after

| Category | Before | After |
| --- | ---: | ---: |
| Queryable worldwide reference source records | 0 | **86,950** |
| Eligible pinned OurAirports snapshot rows materialized | 0 | **86,286 / 86,286** |
| Historical-only reference rows retained outside current snapshot | 0 | **664** |
| Closed reference records, including historical-only | 0 | **13,643** |
| Snapshot rows marked closed | 0 | **13,585** |
| Snapshot rows not marked closed | 0 | **72,701** |
| Reference rows without current IATA or explicit ICAO | 0 | **75,047** |
| Reference rows without current IATA, explicit ICAO or GPS | 0 | **41,716** |
| Reference rows with conservatively matched timezone | 0 | **24,013** |
| IATA reference keys: one source record / multiple source records | 0 / 0 | **9,362 / 237** |
| ICAO reference keys: one source record / multiple source records | 0 / 0 | **10,722 / 17** |
| IATA / ICAO keys with multiple location hypotheses | 0 / 0 | **364 / 181** |
| Reference rows connected to existing curated IDs | 0 | **22** |
| Source records with multiple location hypotheses | 0 | **678** |
| Additional unresolved location hypotheses | 0 | **750** |
| Verified physical airports | 23 | **23 (+0)** |
| Verified historical code assignments | 40 | **40 (+0)** |
| Verified official-name intervals | 3 | **3 (+0)** |
| New historical resolver coverage | — | **0; deliberately unchanged** |

“Not marked closed” is a source classification, not independent proof of active
operations. Identifier counts include retained historical directory observations,
not only snapshot fields. A single source record can contain several possible
locations; a “one source record” key is not necessarily an unambiguous location.
The API reports that additional ambiguity. Distinct source records may also
describe the same physical site. Neither record count nor coordinate-hypothesis
count is a verified-airport count. Exact machine counts live in
`reference/generated/metrics.json`.

All **86,950** records in the existing OurAirports historical identity inventory
were inspected; none of the seven eligible facility types were excluded. The
exact pinned CSV was explicitly recovered once because the inventories are not
a complete archived CSV snapshot. Its hashes/revision are now repository-controlled.
No new worldwide history scan or Wikidata download was performed. Earlier
`airport-codes-raw` transitions with inherited numeric IDs supplement earlier
names, code observations and possible locations, including Temindung/Pranoto;
their derivative provenance and licensing remain explicit.

## Bulk processing

| Category | Observed count |
| --- | ---: |
| Existing source-transition candidates inspected | **1,240,058 / 1,240,058** |
| Candidates selected by event-type rules | **117,356** |
| Source observations represented by selected candidates | **181,297** |
| Duplicate candidate members grouped using existing exact groups | **29,026** |
| Resulting unresolved event groups | **88,330** |
| Groups containing already-reviewed candidates | **28** |
| Other groups awaiting authoritative evidence review | **88,302** |
| Groups conservatively linked to a reference source record | **33,773** |
| Groups without an established reference-record match | **54,557** |
| Groups with multiple OurAirports-family derivative members | **18,390** |
| Empty ICAO-column backfill candidates mechanically excluded | **223,937** |
| Other revision candidates deferred under the documented selection rules | **898,765** |
| Geographically distinct IATA/ICAO association leads, at least 5 km | **493** |
| Full-population exported pending-review packets | **4,416** |
| Events per packet | **20 maximum; final packet 2** |
| Newly accepted historical facts | **0** |

The accounting closes: 117,356 + 223,937 + 898,765 = 1,240,058;
117,356 − 29,026 = 88,330. Selection is rule-based, not an airport-count limit.
The 88,302 exported groups are prepared evidence-review work, not completed human
historical investigations. The other 28 groups retain their existing review
ownership and are skipped by the packet exporter. Three old numeric IDs with no
corresponding baseline record are explicitly unmatched, never dangling references.
Even linked source records do not establish verified physical continuity. Original source candidate
payloads are never copied into every packet or modified.

Candidate classifications are 68,012 code-change observations, 2,006 location
change/correction leads, 13,760 closure/reopening observations and 33,578 name-label
observations. Code changes include directory backfills and corrections that still
need content review. Even 493 geographically distinct associations do not establish
493 code transfers: some are duplicate records, coordinate corrections or erroneous
codes. Multiple occurrences remain auditable through original observation counts.

The workflow reuses existing duplicate groups and disk-backed joins. It exports
unlimited batches while preserving the existing 20-event review validator. The
admission gate checks compatible multi-batch reviews, unchanged permanent records,
exact added-ID mappings, explicit human acceptance, claim-linked dated original
primary evidence, interval assessments and the existing historical schema/semantic
validator. Tests reject derivative confirmations, future observations, unreviewed
packets, missing boundary assessments and changes to existing IDs.

## Operational measurements

One managed Linux worker, Python 3 and Node 24; measurements are observations,
not performance guarantees. Timing includes input validation and compressed output.

| Operation / artifact | Measured result |
| --- | ---: |
| Full reference baseline build | **30.9 s**, peak **968 MiB** |
| Full 1.24-million candidate triage and reuse analysis | **36.2 s**, peak **131 MiB** |
| Compressed reference shards, indexes, manifests and metrics | **21,565,534 bytes** |
| Compressed triage outputs, manifests and metrics | **8,082,156 bytes** |
| Checked-in pinned compressed CSV | **3,798,837 bytes** |
| Entire exported 4,416-packet review workspace, not committed | **257,349,466 bytes** |

Indexed lookups and streaming searches were repeated five times against the
checked-in artifacts while validation also ran on the worker:

| Lookup | Median | Maximum | Result |
| --- | ---: | ---: | --- |
| IATA `JFK` | **169 ms** | 176 ms | 1 unreviewed reference record |
| ICAO `KJFK` | **212 ms** | 227 ms | 1 explicit-ICAO reference record |
| IATA `KTI` | **283 ms** | 448 ms | 3 source-record/location candidates; ambiguous |
| Removed source ID `12148` | **129 ms** | 152 ms | Closed, code-less historical-only facility |
| Historical label `Temindung`, country `ID` | **2,980 ms** | 3,138 ms | 1 repurposed source record, 2 location hypotheses |
| Country `AQ` | **2,387 ms** | 2,822 ms | 47 source records, 50 possible locations |

The query process's peak RSS across these searches was **16.6 MiB**. Code/source-ID
lookups read selected compressed shards; name searches stream the whole population.
Countries spanning all hash shards also require a streaming pass over those
shards. The resolver never loads or calls this reference layer implicitly.

The observed triage rate is approximately **34,200 input candidates/second** on
this worker. Mechanical preparation can therefore handle the existing global
corpus routinely, without multiplying the effort by country or manually choosing
five airports. Review throughput is not measured by this rate: original source
lineage, physical continuity, directory corrections, code-specific effective
boundaries and official-name evidence still need claim-specific assessment.
Unsupported cases stay deferred instead of manufacturing a timeline.

## Validation and limits

`pnpm check` includes all previous gates plus strict reference-schema validation,
full-population/index/hash checks, complete reference and triage byte-identical
rebuilds, full-population input-order identity tests, actual worldwide lookup
tests, memory/runtime smoke checks, compatible multi-batch admission tests and
the frozen 0.7.0 historical resolver comparison (including future dates).

There are no additional verified admissions in this PR. The reused corpus is
secondary/derivative directory evidence; it does not independently support new
historical intervals. No new authoritative corpus was obtained or claimed as
reviewed. The formal evidence horizon and KTI/DKR/ROV uncertainty are unchanged.
No Keepraw-Fly files, server, UI, external database service, merge, tag or Release
is part of this change. See [the reference guide](../reference/README.md) for the
exact source/license rules and reproducible build, query and admission commands.
