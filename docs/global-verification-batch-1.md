# First global candidate verification batch

Reviewed 2026-10-27 after confirming [PR #5](https://github.com/keepraw/airport-history/pull/5)
merged into main at `f616eec670fdbc940d42ad82f2a2a34f55e2d6cc`.
The branch starts at that latest main commit. This review covers **20 event
groups**, with **12 insufficient_evidence, four pending_review, four excluded,
and zero ready_to_admit**. The formal dataset remains byte-for-byte unchanged:
13 physical airports, 20 code assignments, two historical names and 29 sources.

The complete claim-by-claim record is
[batches/global-1.json](../research/discovery/batches/global-1.json).
It contains 37 reference records, publication roles, access checks, specific
supported facts, license restrictions, pinned source transitions, related IDs,
unresolved questions and next actions. **37 research references are not 37 newly
admitted formal sources.** Several URLs were already research leads. Failed
origin retrievals and search-index-only extracts are identified explicitly.

## Selection and dispositions

Nine requested groups take precedence. Other groups come from the existing
1,664-entry priority queue. Exact derivative duplicates of Kankan, Uttaradit and
Hoedspruit retain all three additional IDs but count as the same events, not
independent evidence. The 18 selected machine transitions and two preserved
manual leads therefore cover 20 groups, with 23 linked candidate IDs. Review
overrides cover the 21 machine representations; the two manual replacement
leads retain their existing insufficient-evidence disposition.

Four proposed interpretations were excluded. Subsequent ranked leads including
Limón, Sahiwal, Kankan and Uttaradit were included, keeping the total reviewed
groups at 20. The ceiling includes exclusions; no extra batch was investigated
to manufacture admissions. The machine queue's first twenty are not treated as
twenty distinct historical events.

| Group | Existing primary candidate ID | Conclusion | Reason / retained gap |
| --- | --- | --- | --- |
| Kratie / Techo KTI | `cand_fd2a5e00b9b3f58536c0433e` | insufficient_evidence | Techo KTI/VDTI observed directly; original Kratie allocation/withdrawal and Techo first effective date absent. Not a Kratie-to-Techo physical replacement. |
| Yantai | `cand_8ac1b12707d7c441ce708d32` | insufficient_evidence | 2014 approval/planned coordinate update does not prove final YNT implementation at 2015 flight relocation. |
| Rostov / Platov | `cand_7fc9b08615e93efbdffdc2a8` | insufficient_evidence | Reports place ROV/RVI change before passenger move; primary code implementation and RVI end absent. |
| Lianyungang | `cand_ee28c2f36941d4b62ff604b2` | insufficient_evidence | Separate sites and flight move supported; LYG/ZSLG allocation boundary absent. |
| Yibin | `cand_0b3be5f183608a0f8d8463fe` | insufficient_evidence | Opening and civilian relocation are distinct from YBP/ZUYB implementation and military closure. |
| Luzhou | `cand_6bdbc1b60cf1a50fd06abd88` | insufficient_evidence | About a year of service interruption before Yunlong opening; no seamless LZO/ZULZ interval justified. |
| Jining | `cand_e1f96c81b10b8a30ef076ffa` | insufficient_evidence | Carrier notice proves its flight move, not JNG/ICAO boundary; guessed ZSDA rejected. |
| Dakar | `legacy-dakar` | insufficient_evidence | Old DKR and new DSS differ; no DKR inheritance or proven withdrawal. Carrier transition dates vary. |
| Phnom Penh | `legacy-phnom-penh` | insufficient_evidence | Old PNH and new KTI differ; flight implementation is direct, original allocation/withdrawal remains missing. |
| Samarinda | `cand_3aba472425775e4a29a4d63b` | insufficient_evidence | Different Temindung/APT Pranoto sites and current AAP/WALS confirmed; SRI/AAP and historical WALS dates missing. |
| Calamocha / Castellón | `cand_27f8e5c4d6f78bb8d11e7629` | excluded | Directory repurposing is not Calamocha relocation or CDT transfer from Calamocha. Genuine LECN/CDT and ICAO reuse questions preserved. |
| Wad Medani | `cand_e2f8f10d49342c01a7e4c0ec` | pending_review | Material coordinate conflict; physical identity and closure date unresolved. |
| Narganá | `cand_3788d9d4f8b213d5d1c24425` | excluded | Editor explicitly describes a 75 km marker correction. No NGN transfer or closure date inferred. |
| Chaitén | `cand_4ecbdc43aaa5a0a46a3c5e78` | pending_review | Official resolution says SCTN; another official technical page says SCPC. Old, temporary and new sites need separate mapping. |
| Toul / Brive | `cand_ba1d95c1c6212eaafe0407f3` | excluded | Directory conflates distant locations under LFSL; Toul had no BVE in the before-row. Actual Laroche/Souillac transfer remains a separate follow-up. |
| Kankan | `cand_d143eee2e286e0dfbbaa2339` | pending_review | GUXN/GUXD physical mapping conflicts; KNN transfer date unproved. |
| Uttaradit | `cand_ec671992f93700beb8d14848` | pending_review | Historical airfields, reported closure and retained AIP VTPU listing need reconciliation. |
| Hoedspruit | `cand_410d7e6a2202857176507e0f` | excluded | Non-existent-airport label and South Atlantic marker are erroneous directory content; operator/AIP identify the real South African field. |
| Limón | `cand_025ed86a58c3d799fd1028e1` | insufficient_evidence | Coordinate shift and closed-to-open source flag lack official physical/temporal evidence. |
| Sahiwal | `cand_319a76a6d0b81db2843a9ca4` | insufficient_evidence | Coordinate correction versus move unresolved; SWN/OPSW withdrawal and closure dates missing. |

Exclusion is scoped to the interpretation above. It does not erase historical
code reuse, nearby fields, former facilities or genuine replacement leads.
Every excluded item retains follow-up questions; every unresolved item retains
its original candidate ID and raw transitions.

## What the sources establish

[Spring Airlines](https://www.ch.com/news/33497b984fc54d96927e965b33fa9a1e.html)
directly instructs relocation between the two Yantai fields on May 28, 2015.
The [2014 IATA interview report](https://yantai.dzwww.com/xinwen/ytxw/ytsh/201411/t20141110_11338121.htm)
describes approval and a **planned December 11, 2014 coordinate update**. It does
not confirm that update happened. The later flight move does not resolve actual
IATA implementation. Neither date is admitted as YNT's effective transfer.

The [December 1, 2017 Rostov report](https://www.rusaviainsider.com/platov-airport-open-december/)
already describes new-site ROV and old-site RVI before the
[operator's December 7 passenger opening](https://ar-rov.ru/about/history/).
November 27 is supported by secondary reporting, not a retrieved primary
allocation record. The operator's W17 coordination sheet uses domestic Cyrillic
coding; it is not silently interpreted as an IATA implementation notice.

[China United Airlines](https://info.flycua.com/jcms/publish/APP/appjjtz/j20211123_363_521_8377.html)
and [China Southern](https://www.csair.com/newh5/cn/service_notice/1hi7qev4ktpqb.shtml)
directly instruct their Lianyungang and Jining moves. Neither notice states
the IATA or ICAO effective boundary. Yibin's government-hosted opening account
is explicitly credited to a newspaper, so it remains secondary reporting.
[Luzhou's opening report](https://sc.cnr.cn/sc/2014sz/20180910/t20180910_524356124.shtml)
describes a preceding service gap; it cannot support continuous old-site use
until the 2018 new-airport opening.

The [SAA release reproduced by AVIATOR](https://aviator.aero/press/south-african-airways-advises-of-dakar-airport-change)
explicitly distinguishes DKR and DSS and schedules SAA's first new-site landing
for December 8, 2017. Its general termination wording is not a code withdrawal
or all-use legal closure. The
[Singapore Airlines circular](https://agent360.singaporeair.com/content/dam/agent360/web-assets/pdf/local/hk/HKGSQ_Relocation_of_PNH_to_KTI_Airport_SN125.pdf)
directly implements its PNH-to-KTI operation change on September 9, 2025.
[Techo's developer](https://www.ocic.com.kh/projects/techo-international-airport)
identifies KTI/VDTI and the distinct greenfield site. None of these documents
proves the end of Kratie KTI, first Techo KTI allocation or PNH withdrawal.
Certification, commercial opening and ceremonial inauguration remain separate.

The [DGAC resolution](https://www.dgac.gob.cl/transparencia/pdf2015/DASA027.pdf),
visually inspected at page 1, directly identifies Nuevo Chaitén, SCTN and its
coordinates. The [DGAC technical fiche](https://www.dgac.gob.cl/wp-content/uploads/2024/06/CHAITEN-FICHA-TECNICA.pdf),
page 2, visibly prints SCPC while its map labels SCTN. This looks like an editorial
error but remains a documented conflict for independent review. No code date is
chosen by ignoring it. The temporary road strip is not collapsed into either
permanent site.

These are **primary_direct observations or instructions for the stated facts**.
Secondary news, community directories and pinned Git transitions remain
**indirect** for historical allocation. OurAirports and its derived exports are
not independent corroboration; airportsdata/mwgg keys can be pseudo identifiers.
A city label, GPS field, keyword or syntactically valid four-letter string is
never enough to establish official ICAO allocation.

**No new continuity_inference interval is admitted.** Code/name continuity
between dated observations would remain an inference even with a direct source
at one endpoint. This batch does not use such an inference to supply missing
boundaries or resolve conflicting physical identities. Formal IDs, schema,
package/data versions and all existing intervals remain unchanged.

## Reproducible review without a rescan

The compressed discovery observations and ranked queue remain the PR #5 snapshot,
including their original exported statuses and all unresolved candidates.
`reviews.json` is the authoritative live override, linked to this batch's
claim-specific evidence. The query tool applies it by default to both candidate
shards and the existing ranked queue:

```sh
python3 scripts/discovery/query.py --code KTI --status insufficient_evidence
python3 scripts/discovery/query.py --queue --status excluded
python3 scripts/discovery/query.py --queue --snapshot --limit 20
pnpm research:review-report
pnpm check
```

`--snapshot` intentionally shows the original exported state. Raw source
`evidence` stays pending/indirect and its event date stays unknown even when its
human `review` disposition changes. `summary.json.reviewBatches` describes current
review results separately from exported discovery counts. The bounded metadata
refresh checks existing artifact hashes, updates the batch summary and review
manifest, and never reads source Git history or writes source shards, queue or
formal data. The existing full scan can still export the same overrides during
an explicitly requested future scan. A later full report includes the batch
summary too.

Review refresh authenticates the **old summary size and SHA-256** along with all
other artifacts, then checks **every existing non-review input hash**, before any
output write. Its only manifest changes are `reviewInputs` and the summary entry;
it never re-registers non-review inputs. A changed summary, scanner, source config
or other recorded non-review input fails without modifying outputs. Intentional
generator changes require an explicit `pnpm research:report --reuse-baselines`.
That report rebuilds derived reports from generated candidates and verifies/reuses
the exported regional and Keepraw-Fly comparison baselines, with matching pins,
versions and hashes. It does not open source repositories or fetch/scan histories.

Validation checks the 20-group ceiling, all related candidate IDs, source links,
claim classifications, conflicts, exclusion reasons, retained gaps, pinned raw
observations and review mappings. Tests cover live overrides without source/date
promotion, snapshot preservation, ranked-queue consistency and rejection of
unready formal admissions. No global scan, Wikidata dump, database service,
Keepraw-Fly change, Release or automatic merge is involved.

## Next investigations

First obtain actual IATA/airline implementation records for KTI, YNT and ROV/RVI;
then CAAC AIRAC/code implementation for LYG/JNG and separate closure evidence for
LZO/YBP. Independently resolve Chaitén, Kankan, Wad Medani and Uttaradit maps.
The most promising additional existing queue leads are Sanga Sanga SGS/TWT,
Duqm DQM/JNJ, New Bight CAT/TBI and Qiemo/Yudu IQM. Their exact IDs are retained in
the machine-readable next-batch list; none is newly adjudicated here.

All publication text, images and PDF tables remain with their publishers.
References without an established redistribution grant are reference-only.
OurAirports factual data retains its public-domain designation; derived and MIT
observations retain their source-specific notices. No copyrighted publication
or map extract is included in the repository.
