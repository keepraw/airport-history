# Public-data research licensing

JSONL names identify logical datasets. `jsonl-shards.json` maps each to its ordered gzip files, including sequential `.000.jsonl.gz` shards. The attribution and license scopes below cover every shard and its concatenated dataset.

This package is research material, outside the formal resolver database.

- Wikidata structured main-namespace facts: [CC0](https://www.wikidata.org/wiki/Wikidata:Licensing). Only structured facts, revision IDs and factual change annotations are redistributed; no revision-comment corpus or referenced articles are included.
- OurAirports: public domain. Existing airport-codes derivatives retain their existing ODC-PDDL notices and remain one source family. Reused airportsdata reference attributes retain MIT terms and the notice at `reference/LICENSE-airportsdata`.
- OpenStreetMap: **© OpenStreetMap contributors**, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), [copyright and attribution](https://www.openstreetmap.org/copyright). `osm-airport-entities.jsonl.gz` and `osm-history.jsonl.gz` are OSM-derived databases. The combined `global-crosswalk.jsonl.gz`, `historical-code-candidates.jsonl.gz`, and `physical-reuse-candidates.jsonl.gz` also retain ODbL obligations where they include OSM matches. This package makes no CC0 or MIT relicensing claim over those combined databases. The OSM source snapshots and derived objects needed to inspect those joins are supplied alongside them. Any further public use must retain attribution and applicable share-alike obligations. No OSM data enters `proposed-data.json` or formal data.
- FAA NASR: selected factual US government airport fields, under the government-work scope of [17 USC 105](https://www.copyright.gov/title17/92chap1.html#105). Archives may contain other material; only the listed airport facts are redistributed. No owner contact details, telephone numbers, charts or third-party PDF layouts are included. The original archives remain in the local acquisition cache and are identified by URLs and hashes.
- BTS: factual government AirportID/AirportSeqID lookup records. Descriptions are retained as lookup facts; no flight-record corpus was acquired.

Referenced news, operator and other originals are not redistributed. Wikidata reference URLs do not confer rights in linked content. Source locks preserve acquisition metadata and hashes; restricted originals are not added to the repository.
