# Korean bounded-history readiness (PR24)

This is a two-airport research packet, based on main
`bc27f052cb8c7c2cabb7bc212d5e9170163fcaac` after successful post-merge
[CI 41057146364](https://github.com/keepraw/airport-history/actions/runs/41057146364).
The complete baseline `pnpm check` also passed. All 881 pre-existing files are
hash-protected, including the PR22/23 snapshots, formal 0.10.0 data and Indian
policy, grants and executor. Nothing in this directory admits a fact or a grant.

Read the [Chinese handoff](HANDOFF.zh-CN.md), [evaluated evidence predicates](evidence-conditions.json)
and [production no-go assessment](assessment.json).

The official all-NOTAM menu explicitly searches issue dates. The packet reconciles
all 1,061 PR23 airport server records against newly obtained official responses
through 2026-10-30, retaining five linked later successors. Its per-airport ledgers
distinguish B/C times, estimated ends, PERM, cancellation, replacement, duplicated
text and physical-identity signals. There are 51 RKSI and 34 RKSS effect envelopes
overlapping the candidate window; no unknown relevant airport lifecycle remains
in this bounded corpus. Five missing 2023 predecessors were cancelled before the
window and remain visibly missing; they are not asserted nonexistent.

The new official 2025-04-01 and 2025-05-01 A/G/Z AFS outstanding-NOTAM checklists
are important additional evidence. All 75 enumerated numbers across six checklist messages
were queried; every number was recovered. The ten airport notices outstanding at
each snapshot exactly match the lifecycle ledger, including future-B notices.
These are six records from one publisher, not six independent publishers. The
archive still is not certified complete since 2001. Historical plain-language
monthly PDFs were not obtained; the dated official AFS checklist counterparts were.

A broad FIR query exposed a 9,999-row response cap despite `Total=30787`. It is
retained only as a truncation control. Five complete issue-date segments instead
recover 16,701 RKRR records, including follow-up through 2025-07-10 to close EST
and multipart checklist relationships. The retained 832 overlapping regional
message envelopes include 27 with explicit RKSI/RKSS mentions. They are separate
from the 85 airport notices and are not 832 airport allocation events. Temporary
airspace, military activity and flow restrictions are not code withdrawals.

The AIRAC/ordinary amendment distinction matters: **ordinary AMDT 5/25 was
published on 1 May 2025**, and GEN 3.1 says regular amendments incorporate changes
on their publication date. Its exact UTC clock is not established and is not
borrowed from AIRAC. The two outer AIRAC anchors remain 28 days apart. The
three-edition name/ARP chain, supplements and NOTAM evidence leave the original
`[2025-04-18, 2025-05-15)` window defensible as a conditional hypothesis.

The unified physical-identity batch contains separate site judgments, actual AIP
ARPs, independent operator addresses, NOAA station-location corroboration and a
focused competing-reference screen. NOAA station coordinates are not AIP ARPs;
their station-history dates are not allocation dates. Seoul/SEL is a metropolitan
record. The two airport ARPs are approximately 33,306 m apart. No permanent ID is
allocated; PR22 simulation IDs appear only in in-memory resolver measurements.

`0.2.0-draft` proposes adjacent AIRAC anchors capped at 28 days, all intervening
ordinary editions, reconciled official NOTAM snapshots and existing approved
permanent physical IDs. The old 56-day proposal has not been validated. The old
`0.1.0-draft` and every Indian byte remain unchanged. The new fingerprints bind a
**research** verifier and resolver, not a production Korean admission executor.
Identity approval and a separately reviewed Korean production adapter remain
required; the packet is **not ready for production owner authorization**.

The [authorization proposal](authorization-proposal.json) therefore has a null
production authorization text and issues no request. Its single future identity
review text binds both records by immutable batch digest, and cannot approve any
code period. No current CLI accepts that text as a grant. The existing admission
gate still requires per-record claim/source mappings; one real owner batch comment
could later be recorded against both dossiers after actor/text/digest verification.
Do not create a combined identity-and-policy bypass.

## Reproduce

```sh
# Offline, including all protected main hashes and the local-original receipt:
python3 scripts/evidence/korea_readiness.py validate
node scripts/evidence/korea_readiness_coverage.ts validate
pnpm check
# Explicit network recovery only when needed; changed remote bytes fail closed:
python3 scripts/evidence/korea_readiness.py fetch-originals
# Actual byte hashes, independent extraction, old/new citations and graph replay:
python3 scripts/evidence/korea_readiness.py originals
# Rebuild the two ledgers from the private locked responses:
python3 scripts/evidence/korea_readiness.py build-ledgers
# Existing PR23 audit plus new original/extraction fingerprints:
python3 scripts/evidence/korea_readiness.py rights
```

The receipt covers 98 locked components: 73 matching Korean historical primary
components reused by reference and 25 new components, including query controls.
It checks all 133 reused excerpt spans plus 24 new minimal citations. It does not
reassert that every dynamic PR23 IATA page can be recovered with its old hash.
Those old locks and receipts are preserved; changed current observations are not
silently substituted for historical originals.

Ordinary CI runs the new corpus tests through `test:evidence`, explicitly replaying
the recorded receipt offline. It does not claim to acquire originals. Full HTML,
PDFs, complete NOTAM text, CSVs and extraction files remain only in ignored
`work/pr23/originals/` and `work/pr24/`. Public files contain necessary provenance,+independent factual metadata and minimal attributed citations. No chart or full
commercial code ledger is redistributed. No merge, auto-merge, tag or release is
performed; Keepraw-Fly is outside this task.
