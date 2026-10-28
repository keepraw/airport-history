# 0.5.0 admission review: applying the curated standard to verified research

Reviewed 2026-10-27 on `main` @ `7c8e0b6623ccce51ee27d25df01631097b359afd`
(PR #7 merge, verified through the GitHub API). No discovery scan, upstream
airport-data fetch or Wikidata download was performed; only targeted public
documents were retrieved. The audit record is
[batches/global-3.json](../research/discovery/batches/global-3.json).

| Formal dataset | Airports | Assignments | Names | Sources | Version |
| --- | --- | --- | --- | --- | --- |
| Before (0.4.0) | 13 | 20 | 2 | 29 | 0.4.0 |
| After (0.5.0) | 19 | 29 | 2 | 43 | 0.5.0 |

Schema 3.0.0 is unchanged. All 0.4.0 records are preserved byte-for-byte as
JSON values (`test/curated-0.4.0.json`, SHA-256 equal to the old baseline
`17aa754e…1c6a`, enforced by `test/pr8-admissions.test.ts` and by
`pnpm research:validate` through `curated-baseline.json#preservedBaselines`).

## 1. Were PR #6 and PR #7 stricter than the curated dataset?

Yes. All twenty 0.4.0 intervals are `continuity_inference` built from:

- **dated code observations** that bound an unknown first allocation (ANA cargo
  TAO 2016, Golin/PRWeb IST 2015, ASN HKG 1993, TRB DEN 1989, Radio Moldova KIV);
- **reported approvals or airline/authority implementation reports** for the
  switch (Qingdao News TAO approval, Turkish Airlines IST/ISL retrospective,
  Kazakh CAA NQZ, Radio Moldova RMO, Helis ISB, airport-authored BER notice);
- **secondary compiled end times** (Wikidata HKG, DEN) and current snapshots.

None rests on an original IATA allocation notice. PR #6/#7 instead deferred
ROV, YNT and PNH/KTI because "no primary IATA implementation record" or an
unknown withdrawal existed. That is a higher bar than 0.4.0 used. This review
applies the 0.4.0 rule, without lowering it:

1. **Official implementation record** — desirable; none exists for any curated
   interval, old or new.
2. **Dated code-use observation** — admitted as a bound (latest start / earliest
   end), never as the allocation date.
3. **Reviewed continuity inference** — joins those bounds when a documented
   switch or transfer connects them.
4. **Genuine unknown** — stays open (`null`) or uncertain; no withdrawal or
   allocation date is invented.

## 2. Admissions

Every assignment is `verified` / `continuity_inference`, verified 2026-10-27.

### Rostov-on-Don / Platov (global-1-rov → ready_to_admit)

- **Physical identity — established.** Government order 2434-r (primary) opens
  "Rostov-on-Don (Platov)" and closes the separate "civil aerodrome
  Rostov-on-Don"; OurAirports rows 6518 and 326363 give reference positions
  about 27 km apart.
- **IATA — admitted.** flydubai's 2016-03-19 statement (primary) observes ROV
  at the old airport. Aeroflot's 2017-11-27 agency notice (primary, third-party
  reproduction, citing an attached IATA notice not retrieved) states that from
  27.11.2017 Platov holds ROV and the old airport temporary RVI. This is the
  NQZ/RMO standard: a dated day-level implementation report.
  - `iata-rov-rostov-on-don`: start ≤ 2016-03-20 (unknown earlier); end
    2017-11-27 (day).
  - `iata-rov-platov`: start 2017-11-27 (day); open to the 2026-10-25 horizon.
  - `iata-rvi-rostov-on-don`: start 2017-11-27 (day); end ≥ 2017-11-28, **no
    latest bound** — no RVI withdrawal record exists.
  - Not used as boundaries: passenger transfer 2017-12-07, legal closure
    2018-03-01, a fan-site "code received 2017-11-24" claim (treated as a
    notification date).
- **ICAO — not admitted.** URRR/URRP lack a retrieved AIP amendment or dated
  primary indicator record.
- **Official name — not admitted.** Order wording observed; no name interval.

### Yantai Laishan / Penglai (global-1-ynt → ready_to_admit)

- **Physical identity — established.** Spring Airlines (primary, 2015-05-13):
  separate airports 57 km apart by road; Laishan closes and Penglai opens at
  2015-05-28 00:00.
- **IATA — admitted with a wide uncertain window.** Dazhong (secondary,
  2014-11-10, quoting IATA Beijing): YNT is Laishan's current code and was
  approved for Penglai; IATA planned a coordinate prompt from 2014-12-11. The
  current AIP (third-party copy) shows ZSYT/YNT YANTAI/Penglai. This is the TAO
  pattern, but the approval was not tied to the opening instant, so:
  - `iata-ynt-laishan`: start ≤ 2014-11-11 (unknown earlier); end between
    2014-11-10 and 2015-05-28.
  - `iata-ynt-penglai`: start between 2014-11-10 and 2015-05-28; open.
  - Neither the planned 2014-12-11 date nor the 2015-05-28 opening is asserted
    as the switch.
- **ICAO — not admitted.** ZSYT at Laishan (2013 chart) and Penglai (2025 AIP)
  has no changeover record.

### Phnom Penh (Pochentong) / Techo / Kratie (global-1-pnh → ready_to_admit)

- **Physical identity — established for Pochentong and Techo** (Cambodia's ICAO
  paper and AIP AMDT 09/25; OurAirports 26475, 342098). Kratie is a third site
  and is **not admitted** (no dated observation; global-1-kti stays open).
