# Global airport history discovery

This repeatable research layer discovers worldwide history from source revisions.
Candidates are neither resolver input nor a limit on future coverage. Schema
3.0.0, dataset/package 0.4.0, thirteen permanent airport identities, twenty code
assignments and two name records remain unchanged. `curated-baseline.json`
freezes the complete formal dataset at merged PR #4.

Read [coverage.md](coverage.md) and [generated/summary.json](generated/summary.json)
together. Counts describe inspected source records and research transitions,
never real-world event totals or global completion percentages.

The [first verification batch](../../docs/global-verification-batch-1.md) reviews
20 existing event groups: 12 insufficient evidence, four pending independent
review, four excluded interpretations, zero admissions. Its
[claim-specific record](batches/global-1.json) and `reviews.json` are live curation
overlays. Compressed observations/queue retain their PR #5 snapshot; query applies
the overrides by default (`--snapshot` shows original state, `--queue` queries the
ranked queue). `summary.json.reviewBatches` separates review results from exported
discovery counts. `pnpm research:review-report` checks every old artifact size/hash
(including summary) and every recorded non-review input hash before writing.
It updates only review-input hashes, `summary.json.reviewBatches` and the summary
size/hash; recorded non-review hashes stay unchanged. Unexpected edits require
an explicit report regeneration, not a review refresh. After intentional generator
changes, use `pnpm research:report --reuse-baselines` to regenerate reports and the
manifest from existing generated candidates and verified exported baselines. This
option never reads source Git objects or requires source mirrors/Keepraw-Fly input
downloads. Neither command fetches or scans source repository history.

## Run

Use Python 3.12+ (standard library only), Git, Node 24 and pnpm 10.14.0.

```sh
# Only this explicit research entry point accesses the network.
pnpm research:fetch
# Offline, using local pinned Git objects:
pnpm research:scan
pnpm research:report
pnpm research:validate
pnpm check

python3 scripts/discovery/query.py --code JNG --source ourairports
python3 scripts/discovery/query.py --country CN --type possible_relocation --limit 0
python3 scripts/discovery/query.py --queue --status pending_review
```

Downloads and resumable SQLite caches live in ignored `work/`. Initial scans take
minutes and several GB for full mirrors/caches. Fetch never moves source pins.
To extend coverage, inspect upstream changes/licenses, update the full SHAs in
`sources.json`, fetch explicitly and scan. A descendant revision reuses completed
edge transactions. Rewinds or source/parser configuration changes require a fresh
`--cache` directory. Bump the scanner engine version when changing its semantics.
Review inputs live outside caches in `reviews.json` and `legacy.json`; orphaned
review IDs fail validation.

All main-ancestor file revisions and every merge-parent diff are enumerated, with
no annual endpoint sampling. Unchanged rows are carried through verified CSV
diffs; schema changes and incomplete multiline patches fall back to full parsing.
The target snapshot is independently parsed. Normal runtime, tests, validation
and builds never fetch research data.

## Source boundaries

`sources.json` pins repository, commit, path, entity key, license and adapters.

- **OurAirports:** complete exported `airports.csv` Git history from November
  2021, including closed sites. Daily snapshots do not expose database edits
  reverted between exports. Opening, closure and code-effective dates are absent.
- **datasets/airport-codes:** all revisions of the derived CSV, raw
  `archive/data.csv`, and both earlier CSV paths. The initial file changes from
  a full export to a filtered/reduced-column table, then moves/disappears. Those
  row removals are representation changes, not mass closures. Earlier snapshots
  are sparse. This is an OurAirports derivative, not independent corroboration.
- **airportsdata:** all airport CSV revisions plus the city-code table. Its
  `icao` field includes pseudo identifiers. Operational coverage is not a ledger
  of closed sites or past allocations. City membership remains a separate type.
- **mwgg/Airports:** earlier upstream JSON history, including malformed versions
  and duplicate keys. Ambiguous overwrites are rejected, and each blocked
  comparison is quarantined explicitly. Valid later snapshots resume without
  inventing a transition across a gap.

`source-assessment.json` records actual Wikidata dump/API probes, sizes, revisions
and limitations. No global Wikidata history scan or worldwide official-notice
archive scan is claimed. Existing official evidence and its claim-specific
primary/secondary distinctions are preserved. Opening evidence never silently
becomes direct code-allocation evidence.

All fields are compared. `icao_code`, `gps_code`, `ident` and local identifiers
remain distinct. A new column is a source revision, not thousands of allocations
on the commit day. Historical coordinate text stays verbatim: order/format edits
are not automatically decoded as physical moves. A numeric shift of at least
five kilometres raises a possible-relocation flag but may be a correction. Name
edits may be spelling, translation, city/operator naming or official renaming.

## Registry and identity

