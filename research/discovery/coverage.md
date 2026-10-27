# Measured global source coverage — 2026-10-27

This report measures source inspection, not completeness of global airport history. All counts are reproducible from `generated/summary.json`, per-source coverage/version/gap files and the pinned source manifest. No newly discovered historical fact has been admitted to the resolver database.

The subsequent [first verification batch](../../docs/global-verification-batch-1.md)
reviewed 20 existing event groups (12 insufficient evidence, four pending review,
four excluded, zero ready to admit), recorded in [batches/global-1.json](batches/global-1.json).
Discovery tables below retain the original export counts, including snapshot
review states. Live `reviews.json` overrides cover 21 machine representations of
18 groups, plus two existing manual leads with unchanged deferred dispositions.
Query applies the overrides to candidates and the ranked queue; `--snapshot`
shows original states. `summary.json.reviewBatches` records current batch results.
The [second verification batch](../../docs/global-verification-batch-2.md)
([batches/global-2.json](batches/global-2.json)) reviews the four recorded
next-batch leads (two insufficient evidence, two excluded, zero ready to admit)
and adds dated follow-ups of KTI, YNT and ROV/RVI without remapping them; 31
live overrides now cover both batches.
No observation, queue entry, source pin or formal airport record was removed.

## Source scope actually inspected

Each row is a pinned repository **file history**, not an independent airport population. Main-ancestor commits and every merge-parent comparison are enumerated. Distinct versions include a zero-row deletion version where applicable. Row-version counts represent all rows in distinct parsed snapshots, carried through verified diffs; they are not distinct airports.

| Source/path | Observation range | Target rows | Ever-observed external records | File commits / parent comparisons | Parsed / available versions | Parsed row-versions | Source candidates |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ourairports (`airports.csv`) | 2021-11-02–2026-10-26 | 86,286 | 86,950 | 1,771 / 1,771 | 1,769 / 1,769 | 139,159,902 | 314,515 |
| airport-codes (`data/airport-codes.csv`) | 2015-02-25–2026-10-26 | 86,286 | 92,991 | 418 / 418 | 410 / 410 | 33,944,880 | 520,122 |
| airport-codes-raw (`archive/data.csv`) | 2017-12-12–2026-10-26 | 86,286 | 86,756 | 401 / 401 | 397 / 397 | 33,223,259 | 174,618 |
| airport-codes-initial (`airports.csv`) | 2015-02-02–2015-02-17 | 0 | 46,755 | 4 / 4 | 3 / 3 | 46,755 | 48,714 |
| airport-codes-legacy (`data/airports-codes.csv`) | 2015-02-17–2015-02-25 | 0 | 567 | 2 / 2 | 2 / 2 | 567 | 567 |
| airportsdata (`airportsdata/airports.csv`) | 2020-11-06–2026-09-05 | 28,298 | 31,756 | 117 / 117 | 101 / 101 | 2,847,793 | 110,461 |
| airportsdata-city-codes (`airportsdata/iata_macs.csv`) | 2023-05-24–2023-05-24 | 89 | 89 | 1 / 1 | 1 / 1 | 89 | 0 |
| mwgg (`airports.json`) | 2014-11-25–2026-10-01 | 29,308 | 29,649 | 479 / 520 | 288 / 364 | 8,367,921 | 71,061 |

Seven file histories have no blocked comparisons. `mwgg` enumerates 520 comparisons but 113 are blocked by 76 distinct malformed/duplicate-key versions. Its 288 parsed versions are not a complete historical comparison scan. Every affected commit, endpoint blob and error is retained in `mwgg.gaps.jsonl.gz`; no transition is inferred across an unreadable endpoint.

The one malformed airportsdata EDDB continuation is joined only by the explicit source adapter; repaired blob IDs are listed in its coverage file. One mwgg blob has 1,401 empty elevation tokens interpreted as missing values, with the exact adapter and blob recorded. Original Git objects are preserved. Duplicate JSON keys are rejected rather than overwritten.

