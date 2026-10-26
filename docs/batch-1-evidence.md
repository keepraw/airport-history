# Batch 1 evidence review: 0.3.0

Reviewed 2026-10-26 against Schema 2.0.0. The
[candidate register](batch-1-candidates.md) was created before dataset admission.
Five events add **five physical identities, ten IATA assignments and thirteen
source records**. Totals: thirteen physical airports, twenty assignments
(eighteen IATA, two ICAO), twenty-six sources. The original eight physical
records, ten assignments and thirteen sources are unchanged. No parser, model,
schema or Keepraw-Fly changes are needed.

`verified` means the stated conclusion and its limitations were reviewed. It
does not mean IATA certification, primary allocation evidence or exact temporal
precision. All ten added intervals are `continuity_inference`: the whole
continuous interval depends on continuity between observations. A primary source
at a boundary does not upgrade that whole interval to `primary_direct`.
Secondary code evidence remains secondary even when a government publishes it.

## Admitted events and query behavior

| Event | Historical change | Supported code boundary | Evidence assessment and limits |
| --- | --- | --- | --- |
| ISL, 2019 | Istanbul Airport → Atatürk; inverse of existing IST exchange | 2019-04-06, `day` | First-party participant explicitly reports the exchange at 02:59. The date-only API cannot attribute the whole day to one site. New-airport ISL first allocation remains unknown. |
| ISB, 2018 | Benazir Bhutto/Chaklala → geographically separate new Islamabad | May 2018, `month`: 2018-05-01 through 2018-06-01 | Explicit secondary evidence says the code transferred in May. Government and tourism reporting establish the separate site and May 3 flight move, but do not establish an IATA transfer day. Every May date stays uncertain. |
| SXF → BER, 2020 | Code change at the continuing, expanded Schönefeld airfield | 2020-10-25, `day` | Airport-authored implementation account and slot coordinator explicitly identify the change. One physical identity, despite terminal changes and two upstream reference rows. BER city-code usage before this is excluded. |
| TSE → NQZ, 2020 | Code change at the same Astana airport | 2020-06-08, `day` | Civil aviation administration explicitly separates the April 6 decision from June 8 application. No exact local-midnight instant is proved. |
| KIV → RMO, 2024 | Code change at the same Chișinău airport | 2024-01-18, `day` | Contemporaneous secondary announcement and implementation reports agree. The original IATA notice is not held; no midnight instant or global survey of later KIV reuse is claimed. |

For day boundaries, `earliest` is the named date and `latest` the following
midnight. Old-code and new-code queries on that date are `uncertain`; the
following date resolves only the new assignment. Retired SXF, TSE and KIV return
`not_found` after their respective boundary days, without current-code fallback.
This describes these curated assignments, not an exhaustive global allocation
ledger. For ISL and ISB, boundary queries preserve both physical candidates.

The checked continuing-code horizon is unchanged at **2026-10-25**. Queries on
or after that date are uncertain; whole-date coverage is certain only before it.

## Istanbul: ISL exchange, existing physical IDs

