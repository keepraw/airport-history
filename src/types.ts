export type VerificationStatus = "verified" | "pending" | "disputed";
export interface Source {
  sourceId: string;
  title: string;
  url: string;
  accessedOn: string;
  verificationStatus: VerificationStatus;
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
  sourceIds: string[];
  note: string;
}
export interface Dataset {
  schemaVersion: "1.0.0";
  dataVersion: string;
  sources: Source[];
  airports: PhysicalAirport[];
  assignments: CodeAssignment[];
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
