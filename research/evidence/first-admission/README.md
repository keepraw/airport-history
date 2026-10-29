# First historical admission review preparation

This is a review-only continuation of merged PRs #14–15, based on main
`6f3e50b42b62c4460f7ed0d07f9cc721c278b0b4`. Formal data remains **0.8.0 /
schema 3.0.0 / 27 airports / 43 assignments / 3 names / 77 sources**.
All existing research snapshots and pending decisions are preserved.

Read the [Chinese per-record checklist](generated/审批清单.zh-CN.md),
[exact machine-readable scopes](selection.json), [record dossiers](generated/dossier.json),
[fresh original-source lock](source-lock.json), and
[production-resolver difference](generated/resolver-diff.json).

Nine existing assignment IDs and seven existing permanent physical IDs were
reviewed separately. Eight assignment scopes and seven physical identities are
class A recommendations; MJV is class B. There are no newly reviewed class C
records; eleven earlier blocked codes remain blocked and are not credited as
new research. Classification is a Codex recommendation, never a human decision.

## Evidence and scope choices

- India: VOSR, VOGB, VEKI, VEPY and VOKU retain `[2024-02-23, 2026-07-09)`.
  Ten earlier original AD pages were freshly recovered and hash-matched. Five
  targeted intermediate AD pages from the 2025-06-12 archive corroborate the
  same official names, indicators and ARPs. Chapter publication and amendment
  dates differ from archive edition dates and are recorded separately. Multiple
  AAI editions are temporal observations from **one issuer**. They are not two
  or three independent publishing organizations. Kurnool's conflicting opening
  years remain outside the authorization scope.
- LEMI and RMU: `[2019-08-02, 2026-10-29)` is proposed as bounded same-site
  continuity between the contemporaneous new-airport code statement in the
  2019 parliamentary publication and the 2026 ENAIRE observation. The
  parliamentary statement is a proponent's text, not an allocation notice.
  The long uninspected interval remains an explicit inference risk.
- LELC: **narrowed** to `[2026-04-17, 2026-10-29)`. The 2019 statement about
  the former civil-service site does not prove an active code assignment on
  that publication day. Only the two 2026 official observations support this
  proposed interval. MJV lacks an earlier dated active-code observation and
  remains pending without an approval window. This deliberately does not adopt
  the market pipeline's four uniform cross-year windows.

An airport's lifetime, its service-opening date, a code
association and a continuous assignment are distinct claims. No opening date,
first allocation, final withdrawal, code handover, historical official-name
interval or timezone upgrade is authorized here. Physical identities, display
names and ARP coordinates require separate decisions; name/coordinate attributes
stay `reference`, and timezones stay `unknown`.

All **19 cited original components** were freshly acquired and independently
extracted in this task: **14** matched prior original-byte locks; **5** are
targeted intermediate observations. Only minimal citations and content hashes
are committed. Full originals and extractions stay in ignored `work/`. Online
access and independent extraction establish custody and quoted content, not
human approval or redistribution rights. Offline CI validates retained excerpts
and reproduces outputs; it does not claim to re-download protected originals.

The AAI navigation and cover pages contain specimen template labels. They were
not used as substantive publication-date evidence. The July 2026 GEN 0.2
component still ends with June and is not used to date July. Same-archive AD
AIRAC metadata supplies actual edition anchors. ENAIRE's current index explicitly
marks the new WEF 2026-10-01 and the old WEF 2026-09-03; both Murcia rows are
unmarked current entries. Access on October 29 is an observation, not withdrawal.

Three sampled Indian editions and the scoped Spanish originals contain no
competing allocation/site evidence. This is **not** an exhaustive search of
every intermediate AIRAC, NOTAM or allocation ledger. Continuity remains a
human decision with unknown outer intervals. No new worldwide scan was run.

## Reproduce

Node 24, pnpm 10.14.0, Python 3 and the existing Poppler extractor are sufficient.
No additional dependency, database, server or UI is introduced.

```sh
pnpm evidence:first-admission build
pnpm evidence:first-admission validate
pnpm exec vitest run test/first-admission.test.ts
pnpm check

# Optional: only when independently obtained originals are in private storage.
# Each file is named <sourceId>.bin and must match source-lock.json exactly.
pnpm evidence:first-admission verify-originals work/first-admission-originals
```

Original recovery reused `evidence:global fetch --recover` for the thirteen
global sources and `evidence:markets fetch --recover` for the ENAIRE index.
The five new middle-edition sources have explicit original URLs in the lock.
No inaccessible or changed response was substituted for an existing snapshot.
The optional command authenticates original bytes, independently runs the
existing extractor and checks every raw-HTML/normalized-page citation position.

The builder consumes the immutable proposals by canonical ID. It writes a
**pending-only** scoped proposed dataset; verified hypothesis states are never
serialized. It calls the actual `resolveAirport()` for each singleton A scope
and for their deduplicated union, over all 4,320 local dates from 2015-01-01
through 2026-10-29. It additionally exercises first/last/adjacent dates and
protects all formal code/date answers over the benchmark plus every existing
boundary and its adjacent dates, including boundaries before 2015. All existing
formal records must remain byte-identical, and the original admission gate must
reject the scoped dataset.

Expected accepted-hypothesis gain: **9,820** unique queries (**IATA 2,645;
ICAO 7,175**). Against formal 0.8.0 these are `not_found → resolved`; against
the same unapproved scoped proposal they are `uncertain → resolved`. Another
24,740 outside-window queries become `not_found → uncertain` after the open
possibilities are introduced. This consequence is disclosed, not counted as
coverage. Existing complete answers, resolved identities and conflict states
remain unchanged. There are no `conflict → resolved` transitions.

For a later 0.9.0 admission, consume only explicit per-ID owner decisions and
the exact `exactAuthorization` scopes. The existing event-owner/admission
workflow still needs real accepted decisions and source reviews; these files
are not executable authorization. In particular, do not approve an event group,
copy market-wide intervals, or serialize the in-memory review hypothesis.
