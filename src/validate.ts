import Ajv from "ajv";
import addFormats from "ajv-formats";
import schema from "../schema/dataset.schema.json" with { type: "json" };
import { bounds, dateNumber, interval, overlaps } from "./time.ts";
import type { Boundary, Dataset } from "./types.ts";

const ajv = new Ajv({ allErrors: true, strict: true });
addFormats(ajv);
const validateSchema = ajv.compile<Dataset>(schema);
export interface ValidationResult {
  errors: string[];
  warnings: string[];
}
export function validateDataset(input: unknown): ValidationResult {
  const errors: string[] = [],
    warnings: string[] = [];
  if (!validateSchema(input))
    return {
      errors: (validateSchema.errors ?? []).map(
        (e) => `${e.instancePath || "/"} ${e.message}`,
      ),
      warnings,
    };
  const data = input;
  const unique = (values: string[], kind: string) => {
    const seen = new Set<string>();
    for (const id of values) {
      if (seen.has(id)) errors.push(`Duplicate ${kind}: ${id}`);
      seen.add(id);
    }
  };
  unique(
    data.airports.map((a) => a.airportId),
    "airportId",
  );
  unique(
    data.airports.flatMap((a) =>
      a.externalIds.ourAirports ? [a.externalIds.ourAirports] : [],
    ),
    "OurAirports identity",
  );
  unique(
    data.assignments.map((a) => a.assignmentId),
    "assignmentId",
  );
  unique(
    data.sources.map((s) => s.sourceId),
    "sourceId",
  );
  const sourceById = new Map(data.sources.map((s) => [s.sourceId, s]));
  const airportIds = new Set(data.airports.map((a) => a.airportId));
  const checkRefs = (ids: string[], label: string) => {
    for (const id of ids)
      if (!sourceById.has(id)) errors.push(`${label}: missing source ${id}`);
  };
  function checkBoundary(b: Boundary, label: string) {
    const [min, max] = bounds(b);
    if (min > max) errors.push(`${label}: reversed boundary`);
    if (b.precision === "unknown") return;
    if (b.earliest === null || b.latest === null) {
      errors.push(`${label}: precision requires both bounds`);
      return;
    }
    if (b.precision === "exact") {
      if (min !== max)
        errors.push(`${label}: exact boundary must have equal dates`);
      return;
    }
    const y = Number(b.earliest.slice(0, 4));
    const m = Number(b.earliest.slice(5, 7));
    let expected = min + 1;
    if (b.precision === "month") {
      if (!b.earliest.endsWith("-01"))
        errors.push(`${label}: month must begin on day 01`);
      expected = dateNumber(
        `${String(m === 12 ? y + 1 : y).padStart(4, "0")}-${String(m === 12 ? 1 : m + 1).padStart(2, "0")}-01`,
      );
    }
    if (b.precision === "year") {
      if (!b.earliest.endsWith("-01-01"))
        errors.push(`${label}: year must begin on January 01`);
      expected = dateNumber(`${String(y + 1).padStart(4, "0")}-01-01`);
    }
    if (max !== expected)
      errors.push(`${label}: bounds do not match ${b.precision} precision`);
  }
  for (const airport of data.airports) {
    for (const [key, fact] of Object.entries({
      name: airport.name,
      coordinates: airport.coordinates,
      timezone: airport.timezone,
    })) {
      const label = `${airport.airportId}.${key}`;
      checkRefs(fact.sourceIds, label);
      if ((fact.value === null) !== (fact.status === "unknown"))
        errors.push(`${label}: null must have unknown status and vice versa`);
      if (fact.value !== null && !fact.sourceIds.length)
        errors.push(`${label}: known fact needs evidence`);
      if (
        fact.status === "verified" &&
        fact.sourceIds.some(
          (id) => sourceById.get(id)?.verificationStatus !== "verified",
        )
      )
        errors.push(`${label}: verified fact needs reviewed sources`);
    }
    if (airport.name.value === null)
      errors.push(`${airport.airportId}: needs a display name`);
    if (airport.timezone.value !== null) {
      try {
        new Intl.DateTimeFormat("en", { timeZone: airport.timezone.value });
      } catch {
        errors.push(`${airport.airportId}: invalid IANA timezone`);
      }
    }
  }
  for (const a of data.assignments) {
    checkRefs(a.sourceIds, a.assignmentId);
    if (!airportIds.has(a.airportId))
      errors.push(`${a.assignmentId}: missing airport ${a.airportId}`);
    checkBoundary(a.validFrom, `${a.assignmentId}.validFrom`);
    checkBoundary(a.validTo, `${a.assignmentId}.validTo`);
    const start = bounds(a.validFrom),
      end = bounds(a.validTo);
    if (start[0] >= end[1])
      errors.push(`${a.assignmentId}: impossible or inconsistent interval`);
    if (a.verificationStatus === "verified") {
      if (!a.verifiedOn) errors.push(`${a.assignmentId}: verifiedOn required`);
      for (const id of a.sourceIds) {
        const source = sourceById.get(id);
        if (source?.verificationStatus !== "verified")
          errors.push(`${a.assignmentId}: unreviewed evidence ${id}`);
        if (source && a.verifiedOn && source.accessedOn > a.verifiedOn)
          errors.push(
            `${a.assignmentId}: verification predates evidence access`,
          );
      }
    }
  }
  for (let i = 0; i < data.assignments.length; i++) {
    const a = data.assignments[i]!;
    for (const b of data.assignments.slice(i + 1)) {
      if (a.scheme !== b.scheme || a.code !== b.code) continue;
      const ai = interval(a),
        bi = interval(b);
      const pair = `${a.assignmentId} / ${b.assignmentId}`;
      if (
        a.airportId === b.airportId &&
        a.validFrom.earliest === b.validFrom.earliest &&
        a.validFrom.latest === b.validFrom.latest &&
        a.validTo.earliest === b.validTo.earliest &&
        a.validTo.latest === b.validTo.latest
      )
        errors.push(`Duplicate assignment: ${pair}`);
      if (a.airportId !== b.airportId) {
        if (overlaps(ai.certain, bi.certain))
          errors.push(`Conflicting assignments: ${pair}`);
        else if (overlaps(ai.possible, bi.possible))
          warnings.push(`Possible boundary overlap: ${pair}`);
      }
    }
  }
  return { errors, warnings };
}
export function assertDataset(input: unknown): asserts input is Dataset {
  const { errors } = validateDataset(input);
  if (errors.length) throw new Error(errors.join("\n"));
}
