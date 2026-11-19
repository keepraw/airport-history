# Maintaining the data

Keep a permanent `airportId` for each physical site. A new site gets its own ID
when it takes over a code. Changes to an airport's name or codes retain its
physical ID. External identity mappings identify the same physical site.

Treat IATA and ICAO as separate namespaces. Set a boundary for the assignment
supported by the available dates. A dated opening or rename by itself leaves
the code-assignment date unknown. When a precise handover is unavailable,
keep the possible range and set the corresponding boundary precision.

Use `official` for a canonical airport name with its own time interval.
Record aliases and translations with their respective kinds. Keep reference
display names, coordinates, and geographical timezones as independent
attributes.

Discuss supporting sources and proposed factual changes during PR review.
Record useful context in the dataset's notes and preserve required attribution.
[Third-party notices](../THIRD_PARTY_NOTICES.md)
