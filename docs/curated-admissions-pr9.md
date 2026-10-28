# 0.6.0 admission review: bounded Dakar and Samarinda history

Reviewed 2026-10-28. GitHub API and `git ls-remote` confirmed PR #8 merged and
`main` at `7a9432994cd56058e9c436a3cbd82685f43c716a` before branching.
The machine queue and global-1/2/3 admission gaps were screened first. Only
targeted documents and two specific pinned source files were retrieved; no
discovery scan, source-history clone, Wikidata dump or Keepraw-Fly change.
The claim-specific audit is [global-4](../research/discovery/batches/global-4.json).

| Formal dataset | Airports | Code assignments | Official names | Sources | Version |
| --- | ---: | ---: | ---: | ---: | --- |
| Before | 19 | 29 | 2 | 43 | 0.5.0 |
| After | 23 | 34 | 3 | 56 | 0.6.0 |

Schema **3.0.0**, resolver code and every earlier permanent ID remain unchanged.
One of the four new identities, Temindung, is an identity-only predecessor.

## Screening and stopping decisions

The ten-entry internal shortlist, including separate identity, evidence,
before/after code observations, boundary fit, benefit and risks, is retained in
`global-4.json#screening`. Four groups received bounded full investigation.

| Candidate | Screening conclusion | Full investigation |
| --- | --- | --- |
| Lianyungang LYG | Separate sites and primary airline transfer; likely useful same-code history, missing independent code bounds | Yes; deferred |
| Luzhou LZO | Separate sites, but an approximately twelve-month service gap prevents a simple transfer inference; old code end and new allocation missing | No |
| Yibin YBP | Separate sites; existing opening reports distinguish civil/military use but provide no code boundary | No |
| Jining JNG | Separate sites, recent primary airline move and obtainable old observations; strong prospective benefit, new code bound missing | Yes; deferred |
| Samarinda SRI/AAP | Separate sites; authority-linked operator, dated actual operations and original naming decision obtainable | Yes; partial admission |
| Dakar replacement | Separate sites, existing SAA evidence; independent IATA, BEA and AIP records obtainable | Yes; partial admission |
| Gilgal GGL | Queue coordinate/closure change; physical relocation unproved and no dated primary code source identified | No |
| Ferkessédougou FEK | Same identity/date problems; high machine rank does not establish a move | No |
| Asaloyeh AOY/YEH | Potential code replacement but old/new identity and chronology unresolved | No |
| Gamba GAX | Coordinate shift may be a correction; no independent physical relocation evidence | No |

The last four remain carried-forward leads owned by no new event group in this
PR. Their original global-2 `nextBatch` references are unchanged. Completed
ROV/RVI, YNT and PNH/KTI investigations were not repeated.

## Dakar: Yoff and Diass

