# Changelog

## 0.14.0

- Publish Schema 4.0.0 as the initial production format, with permanent physical
  airport identities, dated IATA and ICAO assignments, and historical name intervals.
- Resolve codes and official names offline with exact and uncertain date bounds
  and report conflicting assignments.
- Build a deterministic distribution and verify the production dataset against
  an immutable Git commit and SHA-256.
