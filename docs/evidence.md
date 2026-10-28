# Evidence review: bootstrap and provenance update (0.2.0)

Version 0.3.0 adds five events, five physical identities, ten assignments and
thirteen sources. See the [batch-1 evidence review](batch-1-evidence.md) and
[candidate register](batch-1-candidates.md). The bootstrap records and their
classification below are unchanged; statements about ten intervals or eight
reference rows in this document refer to that original scope.

Reviewed 2026-10-26. This is a deliberately small factual compilation. Source
verification means the cited content was checked; it is not a claim of official
certification. The intervals combine dated code observations, documented changes
and later corroboration. Continuity between those observations is a documented
curation inference. An allocation ledger could refine or contradict it.

## Assignment classification

Later admission reviews preserve these original findings. The five 0.6.0
intervals are also reviewed `continuity_inference`, including DSS, whose first
allocation observation is direct IATA evidence but whose whole interval still
depends on continuity. See [the claim-by-claim 0.6.0 review](curated-admissions-pr9.md).

Schema 2 separates `Source.sourceType` (publication nature) from
`CodeAssignment.evidenceType` (the basis for the whole historical interval).
`primary_direct` requires a first-hand record explicitly supporting the code
assignment; `indirect` denotes secondary or indirect support. If the interval
depends on continuity inferred between observations, `continuity_inference`
takes precedence. Review status and boundary precision remain independent.

All ten bootstrap intervals already relied on that continuity inference. This
update makes it structured without upgrading their evidence or changing their
sources, review dates or time bounds. No new historical source has been added.

| Assignment | Physical airport | Evidence type | Retained limitation |
| --- | --- | --- | --- |
| `iata-tao-liuting` | Liuting | `continuity_inference` | Earlier airline observation to reported transfer; original assignment start unknown |
| `iata-tao-jiaodong` | Jiaodong | `continuity_inference` | Reported approval plus actual opening establishes the boundary; continuity to current snapshot is inferred |
| `iata-ist-ataturk` | Atatürk | `continuity_inference` | Airline schedule observation to retrospective exchange; original start unknown |
| `iata-ist-istanbul` | Istanbul | `continuity_inference` | Airline exchange report to current snapshot; exchange day remains uncertain |
| `iata-hkg-kai-tak` | Kai Tak | `continuity_inference` | Accident record and secondary code end-time; official closure history does not allocate HKG |
| `iata-hkg-chek-lap-kok` | Chek Lap Kok | `continuity_inference` | Secondary predecessor end-time, opening history and current code; code-switch instant unproven |
| `iata-den-stapleton` | Stapleton | `continuity_inference` | Historical traffic table and secondary end-time; original start and exact switch unknown |
| `iata-den-denver` | Denver International | `continuity_inference` | GAO opening history, secondary predecessor end-time and current code; opening alone does not prove allocation |
| `icao-vhhh-kai-tak` | Kai Tak | `continuity_inference` | Earlier HKG/VHHH observation to secondary VHHH end-time; no primary allocation notice |
| `icao-vhhh-chek-lap-kok` | Chek Lap Kok | `continuity_inference` | Opening, secondary predecessor VHHH end-time and current VHHH; continuity remains inferred |

## Publication classification

`primary` means first-party publication or original institutional record for its
own subject, not that every conclusion drawn from it is direct or official code
allocation evidence. `secondary` includes reporting and compiled structured data.

| Source ID | Source type | What the source actually contributes |
| --- | --- | --- |
| `ourairports-20261025` | `secondary` | Compiled current reference attributes and successor code observations |
| `tzdb-2025b` | `primary` | IANA's own geographical timezone mapping; no allocation evidence |
| `tao-transfer` | `secondary` | News report of simultaneous opening/closure, not an allocation notice |
| `tao-code` | `secondary` | News report of IATA approval; the original IATA notice is not held |
| `tao-earlier` | `primary` | Airline's own TAO procedures and dated earlier use; not first allocation |
| `ist-transfer` | `primary` | Participant airline's retrospective of its move and IST/ISL exchange |
| `ist-earlier` | `primary` | Airline's own announcement distributed by Golin/PRWeb, including IST schedule |
| `hkg-transfer` | `primary` | Government civil aviation history of closure/opening, indirect for code transfer |
| `hkg-code` | `secondary` | Wikidata's compiled HKG/VHHH end-time statements |
| `hkg-earlier` | `secondary` | Specialist accident compilation citing an investigation, not the original report |
| `den-transfer` | `primary` | Original GAO audit report confirming opening, indirect for code transfer |
| `den-code` | `secondary` | Wikidata's compiled DEN end-time statement |
| `den-earlier` | `secondary` | Research table compiling historical FAA traffic figures and airport codes |

These classifications retain all source URLs, access dates, license scopes and
notes. Publication type alone cannot establish `primary_direct`. In particular,
the government HKG and DEN histories are not primary code-allocation records.

## Qingdao: TAO