`source-assessment.json` records Wikidata assessment: zero global entities/revisions scanned. The probed current JSON dump is 103,488,697,311 compressed bytes, larger than the approximately 29 GB available workspace; streaming/external storage and a checkpointed entity/revision inventory are needed for a sustainable job. The inspected 2026-10 XML history jobs are skipped; current XML files total 179,591,010,509 bytes. A Q673202 API probe enumerated 192 revision IDs but did not fetch all revision contents. This is capability evidence, not global coverage. No worldwide regulator/operator/airline archive was scanned (zero global notice records/versions); existing claim-specific evidence remains preserved.

## Current global baseline and Keepraw-Fly comparison

OurAirports is pinned to `d97df1673cc5ba61a09b17ab5936091a669a04ca`, whose last relevant commit is 2026-10-26. Retrieval/assessment date is 2026-10-27. The public-domain terms are linked and hashed in the assessment; other source pins/licenses are in `sources.json` and retained license notices. The original curated dataset retains its earlier evidence horizon unchanged.

| OurAirports facility type | Records |
| --- | ---: |
| balloonport | 63 |
| closed | 13,585 |
| heliport | 23,260 |
| large_airport | 1,175 |
| medium_airport | 4,105 |
| seaplane_base | 1,273 |
| small_airport | 42,825 |

Total: **86,286** external airport/facility records; **9,052** nonempty IATA fields; **10,616** explicit ICAO fields (all satisfy four-letter syntax; not an independently verified allocation ledger); **44,500** GPS-code fields. **74,438** lack both explicit IATA and ICAO; **41,206** also lack GPS codes. **4,337** are marked scheduled-service.

The baseline has **13,585** closed records. Another **664** ever-observed source identities are absent at the target. These are historical-record leads, not validated physical airports or dates of closure. Closed/deleted identities and their observed codes remain in the research inventory. Codeless facilities remain in scope for flight-record research; the current IATA/ICAO resolver cannot yet resolve local-ID/code-free input.

Keepraw-Fly main `0407d77de1a7260256c0209a8f743e5e6a6d68f9` uses airportsdata revision `d306f66b5c33617e0bc13d413fea07292a5d9211` (2026-09-02), producing **7,884** IATA-keyed rows and 40 city groups. Its updater requires a valid IATA-shaped string, finite coordinates and timezone, deduplicates by IATA, omits ICAO/history/status intervals and keeps city groups separate. Airportsdata's ICAO field includes pseudo identifiers. No Keepraw-Fly file was changed.

Comparison with the pinned OurAirports target: **7,696** shared IATA strings; **1,356** only in OurAirports; **188** only in Keepraw-Fly; **2,433** shared-code label differences, **25** country differences and **193** shared-code coordinate differences of at least 5 km. These snapshots have different scopes/dates. Differences may be corrections, naming preferences or pseudo/retired codes, not historical events. Full code lists and comparison rows are shipped.

## Candidate totals and deduplication

The actual scans produced **1,608,335** entity-change observations, grouped into **1,240,058** stable source-transition leads. Repeated identical transitions retain separate source observations/episodes. Exact cross-source grouping found **155,533** groups with **403,103** members, removing **247,570** duplicate lead representations: **992,488** source-transition groups remain under this conservative rule. This is not a count of unique real events.

There are additionally **2,484** within-source multi-entity code-association leads (2,012 IATA; 472 ICAO/possibly pseudo) and **18** preserved manual leads. These collections can overlap the transition groups. Shared codes alone are indexed for research, never merged as proven events.

### Source-transition types (multi-label)

| Observed/candidate type | Leads |
| --- | ---: |
| baseline_closed_record | 13,752 |
| city_label_change | 29,064 |
| coordinate_revision | 323,416 |
| facility_type_change | 5,583 |
| gps_code_change | 28,210 |
| iata_change | 7,904 |
| icao_change | 284,472 |
| identifier_change | 13,290 |
| possible_closure | 13,665 |
| possible_relocation | 2,006 |
| possible_rename | 38,105 |
| possible_reopening | 932 |
| record_added | 174,433 |
| record_removed | 170,847 |
| record_revision | 230,210 |

