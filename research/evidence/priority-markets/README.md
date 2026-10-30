# Priority-market history follow-up (PR #22)

This is incremental research from the actual published **0.10.0 / Schema 3.0.0**
baseline `c712cefcc0b058880b1f21ee728d3cdc8c5ceea7`. The post-merge
[main CI](https://github.com/keepraw/airport-history/actions/runs/41010806134)
completed successfully in both jobs before this branch was created.

The project priority is mainland China, Japan, Korea, the US, the UK and
continental Europe. This stage follows **14 of the existing 60 investigation
units**: six Chinese relocations, two Japanese airports, two Korean airports,
Williston, Doncaster Sheffield, Murcia and Berlin. The other 46 units were not
reinvestigated. There was no new Indian research or worldwide transition scan.

Read the [Chinese handoff](HANDOFF.zh-CN.md),
[case matrix and exact original citations](generated/MATRIX.zh-CN.md),
[real-corpus dry-run decisions](generated/dry-run.json),
[actual production-resolver measurements](generated/coverage.json), and
[identity reuse check](generated/identity-dedup.json).

## Evidence and findings

There are 29 locked source components, 29 distinct original byte streams and
78 short citations. These are acquisition counts, **not historical coverage**.
Sources in one AIP issue, multiple captures of one airline directory and several
documents from one publisher are not counted as independent issuers.

The new Chinese material includes explicit old Lantian **LZO / ZULZ** text,
an old Ershilipu **ENY directory link**, two 2021 Baitabu **LYG directory links**,
Fuqiang's distinct licence and inaugural-flight events, and CAAC meteorological
identifier tables. A preserved stale airline page is not an effective code
observation. In particular, the Lantian and Ershilipu captures postdate their
service relocations. Their actual writing dates remain unknown.

The 2009 meteorological rule permits annex updates and lists cities rather than
physical ARPs. Its base-rule date cannot safely date every annex row. The 2026
replacement explicitly names the six new Chinese sites, but takes effect on
**2026-11-15**, after this investigation. It supplies prospective named
associations, not current validity or historical code handovers.

Centrair's typed code/position profile, Nagoya's separate ARP and the official
2005 chronology improve the Japanese physical-identity dossier. No historical
NGO/NKM allocation boundary has been established. New Korean controlled AIP
editions give RKSI and RKSS distinct, stable airport name/ARP observations.
FAA JO 7350.9GG separates FAA identifiers from IATA and limits the mainland
K-prefix rule. UK AIP pages remain present after Doncaster's reported service
closure. Murcia's official AD 2 pages distinguish both ARPs and retain military
administration at San Javier. FBB distinguishes Tegel's last flight from its
later permit termination and describes the SXF/BER booking-system change.

## Independently scoped drafts

[draft-policies.json](draft-policies.json) contains seven **unauthorized** drafts:

| Draft policy ID (version 0.1.0-draft) | Publisher / purpose | Present limit |
|---|---|---|
| `cn-site-code-association` | CAAC / airline directory associations | No date windows or admission |
| `jp-operator-code-site` | Japanese operator code/site profiles | No historical interpolation |
| `kr-molit-bounded-icao` | Korean controlled AIP AD 2 and issue index | ICAO research hypotheses only |
| `us-faa-typed-identifier` | FAA identifier semantics | No airport-specific or IATA admission |
| `uk-nats-bounded-icao` | UK CAA / NATS AIP | Closure case held for NOTAM/licence review |
| `es-enaire-bounded-icao` | ENAIRE AD 2 / AD 1.3 | Historical controlled pair still missing |
| `de-operator-event` | FBB service / permit / booking events | No code-allocation inference |

Scope includes exact cases, codes, source IDs, original hosts, publisher families
and output types. [Generated bindings](generated/draft-bindings.json) pin each
draft's policy, scope and separate research executor hashes. They are proposed
bindings, not a grant or a production executor registration. Other European
publishers require their own future adapters. The existing Indian policy,
112-day limit, scope, executor and grant files are unchanged.

The Korean draft's proposed 56-day limit is a conservative research budget of
two nominal 28-day AIRAC cycles, with this corpus testing one 28-day pair. It is
not a validated universal Korean continuity rule and does not inherit AAI's
authorization. Two editions from MOLIT remain **one issuer**. Independent physical
identity review and intervening amendment/NOTAM screening are still outstanding.

The 22 real-corpus requests include positive associations and negative examples
of stale captures, city-only references, future rules, opening dates, wrong
namespaces, mixed sites, long gaps, closure interpolation and page-revision
dates. The Korean two-edition hypotheses produce `[2025-04-18, 2025-05-15)`:
16:00 UTC is 01:00 on the next Korean date, so both partially observed edge dates
are excluded. The production resolver measures **54 hypothetical resolved
code/date queries** across RKSI and RKSS. All are unauthorized, and no simulated
verified record is written to disk. Simulation UUIDs are disposable test
identifiers, not newly allocated permanent physical identities.

Formal new resolved queries are **zero**. The actual 0.10.0 dataset is compared
with its immutable published snapshot using the unchanged production resolver:
187,738 code queries, 161,542 existing name queries, 4,366 local/boundary dates,
and a further 151,200 focused market code/date regression queries. Existing
uncertain and conflict results remain visible. No formal admission or 0.11.0
release is proposed. In particular, already formal Williston and Murcia physical
identities are reused, and their deferred assignments are not silently admitted.

## Reproduce and evidence custody

```sh
pnpm install --frozen-lockfile
pnpm evidence:priority-markets verify
pnpm evidence:priority-markets build
pnpm evidence:priority-markets validate
pnpm evidence:priority-markets rights
pnpm check
```

Build and validate use committed minimal citations, frozen inputs, the real
market-specific research adapters and the real TypeScript resolver. The source
lock records canonical publisher URLs, retrieval URLs, archive captures where
applicable, separate publication/effective dates, original/extraction/normalized
hashes, rights assessments and exact excerpt hashes. Citations have normalized
whole-document character offsets (or decoded-HTML offsets for directory links)
and one-based physical PDF pages. Normalization collapses Unicode whitespace.

Offline verification authenticates retained artifacts and the independently
labelled [local original-verification receipt](original-verification.json).
It cannot reconstruct or freshly verify a whole original. Actual acquisition
and the local full-byte/extraction/span checks were performed separately.

```sh
# Reacquire one pinned original into ignored work/, rejecting changed bytes.
pnpm evidence:priority-markets fetch --source kr-rksi-2025-04-16
# With all originals privately cached, check every byte, extraction and span.
pnpm evidence:priority-markets verify --originals
```

Full responses and full extractions stay in ignored `work/priority-markets/`.
Only minimal attributed factual quotations, metadata, URLs and hashes are public;
there is no established right here to redistribute the full publications.
FAA citations use only the agency's factual regulatory text; no third-party
figures, commercial attachments, photographs or full code ledgers are included.
The [discovery log](discovery-log.json) records failures, empty archive indexes,
soft 404s and search-only work separately. Search snippets are not evidence.

The 301 frozen baseline files cover formal data, schema, resolver, existing
published snapshots, prior research, original AAI policy/grants/admission records
and executor files. Changes to these files fail this research validator. Keepraw-Fly
is outside this branch. There is no merge, auto-merge, tag or release operation.