[Xinhua, 2021-08-12](https://www.xinhuanet.com/2021-08/12/c_1127752897.htm)
reports simultaneous Jiaodong opening and Liuting closure at local midnight.
[Qingdao News, 2019-03-22](https://news.qingdaonews.com/qingdao/2019-03/22/content_20304508.htm)
reports IATA approval to carry TAO over from the announced opening midnight.
The approval date is not the transfer date. Together these establish an exact
civil-day boundary on 2021-08-12.

[ANA Cargo](https://www.anacargo.jp/en/news/210430_E.html) explicitly dates an
earlier TAO cargo procedure to 2016-08-16. The old assignment was in use by then;
the conservative latest-start bound is the following midnight, 2016-08-17.
The true original assignment start remains unknown, including earlier history.

## Istanbul: IST

[Turkish Airlines' retrospective](https://blog.turkishairlines.com/en/mega-move-the-story-of-turkish-airlines-great-migration/)
explicitly describes the IST/ISL exchange on 2019-04-06 at 02:59. It also says
the new airport had its first flight in October 2018: airport opening and IST
assignment are distinct. The bootstrap stores the exchange at day precision;
a date-only query on April 6 returns both candidates and `uncertain`.

The [2015 airline announcement distributed through Golin/PRWeb](https://www.prweb.com/releases/turkish_airlines_united_states_expansion_continues_with_the_launch_of_nonstop_service_from_atlanta_to_istanbul_in_2016/prweb12812248.htm)
identifies the existing Atatürk hub and uses IST in the announced schedule.
Its publication date bounds the old code's unknown first assignment; the proposed
2016 Atlanta service start is not used as a code boundary.

The 2019 [EUROCONTROL bulletin](https://www.eurocontrol.int/archive_download/all/node/10969)
was also consulted as corroboration. It has noncommercial reproduction terms,
so no bulletin content or tables are included in the dataset or artifact.

## Hong Kong: HKG / VHHH

The [Hong Kong Yearbook 1998](https://www.yearbook.gov.hk/1998/ewww/14/1413/middle-middle.htm)
describes Kai Tak closure early on 1998-07-06 and Chek Lap Kok commercial service
a few hours later. [Wikidata Q673202](https://www.wikidata.org/wiki/Q673202)
explicitly records HKG and VHHH with end-time 1998-07-06. These structured
statements are secondary evidence, not primary code-allocation notices.

[Aviation Safety Network's 1993-11-04 record](https://aviation-safety.net/asndb/325140)
identifies the destination as Hong Kong-Kai Tak (HKG/VHHH). The legacy record URL
`https://aviation-safety.net/database/record.php?id=19931104-0` redirected to
that directly retrieved record. This supports a latest-start bound of
1993-11-05, while the original assignment dates remain unknown. Earlier BAAA
search results were found but their direct links returned 404; they are **not**
used in the shipped source registry.

We do not equate runway lights-off, first landing and code reassignment times.
Both code schemes remain uncertain for 1998-07-06. An AIP or IATA allocation
notice is the next useful primary source.

## Denver: DEN

The [US GAO retrospective](https://www.govinfo.gov/content/pkg/GAOREPORTS-AIMD-95-230/html/GAOREPORTS-AIMD-95-230.htm)
confirms the new airport opened on 1995-02-28.
[Wikidata Q1436575, inspected revision](https://www.wikidata.org/w/index.php?title=Q1436575&oldid=2473577165)
records the old DEN association ending that day. The exact code-switch instant
was not established, so that civil date is uncertain rather than an invented
midnight switch.

[Transportation Research Record 1218 (1989), Table 3](https://onlinepubs.trb.org/Onlinepubs/trr/1989/1218/1218-001.pdf)
explicitly maps DEN to Denver Stapleton in historical FAA traffic figures.
The downloaded PDF was text-extracted for inspection; it is not redistributed.
A conservative latest-start bound at the end of its publication year avoids
asserting that the IATA code existed at the airport's 1929 opening. IATA code
classification is corroborated by the structured Wikidata statement. Earlier
code allocation records and a primary transfer notice remain useful follow-up.

## Reference attributes and licenses

Only eight rows from [OurAirports commit d97df167](https://github.com/davidmegginson/ourairports-data/commit/d97df1673cc5ba61a09b17ab5936091a669a04ca)
are used; physical-site rows were inspected individually, including closed sites.
OurAirports' [public-domain declaration](https://ourairports.com/data/) was read.
Current codes are corroboration for documented continuing assignments and never
constitute a historical fallback. The checked snapshot horizon is 2026-10-25;
future validity is not guaranteed.

Names are canonical display labels; coordinates are WGS84 site reference
positions. Neither is asserted to be the exact name or aerodrome reference point
in every historical year. Both are tagged `reference`.
Four timezone identifiers are geographical mappings from IANA
[tzdb 2025b zone1970.tab](https://data.iana.org/time-zones/tzdb-2025b/zone1970.tab),
whose [license](https://data.iana.org/time-zones/tzdb-2025b/LICENSE) places that file
in the public domain. These are also tagged `reference`; no fixed historical
offsets are supplied.

Wikidata's main-namespace structured facts are [CC0](https://www.wikidata.org/wiki/Wikidata:Licensing).
Other consulted articles and reports are factual references, with publisher rights
retained. The repository does not redistribute their text, photographs or tables.
Unknown redistribution terms are explicitly `LicenseRef-Reference-Only`.