ICAO changes include column introduction, missing/empty field transitions and corrections. Record additions/removals include schema/filter/path migrations and historical backfills. These large totals must not be presented as mass allocations, openings or closures. A name edit is not proof of formal renaming; a coordinate shift is not proof of physical relocation. All machine evidence remains pending/indirect.

### Source-transition observation years

Event year is unknown for unverified machine leads. These are first observing repository revision years, not effective event years. A zero candidate count is not evidence of no real-world events.

| Observation year | Leads |
| --- | ---: |
| 2014 | 28,803 |
| 2015 | 144,581 |
| 2016 | 0 |
| 2017 | 144,814 |
| 2018 | 34,680 |
| 2019 | 115,481 |
| 2020 | 3,300 |
| 2021 | 40,083 |
| 2022 | 51,296 |
| 2023 | 54,634 |
| 2024 | 127,306 |
| 2025 | 445,005 |
| 2026 | 50,075 |

The complete source/year/country presence matrix is `year-country-coverage.json`: each row identifies the latest available parsed revision in that year and all country row counts. It is a representative denominator only; intervening revisions were scanned for changes. Missing years and unreadable revisions are not claimed as scanned coverage.

### Source-transition countries/regions

All countries/territories and explicit unknown values are listed below. Labels are source codes, not a geopolitical classification. Source-specific continent counts and year/country candidate matrices are in the coverage JSON files.

