# Korean admission adapter v1 (inactive)

This packet contains executable preparation tools, not an identity approval or a
policy grant. Start with [the Chinese handoff](HANDOFF.zh-CN.md),
[machine status](status.json) and [actual isolated resolver receipt](verification.json).

Baseline: main `fdfdb02f46e543395d0cf3ad3f779aff26c47c90`, after PR24 merged and
[its push CI](https://github.com/keepraw/airport-history/actions/runs/41106518661)
completed successfully. All 905 baseline files, including the Indian executor,
grants, package scripts and previous research, are protected byte for byte.

The exact production selector is `kr-molit-bounded-icao@1.0.0`. The independent
CLI neither passes Korean receipts to the Indian `policy_gate` nor modifies that
executor. Its own manifest binds all local script/source/schema dependencies,
the dependency lock, and every package.json value through canonical JSON.
Research `0.2.0-draft` hashes and Indian grants confer no Korean authority.

```sh
python3 scripts/admission/kr_adapter.py inspect
python3 scripts/admission/kr_verify.py validate
python3 scripts/admission/kr_rehearsal.py
pnpm check
pnpm policy:rehearse
python3 scripts/evidence/korea_readiness.py rights
```

`kr_rehearsal.py` uses an uncommitted disposable copy. It runs the original human
identity admission function, the independent Korean adapter, the real schema and
`resolveAirport()`. A distinct test principal and offline evidence dependency are
injected only in that process. A second production process rejects those test
credentials. Isolated Python child processes ignore inherited PYTHONPATH test
bootstraps; outer disposable bundle changes are preserved without weakening the
real 905-file baseline validator. The public receipt contains query results and no test identities or
authorization records. Ordinary CI replays locked evidence **offline**; it does
not claim original acquisition.

The 54 candidate queries resolve only in this isolated exercise. Every production
query is individually marked blocked in status.json. A current recovery attempt
matched 86/98 originals; six drifted and six could not be recovered. Production
`originals` therefore fails. No old pin was overwritten and no drifted response
was substituted. **Full Engineering ready is not claimed.**

```sh
# Requires private exact originals, not an offline receipt:
python3 scripts/admission/kr_verify.py originals
# Safe future identity entry: prints the exact review text; does not approve it.
python3 scripts/admission/kr_adapter.py identity-text
# Only AFTER the real owner posts that exact text:
python3 scripts/admission/kr_adapter.py prepare-identities \
  --comment-url REAL_OWNER_COMMENT_URL --data-version NEW_VERSION \
  --output work/NEW_IDENTITY_PROPOSAL
```

Identity preparation fetches the actual repository owner and comment from GitHub,
checks numeric identity, login, account type, exact comment bytes, issue scope and
timestamps, then verifies the immutable batch, its exact reviewed formal baseline and original evidence.
A changed database requires renewed physical-site competition review and a new batch approval. Only then
can it allocate fresh UUIDs and run the existing human identity gate. It emits a
reviewable proposal in ignored work/, never curated replacements. Separate
per-record dossiers share the one batch approval and retain independent ARPs.

After a separate identity admission PR has been reviewed and manually merged,
its exact records and approval metadata can populate identities.json. Existing
formal identity records are mandatory for both policy text and policy recording.
The current data and identity registry must also exactly match artifacts retrieved
from one real GitHub main commit; unmerged working-tree identities are rejected:

```sh
python3 scripts/admission/kr_adapter.py policy-text
# Only AFTER the owner posts the resulting exact policy text:
python3 scripts/admission/kr_adapter.py record-policy \
  --comment-url REAL_OWNER_POLICY_COMMENT_URL --output work/NEW_GRANT_PROPOSAL
# Only AFTER that separate registry proposal is manually reviewed:
python3 scripts/admission/kr_adapter.py admit --data-version NEW_VERSION \
  --output work/NEW_CODE_PROPOSAL
```

Every production preparation re-fetches both approvals, rejects edited comments,
recomputes exact Policy/Scope/Executor/identity bindings, reads all original bytes
and citations, and applies schema/source/resolver gates before emitting anything.
There is no production test-authority flag, offline admission option, IATA path,
automatic merge, or identity creation through the policy path.

These entry points prepare proposals. Future formal data promotion still needs a
versioned formal-bundle replay integrated with the existing release checks; the
Indian frozen-bundle replay must remain intact. This inactive PR does not claim
that simply replacing data/airports.json will pass existing release CI.

If exact originals cannot be recovered, the smallest safe evidence change is a
new versioned packet, new predicates/bindings, new tests and a newly reviewed
policy boundary. Rewriting PR24 pins or substituting a receipt is forbidden.
The original archive is not certified complete since 2001. Ordinary AMDT 5/25
has a controlled date and no asserted effective instant. NOAA coordinates remain
vicinity corroboration, separate from the exact AIP ARPs.

Full source responses, PDFs, NOTAM bodies and extraction files stay in ignored
work/. The public recovery report contains only source IDs, hashes and outcomes.
The rights audit checks staged files, every newly reachable blob and required
ancestry, independently of ignore rules.
