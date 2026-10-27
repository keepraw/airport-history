# Licensing and source scope

Code, schemas, tests and project documentation: MIT (`LICENSE`).
Project-authored database selection, arrangement, IDs and factual annotations:
CC0 1.0 (`LICENSE-DATA`), to the extent the contributors hold rights to them.
This dedication does not change third-party licenses or confer rights in marks.

| Material | Upstream terms | Use in this repository |
| --- | --- | --- |
| Thirteen OurAirports rows (eight bootstrap, five batch 1), fixed commit in `data/airports.json` | [Public domain declaration](https://ourairports.com/data/) | Names, reference coordinates, numeric external IDs; current codes corroborate continuing assignments. Separate source records preserve each batch's scope; no full snapshot shipped |
| Wikidata structured statements, Q673202 / Q1436575 | [CC0 1.0](https://www.wikidata.org/wiki/Wikidata:Licensing) | Historic code associations and day-level end qualifiers; secondary evidence |
| IANA tzdb 2025b `zone1970.tab` | [Public domain](https://data.iana.org/time-zones/tzdb-2025b/LICENSE) | Eight geographical zone identifiers (four bootstrap, four batch 1); no code or offset tables copied |
| Government reports, airline/airport notices, news articles, Aviation Safety Network, TRB, Helis and Fluko | Each publisher retains its applicable rights; see per-source license records | Links and independently written factual notes only; no source article, PDF, table, image or lengthy extract distributed. Batch 1 includes airport-authored material hosted on Routes and public broadcaster reports classified as secondary |
| Kazakhstan Government Resolutions Nos. 1095 (2006) and 381 (2017), including the original newspaper reproduction and Adilet publication metadata | No open redistribution license established; `LicenseRef-Reference-Only` | Official-name facts and independently written evidence notes with links; no document, newspaper page or PDF redistributed. The new name intervals are reviewed continuity inferences; current reference labels do not prove earlier use |

`LicenseRef-Reference-Only` means no open redistribution license was established.
It is not a permission grant. Source access/review status is separate from its
license: reading a copyrighted source does not make it CC0. The GAO federal report
is identified separately; embedded third-party content is not covered by that
identification. If importing further third-party data, verify its actual terms
and preserve attribution/license notices before including it.

The JSON source registry carries URLs, access dates, review status and license
scope. Every airport attribute, code assignment and name record references that registry.
Formal resolver artifacts contain only the curated historical dataset. Runtime
resolution never downloads or substitutes a current directory for historical
evidence. The separate research inventories are described below.

## Global discovery research artifacts

`research/discovery/generated/` is a separate, non-runtime research layer. It
contains source field transitions, version/coverage metadata and historical
external-record inventories, including closed/deleted/codeless records. It does
not add a worldwide current directory to the formal history database.

| Material | Pinned source and terms | Research use |
| --- | --- | --- |
| OurAirports airport export history | `davidmegginson/ourairports-data` at `d97df1673cc5ba61a09b17ab5936091a669a04ca`; [public domain](https://ourairports.com/data/) | Raw field differences and external record identities; dates are repository observations |
| Derived/raw/earlier OurAirports CSV paths | `datasets/airport-codes` at `0a775c03687f0b57175df2285592397c1099b9dc`; upstream metadata declares ODC-PDDL-1.0 and OurAirports public-domain origin | Every reachable relevant file revision; derivative source overlap remains explicit. [PDDL text](research/discovery/licenses/PDDL-1.0.txt) retained |
| Airport/city-code data and Keepraw-Fly directory comparison | `mborsetti/airportsdata` at `47ae282a8491758e6dafe28d4139539e561b54d5`; Keepraw-Fly pinned directory derives from `d306f66b5c33617e0bc13d413fea07292a5d9211`; MIT | Field transitions, external inventories and comparison facts; [full copyright/license notice](research/discovery/licenses/airportsdata-MIT.txt) retained, including its mwgg attribution |
| Earlier upstream airport JSON history | `mwgg/Airports` at `a89e4e0dda9d9878337e2da190ebe1ef1d6af705`; MIT | Parseable source revisions and explicit malformed/duplicate-key gaps; [full copyright/license notice](research/discovery/licenses/mwgg-MIT.txt) retained |
| Wikidata capability probes | CC0 structured main-namespace data; download documentation and API/dump metadata linked in `source-assessment.json` | Original factual capability notes, revision IDs, sizes and hashes; no full global Wikidata dump or historical statements imported |

MIT source extracts retain MIT terms; they are not relicensed under the project's
CC0 data dedication. Research annotations and tooling do not change the upstream
terms. Official notices and prior deferred evidence remain reference-only links
and independent factual notes; no copyrighted articles/PDFs are bundled.