**Physical identity.** The already-reviewed
[SAA release](https://aviator.aero/press/south-african-airways-advises-of-dakar-airport-change)
distinguishes Léopold Sédar Senghor at Yoff from Blaise Diagne at Diass.
Separate [GOOY](https://aim.asecna.aero/html/eAIP/FR-_13AD-2.GOOY-fr-FR.html)
and [GOBD](https://aim.asecna.aero/html/eAIP/FR-_13AD-2.GOBD-fr-FR.html) AIP
entries corroborate both sites. OurAirports rows 3125/325736 supply reference
attributes; IDs are frozen in [pr9-identities.json](../test/pr9-identities.json).

**Code observations and bounds.**

| Admitted assignment | Start bound | End bound | Specific support |
| --- | --- | --- | --- |
| `iata-dkr-yoff` | Unknown original start, latest 2013-03-30 | Earliest 2017-12-07, latest unknown | Actual DKR flight in BEA/IRBA Table 2; IATA withdrawal notice and SAA old-airport observation; later directory retention prevents certifying the end |
| `iata-dss-diass` | Unknown original start, latest 2017-11-22 | Open, checked through 2026-10-24 | IATA explicitly confirms already allocated DSS on November 21; current fixed directory corroborates continuation |
| `icao-gooy-yoff` | Unknown original start, latest 2013-03-30 | Open, same horizon | Actual GOOY flight in BEA/IRBA; current official AIP retains GOOY at Yoff |
| `icao-gobd-diass` | Unknown original start, latest 2017-12-07 | Open, same horizon | Effective GOBD AIP chart state on December 7; current official AIP |

The [BEA report appendix](https://bea.aero/fileadmin/documents/docspa/2013/sx-s130329/pdf/sx-s130329_06.pdf)
contains the IRBA reconstruction of an actual 2013-03-29 arrival/departure at
Léopold Sédar Senghor, explicitly identifying DKR and GOOY (Table 2).
This bounds unknown starts to the following whole local date; it does not date
original allocations.

The [IATA Coding Administration notice dated 2017-11-21](https://www.hanjinsabre.com/CommonFiles/BoardUpLoadFiles/AirLineNews/58199/SpecialNotif_NOV_21_DKR%20%28002%29.pdf),
reproduced on Sabre's site, explicitly confirms DSS was already allocated to
Blaise Diagne. This supports the November 22 latest-start bound independently of
opening and future flight bookings. It establishes administrative allocation,
not flights operated before the airport opened. No DSS allocation date is invented.

The same notice announces DKR airport-code withdrawal on December 7. The fixed
current OurAirports snapshot still lists DKR at Yoff. This could be stale data,
a cancelled change or later reallocation; no retrieved ledger resolves it. The
reviewed old DKR interval therefore has no latest-end bound. Dates from December
7 remain uncertain. DKR is never assigned to Diass, and city-code changes in the
notice are not airport assignments in this schema.

[ASECNA SUP 100/A/17GO](https://fr.scribd.com/document/691144013/AIRAC-AIP-SUP-N-100-A-17GO-12-OCTOBER-2017)
is a publicly readable third-party reproduction of GOBD charts: page 1 specifies
2017-12-07 0000 UTC effectiveness. Dakar's civil date is UTC+0. The AIP state
bounds latest start; October 12 publication is not indicator allocation. The
original origin PDF was not retrieved, and this limitation is recorded.

Current GOOY AIP use continues under military administration. Passenger
relocation does not withdraw that ICAO indicator or close the physical airfield.
SAA's scheduled December 8 first arrival is not used as either code boundary.
No Dakar historical official-name interval is admitted.

## Samarinda: Temindung and Pranoto at Sungai Siring

**Physical identity.** The [operator history](https://www.aptpairport.id/profile),
linked from the [DGCA airport profile](https://hubud.dephub.go.id/bandara/45),
documents replacement of Temindung by the separate Sungai Siring airport.
The old-site closure (2018-05-23), new-site operation (May 24) and October 25
presidential inauguration are separate events, none automatically a code boundary.

OurAirports row 26763 was repurposed between sites. It is attached **only to
Pranoto**. Temindung receives a new permanent ID with no OurAirports cross-reference;
its label and reference coordinates come from the pinned pre-correction mwgg
WALS row. Those attributes retain MIT terms; the full notice is included in
`THIRD_PARTY_NOTICES.md` and therefore in exported artifacts. Stale SRI/WALS
fields do not become verified history.

**IATA AAP.** The contemporaneous
[2019-08-20 operational report](https://www.merdeka.com/peristiwa/empat-penerbangan-ke-samarinda-dialihkan-ke-balikpapan-akibat-cuaca-buruk.html)
explicitly identifies AAP at Pranoto and actual disruptions involving named
flights, quoting airport operations staff. Publication metadata and the text's
2019 NOTAM reference agree. `iata-aap-pranoto` has an unknown earliest start and
latest start **2019-08-21**, with continuity to the fixed horizon corroborated by
DGCA and OurAirports. This does not backdate AAP to opening, inauguration, route
announcements or booking availability. Earlier Andrau Airpark AAP history remains
unadmitted; earlier AAP queries are uncertain.

**Official name, independently admitted.** The authority's
[KP 676/2017 record](https://hubud.kemenhub.go.id/regulasi/cari/2389) links the
original four-page decree. Operative First clause names the new airport
`Bandar Udara Aji Pangeran Tumenggung Pranoto`; Third clause makes it effective
on determination, signed **2017-07-27**. Day precision leaves July 27 uncertain;
July 28 onward resolves the Indonesian (`id`) name through the evidence horizon.
The September 20 portal publication and six-month administrative deadline are
not name-effective dates. Continued DGCA usage supports the interval as
`continuity_inference`; neither the static International label nor translations
are additional official-name intervals. The name predates opening and has no
effect on code allocation.

**Stopped gaps.** SRI lacks reliable interval/withdrawal bounds in the collected
evidence. The 2010 accident-report lead and stale directory cannot bridge this
gap. WALS lacks a dated transfer amendment despite present-day authority use.
Neither code is admitted. Temindung's predecessor identity remains useful without
certifying those unproved assignments.

## Deferred code claims

Lianyungang and Jining retain their original global-1 identity/transfer evidence.
Targeted follow-ups did not retrieve independent implemented code changes or
sufficient dated before/after code observations. LYG/ZSLG and JNG/ZSJG stay out
of formal data. China United's 2021-12-02 move and China Southern's 2023-12-28
move are operational facts. Encyclopedia summaries, retained-code descriptions,
directory edits and future schedules do not turn them into exact code boundaries.
No guessed ZSDA or ZSJN is accepted. Each case stops here with a specific next
source: code-specific airline/GDS implementation circular or historical AIP amendment.

## Resolver usefulness and measured coverage

All five new code intervals are `verified` / `continuity_inference`, with
independent physical evidence, dated code observations and explicit bound notes.
They are not primary direct evidence of every intervening day.

| Query | Result |
| --- | --- |
| DKR, 2016-01-01 | `resolved`: Yoff |
| DKR, 2017-12-07 or 2024-01-01 | `uncertain`: no certified withdrawal/continuation |
| DSS, 2017-11-21 | `uncertain`: whole observation day |
| DSS, 2017-11-22 | `resolved`: Diass allocation explicitly confirmed by IATA |
| GOOY, 2024-01-01, ICAO | `resolved`: Yoff, despite passenger replacement |
| GOBD, 2017-10-12 / 2017-12-07, ICAO | `uncertain` on publication date / `resolved` on effective AIP date |
| AAP, 2018-05-24 or 2018-10-25 | `uncertain`: opening/inauguration not code observations |
| AAP, 2019-08-21 | `resolved`: Pranoto |
| SRI / WALS | `not_found`: code history not admitted |

[The measured fixture](../test/pr9-coverage.json) and regression test enumerate
the actual resolver over **[2013-03-29, 2026-10-25)** for these five code/scheme
pairs (24,790 distinct queries). All were `not_found` in 0.5.0.

| Code/scheme | Newly `resolved` | `uncertain`, excluded from certain coverage |
| --- | ---: | ---: |
| DKR/IATA | 1,713 | 3,245 |
| DSS/IATA | 3,259 | 1,699 |
| GOOY/ICAO | 4,957 | 1 |
| GOBD/ICAO | 3,244 | 1,714 |
| AAP/IATA | 2,622 | 2,336 |
| Total | **15,795** | **8,995** |

These are model-supported code/date queries, including reviewed continuity
between observations, not independently verified flights or worldwide coverage.
DSS includes **15 pre-opening allocation days** (November 22–December 6), supported
by explicit IATA confirmation; they are not reported as operated-flight coverage.
No uncertainty, booking date or inferred exact allocation adds to the resolved total.
All codes become uncertain at or beyond the fixed 2026-10-25 evidence horizon.

## Preservation, audit and validation

The current 0.5.0 bytes are frozen in `test/curated-0.5.0.json`, SHA-256
`43bb532977cc5df61e6f34b55cab86c7aad3518d5a33ec89745ceccd49d3b67e`.
Both 0.4.0 and 0.5.0 snapshots are pinned in `curated-baseline.json` and checked
by tests and `research:validate`; every airport, assignment, name and source must
survive unchanged. Tests also compare previous resolver results at all old code
boundaries and adjacent dates, including the KTI future-booking regression.

Global-4 carries four follow-ups and no new candidate mappings. Global-1 retains
original claims, sources, gaps and actions; Dakar/AAP status changes are appended
to disposition history. Global-2/3 bytes remain unchanged. Cross-batch tests
check unique mappings, missing follow-up rejection, admission IDs and source links.

`pnpm research:report --reuse-baselines` regenerates the existing deterministic
reports offline. Only `legacy-links.jsonl.gz`, `summary.json` and `manifest.json`
change; source observations, candidate shards and queue stay fixed. The build
checks version/schema, evidence references, licenses and reproducible hashes.
`pnpm check` passed with Node 24 and pnpm 10.14.0: 321 Vitest tests, 50 Python
tests, validation of 1,240,058 source candidates and all four review batches,
and the deterministic 0.6.0 build. Final-head CI is reported in the PR.
