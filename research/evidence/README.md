# Primary publication evidence pipeline (1.0.0)

This is a reproducible **research attachment** layer. It adds no `apt_` identity,
assignment, historical name, accepted reviewer or historical coverage. The reviewed
dataset remains **0.7.0: 23 physical airports, 40 assignments, 70 sources**.

Two working online collectors replace the previous directory-only bottleneck:

* BTS Master Coordinate: the complete official CSV, **20,295 historical attribute
  rows**, acquired through the real ASP.NET download form, not an invented static URL.
* FAA Federal Register: **23 original agency publications**, all pages of the
  targeted `"airport" "permanently closed"` query through 2026-10-28. The public
  metadata API discovers documents; GovInfo supplies each original publication.
  This is a targeted corpus, not all FAA airspace notices or all closed airports.

The **24 original publications** are two issuing-authority families, not 20,433
independent confirmations. FAA proposed/final notices can repeat one underlying
statement. GovInfo and FederalRegister are publication channels for the same
original, not independent corroboration. Underlying fact lineage remains an
explicit claim-review question, even for an official issuer.

## Reproduce

Node 24, the repository's pinned pnpm installation, Python 3 standard library:

```sh
pnpm install --frozen-lockfile
pnpm evidence:build          # OFFLINE: checked-in originals + existing PR #11 indexes
pnpm evidence:validate       # strict schema + hashes + retention + review ownership
pnpm test:evidence           # includes full byte-identical offline rebuild
pnpm reference:review evidence --output work/primary-review-new
pnpm check
```

Use an empty directory for packet export. This exports only the **11,770 groups
with new evidence attachments**, in 589 existing-format batches of at most 20;
it does not recreate all 4,416 preparation packages. Fourteen groups already
owned by earlier reviews are retained separately in
`generated/existing-review-attachments.jsonl.gz`. Their disposition is unchanged;
follow the existing follow-up workflow when a human investigates them. The
admission implementation is unchanged, including all six claim reviews, explicit
human acceptance, interval/continuity assessment, schema and regression gates.

Online operations are separate and opt-in:

```sh
# Recover originals only if upstream still has the identical content.
pnpm evidence:fetch --output work/primary-recovery
# Collect a new snapshot, including changed/moving content, into an EMPTY directory.
pnpm evidence:fetch --discover --output work/new-primary-snapshot \
  --cutoff 2026-10-28 --base-commit d520136e82a348ff6f3429f9c879672ad1dfa5b8
```

Discovery writes a new lock for inspection; it never overwrites the checked-in
one. Recovery rejects changed original hashes. BTS ZIP generation can change its
container bytes; the lock records that transport hash, while recovery checks the
actual CSV member hash and reconstructs the pinned deterministic gzip bytes.
Both online discovery and online recovery were actually run on the 24-publication
corpus; the recovery regression also checks both original and compressed hashes.
Content SHA-256 is the version when the issuer supplies
no revision date. Access timestamps record actual retrieval; offline rebuilds
preserve them. The collector records failed individual FAA retrievals instead of
inventing success. Network failures during the search/BTS bootstrap fail visibly.

## What is traceable

`source-lock.json` binds issuing authority, title, original-publication key,
publication URL, retrieval URL, content version/hash, publication date, regulatory
effective date, actual access timestamp, family, license and limits. Input hashes
cover both compressed files and original bytes. Each observation gives a CSV
record/authority ID or character span in the original GovInfo PRE block, name,
typed codes, country, independently bound coordinates, supported facts and limits.
Original publication headers also retain the printed Federal Register pages.

