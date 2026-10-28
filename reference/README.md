# Worldwide reference and bulk historical review

Reference format **1.0.0** is a separately versioned, offline observation layer.
It contains **86,950 source records**, not 86,950 verified physical airports.
The historical layer remains **0.7.0 / schema 3.0.0**, with its 23 permanent
physical identities, 40 reviewed code assignments and 3 official-name intervals.
`resolveAirport()` continues to use only that reviewed layer.

## Reproduce the baseline

```sh
pnpm reference:build       # offline: baseline, indexes, then worldwide candidate triage
pnpm reference:validate    # strict schema, hashes, full population, namespace and link checks
pnpm test:reference        # full byte-identical rebuilds and behavioral/admission regressions
pnpm check                # all existing and new checks
```

No Git-history scan is required. The checked-in compressed CSV is the exact
OurAirports `airports.csv` at commit
`d97df1673cc5ba61a09b17ab5936091a669a04ca`, Git blob
`fdcf59f3383d63ad14afbd8d7fd8b2ca954845ca`. Its uncompressed SHA-256 is
`27c6500d0a742edece15c5aaf960e08c01df0d4356c5c86255897b5d3749ad3b`.
The source revision was observed at **2026-10-26T03:53:12+01:00**; this differs
from the curated layer's separately fixed October 25 evidence horizon.
See [source-lock.json](source-lock.json). If recovery is necessary, explicitly run:

```sh
pnpm reference:fetch
pnpm reference:fetch-timezones # only if the pinned IANA name catalog needs recovery
```

This downloads that commit's raw file and requires both hashes before replacement.
It never fetches moving HEAD. The existing inventory supplies the additional
664 records absent at the pinned snapshot, and its transition shards supply
historical identifier/name observations and location hypotheses.
`airport-codes-raw` transitions with inherited OurAirports numeric IDs additionally
retain earlier observations at matching source records, including the pre-2021
Temindung/Pranoto case. Their source IDs, blobs and ODC-PDDL-1.0 licensing remain
explicit; they do not establish an independent physical identity or confirmation.
Every reused
discovery input is hash-checked against its existing manifest. The builder also
checks snapshot identity membership against the inventory and the exact source
revision/blob/time against the existing version inventory.

Eligibility includes all seven source facility types: small, medium and large
airports, closed facilities, heliports, seaplane bases and balloonports. There is
no IATA, ICAO, scheduled-service or current-presence requirement. Malformed names,
coordinates/country/identifier values are retained with flags; unsupported types
are counted as exclusions. The pinned population has **zero exclusions**.
Missing timezone is null, rather than guessed from country or longitude.

## Query offline

```sh
pnpm reference:lookup --code JFK
pnpm reference:lookup --code KJFK --scheme ICAO
pnpm reference:lookup --code KTI             # Kratie / Techo observations: ambiguous
pnpm reference:lookup --source-id 26763      # Pranoto plus old source-location hypotheses
pnpm reference:lookup --source-id 12148      # removed, closed, code-less H&H facility
pnpm reference:lookup --name Temindung --country ID
pnpm reference:lookup --country AQ --limit 10 --offset 10
```

Combine filters with AND. `--limit 0` returns all matches; `totalMatches` and
`possibleLocationCount` always cover the full result before pagination. Name
search is a Unicode case-insensitive substring search across current and retained
historical labels. Historical labels are secondary observations, not admitted
official names. Only IATA/ICAO input is uppercased; GPS, LOCAL and IDENT searches
use the source's exact identifier spelling.

| Result status | Meaning |
| --- | --- |
| `reference_only` | One source record with one location hypothesis |
| `ambiguous_reference` | Multiple source records or multiple possible locations |
| `not_found` | No reference observation matches the filters |

All results carry `historicallyVerified: false`. They never return `resolved`,
accept a historical validity date or fall back into the historical resolver.
The response includes source revisions, licenses, observation times, raw source
IDs, flags and separately reviewed `curatedAirportIds` where safely connected.
A curated link identifies an existing physical site; it does **not** verify
every imported code or historical location at that source ID.

