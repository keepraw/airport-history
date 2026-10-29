# PR13: direct historical evidence and pending record proposals

**Historical PR13 snapshot:** no facts were admitted by this demonstration.
Its immutable formal input is 0.7.0, with 23 physical airports, 40 assignments,
3 historical names and 70 sources. The later, separate
[0.8.0 admission](../../admissions/0.8.0/README.md) records explicit user approval
of only four physical identities and three adjusted/retained ICAO windows.
All original proposals, dossiers, source evidence and blocked drafts below remain
unchanged and pending as the original research snapshot; they are not live approval records.
PR #12 was confirmed merged on 2026-10-28 at 14:00:48 UTC; this branch starts at
latest main `8fecd4e6cbc322a23246ebaf2f2f0041c902e505`. Its BTS corpus and
23-publication FAA closure search were not reacquired or expanded.

This demonstration adds actual historical FAA identifier directories, paired
regulatory physical locations and original event/service notices. It prepares
concrete dataset records and per-record judgments through the existing review
workflow. It cannot accept its own judgments.

## Actual progress

| Measure | Result |
| --- | ---: |
| Newly acquired useful original publications | 15 |
| Additional original retained as a rejected unsigned policy sample | 1 |
| Issuing-authority families | 2 (FAA and NOAA/NWS) |
| Existing physical-history cases with directly dated source assertions | 4 |
| Retrospective physical-event facts with an explicit actual day | 1 |
| Direct first-allocation/withdrawal boundary facts | 0 |
| Physical airports in the pending dataset proposal | 6 |
| ICAO continuity intervals in that proposal | 6 |
| IATA intervals proposed | 0 |
| Additional blocked physical/ICAO drafts | 2 / 2 |
| Existing candidate groups investigated | 9 |
| Human-approved records / formal admissions / formal coverage increase | 0 / 0 / 0 |

The four cases are Panama City, St George, Williston and Cleveland. A directly
dated assertion is not necessarily an executed physical event: statutory notices
can announce future events, TAF effectiveness dates weather dissemination, and
an airspace rule dates regulatory airspace. Only the former St George
**2011-01-15 decommissioning** is retrospectively stated with an exact day here.
Panama City's later FAA confirmation dates actual new-site operations only to
**May 2010**, independently of its advance notice's announced May 22/23 days.
The count of four must not be described as four confirmed exact-day moves.

The 15 useful originals comprise two historical identifier editions, two
historical airspace/location editions, three TAF notices, seven FAA event/rule
publications and one later station-list maintenance notice. A document can be
useful as negative/context evidence without supporting admission. These are
original publications, not 15 independent confirmations of each event. Repeated
paragraphs, multiple extraction spans, channels and requested changes do not
create independent corroboration.

## What is concretely reviewable

- [Readable evidence index](generated/evidence-index.md): all 16 originals,
  original hashes/access timestamps, and 35 exact page/span citations with the
  proposed factual judgment and its scope.
- [Pending dataset](generated/proposed-data.json): all frozen formal records
  unchanged, plus six proposed physical IDs, six pending ICAO assignments and
  eleven pending source records. Its `0.8.0` version is reserved inside this
  original proposal only; it is distinct from the separately approved formal `0.8.0` dataset.
- [Record dossiers](generated/dossier.json): twelve pending judgments,
  including separate boundary and continuity assessments for every interval.
  `reviewer` is null and `decision` is pending throughout.
- [Cases](generated/cases.json), [blocked drafts](generated/blocked-record-drafts.json)
  and [exact metrics](generated/metrics.json).
- [Existing-format pending packets](generated/review-packets.jsonl.gz) preserve
  all six claim reviews. Each proposed record has one owner among existing
  candidate events; related events point to that owner without duplicating
  proposed admissions. No candidate ID or completed review was invented.