The input CSV and government-authored Federal Register HTML are US federal
factual works under [17 USC 105 / GovInfo policy](https://www.govinfo.gov/about/policies).
Issuer attribution is preserved. The collectors do not fetch third-party docket
attachments, copyrighted charts, photos or commercial allocation ledgers. This is
not a claim that every attachment or linked publication is public domain. See also
[BTS policies](https://www.bts.gov/policies).

`generated/observations.jsonl.gz` preserves every parsed observation, including
unparsed documents. `matches.jsonl.gz` is many-to-many. `unmatched.jsonl.gz`
retains every observation without a candidate match. `review-packets.jsonl.gz`
contains source metadata and factual summaries, not human approvals. The manifest
locks the input population, source originals, matching implementation and outputs.
No source-transition Git history is rescanned.
The legacy packet field `reviewedOn` denotes the preparation date while
`preparationOnly: true` remains set; it does not record a completed human review.

## Matching and claim boundaries

The join reuses the existing 88,330 candidate-group registry and 493 geographically
distinct code leads. It considers explicitly typed codes, country, reference-site
hypotheses, retained historical names and physical distance. Exact names and
cross-namespace code strings retrieve candidates; they cannot confirm identity.
High confidence requires the same country, compatible name and a location within
2 km of a reference hypothesis. A position beyond 5 km or country disagreement is
retained as a match conflict; weak identity clues remain ambiguous. Multiple
location hypotheses remain flagged. These are **association scores**, not event
verification scores. Even a good association can attach to several different
events at the same reference record, requiring claim-specific human review.

The FAA parser binds a coordinate only to an immediately adjacent name/location
block. A tower closure, runway closure, rejected proposal or hypothetical statement
cannot become an airport-closure assertion. Generic facility names are excluded.
Explicit named closure statements retain year bounds or an unknown start bounded
by the publication; the rule's effective day is never used as the closure day.
The current parser deliberately retains anaphoric/unrecognized statements for
inspection instead of guessing their subject. Directory-update wording is
flagged as context, not automatically adjudicated as a directory correction.

The BTS code field is **USDOT**, explicitly described by the issuer as its own
three-character designation. A lexical match to IATA remains flagged across
namespaces. `AIRPORT_START_DATE`/`AIRPORT_THRU_DATE` describe statistical attribute
intervals, not operational opening/closing dates or IATA allocation. `AIRPORT_ID`
can span physical relocation. UTC offsets are not IANA timezones. Publication
and historical observation dates are null when not available; the access time
does not fill those gaps.

Six observations demonstrate why the distinction matters: BTS puts the new DEN
attributes at 1993-09-01 versus the reviewed site interval beginning 1995-02-28;
HKG at 1998-07-01 versus 1998-07-06; IST/ISL at 2019-04-01 versus 2019-04-06;
NQZ at 2020-06-01 versus 2020-06-08; RMO at 2024-01-01 versus 2024-01-18.
These are **different claims**, retained as boundary warnings, not grounds to
overwrite existing history or evidence that the reviewed history is wrong.

## Actual result and scaling limits

See `generated/metrics.json` for exact counts. The run retains **20,433
observations**, associates **18,101** of them with **11,784 groups**, and retains
**2,332 unmatched observations**. **1,580 groups** have a conflicting association,
**5,256** have an ambiguous one; those categories can overlap. There are **46
groups with directory-update context**, **zero adjudicated corrections**, and
**186 of the 493 priority code leads** have attachments (483 candidate groups).
Three explicit closure observations concern the same Davis Airport statement in
two FAA publications; they are not three independently proven closure events.

The measured offline run takes about **34 seconds**, roughly **610 observations/s**,
with peak RSS about **0.8 GiB** on this worker. A compact projection avoids retaining
all repeated directory-transition provenance, reducing an initial 1.2 GiB peak.
The complete table and 23-document targeted corpus demonstrate more than a
hand-picked airport sample, but do not establish global historical-event coverage.
Memory still includes the worldwide reference projection and group registry;
larger ingestion should use disk-backed joins/country partitions. FAA parsing is
conservative and English-specific; five documents remain unparsed. Public endpoint
rate limits and changes are another bottleneck. Above all, authoritative code
allocation and human physical/boundary review remain the admission bottleneck.

The real Davis closure statement supports a year-bounded closure investigation;
it does not identify a unique permanent physical identity, establish its IATA
history or justify an assignment interval. No record in this run has received
independent human acceptance, so **formal historical additions and query-coverage
increase are both zero**. This is a running source-to-review pipeline, not an
automatic source-to-fact importer.
