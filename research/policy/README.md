# Evidence policy review, engine 1.0.0

This is an offline, deterministic admission preparation workflow. The policy is
**draft** and both authorization registries are empty. No new formal fact is
admitted. Start with [the reproducible Chinese report](generated/审核报告.zh-CN.md)
and [the exact authorization proposal](generated/authorization-proposal.json).

`policy.json` defines the versioned evidence predicates and exclusions.
`policySha256` is SHA-256 of UTF-8 canonical JSON (sorted keys, compact separators,
unescaped Unicode), excluding only `policySha256` and lifecycle `status`.
Authorization separately binds that rules hash, policy ID/version, scope hash and
the executable SHA-256 manifest from `policy_executor.py`. Every critical evaluator,
original parser/verifier, gate, schema, resolver and locked dependency file is bound.
Changing executable bytes invalidates the grant even when the JSON/version is unchanged.
Report prose and test harnesses are outside this execution manifest. Changing a threshold invalidates the grant; changing lifecycle status cannot
authorize a policy without the separate owner record. Disabled policies fail closed.

`input-lock.json` pins a published snapshot from the current formal dataset,
its data/schema version and main commit, research proposals, dossiers, reference
indexes, citations and executable gate inputs. Old research products retain their
original baselines. `freeze` explicitly prepares a new batch from current formal
data; it cannot use an unreleased or mismatched snapshot. The frozen bytes must
match `baseCommit:data/airports.json`, and that commit must be in `origin/main`
history. Preparation requires current formal bytes to equal that published baseline.
**Replay reads the frozen snapshot as old data and the updated formal database as
the candidate**; those two files must not be confused. A new candidate cannot be
frozen as its own published baseline. The original admission gate still rejects
any changed/deleted/duplicate published record.

The intake reads only existing research products and reference indexes. It
deduplicates admitted facts by scheme/code/physical ID, unifies proposals by
permanent assignment ID, checks competing physical IDs and reference location
hypotheses, and rejects inconsistent source hashes across pipelines. The two
supplementary AIP editions have their own publisher, archive edition, component
amendment/publication dates and actual acquisition timestamps. Edition anchors
are real same-archive AD metadata, never directory timestamps or specimen covers.
Repeated bytes do not count as different originals; different editions do not
become different publishers. All unsupported outside periods remain unknown.

`screening.json` records the finite corpus inspected by Codex, with no human
reviewer. It is an input, not an authorization or proof of all-history absence of
conflicts. A missing screen, competing site, changed ARP, unresolved explicit
conflict or unsupported assumption blocks automatic execution. Reference lookup
screens for competition; name/code/proximity alone never merges identities.
An accepted simple-site mapping requires repeated official names and independently
converted ARP against an existing canonical permanent physical hypothesis.

## Reproduce

```sh
pnpm policy:validate
# Rebuild only this small review, not the global research queue:
pnpm policy:build
# Explicit, networked recovery to ignored work/, checking every locked hash:
python3 scripts/evidence/policy_review.py fetch-originals
# Independently re-extract all ten private components and replay every citation:
python3 scripts/evidence/policy_review.py originals
# Produce deterministic, public metadata-only verification records from actual bytes:
pnpm policy:originals
# Explicit offline receipt replay; does NOT fetch or hash original bytes here:
pnpm policy:offline
```

The build writes pending candidates, a separately labeled resolver simulation,
per-record audit results, immutable content-addressed low/medium batches, actual
resolver measurements and the Chinese report. Simulation `verified` states have
no admission authority. The production `resolveAirport()` and name resolver check
published answers, new uncertainty and conflicts separately. Tests simulate grants
only in memory; they never modify either real registry or assert human source reading.

## Activate once, then propose automatically

The owner can approve the exact text in `authorization-proposal.json` in a GitHub
issue comment. The URL must identify a comment by `keepraw`, GitHub user ID
49091395. The activation CLI reads GitHub, checks the actor and exact text, and
records URL, date, original text SHA-256, policy/scope/executor hashes and recorder. It never
posts a comment. A plain JSON claim to be keepraw is not an activation input.

```sh
# FUTURE ONLY, after the owner's exact policy grant:
python3 scripts/evidence/policy_review.py activate --authorization-url OWNER_COMMENT_URL
# After data/research advances, prepare a fresh independent formal baseline:
python3 scripts/evidence/policy_review.py freeze
pnpm policy:build
python3 scripts/evidence/policy_originals.py verify --fetch
python3 scripts/evidence/policy_review.py admit --output work/policy-admission-unique
```

