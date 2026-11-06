# China Batch 7 — first formal physical-identity batch

Based on main `1e35d424a42377ea80c5c4ab53e1ee3d492b5acf`, this batch promotes six existing proposal IDs into `data/airports.json`: Lianyungang Baitabu/Huaguoshan, Yibin Caiba/Wuliangye and Luzhou Lantian/Yunlong. No replacement UUIDs are allocated. The data/package version is 0.11.0; schema remains 3.0.0.

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Physical airports | 37 | 43 | +6 |
| IATA assignments | 28 | 28 | 0 |
| ICAO assignments | 24 | 24 | 0 |
| Sources | 101 | 106 | +5 |
| Historical names | 3 | 3 | 0 |
| Resolved code/date queries | 89438 | 89438 | 0 |
| Uncertain code/date queries | 84099 | 84099 | 0 |
| Conflicting code/date queries | 0 | 0 | 0 |

`coverage.json` calls production `resolveAirport()` through the unchanged `policy_coverage.ts:measure()`: 187,738 code/date queries and 161,542 existing-airport name queries. Dates cover 2015-01-01–2026-10-29 plus 46 boundary dates. All existing answers are unchanged. No cross-site code reuse is newly resolved and no historical uncertainty interval is narrowed. Eighteen additional probes confirm the six deferred IATA/ICAO codes still return `not_found`. Identity growth does not imply code-history coverage.

## Evidence and selection

`readiness.json` screens all 17 existing Chinese cases before selection, including the requested eleven and Dazhou, Chengdu, Zhanjiang, Rizhao and already-published Qingdao/Yantai. Three relocation pairs receive full identity admission review. Daxing, Shiyan, Kunming and Hefei receive targeted code-gap follow-up in `code-gaps.json`. The other cases retain their specific missing originals and next actions in readiness; no worldwide rescan was performed.

The four newly formal official source records reuse PR #33's locked original receipts and bounded citations: `cn-lyg-both-sites-2020`, `cn-lyg-mee-2019`, `cn-ybp-mee-2014`, `cn-lzo-mee-2014`. Prior CAAC statistical/operation and Luzhou operator citations establish actual airport execution separately from project approvals. PR #22 and #31 evidence and existing pending IDs are reused through the Batch 6 crosswalk and prior market excerpts. No previously verified original was downloaded again. `original-verification.json` is explicitly an offline reuse receipt, not a fresh raw-byte replay.

One new official original was retrieved: the government-hosted Copyright Law text, for Article 5 administrative-document applicability (`rights-basis.json`). No new airport-code original was obtained. Administrative documents are individually scoped; this is not a blanket website or AIP redistribution licence. Full HTML, PDFs and complete extractions remain outside Git. Five new formal sources comprise four administrative documents and one separately scoped public-domain OurAirports extract. Numerical positions and English labels remain **reference** attributes, not historical ARPs or legal-name intervals; timezones are unknown.

## Machine admission

The explicit Batch 7 user instruction authorizes autonomous project-level review. `source-claims-v1/policy.json` activates Chinese administrative physical-identity claims only. Code/name claims fail closed. CAAC AIP and code-allocation profiles specify missing requirements and remain inactive; the draft 28-day ceiling grants no continuity inference. No proposal-only document is relabelled authorized, no personal reviewer is invented, and no AAI/Korean authority is inherited.

`project_admission.py` checks locked sources/receipts/citations, source class/custody/rights, observed dates, execution corroboration, country, reference rows, unique physical IDs, append-only records, shared batch validation and production schema semantics. The fingerprinted AAI helper imports its country-specific gate directly; those files remain byte-identical. A small current-version dispatch adds China validation and separately replays the original AAI bundle. Historical PR22 research is checked in a disposable offline archive so its frozen-data assertions do not prohibit later formal growth; its scripts and draft bindings are unchanged.

## Reproduce

```sh
pnpm validate:data
pnpm validate:admission
pnpm test
pnpm test:evidence
pnpm evidence:priority-markets validate
pnpm evidence:history
pnpm build
```

The eight China negative tests reject altered published records, unsupported code intervals, changed original hashes, inactive AIP families, missing execution evidence, substituted coordinates and fabricated human reviewers. PR #29/#32 and Keepraw-Fly are untouched. No merge, auto-merge or Release is requested.

Legacy Korean research additionally binds all package values. The existing Korean/rule and AAI rehearsal checks therefore run against the exact prior main in an isolated checkout after rejecting changes to every pre-existing script, test, schema and research file. Current schema/admission, TypeScript tests, source hashes, new China negative tests, resolver differential and history audit still run on the new dataset. This preserves old authorization scope rather than updating its fingerprints to authorize China. CI command entry points change; no timeout or executor changes.
