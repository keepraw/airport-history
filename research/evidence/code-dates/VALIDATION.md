# Local validation and audit receipt

Baseline: `80df6f95143c33e861b74243637e8e4a7ff92172`, merged PR22.
The baseline's [post-merge CI](https://github.com/keepraw/airport-history/actions/runs/41018240556)
succeeded in both jobs. Full baseline `pnpm check` passed before branch creation.

Final research-tree checks performed on 2026-10-30:

| Check | Result |
|---|---|
| Complete `pnpm check` | Passed: 437 TypeScript, 50 discovery, 15 reference, 102 evidence tests; all validators and deterministic build |
| Code-date original verification | 97 locked components, 183 exact citations, five reused PR22 originals rechecked |
| Code-date offline validation | Passed; explicitly reports `originalBytesRecheckedHere=false` for that invocation |
| Existing priority-market validation | Reproduced 0 formal new resolved and 54 unauthorized hypothetical resolved |
| Main baseline protection | All 772 pre-existing files unchanged, including all formal data, policy/grant/executor files and previous research snapshots |
| Dataset/schema/counts | 0.10.0 / 3.0.0; 37 airports, 52 assignments, 101 sources, 3 names |
| Published dataset build SHA-256 | `03b267486089a2a5ade9f3d4ff7949603d198e04c718f7c9f6bc84cbef5ab61f` |
| Ordinary author/committer identity | Both checked as `keepraw <49091395+keepraw@users.noreply.github.com>`; local `user.useConfigOnly=true` |

The staged additions passed the reachable-history/content gate and the
source-specific minimal-quotation review. No new full original, full extraction,
chart, photograph, commercial ledger or complete NOTAM text is staged. Existing
restricted-blob fingerprints remain an audit inventory, not proof that old remote
objects were erased. Actual original rechecking is separate from offline CI.

The local original receipt binds the assessments, matrix, screening metadata,
baseline lock and verification implementation. The ordinary evidence tests also
run in the admission rehearsal's disposable candidate; they deliberately do not
interpret that fixture's replaced formal/grant files as the real baseline.

Final commit SHA, post-commit ancestry audit, isolated admission rehearsal and
GitHub final-head CI are reported in the PR and final delivery report. Their
status is not inferred from the successful baseline run. Human merge remains
required; no merge, auto-merge, tag or release is performed.
