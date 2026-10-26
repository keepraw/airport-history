export type VerificationStatus = "verified" | "pending" | "disputed";
/** Nature of the publication, independent of the claim it supports. */
export type SourceType = "primary" | "secondary";
/** Basis for the whole continuous claim, not just an event at one boundary. */
export type EvidenceType =
  | "primary_direct"
  | "indirect"
  | "continuity_inference";
export interface Source {
  sourceId: string;
  title: string;
  url: string;
  accessedOn: string;
  verificationStatus: VerificationStatus;
  sourceType: SourceType;
  license: { id: string; url: string | null; note: string };
  note: string;
}
export interface Fact<T> {
  value: T | null;
  status: "verified" | "reference" | "unknown";
  sourceIds: string[];
  note: string;
}
export interface PhysicalAirport {
  airportId: string;
  /** Compatibility reference label; use resolveAirportName for historical use. */
  name: Fact<string>;
  coordinates: Fact<{ latitude: number; longitude: number }>;
  timezone: Fact<string>;
  externalIds: { ourAirports?: string };
}
/** Bounds on the actual boundary, NOT an asserted start/end date. */
export interface Boundary {
  earliest: string | null;
  latest: string | null;
  precision: "exact" | "day" | "month" | "year" | "unknown";
}
export interface CodeAssignment {
  assignmentId: string;
  scheme: "IATA" | "ICAO";
  code: string;
  airportId: string;
  validFrom: Boundary;
  validTo: Boundary;
  verificationStatus: VerificationStatus;
  verifiedOn: string | null;
  evidenceType: EvidenceType;
  sourceIds: string[];
  note: string;
}
/** One canonical official name, alias or translation; city names are not airport names. */
export interface AirportName {
  nameId: string;
  airportId: string;
  name: string;
  language: string;
  kind: "official" | "alias" | "translation";
  validFrom: Boundary;
  validTo: Boundary;
  verificationStatus: VerificationStatus;
  verifiedOn: string | null;
  evidenceType: EvidenceType;
  sourceIds: string[];
  note: string;
}
export interface Dataset {
  schemaVersion: "3.0.0";
  dataVersion: string;
  sources: Source[];
  airports: PhysicalAirport[];
  assignments: CodeAssignment[];
  names: AirportName[];
}
export interface AirportNameCandidate {
  record: AirportName;
  temporalMatch: "certain" | "possible";
  evidence: Source[];
}
export interface AirportNameResolution {
  status:
    | "resolved"
    | "reference"
    | "uncertain"
    | "conflict"
    | "not_found"
    | "invalid_input";
  dataVersion: string;
  query: { airportId: string; date: string };
  airport: PhysicalAirport | null;
  name: string | null;
  language: string | null;
  historicallyVerified: boolean;
  candidates: AirportNameCandidate[];
  evidence: Source[];
  reason: string;
}
export interface Candidate {
  airport: PhysicalAirport;
  assignment: CodeAssignment;
  temporalMatch: "certain" | "possible";
  evidence: Source[];
}
export interface Resolution {
  status: "resolved" | "not_found" | "uncertain" | "conflict" | "invalid_input";
  dataVersion: string;
  query: { code: string; date: string; scheme: "IATA" | "ICAO" };
  airport: PhysicalAirport | null;
  candidates: Candidate[];
  evidence: Source[];
  reason: string;
}