[Ercan's operator, 2018-10-31](https://www.ercanhavalimani.aero/en/news/kktc-iin-nemli-gn)
identifies TK978 from the newly built Istanbul Airport as ISL–ECN. It is a
first-party record of the receiving airport's own flight. The unknown first ISL
assignment at Istanbul therefore has latest-start bound **2018-11-01**; the
airport's October inauguration is not an allocation date.

The already-registered
[Turkish Airlines participant retrospective](https://blog.turkishairlines.com/en/mega-move-the-story-of-turkish-airlines-great-migration/)
explicitly describes both directions of the April 6, 2019 IST/ISL exchange.
The existing Istanbul and Atatürk permanent IDs and reference positions are
reused, without editing their existing IST intervals. The original
[OurAirports snapshot](https://raw.githubusercontent.com/davidmegginson/ourairports-data/d97df1673cc5ba61a09b17ab5936091a669a04ca/airports.csv)
records ISL at Atatürk and IST at the new airport. Those observations support
inferred continuation, not a claim that passenger service still uses Atatürk.
Other historical uses of ISL, including outside Türkiye, are not researched or
asserted by these intervals; dates before the first observation remain uncertain.

## Islamabad: code month and operating day are distinct

[PIA's 2016-05-06 safety circular, page 1](https://crewserver1.piac.com.pk/Documents/Circular/FLT_OPS_-_SAFETY_-_3_-_Fri_May_06_2016_356.pdf)
explicitly identifies its then-operating Islamabad airport as ISB. It supplies
the latest-start bound **2016-05-07**, not the code's original allocation date.
The [government's 2018-04-18 release](https://pid.gov.pk/site/press_detail/8275)
describes a separate greenfield airport and plans for May 3 operation. This is
primary evidence of the site and plan, not completed operation or IATA allocation.
[TAT Newsroom's May 4 account](https://www.tatnews.org/2018/05/thai-shifts-to-serve-pakistans-newly-opened-islamabad-international-airport/)
reports THAI using the new airport from May 3. TAT is reporting another
operator's activity, so this source is classified `secondary`.

[Helis's OPRN history](https://www.helis.com/database/gps/OPRN/)
explicitly reports transfer of ISB with international scheduled services in
**May 2018**, while also saying the old airfield remains open. It does not give
a code-transfer day. Consequently both ISB boundaries use the conservative
**month** bounds `[2018-05-01, 2018-06-01]`. The inauguration, first landing,
flight move and code transfer are not collapsed into one exact event. An
allocation notice could refine this month; May 3 must remain uncertain today.

The old physical identity survives civil-service cessation. Its current
OurAirports row 5274 is labelled PAF Base Nur Khan (Benazir Bhutto International
Airport) with no IATA code. The new airport is row 333692, approximately 26 km
away. OPRN and OPIS are distinct ICAO codes; no ICAO interval or inheritance is
invented. The present airport's
[official introduction](https://islamabadairport.com.pk/About/About-Introduction.aspx)
still gives an April 20 inauguration/regular-operation statement, while
contemporaneous notices place the flight move in May. That retrospective
inconsistency is not used to choose or sharpen an ISB boundary and the page is
not admitted as verified allocation evidence.

## Berlin: code change, continuing airfield, city code excluded

[Fluko's W20/S21 coordination notice, page 1](https://fluko.org/wp-content/uploads/2020/05/BER-Information-on-Airport-Slot-Coordination-W20-S21-20200506.pdf)
explicitly describes BER as an extension of SXF airside infrastructure and says
SXF is renamed BER on October 25. Its document date is **2020-04-30** on page 5;
the filename's May 6 is not used as the observation date. Existing SXF is thus
bounded by **2020-05-01**, with original allocation unknown.
The [airport's own implementation announcement on its Routes profile](https://www.routesonline.com/airports/2515/berlin-brandenburg-airport/news/294598/sxf-becomes-ber-schonefeld-airport-is-now-ber-terminal-5/)
confirms the October 25 change and continued use of the Schönefeld facilities
as T5. Its October 27 posting date is not the effective date. These are `primary`
publications for their own coordination and airport operations.

One new permanent identity represents the continuing, expanded physical airfield.
The current OurAirports snapshot separates a former Schönefeld terminal-area row
2209 (52.380001, 13.5225) and Brandenburg row 301881 (52.361738, 13.502341).
That upstream record split is not evidence of a physically separate replacement
airfield: the first-party infrastructure account supports continuity. The latter
row is the single external reference retained here. Its coordinates are a
**current airfield reference position**, not a claim about an SXF terminal or
historical aerodrome reference point. No second airportId is created for T1/T5.

The airport code starts with the October 25 change, before T1 opened October 31.
Earlier metropolitan BER search usage does not create an airport assignment.
TXL is not transferred to this identity or imported as a fictitious predecessor
code. The code change remains day precision, without an asserted midnight instant.

## Astana: TSE → NQZ without relocation

[Aviation Administration of Kazakhstan, 2020-04-06](https://caa.gov.kz/ru/blog/post/kod-aeroporta-g-nur-sultan-izmenen)
explicitly identifies existing TSE, the April 6 IATA decision and application
from **2020-06-08**. Existing TSE has unknown original allocation, with
latest-start bound **2020-04-07**. Its
[June 7 implementation notice](https://caa.gov.kz/ru/blog/post/nqz-novoe-imya-na-karte-poletov)
repeats the effective code date. These are primary administration publications,
although the underlying IATA notice is not redistributed. Both codes belong to
one physical identity, OurAirports row 6423. Airport/city renames and the 2019
policy process are not new physical sites or the effective code boundary.
June 8 is stored at day precision; an exact local instant is not established.

## Chișinău: KIV → RMO without relocation

[Radio Moldova's December 19, 2023 report](https://radiomoldova.md/p/27139/)
identifies existing KIV and announces the IATA code change from **2024-01-18**.
The old interval retains unknown original allocation and latest-start bound
**2023-12-20**. Its
[January 18 implementation report](https://www.radiomoldova.md/p/28718/attention-travelers-abbreviation-kiv-is-replaced-by-rmo-on-flight-charts-starting-today)
confirms use of RMO instead of KIV. Both are **secondary** code evidence, despite
the public broadcaster's ownership. The airport-channel
[January 18 post](https://t.me/s/chisinauairport/127) was also inspected as a
corroborative lead, but is not needed or registered as independently authenticated
primary allocation evidence.

Both codes reference one permanent identity, OurAirports row 4571. Day precision
preserves uncertainty for January 18. Tickets originally sold under KIV remaining
usable do not prove a second active code interval. Later KIV reuse has not been
established. The retained canonical reference name is not a historical name
assertion.

## Assignment bounds and evidence classification

| Assignment ID | Start | End | Whole-interval evidence |
| --- | --- | --- | --- |
| `iata-isl-istanbul` | Unknown first allocation; by 2018-11-01 | 2019-04-06, day | `continuity_inference`, primary observation and exchange |
| `iata-isl-ataturk` | 2019-04-06, day | Checked before 2026-10-25; actual end unknown | `continuity_inference`, primary exchange plus secondary current corroboration |
| `iata-isb-benazir-bhutto` | Unknown first allocation; by 2016-05-07 | May 2018, month | `continuity_inference`, primary observation plus explicit secondary transfer |
| `iata-isb-islamabad` | May 2018, month | Checked before 2026-10-25; actual end unknown | `continuity_inference`, secondary transfer plus site/operation evidence and snapshot |
| `iata-sxf-schonefeld-brandenburg` | Unknown first allocation; by 2020-05-01 | 2020-10-25, day | `continuity_inference`, primary coordination and change records |
| `iata-ber-schonefeld-brandenburg` | 2020-10-25, day | Checked before 2026-10-25; actual end unknown | `continuity_inference`, primary change and secondary current corroboration |
| `iata-tse-astana` | Unknown first allocation; by 2020-04-07 | 2020-06-08, day | `continuity_inference`, primary administration notices |
| `iata-nqz-astana` | 2020-06-08, day | Checked before 2026-10-25; actual end unknown | `continuity_inference`, primary change and secondary current corroboration |
| `iata-kiv-chisinau` | Unknown first allocation; by 2023-12-20 | 2024-01-18, day | `continuity_inference`, secondary observation and change reports |
| `iata-rmo-chisinau` | 2024-01-18, day | Checked before 2026-10-25; actual end unknown | `continuity_inference`, secondary implementation and current corroboration |

All added sources have review status `verified` for the **limited claims actually
described** in their notes. No inaccessible search-only result is admitted as
reviewed evidence. None of these records is classified `primary_direct` because
the entire interval relies on inferred continuity. `indirect` likewise would
underdescribe that continuity basis, even for the secondary-only Chișinău case.

## Reference data, licenses and verification

Five rows of the fixed
[OurAirports commit d97df167](https://github.com/davidmegginson/ourairports-data/commit/d97df1673cc5ba61a09b17ab5936091a669a04ca)
were individually inspected, including the former civilian Islamabad field.
[OurAirports' data terms](https://ourairports.com/data/) release the data to the
public domain. Names and WGS84 coordinates remain `reference`, not verified
historical names or surveyed positions. No current directory lookup is performed
by the resolver and a blank current IATA does not remove a physical identity.
The source record for the five new rows is separate from the unchanged bootstrap
eight-row record, despite sharing the same snapshot URL.

Four new geographical timezone mappings use IANA
[2025b zone1970.tab](https://data.iana.org/time-zones/tzdb-2025b/zone1970.tab),
with its [public-domain license](https://data.iana.org/time-zones/tzdb-2025b/LICENSE)
inspected. Astana maps to `Asia/Almaty`; this is not a fixed offset. Neither
timezone rules nor airport-code validity are inferred from the zone's reference
coordinate. No new Wikidata content is imported in this batch.

All eleven other new sources are reference-only publications: no open
redistribution grant was established, including for the government sites. Each
is `LicenseRef-Reference-Only`, with publisher rights retained. Only URLs and
original factual notes are shipped, never article prose, PDFs, photographs or
tables. The PIA and Fluko PDFs were directly inspected. MIT applies to code,
tests and documentation; CC0 applies only to project-owned dataset contributions.

Regression tests cover each event before and after the change, boundary-day or
month uncertainty, retired/reassigned codes, permanent identity and coordinates.
They also check the ISL/IST inverse exchange, absence of pre-change BER airport
resolution, the fixed evidence horizon and lack of invented OPRN/OPIS intervals.
The original eight-ID fixture is unchanged; the new fixture freezes five new IDs.
Build tests export Schema 2.0.0 and data/package 0.3.0 twice in different process
timezones, compare every byte and independently verify every SHA-256 digest.

## Deferred candidates and unresolved research

- **Yantai YNT:** flight relocation at 2015-05-28 midnight is well supported by
  the operator and airline, and a 2014 report explicitly says YNT was approved
  for retention. However, that same report describes a planned IATA coordinate
  update on 2014-12-11, before the eventual operating move. Actual code/location
  implementation or a revised notice is needed. No exact May 28 code boundary
  is silently chosen from the opening date.
- **Rostov ROV/RVI:** a November 27 report describes completed code transfer;
  an earlier account predicts it with the later move, while the operator dates
  the flight move to December 7. Need an allocation or airline-system record
  to settle code timing separately. Neither date is selected for the dataset.
- **Lianyungang, Yibin, Luzhou and Jining:** good opening/flight-move leads,
  but no independently established code-transfer boundary was collected for
  admission. No allocations are manufactured from those openings.
- **Dakar DKR/DSS and Phnom Penh PNH/KTI:** distinct-code replacements. No code
  inheritance is claimed, and flight relocation alone does not prove allocation
  or withdrawal dates. Need code-specific notices and dated observations.

No architectural decision is required for this batch. Primary allocation notices
for ISB and KIV/RMO and broader historical observations remain research gaps.
Any future policy for cross-timezone reuse or instant-level resolution should
be reviewed separately; this batch does not change those semantics.