Python callers can add `scripts/reference` to their module search path and import
`query.lookup`, with the same filters and result shape. Code and source-ID searches read only necessary
record shards. Country searches use an index; substring name search streams the
shards without retaining the entire population. No service or external database
is used. The transient SQLite join in the bulk builder is Python's built-in
module and is removed on completion.

## Identity, provenance and data boundaries

`ref_<hash>` is a deterministic identity of **OurAirports + numeric source ID**.
`loc_<hash>` additionally identifies one exact coordinate observation. Neither
namespace creates a permanent `apt_` identity. Input ordering does not affect
these IDs. Coordinates changing in a directory do not establish a relocation.
Duplicate source records are not silently collapsed into one physical airport.

All 22 reviewed airports with an OurAirports cross-reference are linked only
when the current/last-known position is within 1 km of the reviewed reference
position. A reused source ID at another location fails this gate. Temindung has
no independent current OurAirports cross-reference and is deliberately not linked
by the old numeric ID now used for Pranoto. No IATA-only match creates a link.

The 678 source records with large source-coordinate transitions retain 750
additional location hypotheses, flagged as possible repurposing **or directory
correction**. Only explicitly changed latitude **and** longitude can reconstruct
a historical position. An unchanged axis is never filled from today's coordinates.
Other uncertain transitions retain the incomplete-location flag and original
candidate ID. Distinct coordinates can describe a correction at one site; these
counts must not be presented as numbers of verified physical airports.

IATA, explicit OurAirports ICAO, GPS, local and source-ident fields stay separate.
GPS and four-letter pseudo identifiers are never inferred to be ICAO. City-code
membership files are not imported as airport-code assignments. Historical IATA
and ICAO values carry their original candidate, before/after blob, commit and
revision-observation timestamp. Before-side values were in the **before blob**;
the later commit timestamp is a transition observation, not proof of code use on
that date. Their association with a physical location remains unverified.

For removed records the inventory's removal `afterBlob` may no longer contain
the retained row. The builder instead links a matching pre-removal blob to an
earlier observed revision. If unavailable it retains inventory-only provenance
and a null row-observation date. Neither removal nor source type `closed`
establishes a closure date.

Timezone enrichment uses only present-at-target `airportsdata` inventory rows at
its pinned revision, with a unique resulting zone, same country, a matching
explicit ICAO/GPS/source identifier and a position within 1 km. Conflicting zones
retain all observations and a null selected value. The upstream `icao` field
contains pseudo identifiers; it is used for matching, **never** for importing
ICAO assignments. This is an additional reference attribute, not independent
historical confirmation. [Upstream MIT notices](LICENSE-airportsdata) are retained.

Timezone-name validity uses the checked-in **IANA tzdb 2025b** catalog of 598
Zone/Link identifiers, rather than the host's installed timezone database. This
includes `America/Coyhaique` even on older hosts. The exact IANA release archive
URL, SHA-256 and source members are pinned in `timezones-lock.json`; the recovery
command validates that hash before reconstructing the sorted catalog. Ordinary
offline builds need neither that archive nor host tzdata. This catalog validates
names only; it does not assert historical timezone rules or airport timezones.

The strict [record schema](../schema/reference-record.schema.json), reference and
triage manifests, exact [metrics](generated/metrics.json) and source metadata
are versioned in Git. Sixteen compressed record shards and separate namespace
indexes avoid requiring a monolithic JSON load.

## Bulk historical review and admission

The builder examines **all 1,240,058 existing source-transition candidates**.
It selects every IATA change, nonempty explicit ICAO change, possible relocation,
closure/reopening and name-label change. It mechanically excludes empty ICAO
column backfills; unrelated revisions are deferred. Source additions/removals
without one of these signals remain in the original discovery registry. Selection
is by documented event rules, with no numeric sampling limit.

