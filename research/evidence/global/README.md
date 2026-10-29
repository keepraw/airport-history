# Global airport-history research, 2015–2026

**Current continuation:** use the [priority-market correction](../markets/README.md)
and its [Chinese measured report](../markets/generated/RESULTS.zh-CN.md). The
worldwide counts below describe the preceding research stage. Its judgments and
query results remain reproducible; protected full originals/full text have been
replaced in the current branch tree by minimal hash-checked cited spans.
Offline verification authenticates those retained spans and original-hash
provenance. Full original re-extraction requires separate recovery and is not
claimed by an offline excerpt build. Older Git objects were not rewritten.

This research starts at main `9a22e059eb997d8195450b48f1f9b794550f2b28`,
which merged PR14. Formal data remains **0.8.0: 27 physical airports, 43
assignments, 3 historical names, 77 sources**. No new fact is human-approved.
The reserved 0.9.0 version exists only in the proposed dataset.

Actual results and scope are in [generated metrics](generated/metrics.json),
[the Chinese per-record review list](generated/待审核清单.md),
[original evidence index](generated/evidence-index.md),
[record dossiers](generated/dossier.json), and
[actual resolver coverage](generated/query-coverage.json).

The existing 1,240,058 transitions, 88,330 event groups, 493 priority code-reuse
leads and 86,950 reference records were reused. No upstream history scan or
worldwide directory regeneration was run. The 100-event selected queue is a
research workload, not an increase in historical coverage. Its 65 screened-only
leads have no invented event year. Research failures and publication shells are
retained; they do not become primary evidence.

## Review scope

The pending dataset contains actual physical and typed code records, with
explicit unknown allocation/withdrawal bounds. It is based on current 0.8.0,
not PR13's proposed 0.8.0 snapshot. Existing formal records remain byte-for-byte
unchanged. The builder uses current permanent IDs and the reserved older
physical proposals to prevent duplicate airports.

The 23 proposal event groups span multiple countries and are exported in two
existing-format batches (20 and 3). All six claim judgments, source provenance,
record ownership, original citations and per-record decisions remain pending.
The unchanged admission function rejects these packets. Codex assessments,
source extraction checks and recommendations are not independent human review.

Only seven proposal events have an executed day at exact precision. Other
physical events have year/month/quarter or unknown dates. Code observation
windows have their own dates; most do not date first allocation or withdrawal.
For example, the carrier's LGP→DRP change is explicitly dated 2022-12-15, whereas
Rajkot's first flight is 2023-09-10, not its July inauguration. Bohol's 2025
report labels its flight schedule **November 2024**. Ndola's August/October
chronology stays unresolved. Kurnool's 2020/2021 government statements conflict.
The former SSVC at Brazil's new airport is distinct from SBQV at the old site.

Complete P0 IATA transfer histories remain a material gap. Current new-site
codes do not establish old-site withdrawal or first allocation. Bohol TAG,
Ndola NLA, Qaqortoq JJU, Gwadar GWD and the Chinese replacement leads still need
allocation-specific history. Greenland's carrier city-code list is expressly
labelled city codes; it is not treated as a physical-airport allocation ledger.
[P2 follow-ups](P2-blockers.md) preserve KSGU, KDXZ and KXWA blockers. The
resolver's real cross-site uncertainty is exercised, not removed to inflate gains.

## Reproduce and continue

Requirements: Node 24, pinned pnpm 10.14.0, Python 3 standard library, Poppler
`pdftotext`. No server, UI, external database or new dependency.

```sh
pnpm install --frozen-lockfile
pnpm evidence:global verify       # all retained response/original byte hashes
pnpm evidence:global build        # offline originals + explicit judgments → proposals
pnpm evidence:global validate     # re-extract actual originals and check every citation
pnpm check                       # formal schema, admission, all frozen regressions,
                                 # legacy reproducibility and new negative tests
```

`generated/query-coverage.json` runs the real resolver for every whole local date
from 2015-01-01 through 2026-10-29. New review states exist only in an in-memory
hypothesis. It reports per-assignment certain windows, remaining uncertain/not
found dates, conflicts and any change to a previously published resolved result.
Its potential count is not formal coverage. A single instantaneous or day-bounded observation has no certain whole-local-day interval. Only bounded continuity between multiple observations can contribute resolved days in this corpus. The country/year table has an
explicit unknown-year bucket; zero is never interpreted as no historical change.
Countries outside this selected workload remain not assessed.

Continue without rescanning:

1. Pick remaining `screened_only` rows from `generated/queue.jsonl.gz`, or related
   groups in the existing registry. Review the current formal matches first; an existing numeric external reference requires an explicit `existingAirportId` physical judgment and never merges automatically.
2. Add official publication metadata, rights notes and content fingerprints to
   `catalog.json`; no airport-specific collector code or country whitelist is
   required. Several files in one AIP edition share one originalPublicationKey.
3. Run `pnpm evidence:global fetch --limit 10` or use repeated `--source ID`.
   Originals and text are saved and hash-locked after every attempt. Existing
   originals are authenticated and skipped; HTTP failures stay recorded. Use
   `--retry-failures` deliberately for failed acquisitions. Error/shell snapshots
   are immutable; give an authorized replacement publication a new source ID.
4. Record explicit factual judgments, namespace/site bindings and true uncertain
   time limits in `assessments.json`. Reuse a permanent/reserved physical ID.
   Keep reviewer null, source/assignment status pending and all six claim scopes.
5. Build and validate again. The builder emits as many <=20-event packets as
   necessary. Its formal baseline hash forces an explicit rebase/deduplication
   when formal data changes. PR11–13 snapshots are never rebased in place.
6. Human review and later formal admission use the existing workflow. This
   branch does not approve, merge, tag or release anything.

For an independent source snapshot, `fetch --output work/global-new` preserves
its own attempts, access times and originals, then `build --sources
work/global-new --output work/global-proposal` consumes that exact snapshot.
Recovery into a separate destination with `fetch --recover` rejects changed
original bytes. Dynamic websites may have changed; a recovery failure is
retained and must never be silently normalized into a success. Online recovery
is not claimed for all dynamic pages; deterministic **offline** reconstruction
and original-hash verification are tested for the complete committed corpus.

The collector uses bounded reads, sequential moderate requests, retries only
transient errors, atomic checkpoints and an exclusive snapshot lock. Offline
builds load a compact reference projection, not 1.24 million transition objects.
Output/input hashes bind the source lock, live formal baseline, judgments,
reference projection, resolver, schema and unchanged review implementation.

## Source rights and dependence

Originals remain subject to their publishers' rights and are excluded from the
repository MIT license. Each source lock records publisher, original URL,
retrieval URL, SHA-256, retrieval time, publication/effective dates, scope,
limitations and rights notes. Public access is not a general reuse license;
linked photographs, maps and commercial ledgers are not licensed for downstream
reuse by this project. No authentication/access restriction was bypassed.

AIP forward/reverse indices and AD pages count as one original edition. Mirrors,
republished government statements and multiple quoted spans do not multiply
independent confirmation. Several source families remain dependent or partly
unestablished per claim. The independent technical check re-extracts citations
from the original bytes; human acceptance is still required for their meaning.
