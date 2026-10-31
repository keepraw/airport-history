# Rule-based physical identity admission (inactive)

This release implements independent physical identity and Korean code rule
authorization, immutable evidence versions, and a versioned candidate release
pipeline. **No real rule grants, permanent Korean identities, or formal Korean
resolved results are included.** See [the Chinese handoff](HANDOFF.zh-CN.md) for
the twelve acceptance answers and precise remaining activation conditions.

```mermaid
flowchart LR
  O[Official originals in private CAS] --> I[Three-state physical identity review]
  I --> A[Exact live Owner identity rule grant]
  A --> U[Stable site ledger and UUID allocation]
  U --> S[Identity schema and immutable-record gate]
  S --> C[Independent code grant and original fact replay]
  C --> B[Versioned formal candidate bundle]
  B --> R[Actual resolveAirport and regression gate]
  R --> P[One batched candidate PR]
  P --> M[Human merge]
```

The classifier has no airport allowlist. The identity rule currently applies to
KR/MOLIT controlled AIP observations, with explicitly reviewed IIAC/KAC asset
address lineage. Two observations must be at most 28 days apart; the official
index must enumerate every intervening edition. Exact original name/ARP facts,
operator-owned named-site/address support, notice risks, and formal/pending/
historical competition all participate. NOAA vicinity cannot replace operator
site support. Names/codes alone are never physical deduplication keys.

`AUTO_ELIGIBLE`, `MANUAL_REVIEW`, and `INSUFFICIENT_EVIDENCE` are distinct outputs.
The whole candidate batch is checked for competing sites before any UUID is
minted. The durable facility key and published/pending registry preserve IDs
across runs; open candidate PR ledgers are read before allocation on another
worker. Stable exception keys retain evidence revisions without duplicate tasks.

The code rule is independently authorized and remains bounded to RKSI/RKSS and
`[2025-04-18, 2025-05-15)`. It cannot allocate identities. Identity admission
cannot establish code validity. The code bridge uses the preserved PR25 finite
predicates and additionally re-evaluates all necessary current-version originals,
historical notice graphs, official outstanding sets, SUP, AIP and local dates.
It does not inherit v1 or Indian grants.

The v2 executor manifest is an explicit transitive file closure, including its
own input list, release pipeline and CI template. Adding an unrelated country
module does not enter it. Changes to a shared bound file require independent
reauthorization of affected rules. All package values are bound except the
explicit release variable `version`, which must increase and match the candidate.
The old Indian and Korean v1 manifests and all 923 baseline files stay unchanged.

## Evidence and validation scope

`evidence-versions/` contains **metadata only**. Each filename is its canonical
SHA-256; parents preserve acquisition history. Originals live only under ignored
`work/rule-admission/cas/sha256/`, with exclusive object creation, private file
permissions, and digest validation on every read. New observations create new
manifests. Changed responses never overwrite historical SHA pins or inherit an
old conclusion.

The old twelve fact blockers were re-proved using qualified new originals and
split official checklist requests. None of their old exact byte sequences was
restored. The current version has 98 logical sources and 160 independently
acquired original components. The truncated all-FIR diagnostic query is not
coverage evidence; complete temporal segments and six official snapshots are.
Current UI/operator/IATA pages support only their explicit current/protocol/site
facts, never historical allocation by themselves.

`source-revalidation.json` records per-source checks and deliberately does not
claim a complete historical replay on its own. The bounded code replay and live
isolation receipt record the separate 19,639-row graph evaluation, 54 conditional
resolved dates, zero extra boundary dates, and 37,736 unchanged formal queries.

Public CI has no private CAS. It validates version metadata and runs clearly
synthetic offline E2E tests. It cannot claim fresh original replay or production
success. `release.py validate --offline` reports that limit and is not accepted
by production PR preparation. Real preparation and submission require live Owner
authentication and private-original replay. A new evidence version must reprove
the facts and historical window; raw mutation at an old address fails closed.

## Operation

Run `python3 admission/v1/verify.py` and
`python3 admission/v1/test_engine.py`. See the handoff for acquisition, standalone
raw verification, isolated rehearsal, exact authorization text/recording, and
production preparation/submission commands. No production command offers a test
authority flag. The isolated harness copies the repository and originals into a
disposable checkout and proves that a clean production reader rejects its grants.

`release.py` performs an identity-only formal schema/resolver stage before code
admission. The final bundle includes its frozen baseline commit, independent
grants, exact identity/evidence/bundle hashes, decisions, sources and exceptions.
`publish.py plan` produces reviewable changes; `submit` uses a stable batch branch,
requires a clean published main checkout, checks main has not advanced, audits and validates the candidate, commits with the
owner's identity, and opens one PR. It contains no merge, auto-merge, tag, or
release operation. This release exercised real-original PR preparation only in
isolation; it did not submit a formal data PR with test authority.

Future candidate PRs include the reviewed versioned CI routing template. It
replays legacy checks in their historical trees, then validates the extension.
It never rewrites a historical grant to pretend a changed executor is unchanged.
Keep the CAS in persistent private storage, or reacquire and revalidate a qualified
new version before each production batch. A missing required original stays a
blocker regardless of recorded offline receipts.
