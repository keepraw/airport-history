export interface Fact<T> {
  value: T | null;
  status: "verified" | "reference" | "unknown";
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
  note: string;
}
export interface Dataset {
  schemaVersion: "4.0.0";
  dataVersion: string;
  airports: PhysicalAirport[];
  assignments: CodeAssignment[];
  names: AirportName[];
}
export interface AirportNameCandidate {
  record: AirportName;
  temporalMatch: "certain" | "possible";
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
  /** Whether an official-name interval establishes the name on the query date. */
  historicallyVerified: boolean;
  candidates: AirportNameCandidate[];
  reason: string;
}
export interface Candidate {
  airport: PhysicalAirport;
  assignment: CodeAssignment;
  temporalMatch: "certain" | "possible";
}
export interface Resolution {
  status: "resolved" | "not_found" | "uncertain" | "conflict" | "invalid_input";
  dataVersion: string;
  query: { code: string; date: string; scheme: "IATA" | "ICAO" };
  airport: PhysicalAirport | null;
  candidates: Candidate[];
  reason: string;
}
