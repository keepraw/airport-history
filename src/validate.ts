import Ajv from "ajv";
import addFormats from "ajv-formats";
import schema from "../schema/dataset.schema.json" with { type: "json" };
import { bounds, dateNumber, interval, overlaps } from "./time.ts";
import { hasReviewedEvidence } from "./evidence.ts";
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
  unique(
    data.names.map((n) => n.nameId),
    "nameId",
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
  for (const name of data.names) {
    try {
      if (Intl.getCanonicalLocales(name.language)[0] !== name.language)
        errors.push(
          `${name.nameId}: language must be a canonical language tag`,
        );
    } catch {
      errors.push(`${name.nameId}: invalid language tag`);
    }
  }
  // Names and code assignments share temporal and evidence requirements.
  for (const a of [...data.assignments, ...data.names]) {
    const id = "assignmentId" in a ? a.assignmentId : a.nameId;
    checkRefs(a.sourceIds, id);
    if (
      a.evidenceType === "primary_direct" &&
      !a.sourceIds.some((id) => sourceById.get(id)?.sourceType === "primary")
    )
      errors.push(
        `${id}: primary_direct needs a primary source supporting the claim`,
      );
    if (!airportIds.has(a.airportId))
      errors.push(`${id}: missing airport ${a.airportId}`);
    checkBoundary(a.validFrom, `${id}.validFrom`);
    checkBoundary(a.validTo, `${id}.validTo`);
    const start = bounds(a.validFrom),
      end = bounds(a.validTo);
    if (start[0] >= end[1])
      errors.push(`${id}: impossible or inconsistent interval`);
    if (a.verificationStatus === "verified") {
      if (!a.verifiedOn) errors.push(`${id}: verifiedOn required`);
      for (const sourceId of a.sourceIds) {
        const source = sourceById.get(sourceId);
        if (source?.verificationStatus !== "verified")
          errors.push(`${id}: unreviewed evidence ${sourceId}`);
        if (source && a.verifiedOn && source.accessedOn > a.verifiedOn)
          errors.push(`${id}: verification predates evidence access`);
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
        if (!overlaps(ai.possible, bi.possible)) continue;
        if (
          !hasReviewedEvidence(a, sourceById) ||
          !hasReviewedEvidence(b, sourceById)
        )
          warnings.push(
            `Unconfirmed assignment overlap (review required): ${pair}`,
          );
        else if (overlaps(ai.certain, bi.certain))
          errors.push(`Conflicting assignments (confirmed conflict): ${pair}`);
        else warnings.push(`Possible boundary overlap: ${pair}`);
      }
    }
  }
  for (let i = 0; i < data.names.length; i++) {
    const a = data.names[i]!;
    for (const b of data.names.slice(i + 1)) {
      if (a.airportId !== b.airportId || a.kind !== b.kind) continue;
      const sameName = a.name === b.name && a.language === b.language;
      const pair = `${a.nameId} / ${b.nameId}`;
      if (
        sameName &&
        a.validFrom.earliest === b.validFrom.earliest &&
        a.validFrom.latest === b.validFrom.latest &&
        a.validTo.earliest === b.validTo.earliest &&
        a.validTo.latest === b.validTo.latest
      )
        errors.push(`Duplicate airport name interval: ${pair}`);
      if (a.kind !== "official" || sameName) continue;
      const ai = interval(a),
        bi = interval(b);
      if (!overlaps(ai.possible, bi.possible)) continue;
      if (
        !hasReviewedEvidence(a, sourceById) ||
        !hasReviewedEvidence(b, sourceById)
      )
        warnings.push(
          `Unconfirmed official-name overlap (review required): ${pair}`,
        );
      else if (overlaps(ai.certain, bi.certain))
        errors.push(`Conflicting official names (confirmed conflict): ${pair}`);
      else warnings.push(`Possible official-name boundary overlap: ${pair}`);
    }
  }
  return { errors, warnings };
}
export function assertDataset(input: unknown): asserts input is Dataset {
  const { errors } = validateDataset(input);
  if (errors.length) throw new Error(errors.join("\n"));
}