- **IATA PNH — admitted.** Korea Airportal sheet (secondary, reference date
  2008-12-31) bounds the start (≤ 2009-01-01); Singapore Airlines and Vietnam
  Airlines move operations at 00:01 on 2025-09-09. End ≥ 2025-09-09, **no
  latest bound**: no PNH withdrawal or reuse decision was found.
- **ICAO VDPP — admitted.** ICAO FASID table dated 2014-04-25 bounds the start;
  Cambodia states the aerodrome closes 1700 UTC 2025-09-08. End ≥ 2025-09-08,
  no latest bound (closure is not indicator withdrawal).
- **IATA KTI at Techo — admitted.** Start: no earliest bound (allocation date
  unknown; KTI is reported as previously Kratie's), latest **2025-09-10**; open
  end. AeroRoutes' 2025-07-22 report shows schedules filed under KTI for travel
  from 2025-09-09: booking availability for future flights, not flights operated
  at Techo under KTI, so it is not a flight-date boundary (revised in review; an
  earlier draft used 2025-07-23). Vietnam Airlines moved operations at 00:01
  local on 2025-09-09 and Singapore Airlines from that date; under the
  resolver's whole-local-date rule the transfer day stays uncertain.
- **ICAO VDTI — admitted.** Latest start 2025-09-04, the AIP/ICAO-stated
  operating date; indicator issue date unknown; open end. The AIP effective date
  (2025-09-04), airline move (2025-09-09) and IATA allocation (unknown) remain
  three distinct facts.

### Not admitted in this PR

- **Qiemo / Yudu (IQM/ZWCM).** The two sites are established by primary CAAC and
  EIA documents, but every IQM/ZWCM observation found is either before 2012 or
  a current directory, so no dated bound exists at Yudu and a 2011–2016 service
  gap separates the sites. Admitting the identities alone would add no
  resolvable fact; they remain research-only. Next source: CAAC eAIP ZWCM
  amendment or a 2016–2017 airline/Travelsky notice citing IQM.
- **Kratie KTI, URRR/URRP, ZSYT, RVI withdrawal, PNH/VDPP withdrawal** — listed
  as remaining gaps in global-3.
- **Official names among curated airports.** İstanbul Airport: the name was
  announced at the 2018-10-29 ceremony (Turkish government communications,
  operator and Limak), but no dated decree or official naming record was found.
  Berlin Brandenburg "Willy Brandt": only an undated operator page. Neither is
  admitted; static labels are unchanged.

## 3. Resolver behaviour (tests in `test/pr8-admissions.test.ts`)

| Query | Before | After |
| --- | --- | --- |
| ROV 2016-06-01 / 2017-11-26 | not_found | old Rostov-on-Don |
| ROV 2017-11-27 | not_found | uncertain (both sites) |
| ROV 2017-11-28 / 2017-12-07 / 2024-06-01 | not_found | Platov |
| ROV 2015-01-01 | not_found | uncertain (start unknown) |
| RVI 2017-12-01 / 2019-01-01 | not_found | uncertain (old site only candidate) |
| YNT 2014-12-11 / 2015-05-27 | not_found | uncertain (both sites) |
| YNT 2015-05-28 / 2020-01-01 | not_found | Penglai |
| PNH 2015-01-01 / 2025-09-08 | not_found | Pochentong |
| PNH 2025-09-09 | not_found | uncertain (no withdrawal record) |
| KTI 2025-07-23 / 2025-09-09 | not_found | uncertain (booking-only / transfer day) |
| KTI 2025-09-10 | not_found | Techo |
| KTI 2020-01-01 | not_found | uncertain (Kratie not modelled) |
| VDTI 2025-09-04 | not_found | Techo |
| VDPP 2020-01-01 / 2025-09-07 | not_found | Pochentong |
| ZSYT, URRR any date | not_found | not_found (not admitted) |

Within the 2026-10-25 evidence horizon, the newly certain intervals cover
19,112 code-days that previously returned `not_found`: ROV old 617, ROV Platov
3,253, YNT Penglai 4,168, PNH 6,095, VDPP 4,153, KTI 410, VDTI 416. All
existing 0.4.0 queries and warnings are unchanged; the validator adds exactly
two expected possible-overlap warnings (ROV, YNT).

## 4. Integrity changes

- `curated-baseline.json` now pins the 0.5.0 dataset (counts, version, hash)
  and keeps the 0.4.0 baseline in `preservedBaselines`; `validate.py` checks
  both. Nothing was weakened.
- `review.py`: follow-ups form an ordered disposition chain from the owning
  event's original status to its live status; follow-up-only batches are
  allowed; unready follow-ups cannot admit formal IDs. `validate.py` checks
  that admitted IDs exist in the formal dataset.
- global-1 ROV/YNT/PNH keep their PR #6 claims, gaps and next actions, with a
  `dispositionHistory` (original → global-3). Their candidate mappings remain
  in global-1 only; legacy leads keep their manual-lead status.
- The manifest was regenerated with `pnpm research:report --reuse-baselines`.
  `legacy-links.jsonl.gz` changes because legacy leads now match the new ROV,
  YNT and PNH/KTI assignments; candidate shards, queue and source pins are
  byte-identical.

All publication text stays with its publishers; sources are links with
independently written notes. OurAirports rows are public domain; IANA zone1970
is public domain.