| Country/territory code | Leads |
| --- | ---: |
| AD | 55 |
| AE | 2,589 |
| AF | 1,430 |
| AG | 99 |
| AI | 36 |
| AL | 363 |
| AM | 272 |
| AO | 1,736 |
| AQ | 732 |
| AR | 13,041 |
| AS | 95 |
| AT | 3,555 |
| AU | 46,364 |
| AW | 52 |
| AZ | 719 |
| BA | 438 |
| BB | 42 |
| BD | 844 |
| BE | 3,488 |
| BF | 1,080 |
| BG | 3,245 |
| BH | 195 |
| BI | 113 |
| BJ | 194 |
| BL | 28 |
| BM | 72 |
| BN | 153 |
| BO | 4,033 |
| BQ | 86 |
| BR | 117,293 |
| BS | 1,555 |
| BT | 140 |
| BW | 1,757 |
| BY | 980 |
| BZ | 531 |
| CA | 54,030 |
| CC | 24 |
| CD | 6,986 |
| CF | 868 |
| CG | 1,031 |
| CH | 2,252 |
| CI | 623 |
| CK | 217 |
| CL | 9,915 |
| CM | 679 |
| CN | 11,138 |
| CO | 10,285 |
| CR | 2,624 |
| CU | 2,670 |
| CV | 223 |
| CW | 20 |
| CX | 27 |
| CY | 860 |
| CZ | 6,070 |
| DE | 21,728 |
| DJ | 252 |
| DK | 2,395 |
| DM | 48 |
| DO | 920 |
| DZ | 1,780 |
| EC | 3,991 |
| EE | 919 |
| EG | 2,142 |
| EH | 308 |
| ER | 199 |
| ES | 7,913 |
| ET | 1,224 |
| FI | 2,433 |
| FJ | 647 |
| FK | 418 |
| FM | 138 |
| FO | 195 |
| FR | 25,301 |
| GA | 809 |
| GB | 20,830 |
| GD | 71 |
| GE | 609 |
| GF | 304 |
| GG | 70 |
| GH | 253 |
| GI | 29 |
| GL | 1,716 |
| GM | 26 |
| GN | 330 |
| GP | 164 |
| GQ | 122 |
| GR | 2,731 |
| GS | 7 |
| GT | 1,073 |
| GU | 114 |
| GW | 142 |
| GY | 943 |
| HK | 1,298 |
| HM | 16 |
| HN | 3,093 |
| HR | 1,287 |
| HT | 272 |
| HU | 2,275 |
| ID | 11,749 |
| IE | 1,854 |
| IL | 883 |
| IM | 92 |
| IN | 9,217 |
| IO | 23 |
| IQ | 1,402 |
| IR | 4,584 |
| IS | 1,948 |
| IT | 12,409 |
| JE | 25 |
| JM | 394 |
| JO | 351 |
| JP | 29,307 |
| KE | 7,110 |
| KG | 1,075 |
| KH | 419 |
| KI | 474 |
| KM | 100 |
| KN | 51 |
| KP | 1,216 |
| KR | 14,756 |
| KS | 27 |
| KW | 358 |
| KY | 127 |
| KZ | 2,828 |
| LA | 444 |
| LB | 339 |
| LC | 39 |
| LI | 25 |
| LK | 553 |
| LR | 337 |
| LS | 720 |
| LT | 1,250 |
| LU | 226 |
| LV | 1,290 |
| LY | 1,393 |
| MA | 1,065 |
| MC | 41 |
| MD | 263 |
| ME | 174 |
| MF | 33 |
| MG | 1,634 |
| MH | 637 |
| MK | 408 |
| ML | 805 |
| MM | 1,593 |
| MN | 709 |
| MO | 55 |
| MP | 247 |
| MQ | 42 |
| MR | 563 |
| MS | 48 |
| MT | 154 |
| MU | 109 |
| MV | 426 |
| MW | 692 |
| MX | 25,777 |
| MY | 2,298 |
| MZ | 1,253 |
| NA | 3,999 |
| NC | 597 |
| NE | 560 |
| NF | 24 |
| NG | 1,049 |
| NI | 756 |
| NL | 3,108 |
| NO | 4,953 |
| NP | 1,272 |
| NR | 24 |
| NU | 25 |
| NZ | 4,616 |
| OM | 809 |
| PA | 1,557 |
| PE | 3,849 |
| PF | 1,182 |
| PG | 9,747 |
| PH | 8,697 |
| PK | 3,044 |
| PL | 5,952 |
| PM | 48 |
| PR | 1,071 |
| PS | 124 |
| PT | 3,191 |
| PW | 61 |
| PY | 1,966 |
| QA | 248 |
| RE | 120 |
| RO | 1,989 |
| RS | 903 |
| RU | 25,733 |
| RW | 169 |
| SA | 2,527 |
| SB | 784 |
| SC | 430 |
| SD | 905 |
| SE | 5,090 |
| SG | 191 |
| SH | 55 |
| SI | 798 |
| SK | 1,756 |
| SL | 245 |
| SM | 57 |
| SN | 387 |
| SO | 631 |
| SR | 832 |
| SS | 1,507 |
| ST | 77 |
| SV | 567 |
| SX | 29 |
| SY | 743 |
| SZ | 383 |
| TC | 186 |
| TD | 714 |
| TF | 84 |
| TG | 156 |
| TH | 1,948 |
| TJ | 287 |
| TL | 254 |
| TM | 635 |
| TN | 430 |
| TO | 131 |
| TR | 4,920 |
| TT | 76 |
| TV | 47 |
| TW | 1,528 |
| TZ | 2,511 |
| UA | 4,100 |
| UG | 631 |
| UM | 168 |
| US | 498,575 |
| UY | 834 |
| UZ | 3,367 |
| VA | 16 |
| VC | 135 |
| VE | 11,944 |
| VG | 102 |
| VI | 186 |
| VN | 1,825 |
| VU | 704 |
| WF | 44 |
| WS | 100 |
| XK | 205 |
| XP | 50 |
| YE | 769 |
| YT | 25 |
| ZA | 10,701 |
| ZM | 2,008 |
| ZW | 2,308 |
| ZZ | 14 |

### Review states

| State | Source transitions | Code-association leads | Preserved manual leads |
| --- | ---: | ---: | ---: |
| pending_investigation | 1,240,058 | 2,484 | 0 |
| insufficient_evidence | 0 | 0 | 9 |
| pending_review | 0 | 0 | 0 |
| ready_to_admit | 0 | 0 | 0 |
| already_curated | 0 | 0 | 6 |
| excluded | 0 | 0 | 3 |

The eight deferred PR #3 groups are retained. The ninth insufficient-evidence manual lead is earlier Astana official naming. Six manual groups describe facts already curated; three exclude corporate, city and terminal interpretations. No machine source edit is ready for formal admission.