The existing exact cross-source duplicate groups are reused. Shared names/codes
alone never combine events. Each selected candidate belongs to exactly one group;
all original candidate IDs and observation counts remain auditable in the original
shards. Recurring transitions are grouped research leads and keep their source
observation counts; this is not a proven count of distinct real-world events.

OurAirports and `datasets/airport-codes` variants are one source family.
`airportsdata` and `mwgg` lineage is unestablished for historical corroboration;
they do not automatically supply independent confirmations. Groups initially
have zero independent historical confirmations, no event date, and no proposed
validity interval. Existing reviewed candidates keep their prior review ownership.
The separate code-reuse lead file detects geographically distinct code
associations at least 5 km apart, including same-ID location changes, while
retaining correction/repurposing as alternatives to true historical reuse.

Export **all** eligible groups into as many compatible review batches as needed:

```sh
pnpm reference:review prepare \
  --output work/bulk-review \
  --date 2026-10-28 \
  --base-commit 4b3e80fc47c18a9a39f8716a0c2caf83c624351a
```

Use an empty output directory. Each batch has at most 20 events and passes the
existing `validate_batch_series` gate; there is no five-airport or total-event
ceiling. The export includes a hash manifest. These are explicitly
`preparationOnly` / `pending_review` packets, not completed human investigations.
No source access outside the hash-checked local artifacts is claimed.

For a supported subset, complete the existing six claim-specific reviews, add
actual authoritative source records, mark supported events `ready_to_admit`,
remove `preparationOnly` after review, and populate their admitted IDs. Prepare a
proposed historical dataset with a new historical dataVersion and an evidence
dossier. A dossier is an array with one entry for each added airport, assignment
or name; for example (placeholders are not evidence):

```json
{
  "recordId": "<proposed permanent record ID>",
  "reviewer": "<reviewer identity>",
  "decision": "accepted",
  "boundaryAssessment": "<claim-specific uncertainty, bounds and dated support>",
  "continuityAssessment": "<whether/why continuity is inferred; evidence horizon>",
  "observations": [{
    "sourceId": "<verified primary source in both review and proposed dataset>",
    "observedOn": "<YYYY-MM-DD>",
    "sourceFamily": "<original issuing authority>",
    "independentOriginal": true,
    "claimScope": "<exact code, identity or official-name observation>",
    "basis": "<original factual annotation explaining what this publication proves>"
  }]
}
```

Validate the proposal through the existing historical schema/semantic validator:

```sh
pnpm reference:review validate \
  --batches work/reviewed-subset \
  --dataset work/proposed-history.json \
  --dossier work/evidence-dossier.json \
  --output work/validated-history.json
```

The gate requires cross-batch uniqueness (also against existing reviews), exact
agreement between admitted IDs and dataset additions, preservation of all existing
records, explicit human acceptance, dated original primary observations linked to
the claim and record, and boundary/continuity assessments for intervals. Prepared
packets and known directory families cannot satisfy the gate. Only then is the
ordinary historical schema/evidence/overlap validator invoked. The output remains
a reviewable proposal; the command refuses to overwrite `data/airports.json`.
The eventual reviewed repository edit must also update the ordinary package/data
version, research baseline/reports, tests and frozen baselines under their existing
rules. Follow-ups to existing review groups use the existing follow-up mechanism.

Software validates structure, links and explicit review declarations; it cannot
determine whether a linked publication actually supports the prose claim. That
claim review, correction-versus-relocation judgment, original-publication lineage
and unknown historical boundaries still need human evidence assessment. A single
official dated observation can bound uncertainty without establishing first
allocation, closure or continuity. Do not manufacture those dates from commits,
opening ceremonies or passenger moves.

This PR makes **zero** new verified historical admissions. The reused corpus is
secondary directory evidence, and no new independently reviewed authoritative
historical evidence was obtained. The baseline and scalable review workflow are
usable immediately without weakening KTI, DKR, ROV or future-booking safeguards.
