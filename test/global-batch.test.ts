import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { resolveAirport } from "../src/resolve.ts";
import { assertDataset } from "../src/validate.ts";
import type { Dataset } from "../src/types.ts";

const read = (p:string) => JSON.parse(readFileSync(new URL(p,import.meta.url),"utf8"));
const formal:Dataset=read("../test/curated-0.8.0.json");
const pending:Dataset=read("../research/evidence/global/generated/proposed-data.json");
const report=read("../research/evidence/global/generated/query-coverage.json");

describe("global historical proposals",()=>{
  it("validates pending records without altering formal history",()=>{
    assertDataset(pending);
    expect(formal).toEqual(read("./curated-0.8.0.json"));
    expect(pending.assignments.slice(formal.assignments.length).every(a=>a.verificationStatus==="pending"&&a.verifiedOn===null)).toBe(true);
    expect(resolveAirport(pending,"DRP","2024-01-24").status).toBe("uncertain");
  });

  it("retains zero formal benefit and records exhaustive in-memory query results",()=>{
    expect(report.formalNewResolvedQueries).toBe(0);
    expect(report.potentialNewResolvedQueries).toBeGreaterThan(0);
    expect(report.changedPublishedResolvedQueries).toBe(0);
    expect(report.changedPendingResolvedQueries).toBe(0);
    expect(report.byAssignment).toHaveLength(pending.assignments.length-formal.assignments.length);
    expect(report.byAssignment.find((a:{code:string})=>a.code==="LLER").newlyResolvedDays).toBe(0);
    const assessment=read("../research/evidence/global/assessments.json");
    for(const a of assessment.assignments){
      if(a.certaintyPolicy!=="bounded_continuity")
        expect(report.byAssignment.find((r:{assignmentId:string})=>r.assignmentId===a.assignmentId).newlyResolvedDays).toBe(0);
    }
  });

  it("actually resolves the preserved KSGU cross-site blocker under a test-only approval hypothesis",()=>{
    const old:Dataset=read("../research/evidence/direct/generated/proposed-data.json");
    const trial=structuredClone(formal);
    const assignments=old.assignments.filter(a=>a.code==="KSGU");
    const airportIds=new Set(assignments.map(a=>a.airportId));
    const sourceIds=new Set(assignments.flatMap(a=>a.sourceIds));
    trial.airports.push(...old.airports.filter(a=>airportIds.has(a.airportId)));
    const existingSources=new Set(trial.sources.map(s=>s.sourceId));
    trial.sources.push(...old.sources.filter(s=>sourceIds.has(s.sourceId)&&!existingSources.has(s.sourceId)));
    for(const s of trial.sources) if(sourceIds.has(s.sourceId))s.verificationStatus="verified";
    trial.assignments.push(...assignments.map(a=>({...a,verificationStatus:"verified" as const,verifiedOn:"2026-10-29"})));
    for(const date of ["2011-01-01","2011-12-16","2014-07-23","2024-01-01"]){
      const result=resolveAirport(trial,"KSGU",date,"ICAO");
      expect(result.status).toBe("uncertain");
      expect(new Set(result.candidates.map(c=>c.airport.airportId)).size).toBe(2);
    }
    expect(formal.assignments.some(a=>a.code==="KSGU")).toBe(false);
  });
});
