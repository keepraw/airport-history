# 0.7.0 review: historical ICAO coverage at existing airports

Reviewed 2026-10-28. Before branching, GitHub API confirmed the authorized actor
as `keepraw` (49091395), PR #9 as merged, and latest `main` as
`cb0f003c21f0cb77cf4576dbe915cee1c9971a91`. The merged data bytes were copied
to `test/curated-0.6.0.json` before formal changes. Its SHA-256 is
`a64086c6864cdf6e2d3ab3df72ffec704a3bdef3cc3d70f1c29cb2d7eeeabe80`.

| Dataset | Physical airports | IATA | ICAO | All assignments | Official names | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.6.0 | 23 | 28 | 6 | 34 | 3 | 56 |
| 0.7.0 | 23 | 28 | 12 | 40 | 3 | 70 |

Schema remains **3.0.0**. All old assignments, sources, names, permanent IDs and
reference attributes are unchanged. No original naming decision was discovered;
no name interval is added. The resolver implementation is unchanged.

## Screening and bounded selection

| Case | Official-document availability and decision |
| --- | --- |
| Islamabad OPRN/OPIS, A | Selected. Historical Pakistan AIP reproductions explicitly distinguish coordinates; CAA occurrence notification and current PAA amendment are available. Current OPRN ICAO corroboration is limited. |
| Istanbul LTBA/LTFM, A | Selected. Current original DHMI AD 2 entries, historical supplement reproduction and dated actual flight records are available. Commissioning and IATA exchange must remain separate. |
| Schonefeld/Brandenburg EDDB, A | Selected. Pre-expansion BFU notification held by BEA, existing Fluko infrastructure evidence and dated operator aerodrome manual are available. Preserve one physical identity. |
| Astana UACC, B | Selected as the fourth case. Original ANAC reconstruction of actual flight legs, Kazakhstan occurrence notification and effective-dated official eAIP identify the same airport across TSE/NQZ. |
| Chisinau LUKK, B | Screened, not selected within the four-case ceiling. [National AIM portal](https://aim.moldatsa.md/) returned 403; [CAA exemption register](https://caa.md/en/exemptions) and [EUROCONTROL 2024 report](https://www.eurocontrol.int/sites/default/files/2025-05/eurocontrol-lssip-2024-moldova.pdf) are leads, not a completed pre/post-KIV/RMO code-interval review. Need dated site-specific ICAO observations and an admitted endpoint. |
| Qingdao ZSQD, B | Deferred at screening. Historical Liuting and current Jiaodong AIP reproductions surfaced, but no retrieved original AIRAC/NOTAM establishes when the indicator changed physical sites. [Current certification table reproduction](https://yinlei.org/x-plane10/doc/AD.pdf) gives a 2021-06-07 certificate date, which is not an ICAO transfer date. Existing TAO/opening evidence does not close this gap. |
| Denver KDEN, B | Deferred at screening. [Operator retrospective](https://www.flydenver.com/press-release/den-celebrates-30th-anniversary/) establishes the 1995-02-28 opening and predecessor operations, but no inspected FAA/ICAO record here supplies KDEN's old-site end and new-site allocation. DEN, an FAA location ID, and KDEN are not interchangeable evidence. |

No new global discovery batch, history scan, bulk Wikidata retrieval or directory
history clone/fetch was performed. One already pinned OurAirports file was read
to inspect six existing rows; it is corroboration, not historical allocation
evidence. Existing discovery events need no disposition changes for these
additional, differently scoped ICAO claims. No candidate is remapped. Dakar,
Samarinda, YNT, ROV and KTI investigations were not reopened. ZSYT, URRR/URRP
and WALS stay unadmitted.

## Boundary policy

Every new interval is verified **`continuity_inference`**. Its first allocation
is unknown (`validFrom.earliest = null`, precision `unknown`). A latest-start
bound is an upper bound supported by an observation, never an invented allocation
date. Every latest-end bound remains null: no withdrawal is established.

| Assignment and existing physical airport | Latest start, inclusive certain coverage | Earliest end, exclusive certain coverage |
| --- | --- | --- |
| `icao-oprn-chaklala`: old Chaklala / Benazir Bhutto / Nur Khan, `apt_d28173b7-5c8b-4012-8eed-18f96c13a0ce` | 2016-08-09 | 2021-03-25 |
| `icao-opis-islamabad`: new Islamabad, `apt_896e8191-7c0b-4a94-bc14-9dcd7e35feac` | 2017-06-23 | 2026-10-25 |
| `icao-ltba-ataturk`: Ataturk, `apt_d8f290d3-11cc-4441-af6d-f4dd52d3b8dc` | 2011-10-17 | 2026-10-25 |
| `icao-ltfm-istanbul`: new Istanbul, `apt_92a92544-1808-487a-85e0-0fa995e1de82` | 2018-10-12 | 2026-10-25 |
| `icao-eddb-berlin`: Schonefeld/Brandenburg, `apt_f642eef8-1864-43c4-8944-47aaa7ac35ce` | 2016-07-09 | 2026-10-25 |
| `icao-uacc-astana`: Astana/Nazarbayev, `apt_99f19660-7609-49c5-b221-ed4a37046566` | 2016-05-01 | 2026-10-25 |

The fixed evidence horizon stays 2026-10-25 exclusive. OPRN has a deliberately
earlier endpoint. Queries before a latest start, on/after an earliest end, or
after the horizon remain `uncertain` with no selected airport. These are open
uncertainty bounds, not asserted withdrawals or a current-directory fallback.

### Islamabad

[BEA2016-0485](https://bea.aero/en/investigation-reports/notified-events/detail/serious-incident-to-the-airbus-a320-200-registered-ap-bla-operated-by-pakistan-international-airlines-on-08-08-2016-at-islamabad-investigation-led-by-caa---pakistan/)
records AP-BLA departing OPRN/Chaklala and returning to runway 30 on local
2016-08-08. Latest start is the next whole date, August 9. The
[CAA AD 2 OPRN-1 page dated 25 MAR 2021](https://www.scribd.com/document/896418285/RNLNSW4)
explicitly identifies OPRN at **33°37′00.36″N 73°05′55.46″E**, runway 30/12,
joint PAF/CAA administration. This confirms retention at the old site after the
civil move. It is an original AIP page in a third-party reproduction, not an
origin-hosted authenticated copy. No historical official-name interval is inferred
from the page's retained Benazir Bhutto label.

The fixed OurAirports OPRN row has **blank `icao_code` and `gps_code=OPRN`**.
It cannot extend ICAO coverage to 2026. The last AIP observation date is therefore
an exclusive conservative endpoint, 2021-03-25. Later withdrawal, continued use
or reallocation is unproved; the latest end remains unknown. Some later BEA
pages incorrectly retain old OPRN/ISB labels for apparent new-airport civil
flights; those pages do not establish old-site continuation and are not admitted.

[CAA AIRAC SUP S-12/17](https://gateway.x-plane.com/bug_reports/attachments/20946),
published 2017-04-27 and effective **2017-06-22 0001 UTC**, explicitly designates
OPIS in Appendix A-1 AD 2.1 and puts its ARP at
**33°32′56.70″N 72°49′32.34″E**. At Pakistan UTC+5 this is 0501 local; latest
start is June 23. Paragraph 7 separately reserves commissioning for a NOTAM.
This is an administrative AIP code designation before airport service, not an
operated flight, first allocation, or exact ICAO transfer on the May 2018 opening.
The inspected PDF is a third-party attachment. The later
[S-06/18 reproduction](https://www.scribd.com/document/716564811/AIRAC-AIP-Supplement-S-06-18)
corroborates the same OPIS coordinates and expressly supersedes S-12/17;
its April 26, 2018 effectiveness is not used to replace the earlier bound.
[Official PAA amendment 02/26](https://paawebadmin.paa.gov.pk/media/eaip/02-26/eAIP/main.html),
effective 2026-06-11, still explicitly updates Islamabad (OPIS). Continuation
to the fixed horizon is reviewed inference with the existing pinned snapshot.

### Istanbul

[BEA f-xi111015](https://bea.aero/en/investigation-reports/notified-events/detail/mouvements-daileron-de-profondeur-droit-non-commandes-en-tangage-en-croisiere/)
identifies actual F-GKXI departure from LTBA/Ataturk on a flight whose occurrence
was on France-local 2011-10-15. Departure time is missing; Turkey was one hour
ahead of France. Latest start **2011-10-17** conservatively allows a local-day
rollover without claiming either departure date or original allocation.
[Official DHMI AD 2 LTBA-1](https://www.dhmi.gov.tr/AIPDocuments/LT_AD_2_LTBA_en.pdf),
dated **2026-03-19**, retains LTBA at **40°58′34″N 28°48′51″E**, TWY D.
The PDF wrapper's stray 2016 amendment text is not the entry date.

[DHMI SUP 04/18 reproduction](https://www.scribd.com/document/421103799/LT-Sup-2018-04-en)
is published **2018-09-11**, effective **2018-10-11**. It explicitly designates
Istanbul New Airport as LTFM and separately retains LTBA procedures. Its
paragraphs 2-3 make procedure use conditional on service and commissioning by
NOTAM. We admit the administrative designation by the effective edition,
conservatively at the next whole date **October 12** because no instant is
proved. We do not certify flights on October 11/12, use opening as allocation,
or treat the document's publication as an exact allocation date. The origin
historical PDF was unavailable; the reproduction limitation remains explicit.

[BEA2020-0011](https://bea.aero/en/investigation-reports/notified-events/detail/serious-incident-to-the-airbus-a330-registered-tc-lol-operated-by-turkish-airlines-on-31-12-2019-at-port-harcourt-nigeria-investigation-led-by-bfu---germany/)
separately observes an actual LTFM departure for TC-LOL's 2019-12-31 Port
Harcourt arrival. Its heading mentions BFU/Germany, while responsible entity and
summary identify Nigeria/AIB; that heading is not relied on as provenance.
[Official DHMI AD 2 LTFM-1](https://www.dhmi.gov.tr/AIPDocuments/LT_AD_2_LTFM_en.pdf),
dated **2026-03-19**, puts LTFM at **41°16′31″N 28°45′07″E**, Arnavutkoy.
The two coordinates and already curated replacement-site history distinguish
the sites. Neither indicator transfers in the 2019 IST/ISL exchange.

### Berlin

[BEA2016-0398](https://bea.aero/en/investigation-reports/notified-events/detail/serious-incident-to-the-airbus-a320-registered-d-aicf-operated-by-condor-flugdienst-gmbh-on-08-07-16-en-route-investigation-led-by-bfu---germany/)
holds the German BFU notification of actual D-AICF departure from EDDB/SXF
Schonefeld on **2016-07-08**; France and Berlin share the local offset.
Latest start is July 9. The existing
[Fluko document](https://fluko.org/wp-content/uploads/2020/05/BER-Information-on-Airport-Slot-Coordination-W20-S21-20200506.pdf)
establishes BER as an extension of the SXF airside infrastructure.
[Operator Aerodrome Manual EDDB A.8](https://corporate.berlin-airport.de/content/dam/corporate/en/geschaeftspartner/ordnungen-antraege/flugplatzhandbuch/eddb-a8-en.pdf),
**version 10.8, effective 2026-04-01**, section 1.1 on page 5, explicitly
associates Brandenburg with AD 2 EDDB. Earlier dates in the manual's revision
history do not establish original allocation. DFS's October 2026 edition was
located, but the actual AIP page image could not be retrieved; it is not used
as formal evidence.

There is **one EDDB interval at one existing physical ID**, spanning the
2020-10-25 SXF/BER change, T5 incorporation and October 31 T1 opening. No extra
entity, terminal-based split or ICAO transfer date is created.

### Astana

[ANAC Parecer 501/2019](https://www.anac.gov.br/acesso-a-informacao/junta-recursal/decisoes-monocraticas/2019/maio/00058-522585-2017-13/@@display-file/dlb_arquivo/SEI_00058.522585_2017_13.pdf),
pages 1-2, reconstructs an actual PR-OMX journey from authenticated logbooks,
including **2016-04-29 EPWA-UACC (Astana)-ZWWW**. This is not an announced
schedule; 2019 is the later authority record's date. The log table lacks a time
standard. Allowing a rollover at Astana's historical UTC+6 gives conservative
latest start **2016-05-01**, leaving April 29 and 30 uncertain.
[BEA2018-0361](https://bea.aero/en/investigation-reports/notified-events/detail/serious-incident-to-the-airbus-a320-registered-p4-kbb-and-operated-by-air-astana-on-22-05-2018-at-astana-investigation-led-by-aaid---kazakhstan/)
independently identifies an actual landing at UACC/TSE on local **2018-05-22**.
[Kazaeronavigatsia's effective 2026-10-01 AD 2 entry](https://www.ans.kz/AIP/eAIP/2026-10-01-AIRAC/html/eAIP/UA-AD-2.UACC-en-GB.html)
identifies UACC-Astana at **51°01′21″N 71°27′58″E**, runway center, with
Nazarbayev airport administration and NQZ SITA address. This confirms an
aerodrome indicator, not UACC FIR/ACC usage. The future October 29 edition and
a guessed 2019 URL that returned a soft 404 are not used.

UACC stays with the same curated runway/site across TSE/NQZ, airport naming and
city renaming. No extra name interval or physical entity is created.

## Measured resolver benefit

`test/pr10-coverage.json` fixes a daily query window **2011-10-15 inclusive to
2026-10-25 exclusive**, six distinct ICAO keys. The test executes every query
against frozen 0.6.0 and 0.7.0, checks status and permanent identity, and excludes
uncertain dates from the gain.

| Code | Newly resolved code/date queries | Still uncertain queries | Certain range, inclusive |
| --- | ---: | ---: | --- |
| OPRN | 1,689 | 3,800 | 2016-08-09–2021-03-24 |
| OPIS | 3,411 | 2,078 | 2017-06-23–2026-10-24 |
| LTBA | 5,487 | 2 | 2011-10-17–2026-10-24 |
| LTFM | 2,935 | 2,554 | 2018-10-12–2026-10-24 |
| EDDB | 3,760 | 1,729 | 2016-07-09–2026-10-24 |
| UACC | 3,829 | 1,660 | 2016-05-01–2026-10-24 |
| Total | **21,111** | **11,823** | |

All 32,934 queries were `not_found` in 0.6.0. The 11,823 newly exposed uncertain
candidate queries are **not coverage**. Every interval, including dates with a
direct observation, is classified as reviewed continuity inference. Direct
operational records are six dated observations: LTBA 2011 flight, EDDB 2016
flight, OPRN 2016 flight, UACC 2016 journey and 2018 landing, and LTFM 2019
flight. Two starts instead use administrative AIP designation; they do not
certify pre-commissioning flights. None of the 21,111 is counted as an
independently verified daily flight, a source-directory revision, or a future
booking. First allocation and the complete earlier chronology remain unknown.

Representative results: EDDB resolves to the same ID on October 24, 25 and 31,
2020; UACC on June 7, 8 and 9, 2020. OPRN and OPIS resolve to distinct old/new
IDs on 2018-05-03; LTBA and LTFM resolve to distinct IDs on 2019-04-06. OPRN on
2024-01-01 is uncertain, while all other added keys resolve then. Every added
key is uncertain on 2026-10-25 and 2030-01-01, with no selected airport.
Unadmitted reused codes ZSQD and KDEN return `not_found` around their alleged
transitions, preventing a silent assignment to the wrong physical airport.

Tests compare every old code and name at every old boundary and adjacent date,
plus representative earlier, move, observation and future dates. All old records
are exact-equal to the three frozen datasets. New assignments use only six keys
absent from 0.6.0, and the resolver code is unchanged, preserving results for
all old keys at other dates as well (apart from reported dataset version).
KTI advance-booking regressions on 2025-07-22/23 remain uncertain.

## Reproduction and protection

0.4.0, 0.5.0 and 0.6.0 snapshots are pinned independently in regression tests
and in `curated-baseline.json`; the research validator requires every old
airport, assignment, name and source record unchanged. Package/data version
advances together to 0.7.0. License notices are preserved; new sources remain
reference-only links and original annotations. Downloaded source contents stay
in ignored `work/` and are not redistributed.

After updating the formal baseline, use the established offline workflow:

```sh
pnpm research:report --reuse-baselines
pnpm check
```

The report reuses and authenticates existing exported discovery baselines; it
never fetches/scans source histories or reads a Keepraw-Fly checkout. The affected
legacy-link record gains the two formal Islamabad assignment references, and its
hash and the curated-baseline input hash are regenerated in the manifest. This
does not change candidate/event ownership. Candidate inventories, review
dispositions and discovery totals remain unchanged. Deterministic artifact
tests build twice under different timezones and verify all license/manifest
hashes. The PR is left unmerged, without a tag or Release.

Local validation passed with Node 24 and pnpm 10.14.0: the complete `pnpm check`,
382 TypeScript tests, 50 Python research tests, formal/research validation and
deterministic build. Existing boundary warnings are unchanged. Offline report
regeneration changed only `legacy-links.jsonl.gz` and `manifest.json`; summary
and candidate/queue bytes remain unchanged.
