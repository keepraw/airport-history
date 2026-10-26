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

`LicenseRef-Reference-Only` means no open redistribution license was established.
It is not a permission grant. Source access/review status is separate from its
license: reading a copyrighted source does not make it CC0. The GAO federal report
is identified separately; embedded third-party content is not covered by that
identification. If importing further third-party data, verify its actual terms
and preserve attribution/license notices before including it.

The JSON source registry carries URLs, access dates, review status and license
scope. Every airport attribute and code assignment references that registry.
No bulk worldwide airport snapshot is shipped. Runtime resolution never downloads
or substitutes a current directory for historical evidence.