Source candidates carry stable IDs, external keys, original normalized field
transitions, country/city/name/code context, every observing commit and before/
after blob, tentative types, unknown event dates, evidence classification,
matching results, status, gaps, conflicts/exclusion reasons and next action.
The searchable `context.codes` list includes related identifiers from all
namespaces; raw field names and the structured code index keep IATA, ICAO,
GPS/local identifiers separate. Code-only matches remain tentative.
`observedAt` is a source committer timestamp, never an effective event boundary.
Commit + blob + pinned repository identifies reproducible source content.

`cand_<hash>` hashes source ID, external key and exact transition. Repeated
occurrences retain all observations under that lead; inverse changes get another
ID. IDs do not depend on rank, line order, run time or moving HEAD. These are
research IDs, never permanent `airportId`s. The old reduced tables use numeric
IDs when present, otherwise explicit code/country/name composites; a composite
does not assert physical continuity.

`*.entities.jsonl.gz` retains all observed external identities, including deleted,
closed and codeless records. Helipads, seaplane facilities and private strips stay
in research scope if they can occur in flight records. Absence from a current
IATA directory never excludes an old airport. The current resolver still accepts
only IATA/ICAO and date: local-ID/code-free records require later matching policy
and independently reviewed physical identities.

Numeric OurAirports cross-references match curated permanent identities directly.
Code-only matches are explicitly possible matches. Equal codes never prove equal
physical identity. Deleted/renamed source keys are not automatically merged.

## Deduplication and review

`duplicate-groups.jsonl.gz` groups the same numeric OurAirports identity and
identical normalized transition across exports. Derived `ident` keys map only
when unique. All member IDs and observations survive, including recurrence.
Groups are research transitions, not proven events or merged validity intervals.
Other shared codes appear in `cross-source-code-index.jsonl.gz` as work queues.

`code-links.candidates.jsonl.gz` finds every within-source code attached to
multiple external entities over inspected versions. These can be transfers,
duplicates, corrections or historical conflicts; simultaneous validity is not
inferred. Pseudo-ICAO limitations remain visible. `verification-queue.jsonl.gz`
ranks all qualifying code replacements, coded coordinate shifts and status
changes. Its first twenty entries are one batch, not the discovery scope.

All thirteen PR #3 candidate groups, including eight deferred cases, and five
later name/city/corporate/terminal leads survive in `legacy.json` and the unified
`legacy-links.jsonl.gz`. The old manual list is not machine discovery input.

Edit `reviews.json` by candidate ID to track `pending_investigation`,
`insufficient_evidence`, `pending_review`, `ready_to_admit`, `excluded` or
`already_curated`, plus conflicts, gaps, exclusion reason, next action and related
groups/leads. Source edits stay pending/indirect. Independently reviewed claim
evidence belongs in the admission review; no research command writes formal data.

Review physical identity, IATA, ICAO, official name, closure/reopening and
replacement separately. Obtain code-specific primary implementation/allocation
evidence and dated observations, and resolve contradictory dates. Opening dates
do not allocate codes; city renames do not rename airports; terminal openings do
not create physical sites. Apply the whole-interval `primary_direct`, `indirect`
and `continuity_inference` rules in [docs/evidence.md](../../docs/evidence.md).
Name and code timelines remain independent.

## Coverage and audit

Each source report counts current rows/types/code fields, historical external
records, commits, comparisons, distinct file versions, parsed row-version totals,
candidate types/countries/observation years/statuses, repeated observations and
format adapters. `*.gaps.jsonl.gz` lists every comparison blocked by an invalid
endpoint. `uniqueFileVersions` includes unparsed versions and a zero-row deleted
file version when present. `parsedFileVersions` and `recordVersionsProcessed`
exclude unreadable contents. Row-version totals count records represented in all
distinct parsed snapshots, including unchanged rows carried through verified
diffs, rather than distinct airports or full CSV reparses.

`year-country-coverage.json` measures country presence in the latest available
parsed revision of each observation year, with its exact commit. This regional
denominator does not replace the all-revision scan. Missing years have no measured
coverage. Candidate year is the first observing revision's calendar year, not the
event year. Missing country/continent stays explicit. Type totals overlap.

Gzip headers omit clocks/filenames. Sixteen stable hash-prefix shards bound each
candidate artifact. Full unchanged worldwide snapshots are not copied into the
formal database. `manifest.json` fixes artifact hashes/sizes and generation-input
hashes. Offline validation streams every shard and checks IDs, counts, matches,
parse gaps, statuses, versions and unchanged formal data. Tests cover intervening
changes/reversals, recurrence, incrementality, curation retention, merge history,
deletion, multiline CSV, duplicate JSON keys, explicit format repair, deterministic
output and quarantine without bridging an unreadable revision.

Source licenses are retained in [licenses/](licenses/) and
[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md). MIT extracts are not CC0.
Copyrighted publications remain links and independently written factual notes.
