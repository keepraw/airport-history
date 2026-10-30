# First production policy admission: 0.10.0

This candidate adds **three physical airports, three ICAO assignments and six
source records** using the existing `official-aip-bounded-icao@1.0.0` policy.
The exact output of the production `policy_review.py admit` command is copied to
[proposed-data.json](proposed-data.json), `data/airports.json` and the immutable
`test/curated-0.10.0.json` snapshot. This is a real formal-version candidate and
still requires human final PR merge.

The frozen old database remains **0.9.0 / Schema 3.0.0**, SHA-256
`1beec87eac60c8f844a5756073811edadbfb6d4a831fb4f03ce5552796ce539b`, published in
main `458078b5a6662f9cdbe3f778d04dfeec959686cd`. PR #20 is merged, and its
[main CI run](https://github.com/keepraw/airport-history/actions/runs/41005671737)
completed successfully in both jobs before production admission. No concurrent
formal-data PR was open. Official `freeze` retained all 261 locked inputs with
unchanged content hashes, advancing only the baseline main commit. The new
canonical input-lock SHA-256 is
`10fcfff3f6f25609e46f4a88386c9d0940478f01f9c5fac2e70a272942520d4e`.
The 0.10.0 candidate was never frozen as its own old baseline.

## Authorization and selection

The only production policy grant remains the original
[keepraw owner comment](https://github.com/keepraw/airport-history/issues/19#issuecomment-6513409968),
GitHub ID **49091395**. Its current text, actor and timestamps were checked against
GitHub. The existing authorization registry and original text are unchanged;
activation was not repeated and no per-record approval was requested or invented.

| Binding | Unchanged SHA-256 |
| --- | --- |
| Policy | `3c606e60766f0ec89090e2b382939da67be00a7e9070aefc7568fe5559e05958` |
| Scope | `6242a7bfaa66700aefc925bc8a3532f9ad62ca81334b156509835616419d1cb3` |
| Executor | `2415279526ff8c0eaf9ee1b3ee5afca8bde26e95bfac2c98930212f9f7992a3f` |

The production CLI recomputed all decisions from the locked research evidence.
The following results are a policy selection, not a manual code allowlist:

| ICAO | Physical airport | Permanent airport ID | Certain local-date window |
| --- | --- | --- | --- |
| VEHO | Donyi Polo Airport (Hollongi) | `apt_9acf6a6b-6e22-48c6-881c-d602429a9268` | `[2026-04-17, 2026-07-09)` |
| VASD | Shirdi Airport | `apt_fa1bf7a7-a97d-4676-9c9a-7871eda47767` | `[2026-04-17, 2026-07-09)` |
| VOKN | Kannur International Airport | `apt_58a2554f-6a9b-4ad7-bc2c-2550ad21b962` | `[2026-04-17, 2026-07-09)` |

Assignment IDs remain `global-proposal-hollongi-icao-veho`,
`global-proposal-shirdi-icao-vasd` and `global-proposal-kannur-icao-vokn`.
Each candidate has two controlled observations (2026-04-16 and 2026-07-09), two
different originals, one AAI publisher, a stable official name and independently
converted ARP, and a single screened physical hypothesis. The observation gap
is 84 days; the admitted window contains 83 complete local dates and satisfies
both unchanged 112-day limits. Finite locked-corpus conflict screening does not
establish absence of counterevidence throughout all history.

[dossier.json](dossier.json) contains six accepted decisions, one per airport and
assignment. They state `reviewMode=policy`, the real policy/version/hash and
`reviewer=null`. [policy-receipt.json](policy-receipt.json) links the real owner
grant and the exact baseline, inputs, decisions, dataset, batches, dossier and
original-verification record. The owner authorized the rule; these records do
not claim the owner personally reviewed each original.

## Original verification and rights

On 2026-10-30, actual network acquisition and independent local verification succeeded for all
**10 required AAI chapter components / 8 distinct original byte streams / 40 short
citation spans** across the low/medium evidence corpus. The production low-risk
bundle needs **6 components / 6 distinct originals / 24 spans**, all included in
[original-verification.json](original-verification.json). The verification checked
raw SHA-256, independently extracted text SHA-256, every exact short-quote range,
and same-archive AIRAC edition anchors. No download, hash, extraction, citation or
anchor anomaly occurred. Repeated VOGA/VEDG bytes still fail the distinct-original
requirement and those records remain medium-risk and unadmitted.

The fresh low-risk verification canonical SHA-256 is
`08de9792a873524f175c2ee074a5256c000c52cefd820bf96e01d0e4dd731753`.
The production receipt canonical SHA-256 is
`8e5ba921c2a4750f6a10ec4e2619a5dba5d193fe265f37d09bbc759611528c1e`.
The receipts bind the new frozen input lock, not the preceding activation batch.
Edition dates, component amendment/publication dates and the originally recorded
acquisition timestamps remain distinct in the unchanged source lock. Those older
acquisition timestamps are not relabeled as today's download time; this dated
record documents the fresh recheck, whose deterministic receipts bind content.

`admit` actually re-read the private originals before emitting the production
bundle. Subsequent admission replay and ordinary GitHub CI validate the bound
receipt **offline**, explicitly reporting no original-byte acquisition by that
process. No manually dispatched GitHub network-verification run is claimed.
All full HTML/PDF bytes and full extractions remain in ignored `work/`. Public
materials contain only existing minimal citations, metadata, URLs, hashes and
review records. AAI rights remain reserved; public access does not grant
redistribution or relicense the originals under MIT/CC0.

## Formal data and actual resolver effect

| Collection | 0.9.0 | 0.10.0 |
| --- | ---: | ---: |
| Physical airports | 34 | 37 |
| Code assignments | 49 | 52 |
| Sources | 95 | 101 |
| Historical names | 3 | 3 |

All new names and coordinates retain `reference`; timezone values remain null
with status `unknown`. First allocation and final withdrawal bounds remain null.
The first official observation is not an allocation date, and the last is not
a withdrawal date. Observation endpoint local days are excluded. Physical
reference notes are copied unchanged from the policy-selected proposals;
acceptance is recorded in the separate policy dossier.

[coverage.json](coverage.json) was built from actual `data/airports.json` bytes
using the unchanged production `resolveAirport()` comparison in `policy_coverage.ts`.
It is independently stored as `mode=formal_policy_admission`; no dry-run totals
were copied. Candidate/snapshot file SHA-256:
`2268bdd3426e0d459b7b46d1214b165e3ab90f3526d4f2528f60238f4ee94b13`.
Replay reads that exact immutable formal candidate snapshot and bundle.

- **249 new resolved** code/local-date queries: 83 for each ICAO code.
- **12,849 new uncertain** queries outside the windows: 4,283 per code.
- **0** changed existing answers, changed published resolved answers, new
  conflicts or removed conflicts.
- **187,738 code queries** across the old/new code union and **148,444 existing
  airport-name queries**, over 4,366 dates: 2015-01-01 through 2026-10-29 plus 46
  boundary/adjacent dates. Every existing code and name answer is preserved.
- Boundary checks explicitly include April 15–18 and July 7–10 for every new
  assignment. Making required evidence unreviewed prevents resolution.

The gate protects every published airport, assignment, name, source and permanent
ID. All older snapshots, including 0.7.0, 0.8.0 and 0.9.0, remain unchanged.
The formal JSON adopts the existing CLI's deterministic key order; key ordering
changes do not alter any existing record.

## Reproduction

Production preparation used the existing commands in order: `freeze`,
`pnpm policy:build`, `policy_originals.py verify --fetch`, `policy_review.py originals`,
`policy_review.py admit --output work/policy-admission-0100-production`, and
`policy_formal.py --bundle ... --candidate ...`. Only after the original admission
CLI and real resolver gates passed was its exact output copied into formal data.
Do not rerun `freeze` or production preparation against this unmerged candidate.

Offline review commands:

```sh
pnpm validate:admission
node scripts/evidence/admission_0100_coverage.ts validate
pnpm policy:validate
pnpm check
pnpm policy:rehearse
pnpm evidence:history
git diff --check
```

The added coverage recorder reuses the existing resolver measurement; admission
still runs exclusively through the original CLI. The rehearsal harness alone
resets its disposable clone to frozen 0.9.0 before exercising its explicitly
isolated ID 0 fixture. Its production rejection check remains intact, and it
cannot change the real owner grant, policy or formal candidate. No protected
executor file or dependency is changed.

Local verification on 2026-10-30 passed the complete `pnpm check`: **437 TypeScript,
50 discovery, 15 reference and 86 evidence tests**, all validations and the
deterministic 0.10.0 build. The complete isolated candidate check also passed;
production rejected its ID 0 grant and real formal/authorization hashes stayed
unchanged. Five research builders reproduced all **53** existing artifacts
byte-for-byte, and a second policy build reproduced all **15** generated and
verification artifacts. Full reachable Git history and all staged public files
passed the pre-commit rights audit. Local subprocess tests initially hit sandbox
`EPERM`; rerunning with the required execution permissions passed unchanged tests.

VOGA/VEDG, all other medium/high/insufficient or excluded candidates, LEMI/RMU/MJV,
TAG/LYG/YBP, IATA assignments, historical names, timezone upgrades and published
corrections are outside this admission. The medium authorization registry remains
empty. No Keepraw-Fly change, tag, release, merge or auto-merge is included.

To grow the next low-risk batch, add controlled dated AAI archive components,
minimal name/code/ARP citations and real edition anchors through normal evidence
review. Preserve canonical physical IDs and explicit conflict screening. After
this PR is merged, freeze the newly published baseline, verify actual originals
and run the same authorized production CLI. Unchanged policy/scope/executor
bindings permit future qualifying low-risk records without per-record approval;
failures and medium/high-risk records require the existing separate paths.
