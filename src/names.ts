import { dateNumber, interval, overlaps } from "./time.ts";
import type { AirportNameResolution, Dataset } from "./types.ts";

/** Pure, offline canonical official-name resolution. Validate the dataset first.
 * Aliases and translations never establish an official-name interval.
 */
export function resolveAirportName(
  dataset: Dataset,
  airportId: string,
  date: string,
): AirportNameResolution {
  const result: AirportNameResolution = {
    status: "not_found",
    dataVersion: dataset.dataVersion,
    query: { airportId, date },
    airport: null,
    name: null,
    language: null,
    historicallyVerified: false,
    candidates: [],
    reason: "",
  };
  const start = dateNumber(date);
  if (!Number.isFinite(start) || !airportId.trim())
    return {
      ...result,
      status: "invalid_input",
      reason: "Use an airportId and a valid local Gregorian YYYY-MM-DD date.",
    };
  const airport = dataset.airports.find((a) => a.airportId === airportId);
  if (!airport)
    return { ...result, reason: "No physical airport has this permanent ID." };
  result.airport = airport;
  const day: [number, number] = [start, start + 1];
  for (const record of dataset.names) {
    if (record.airportId !== airportId || record.kind !== "official") continue;
    const span = interval(record);
    if (!overlaps(day, span.possible)) continue;
    result.candidates.push({
      record,
      temporalMatch:
        span.certain[0] <= start && span.certain[1] >= start + 1
          ? "certain"
          : "possible",
    });
  }
  result.candidates.sort((a, b) =>
    a.record.nameId < b.record.nameId
      ? -1
      : a.record.nameId > b.record.nameId
        ? 1
        : 0,
  );
  if (!result.candidates.length)
    return {
      ...result,
      status: "reference",
      name: airport.name.value,
      reason:
        "No official-name record covers this date. The display label is a reference.",
    };
  const certain = result.candidates.find(
    (candidate) => candidate.temporalMatch === "certain",
  );
  if (certain) {
    const competing = result.candidates.filter(
      ({ record }) =>
        record.name !== certain.record.name ||
        record.language !== certain.record.language,
    );
    if (competing.some((candidate) => candidate.temporalMatch === "certain"))
      return {
        ...result,
        status: "conflict",
        reason:
          "Different official names have intervals covering the whole date.",
      };
    if (!competing.length)
      return {
        ...result,
        status: "resolved",
        name: certain.record.name,
        language: certain.record.language,
        historicallyVerified: true,
        reason: "One official name covers the whole date.",
      };
  }
  return {
    ...result,
    status: "uncertain",
    reason: "The date bounds leave the official name uncertain.",
  };
}
