# Second global candidate verification batch and KTI/YNT/ROV follow-up

Reviewed 2026-10-27 after confirming through the GitHub API that
[PR #6](https://github.com/keepraw/airport-history/pull/6) is merged and `main`
is still `02d4f2396a1bec8ad5ee0c8b10c3a8eb30db5643`. The branch starts there.

The machine-readable record is
[batches/global-2.json](../research/discovery/batches/global-2.json). It holds
44 reference records (publisher role, publication date where known, original
versus third-party reproduction, access result with HTTP status/size/SHA-256 or
the exact retrieval failure, supported facts, limitations and licence notes),
four new event groups and three dated follow-ups of global-1 events.

**Outcome:** four new event groups, two `insufficient_evidence`, two `excluded`,
zero `pending_review`, zero `ready_to_admit`. The three follow-ups keep
`insufficient_evidence`. **No formal airport, assignment, name or source record
changes**; `data/airports.json` still matches `curated-baseline.json`.

## Data-model rules applied

- KTI, YNT and ROV/RVI remain owned by `global-1`. Their follow-ups live in
  `global-2.json#followUps` with `candidateIds: []`; validation rejects any
  follow-up that maps a candidate, targets an event that is not in an earlier
  batch, or states a disposition that disagrees with the owning event.
  `global-1.json` is byte-for-byte unchanged (SHA-256 pinned in a test).
- Every candidate ID maps to at most one event across all batches
  (`validate_batch_series`). Derived duplicates of the same transition are
  `relatedCandidateIds` and count once; they are not independent evidence.
- Each batch may set its own `maximumEvents` (at most 20); global-2 uses 4.
- `reviews.json` gains 10 overrides for the global-2 IDs; the 21 global-1
  overrides are unchanged.

## Workstream A: follow-up of global-1 priority cases

### Kratie / Techo — KTI (`global-1-kti`, `cand_fd2a5e00b9b3f58536c0433e`)

**Newly established (primary):** Cambodia told an ICAO APAC meeting that VDTI
was issued by ICAO and that Techo operates from **0000 UTC 2025-09-04**, with
Phnom Penh VDPP closing at **1700 UTC 2025-09-08**. The Cambodia AIP
(AIRAC AMDT 09/25, seen as a third-party copy) titles the aerodrome
"VDTI - TECHO INTERNATIONAL AIRPORT". Vietnam Airlines moves its own
operations from 00:01 on 2025-09-09; AeroRoutes saw KTI schedule filings by
July 2025; Qatar Airways reports the KTI *city name* changing from Krong Ta
Khmau to Phnom Penh from 2025-11-20.

**Still indirect:** a Cambodian embassy notice (2025-09-09) states KTI was
"previously assigned" to a smaller airport in Kratie and "officially
reassigned" to Techo — the only official statement tying KTI to Kratie, but
it is a diplomatic notice without dates, not a coding record.

**Negative results:** no IATA notice, GDS bulletin or news giving the KTI
assignment date; no official source for VDKT (aggregators only); CATS eAIP
requires login; no evidence of scheduled flights to Kratie; Khmer-language
search not done. **Gaps:** Kratie allocation and withdrawal, Techo IATA
effective date, VDKT status. The ICAO/AIP date, airline operational date and
city-name date are kept as separate events; none is used as the KTI boundary.

### Yantai — YNT (`global-1-ynt`, `cand_8ac1b12707d7c441ce708d32`)

**Newly established:** a 2013-11-15 CAAC chart (third-party copy) is headed
"ZSYT YANTAI/Laishan"; the current AIP section (EFF2510011600, hobby mirror)
is "ZSYT/YNT 烟台/蓬莱 YANTAI/Penglai". The operator's 2015-04-08 tender
describes whole-airport relocation from Laishan to Penglai.

**Operational boundary only:** Laishan civil use ended 2015-05-27 24:00 and
Penglai opened 2015-05-28 00:00 local (operator notice seen as a search
extract; Qilu Evening News). The 2014-12-11 coordinate update remains a plan
tied to an opening that slipped by about five months. A likely AIRAC 1506
amendment time is an inference and is **not** recorded as a boundary. ZSYT
continuity across the two sites is documented at two endpoints only.

**Negative results:** no IATA/CAAC code notice, Travelsky/Amadeus/Sabre/OAG
bulletin, AIP amendment or NOTAM text; several operator/news pages returned
404/403/502. **Gaps:** record-level YNT repointing date, ZSYT changeover
amendment, whether the 2014 plan was implemented.

### Rostov-on-Don / Platov — ROV/RVI (`global-1-rov`, `cand_7fc9b08615e93efbdffdc2a8`)

**Newly established (primary):** Government order No. 2434-r of 2017-11-04
opens "international airport Rostov-on-Don (Platov)" and closes the separate
"civil aviation aerodrome Rostov-on-Don"; the order takes effect
**2017-11-27**, while closure and removal from the federal list take effect
**2018-03-01**. A customs order (reproduced) mirrors those dates and lists the
Defence Ministry aerodrome Rostov (Tsentralny) separately.

**Strongest code record:** an Aeroflot agency notice dated 2017-11-27
(republished by a ticketing site) says Platov "is assigned ROV, previously
belonging to" the old airport, which receives temporary RVI, and that the
IATA notice is attached. The attachment was not found, so this remains an
airline record in third-party reproduction, not an IATA publication. Kommersant
reports the old airport ceased operations on 2017-12-07 with limited movements
until end-February 2018. One fan site gives 2017-11-24 for receipt of the code
(unresolved).

**Negative results:** no IATA notice, no other airline/GDS bulletin, no
Rosaviatsia order or AIP amendment for URRP/URRR, no RVI withdrawal notice.
**Gaps:** IATA notice and exact effective instant, RVI end, URRP/URRR AIP dates.
Legal civil closure is not treated as code withdrawal. The airport-codes
representation `cand_9aecceb0a56bba9d1eaf7d96` is unmapped in global-1 and
was deliberately not remapped here.

ROV is now the closest case to admission, but an admission would need the IATA
notice (or an equivalent second primary implementation record) and an RVI end;
the disposition is therefore unchanged.

## Workstream B: four new event groups

| Group | Candidate (related IDs) | Disposition | Basis |
| --- | --- | --- | --- |
| Sanga-Sanga SGS/TWT | `cand_07f311536256078e1803e39f` (`cand_46c26d…`) | insufficient_evidence | Same airfield; SGS in 2009 references and marked obsolete; TWT in PAL Express systems by 2014-02-09. The 2018-01-01 directory edit lags the real change; no dated allocation. |
| Duqm DQM/JNJ | `cand_5ebbfdbcea7f1b2aa138be41` (`cand_8244804d…`) | excluded | Directory record conflated Duqm (OODQ) with the separate Ja'aluni strip (OOJA, ~35 km west); the AIP lists both. Same-airport JNJ→DQM transfer rejected. |
| New Bight CAT/TBI | `cand_cb20612a6a4f6d8542872ae1` (`cand_ccacc72d…`, `cand_b96e3d61…`, `cand_49910068…`) | excluded | One aerodrome (MYCB); TBI in working use by 2006; directory corrected CAT→TBI in 2018 as an incorrect code. Contemporaneous transfer rejected. |
| Qiemo / Yudu IQM | `cand_dbe848d5c843e4ffc5270e26` (`cand_9d7392c0…`) | insufficient_evidence | Two airfields ~11 km apart (primary); old service ended 2011-05; Yudu validation flight 2016-08-26 and first scheduled service 2016-12-19; no IQM/ZWCM reassignment record. |

**Sanga-Sanga.** The coordinate edit is precision only; RPMN is constant in all
sources (not checked against the Philippine AIP). Great Circle Mapper marks SGS
"Obsolete (see TWT)", which suggests a real former code, but no IATA record
proves SGS was allocated or dates the change. An uncited "end of 2011" claim
is not used. Next: 2010–2013 airline booking captures and CAAP AIP.

**Duqm.** Oman Air flew a Muscat–Ja'aluni charter from 2012 and moved it to the
new airport when it opened on 2014-07-23. The OurAirports history shows the
OM-0003 record oscillating between "Duqm Jaaluni/JNJ" and "Duqm
International/DQM" with an editor stating Ja'aluni is 19 NM west. JNJ is
attributed only by directories and a 2013 business report. Exclusion covers
the same-site transfer only; the Ja'aluni identity, any JNJ allocation and the
DQM allocation date stay open.

**New Bight.** The Bahamas CAA register lists New Bight (MYCB) and Arthur's
Town (MYCA) separately. A derived IATA list carries "Cat Island CAT New Bight"
and "The Bight TBI" side by side; UN/LOCODE carries CAT and TBI as separate
entries (UN/LOCODE is not IATA). The airport-codes, airportsdata and mwgg
transitions all follow the same OurAirports correction and are related IDs, not
corroboration. Historical Cat Island CAT and its reuse at Cascais (associated
by 2016) remain a separate open question.

**Qiemo.** CAAC and the MEE-hosted EIA establish the two sites, the relocation
approval (Guohan [2012] No. 62) and the Yudu name in official use by
2016-09-05. Reference lists keep IQM throughout 2010–2017 and show the old site
in 2012. Assigning IQM/ZWCM to Yudu from 2016-12-19 would rest on continuity
inference across a five-year gap and is not admitted.

## Evidence classes and limits

- `primary_direct` is used only where a primary publication was actually read
  and states the specific claim (e.g. the Rostov order, Oman AIP, Bahamas
  register, CAAC Qiemo items). Opening, service, certification and city-name
  dates are never promoted to code-effective boundaries.
- Third-party reproductions (OPSGROUP AIP copy, AIP mirrors, republished
  airline notices, web-archive captures) are labelled `third_party_reproduction`.
- Pages that blocked workspace retrieval are recorded with the error; where the
  text was read through a web reader that is stated, and search-index extracts
  are labelled `indexed_extract_only_origin_blocked` and never support admission.
- All publications are reference-only: links and independently written factual
  notes, no article, PDF, chart, map or photograph text is redistributed.

## Reproduce

```sh
python3 scripts/discovery/query.py --code IQM
python3 scripts/discovery/query.py --queue --status excluded
pnpm research:validate
pnpm check
```

`review.py` changed (batch-series semantics), so the manifest was regenerated
with `pnpm research:report --reuse-baselines`, which reads no source Git
objects. Only `summary.json` (`reviewBatches`) and `manifest.json` changed;
every other generated artifact is byte-identical. No `research:fetch`,
`research:scan`, Wikidata dump, source clone, Keepraw-Fly change, Release or
merge is involved.

## Next

`global-2.json#nextBatch` records Gilgal GGL, Ferkessédougou FEK, Asaloyeh
AOY/YEH and Gamba GAX. `mappingObservations` records unmapped alternative
representations of Samarinda (global-1-aap) and Rostov (global-1-rov) for a
future reviewed change to those events.