## Potential omissions and next verification batches

The machine priority queue has **1,664** qualifying leads. Its first twenty are reproducible in `summary.json`; the complete queue is shipped. High scores do not verify facts: coordinate fixes, pseudo identifiers and schema changes can still surface.

Examples discovered from source revisions, rather than copied from the manual list:

| Lead | Actual observed revision | Admission question |
| --- | --- | --- |
| Lianyungang `cand_ee28c2f36941d4b62ff604b2` | Raw OurAirports derivative changes Baitabu Air Base coordinates/name to Huaguoshan and adds LYG in a 2024-10-01 snapshot | Is this a source identity conflation/backfill? Preserve separate physical sites and establish actual code timing; the snapshot is not the 2021 move date. |
| Rostov `cand_7fc9b08615e93efbdffdc2a8` | Old-site ROV → RVI and closed status observed in a 2019-06-13 snapshot | Reconcile the already recorded 2017-11-27 code report with the 2017-12-07 flight move. |
| Kratie/Techo KTI `cand_fd2a5e00b9b3f58536c0433e` | Kratie loses KTI and becomes closed in a 2024-10-01 raw snapshot | Investigate prior KTI allocation and subsequent Techo use independently of PNH flight relocation; do not assume KTI was a new unused code. |
| Jining `cand_e1f96c81b10b8a30ef076ffa` | Jining Qufu loses JNG in a 2024-09-23 source revision | Locate code-specific implementation evidence for the separate Da’an airfield; do not date the transfer to the edit or opening automatically. |
| Mopa `cand_4ec4f3ba9374292720d2d0a7` | GOX is removed from an under-construction record in 2022-11-09 source history | Review interim source corrections and allocation/implementation observations; annual endpoint comparison could hide reversals. |

These examples are research leads, not new facts. The formal thirteen-airport database cannot resolve these histories yet. Inspect code-link groups and duplicate-group members, obtain regulator/AIP/IATA/airline-system evidence, and review identity, IATA, ICAO, official name and closure independently. Resolve contradictions before assigning permanent IDs or intervals. Keep existing IDs/facts unchanged.

Prioritize (1) multi-entity IATA associations and coded coordinate shifts, beginning with the generated first batch; (2) the eight deferred groups and the new KTI prior-use conflict; (3) formal name decisions for high-use continuing sites, with city/operator/terminal edits excluded; (4) closed/codeless records associated with actual flight imports; (5) primary-source archive onboarding and Wikidata ingestion at suitable scale. Each admission batch needs an evidence review and regression cases, not an automatic promotion rule.

## Known gaps and defensible claims

- Selected Git history begins in 2014/2015/2020/2021 by source; earlier real airport/code/name history is not reconstructed merely because a record exists today.
- Derived snapshots before daily retention are sparse. Changes and reversals between exports, unpublished corrections, removed upstream entities and source omissions remain invisible.
- mwgg has 76 unreadable/ambiguous versions and 113 blocked comparisons. Exact gap commits/blobs/errors are shipped, and no event is inferred across them.
- Current names/coordinates/status are reference observations. None of the selected airport tables provides a complete official-name or allocation ledger, nor reliable opening/closure effective dates.
- Wikidata global history, deleted statements/entities, and worldwide official notices were not scanned. The documented API probe is not a substitute. Future ingestion needs pinned dumps, streaming/external storage, a complete entity inventory, revision-content checkpoints, and explicit missing-range accounting.
- Unmerged branch histories and database-internal edits are outside the selected main-ancestor scope. Other public archives may exist; no claim that these repositories exhaust all obtainable evidence is made.
- Coverage by country/year measures source presence and revisions processed, not the fraction of all real historical events found. Countries with many candidates can simply have more records or bulk corrections. No global completion percentage is calculated.

What is established: all selected file histories were enumerated at pinned versions; seven have complete parseable comparisons, mwgg has explicit gaps; machine leads, duplicates, review states and source coverage can be regenerated and incrementally extended. What is not established: completeness of global historical airport identities, allocation dates, official names or effective event timelines.