| Physical site / proposed ICAO indicator | Latest start bound | Earliest end bound (exclusive) | Important limit |
| --- | --- | --- | --- |
| Panama City-Bay County / KPFN | 2009-05-08 | 2010-05-22 | Stop before announced closure day; withdrawal unknown |
| Northwest Florida Beaches / KECP | 2010-05-24 | 2014-07-24 | TAF, actual month of opening and FAA airport row are separate facts |
| Former St George / KSGU | 2009-05-08 | 2011-01-12 | Conservative observation cutoff, not code withdrawal |
| Replacement St George / KSGU | 2011-12-16 | 2014-07-24 | KDXZ intermediate history retained; no January KSGU transfer asserted |
| Sloulin Field / KISN | 2009-05-08 | 2014-07-24 | No extrapolation across unobserved 2014–2019 allocation history |
| Williston Basin / KXWA | 2019-08-30 | 2020-05-06 | Administrative designation can precede operational opening |

First allocation and final withdrawal remain unknown: every `validFrom.earliest`
and `validTo.latest` is null. All whole intervals are **continuity_inference**,
not `primary_direct` daily histories. The FAA's section 1-4-1 explicitly defines
international indicators for contiguous-US **airports** as K plus the three-letter
FAA identifier. This scoped authority rule is cited alongside actual airport
rows; it is never applied to IATA, arbitrary GPS fields, navaids, Alaska, or a
bare matching string. Section 1-2-6 itself explains that user groups can set
different assignment effectiveness dates. An edition date is an observation
bound, not an exact first-allocation date.

**St George still has a boundary blocker.** Both KSGU proposals have open possible
bounds spanning the other site. Even a hypothetical review-state change alone
would leave KSGU queries uncertain. Its two drafts need additional code-specific
end/start evidence before they can increase resolved coverage; the validator and
resolver were not weakened to conceal this. Tests demonstrate this limit, as
well as four single-site keys resolving in a test-only hypothetical reviewed
state. No hypothetical acceptance is written to any evidence artifact.

Cleveland has two concrete physical/interval drafts outside the proposed dataset.
The 2013 FAA rule says Hardwick has already closed, while the 2014 statutory
notice sets permanent closure to March 14, 2014 and says tenants/operations have
moved. Operational closure versus administrative release is a plausible
explanation, not an established finding. There is no existing transition group
for these two reference records. Both the chronology and review ownership need
resolution before proposing admission through the current gate. No fixed
three/five-airport limit caused the deferral.

## Evidence distinctions that matter

The official locations separate Panama City's sites by **19.653 km**, St George's
by **9.499 km**, Williston's by **12.239 km**, and Cleveland's by **3.128 km**.
These are identity anchors from named regulatory airport blocks, not runway
footprints or code dates. The 2012 St George property notice's approximate
15-mile/east wording disagrees with the regulatory locations; that geographical
problem stays explicit. It does not overwrite either source or the formal data.

- **Source repetition:** one original-publication key per issuer/document;
  mirrors and multiple spans cannot count as independent confirmations.
- **Identity ambiguity:** the reused KSGU observations deliberately retrieve
  associations to the wrong physical-site hypothesis as well as useful matches.
  All 19 associations survive inspection; 3 groups have association disagreement
  and 7 have identity ambiguity, with overlapping categories.
- **Unresolved historical chronology:** Cleveland retains both official closure
  statements. This is not counted as a confirmed overlapping code allocation.
- **Directory revision/context:** Williston's 2019/2020 coordinate points differ
  by roughly 130 m at the same new airport; the later rule explicitly describes
  a database correction. The 2023 RTMA station-list replacement KISN→KXWA is
  maintenance context, not a new 2023 airport relocation or allocation date.
  There is one coordinate-revision context and one station-list context, but
  zero adjudicated directory corrections or confirmed historical code conflicts.

NWS TIN10-63's printed publication year, TIN10-18's weekday, and SCN23-112's
prospective effective year are internally inconsistent. The original text and
[source date warnings](assessments.json) are retained; no date is silently fixed.
The January 13 St George claim in the unsigned sample waiver is excluded from
actual-event/boundary evidence. KDXZ's authenticated ICAO allocation/withdrawal
ledger, IATA histories and exact executed opening days remain missing.

PR12's metrics now name its 1,580 groups `associationConflictGroups` and its
5,256 groups `identityAmbiguityGroups`, alongside
`confirmedHistoricalCodeConflicts: 0`. This corrects the reporting vocabulary;
all 20,433 original observations, matches, candidate ownership and formal data
are unchanged. Their original source lock was not replaced.

