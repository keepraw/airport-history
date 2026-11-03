# Global historical airport batch 5

Targeted original-document research over **12 existing event groups** (46 triage
groups) from main `19b7b1d`. Formal data stays **0.10.0 / 37 / 52 / 101 / 3**:
**0 formal admissions**. See the [Chinese handoff](README.zh-CN.md).

- `catalog.json` – sources, publishers, date meanings, independence family, short anchors.
- `source-lock.json` – per-source acquisition result, original SHA-256, byte size,
  normalized-text SHA-256 and anchor location. Originals stay in ignored `work/`.
- `batch.json` – per-event claims, separated opening / service-end / closure /
  IATA / ICAO dates, status, gaps, conflicts and next action.
- `proposals.json` – exact, **unauthorized** candidate records for the Bengaluru and
  Hyderabad cases, for a possible record-by-record owner approval.
- `coverage.json` – production `resolveAirport()` measurement: formal delta 0;
  proposal-only simulation 26,049 new resolved code/date queries (not counted).

Why nothing was admitted: the only registered production rule (Korean RKSI/RKSS,
`admission/v1`) rejected the fresh evidence version because the official
`kr-history` index bytes changed and the bound executor has no replacement
contract; every other market needs explicit per-record owner approval, and the
protected baselines pin `data/airports.json`, so no unapproved release route exists.

```sh
python3 research/evidence/global-batch-5/tools/global_batch_5.py fetch      # re-acquire originals into work/
python3 research/evidence/global-batch-5/tools/global_batch_5.py validate   # offline checks + resolver replay
node research/evidence/global-batch-5/tools/coverage.ts build
```

Tools live under `tools/`, not `scripts/`: the legacy Korean executor fingerprints every file in `scripts/`, `src/` and `schema/`, so a new file there would invalidate its authorization.
