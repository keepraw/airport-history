# Human Admission v1

A generic, auditable way to turn an **exact, Owner-approved batch** of airport
identities, IATA/ICAO assignments and historical official names, from any
number of countries, into a formal data release. It is not a policy, it grants
nothing by itself, and an approval never carries over to another batch.

## Reuse, not a new gate

| Concern | Existing code reused unchanged |
|---|---|
| Review/claim gate, permanent-record immutability, dossier provenance | `scripts/reference/admissions.validate_admission` (human path, no `policy_context`) |
| Review batch format, ≤ 20 events, candidate uniqueness | `scripts/discovery/review.validate_batch_series` |
| Schema, physical identity, overlap/conflict semantics | `src/validate.ts` (`validateDataset` / `assertDataset`) |
| Production resolver differential, published-answer immutability | `scripts/evidence/policy_coverage.ts` `measure()` → `src/resolve.ts` `resolveAirport()` |

Human v1 adds only: the batch manifest and its exact approval text, original
evidence locking and live replay, interval-bound date checks, explicit approval
for timezone/name/coordinate upgrades, one-active-batch and cross-batch identity
checks, and a CI router.

AAI (`scripts/evidence/policy_*`), Korean v1 (`scripts/admission/*`) and the
rule engine (`admission/v1/*`) are not modified and keep their bindings.

## Workflow

```sh
python3 admission/human-v1/human.py prepare --spec work/<batch>.json      # exact records from research
python3 admission/human-v1/human.py verify-originals --version 0.11.0     # live download, SHA-256, extraction, citations
python3 admission/human-v1/human.py build --version 0.11.0                # candidate + gates + resolver diff + manifest
python3 admission/human-v1/human.py approval-text --version 0.11.0        # text the Owner posts verbatim
#   Owner posts the text as a comment on an issue in keepraw/airport-history
python3 admission/human-v1/human.py record-approval --version 0.11.0 --url <comment URL>
python3 admission/human-v1/human.py validate --version 0.11.0             # everything again, approval re-read live
python3 admission/human-v1/human.py submit --version 0.11.0               # formal data commit on data/human-<batch>
```

Push the branch and open a draft PR. Merging remains the Owner's decision.

## What one approval binds

`research/admissions/<version>/human-v1/manifest.json` holds: batch ID, base
main commit, base data version and SHA-256 (equal to its immutable
`test/curated-*.json`), candidate SHA-256, records SHA-256 (every approved
record's exact content), evidence-lock SHA-256, review batches, dossier,
excluded list, resolver differential and the executor SHA-256 (all Human v1
files plus every reused gate). The approval text lists every record ID and the
excluded IDs and repeats the hashes, including the SHA-256 of the complete
`original-verification.json` receipt. Rebuilding deletes any recorded approval;
re-verifying originals deletes the manifest, approval text and approval, so a new
build and a new Owner comment are required. An edited or replaced receipt no
longer matches `originalVerificationSha256` and voids the approval.

## Base freshness

A batch is prepared only on the current published `origin/main` (fetched).
`verify-originals`, `build`, `record-approval`, `validate` and `submit` refuse as
soon as main has advanced: prepare, verify and build again on the new main and
obtain a new Owner approval. `submit` creates the formal data commit directly on
the approved base (HEAD must equal it).

In CI (`check_release_lineage`): while main does not yet carry the release
(the data PR), `origin/main` must still equal the approved base, so an old PR
re-run after main advanced fails. On every run the first commit on HEAD's
first-parent chain that carries the release must have the approved base as its
first parent: a merge commit, a squash or a one-commit rebase made while main was
the base all pass, later main commits pass, a merge onto a newer main fails.
Historical releases keep replaying because the base itself is only checked for
ancestry of main.

## Concurrent batches: what is and is not guaranteed

`check_single_active` sees only bundles in the checkout. Two branches can each
prepare a batch on the same main. What stops the second one is base freshness:
after the first merges, the second's CI, `validate` and `submit` refuse, and
re-preparing on the new main runs every gate against the new data (reused
permanent IDs and conflicting code windows are refused). This is enforced only by
CI and the CLI. On 2026-11-04 `main` had no branch protection and no rulesets
(GitHub API, admin read), so nothing forces CI to be green, or re-run, at merge
time: a stale PR merged on an old green check would be caught by the main push CI
only after it landed. Real global exclusivity needs the Owner to require the
`human-admission` check with "require branches to be up to date" (or a merge
queue), or to re-run CI immediately before merging.

`record-approval` and every `validate`/CI run fetch the real comment and require
author `keepraw` (GitHub user ID 49091395), the exact text, this repository and
non-future timestamps. There is no offline, fixture or flag-based authority.
The record states what it is: an Owner comment binding hashes, not a GitHub
review or signature, and not a claim that the Owner read every original.

## Evidence

`evidence-lock.json` records per source: URL, publisher, independence key,
original SHA-256, independent extractor and text SHA-256, rights
(`citation-only`), publication/effective/observation dates and short citations
(≤ 240 characters) with their positions, the records they support and the dates
they state, each with a kind. Only `code_effective`, `name_effective`,
`observed_in_force` and `observed_not_in_force` dates can bound an interval;
opening, capture, licence, publication and Git dates cannot. Unknown bounds stay
`null`. Originals and full extractions stay in ignored `work/`.

CI cannot download originals. It replays the committed live-acquisition receipt
offline and says so.

## CI

`.github/workflows/human-admission.yml` runs `human.py ci`:

* No human release at the current `dataVersion`: no-op, the legacy workflows run unchanged.
* A human release: validate the bundle (approval re-read live), require
  `data/airports.json` = approved candidate = `test/curated-<version>.json` and
  `package.json` version, then replay **every** legacy workflow step unchanged in
  the frozen base tree (`git archive` of the base commit, so AAI `policy_formal`,
  `policy:validate`, Korean adapter, rule engine and all tests run on the bytes
  they were authorized for), then run every legacy step that does not pin the
  0.10.0 bytes in the current tree. The data-pinned steps are listed with
  reasons in `core.DATA_PINNED`.
* `korea_readiness.py rights` reaches the 0.10.0 priority-markets lock indirectly
  (`priority_markets.rights_audit()` -> `verify()`), so it is data-pinned too and
  runs unchanged in the frozen tree. In the current tree `rights.py` runs the same
  unmodified Korean, code-dates and priority-markets audits over all of HEAD; only
  that one entry check is narrowed: every other file in the priority-markets
  baseline lock must match byte for byte, and `data/airports.json` plus the version
  must equal the approved bundle. No hash, lock or authorization is changed.

`submit` removes `ci.yml`, `kr-admission.yml` and `rule-admission.yml` in the data
PR because their steps then run inside the router. See the Owner decisions in
the PR description before using it for real data.
