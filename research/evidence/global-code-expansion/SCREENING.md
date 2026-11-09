# Complete global candidate screening

`python3 scripts/evidence/global_code_screen.py` reads the existing discovery
shards, reference records, triage event groups, code links and geographic reuse
leads. It fetches no original, scans no Git history and changes no formal data.
`python3 scripts/evidence/global_code_screen.py --check` repeats the pass in ignored
`work/` and requires byte-identical generated outputs and a matching manifest.

The screening covers all 1,240,058 existing source revision candidates, classifies
their existing exclusions/deferred observations, joins all 117,356 selected
candidates to all 88,330 event groups, and ranks every event group. It separately
ranks all 2,484 source code-association candidates and all 493 geographic reuse
leads. Input and output SHA-256 values are recorded in `screening-manifest.json`.

| Output | Scope |
|---|---|
| `ranked-events.manifest.json` and `ranked-events.*.jsonl.gz` | Every event group, ordered by score and stable event ID across bounded shards |
| `ranked-code-links.jsonl.gz` | Every code-association candidate, including malformed source values |
| `ranked-reuse-leads.jsonl.gz` | Every geographic reuse lead, with event and formal-code joins |
| `high-value-queue.jsonl.gz` | All events scoring at least 65, excluding previously rejected interpretations |
| `queue-*.json` | Up to 100 acquisition clusters per broad reading market; navigation slices only |
| `screening-summary.json` | Complete pass counts, exclusions, tiers, source and country breakdowns |

Read ranked event shards in the manifest's `files` array order. Each gzip contains
complete JSONL records and at most 8 MiB of uncompressed bytes. The manifest records
each shard's SHA-256, compressed and uncompressed byte counts, record count and
first/last rank, plus aggregate counts and the SHA-256 of the concatenated
uncompressed stream. Sharding preserves every record and its global rank.
`screening-manifest.json` covers the index and every shard. Deterministic checking
also rejects missing or stale screening outputs, including the retired monolithic
`ranked-events.jsonl.gz`.

There is one global score. No country or market receives a quota or score bonus.
The full high-value queue has no airport/event cap. The three readable market
slices do not set the scope or investigation count. Research batches can follow
any higher-value event in the complete ranked output.

The score rewards explicit typed code replacements and additions/removals,
geographically distinct associations, existing formal physical identities,
reusable exact-ID evidence, and passenger-airport reference types. A spatial
difference adds value only alongside a typed code change; a very large difference
reduces priority because source repurposing is plausible. Previously excluded
interpretations, duplicate/unknown/nonexistent labels and observations with no
typed code change receive penalties. The per-row point breakdown is auditable.
Source availability is represented by reusable evidence and issuer discovery
entry points, not by claiming an unfetched AIP is accessible. Directory licence
metadata is retained separately from missing primary-source use rights.

`researchClusterKey` groups the same reference/name and typed code set for shared
acquisition. Related event groups remain visible, but do not become independent
historical events or corroborating sources simply because different directories
or revisions repeat them. Review reports should count distinct investigated
physical cases/acquisition clusters alongside raw event-group IDs.

Coordinates do not prove relocation. A code appearing at separated reference
locations does not prove chronological reuse. A same-site code edit may be an
allocation, correction or duplicate; an opening/closure observation does not
establish the corresponding code boundary. GPS/IDENT values are never silently
converted into ICAO. OurAirports derivatives are one source family, and other
directory lineages remain unestablished.

Every ranked record retains unknown date bounds and labels forecast coverage as
unmeasured. This pass admits zero assignments and generates zero formal resolved
answers. Only claim-specific original review and production `resolveAirport()`
differentials can establish candidate coverage; formal merged results must be
reported separately.