The last command re-evaluates everything, validates the owner and executor grant,
actually reads/replays the private originals and runs the **existing** `validate_admission()` with a restricted
`policy_context`. That gate retains source/claim linkage, primary provenance,
schema stability and immutable-record checks. The context is recomputed and
compared to the exact dataset, batches and dossiers; caller receipts cannot enlarge
the selection. The schema/semantic and resolver gates run before writing any
proposal. Output is limited to a new ignored `work/` directory. An empty successful
batch is not an admission. No CLI writes formal data, pushes, merges or releases.

After authorization, copy the validated bundle to `research/admissions/NEW_VERSION/`,
its exact `proposed-data.json` to the proposed formal database, and set the package
version to that candidate version. Keep the existing frozen baseline and receipt;
do not run `freeze` against the unmerged candidate. `pnpm validate:admission` now
automatically replays that exact bundle through the original admission CLI against
the frozen old data, including the real schema, evidence and resolver gates. Run
`pnpm check` and retain all previous published snapshots. No per-record owner
grant is needed for low-risk records. GitHub final merge remains the owner's action.
As with the existing human approval files, offline authorization replay trusts
the owner-reviewed repository registry; it is not a cryptographic human signature.

## Medium batches and exceptions

Each medium batch includes the complete IDs, exact candidate records/physical
attributes, windows, links/hashes, reasons and residual risks. Its digest covers
the entire record list, baseline, policy and input lock. A changed batch gets a
different digest and cannot inherit an older approval. Its real resolver effect
is in `generated/medium-coverage.json`.

```sh
# FUTURE ONLY, separate exact-batch owner grant; no ongoing policy activation:
python3 scripts/evidence/policy_review.py activate --authorization-url OWNER_COMMENT_URL --batch-sha256 EXACT_SHA
python3 scripts/evidence/policy_review.py admit --batch-sha256 EXACT_SHA --output work/medium-admission-unique
```

Batch dossiers truthfully record exact batch acceptance by keepraw and distinguish
it from automatic policy execution and personal reading of sources. A policy-only
grant cannot admit medium records. High-risk and insufficient records cannot be
selected by either automatic path; use the original human exception workflow.
Published corrections require a separately authorized, traceable correction PR.

## Rights and limits

Only original-byte hashes, links, necessary short citations and independent facts
are public. Full HTML/PDF responses and complete extractions remain in ignored
`work/`; AAI rights are retained and no chart/photo redistribution is inferred.
The complete history audit includes these new original/extraction hashes. Original
recovery is explicit and networked; ordinary CI validates locked excerpts offline
and does not claim it downloaded or personally read an original. Production policy
admission requires fresh hash-verified original replay before emitting a proposal.

This initial adapter supports AAI archive HTML and the existing research record
shapes, not arbitrary world publications. Evidence ingestion stays reviewable:
new original metadata/citations and any conflict assessment enter a normal PR,
then an authorized policy can evaluate new records without per-record signatures.
The rule engine cannot establish truth from an AI confidence score or missing
counterevidence. No UI, service, scheduler or Keepraw-Fly integration is added.

## Private originals, offline CI, and the real rehearsal

`verification/low.json` and `verification/medium.json` are deterministic records
created only after actual private byte hashes, independent extractions and every
minimal citation were checked. They bind baseline, inputs, executor and the exact
source/quote set. They contain no original or full extraction. They are mechanical
attestations reviewed with the repository, not cryptographic evidence that another
process downloaded the publication or that a human read it.

`admit` always requires the actual originals. An admission bundle carries the
verification record and its hash. Offline admission replay validates the entire
record against the locked inputs and regenerates decisions and candidate bytes;
it explicitly reports `originalBytesObtainedHere=false`. Missing, stale or altered
records fail closed. Ordinary CI claims only this offline replay. The separate
**Explicit private original verification** workflow is manually dispatched when
fresh acquisition in GitHub is wanted: it actually fetches the originals, fails
on unavailability/hash changes and compares regenerated receipts. It neither
caches nor uploads copyrighted originals. No network verification is claimed
unless that workflow actually ran successfully.

```sh
# Full local end-to-end exercise, including actual private bytes:
pnpm policy:rehearse --live-originals
# Full CI-compatible exercise from recorded verification, no raw-byte claim:
pnpm policy:rehearse
```

The exercise uses a disposable shared Git clone, copies only public working files,
and injects a distinct `policy-rehearsal` / ID 0 authority and fixture transport.
It calls activation, evaluates the real VEHO/VASD/VOKN records, prepares the bundle,
updates only the isolated formal database/package to 0.10.0, invokes the original
admission CLI and real resolver, then runs the **entire candidate `pnpm check`**.
The original-byte dependency is live locally or explicitly recorded/offline in CI.
There are no gate, evaluator or resolver mocks. Production rejects this test grant.
No test-authority switch exists in production CLI arguments or caller JSON.
No test candidate, grant or activation is committed as real formal data. Both real
registries and the real draft policy are hashed before/after and remain unchanged.