## Reproduce from the actual new authorities to the pending proposal

Node 24, pinned pnpm 10.14.0, Python standard library. Online PDF extraction also
requires Poppler's `pdftotext`; this run used 25.03.0. Regular offline CI reads
committed, separately hash-locked extractions and needs no PDF package/network.

```sh
corepack pnpm install --frozen-lockfile
# Online, EMPTY destination: refetch all 16 originals from official hosts.
# Reject any changed original bytes; authenticate each citation in fresh extraction.
corepack pnpm evidence:direct fetch --recover --output work/direct-recovered
# Or collect a separately inspectable new snapshot and feed it directly to build:
corepack pnpm evidence:direct fetch --output work/direct-new-snapshot
corepack pnpm evidence:direct build --sources work/direct-new-snapshot --output work/direct-new-proposal
corepack pnpm evidence:direct validate --output work/direct-new-proposal

# Offline: committed originals → exact source citations → physical/code judgments
# → existing candidate join → actual schema-valid pending dataset and dossiers.
corepack pnpm evidence:direct build
corepack pnpm evidence:direct validate
corepack pnpm check
```

Use a fresh empty destination for each online attempt. Fresh snapshots are never
adopted automatically. The build reads the catalog/lock and explicit Codex
judgments in `assessments.json`, reuses PR12's hash loader/many-to-many matcher and
original acquisition writer, and calls the unchanged admission implementation.
It does not pretend that parsing can decide historical identity or continuity.
The pending dataset passes the normal schema/semantic validator and is then
**rejected by the existing human-review admission gate**, as required.

A separate real online acquisition was also consumed directly with `build
--sources work/direct-end-to-end --output work/direct-end-to-end-proposal`.
Its manifest binds all sixteen freshly acquired originals and their extractions;
validation passed and its pending dataset is byte-identical to the committed
proposal. Provenance paths/access timestamps reflect the actual input snapshot.
The explicit-snapshot regression additionally proves the build uses that input
rather than silently rereading the committed source lock.

An actual full online recovery succeeded for all 16 original-content hashes and
deterministic compressed hashes, with every cited span re-extracted. The first
attempt failed on regenerated Cloudflare email-protection markup in the 2020
GovInfo HTML. The adopted original is the same official document's stable PDF;
its new lock preserves the failure. No content normalization or relaxed original
hash check was used to turn the failure into success. Other original HTML works
retain their exact byte locks. Extracted text has its own compressed/original
hashes; page/span recovery allows other Poppler versions to vary irrelevant
layout while requiring the same actual citations.

The measured offline build takes about **7.0 seconds**, peaks at **771 MiB RSS**,
and reuses the worldwide reference projection. Original archives occupy about
**47.9 MB** compressed. No new global scan or BTS statistical join was performed.
The existing reference projection dominates memory; this small demonstration is
not a claim of low-memory worldwide ingestion. Tests perform a complete,
byte-identical rebuild with network access disabled, reject changed/escaping
sources and wrong namespace/location bindings, preserve historical boundary
semantics, retain the original confirmed-overlap rejection, and compare old
queries at every frozen boundary and adjacent day.

## Human review and merge scope

Code, source archives, evidence judgments, report terminology, reproducibility
and tests can be reviewed for merge. This PR is **not** approval to merge the
pending dataset into `data/airports.json`. Human reviewers must inspect cited
originals, decide each of the six claim scopes, resolve or explicitly delimit
uncertainty, set verified source status only after review, and record real
per-record acceptance/reviewer information through the existing workflow.
Preparation dates are not review completion dates. Keep `preparationOnly` until
that work has actually occurred. Approved additions then pass
`reference:review validate`, the same schema, overlap and frozen-history gates.
A later curated edit/version change remains separate from preparing this PR.

No frozen record, interval policy, runtime resolver, UI, server, Keepraw-Fly file,
tag or release was changed. The actual accurately resolved global historical
coverage has **not increased** relative to PR12. What increased is the stock of
original, directly scoped evidence and concrete records a human can adjudicate;
claim approval, KSGU transfer bounds, IATA ledgers and the Cleveland chronology
still constrain formal growth.
