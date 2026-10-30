# Evidence policy review, engine 1.0.0

This is an offline, deterministic admission preparation workflow. The policy is
**draft** and both authorization registries are empty. No new formal fact is
admitted. Start with [the reproducible Chinese report](generated/审核报告.zh-CN.md)
and [the exact authorization proposal](generated/authorization-proposal.json).

`policy.json` defines the versioned evidence predicates and exclusions.
`policySha256` is SHA-256 of UTF-8 canonical JSON (sorted keys, compact separators,
unescaped Unicode), excluding only `policySha256` and lifecycle `status`.
Authorization separately binds that rules hash, policy ID/version and scope hash.
Changing a threshold invalidates the grant; changing lifecycle status cannot
authorize a policy without the separate owner record. Disabled policies fail closed.

`input-lock.json` pins a published snapshot from the current formal dataset,
its data/schema version and main commit, research proposals, dossiers, reference
indexes, citations and executable gate inputs. Old research products retain their
original baselines. `freeze` explicitly prepares a new batch from current formal
data; it cannot use an unreleased or mismatched snapshot. Admission additionally
requires the baseline bytes to equal current `data/airports.json`.

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
records URL, date, original text SHA-256, policy/scope hashes and recorder. It never
posts a comment. A plain JSON claim to be keepraw is not an activation input.

```sh
# FUTURE ONLY, after the owner's exact policy grant:
python3 scripts/evidence/policy_review.py activate --authorization-url OWNER_COMMENT_URL
# After data/research advances, prepare a fresh independent formal baseline:
python3 scripts/evidence/policy_review.py freeze
pnpm policy:build
python3 scripts/evidence/policy_review.py fetch-originals
python3 scripts/evidence/policy_review.py admit --output work/policy-admission-unique
```

The last command re-evaluates everything, validates the owner grant, replays the
originals and runs the **existing** `validate_admission()` with a restricted
`policy_context`. That gate retains source/claim linkage, primary provenance,
schema stability and immutable-record checks. The context is recomputed and
compared to the exact dataset, batches and dossiers; caller receipts cannot enlarge
the selection. The schema/semantic and resolver gates run before writing any
proposal. Output is limited to a new ignored `work/` directory. An empty successful
batch is not an admission. No CLI writes formal data, pushes, merges or releases.

After authorization, use the validated proposal and external audit files to form
a normal formal-data PR, replay the same policy context in that PR's CI, run
`pnpm check`, and retain the previous published snapshot. No per-record owner
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
