# AAI bounded ICAO admission, 0.12.0

The unchanged owner-authorized AAI policy admits three newly researched ICAO
assignments: VOSH (Shivamogga), VEAY (Ayodhya) and VANM (Navi Mumbai). Each has
two controlled AAI AD 2 observations, 11 June and 9 July 2026, with matching
official name and ARP and one matching reference site. The certain interval is
27 whole local dates, **2026-06-12 through 2026-07-08**. First allocation and
final withdrawal remain unknown; both observation boundary dates are excluded.

The proposed formal dataset grows from 43 to 46 physical airports, from 24 to
27 ICAO assignments, and from 106 to 112 attributed sources. The 28 IATA
assignments and three historical names are unchanged. Production
`resolveAirport()` measures **81 new resolved code/date queries**, all previously
`not_found`, and preserves existing published answers and conflicts. These are
proposed-data measurements until the PR is merged; no unmerged candidate is
reported as growth in the published main dataset. VOMY is excluded because its
reference lookup has competing locations.

The authorization, policy parameters and executor fingerprint are identical to
the 0.10.0 admission. New evidence was prepared through the original
`policy_review.py freeze/build/admit` commands in an isolated checkout of
published 0.11.0. The original gate classified all three records as low risk,
replayed the six AD 2 originals plus the edition-control original, checked raw
and extracted-text hashes and every exact citation, and invoked the original
shared admission validator, schema and production resolver. No personal
per-airport approval is claimed, and no Chinese or Korean authority is reused.

The original intake has fixed file paths and historical archival checks require
old repository artifacts to remain byte-identical. The new
`global_code_admission.py` restores only the thirteen recorded data inputs in a
temporary published-baseline checkout, then invokes the **same** original
`policy_formal.py` admission CLI. The helper grants no authority and defines no
alternative evidence rules. The replay manifest fingerprints every bound
executable and restricts overlay targets to the recorded research data and
minimal excerpts. Old live research, policies, grants and executors are unchanged.

AAI retains its publication rights. Necessary code/name/ARP facts, attribution,
hashes and short citations are retained under the existing scoped treatment;
no general publication licence is claimed. Full originals and full extractions
remain in ignored `work/`. The public original-verification receipt records the
actual preparation replay; CI subsequently checks that receipt **offline** and
does not claim to reacquire originals or independently read private bytes.

Reproduce the admission, boundary checks and normal deterministic build:

```sh
python3 scripts/evidence/global_code_admission.py
pnpm validate:data
pnpm validate:admission
pnpm test
pnpm build
```

The exact new intake is in
[`replay-manifest.json`](../../evidence/global-code-expansion/policy/aai-intake/replay-manifest.json).
The global survey, other source-family proposals and separately pending
international code evidence remain under `research/evidence/global-code-expansion/`.
