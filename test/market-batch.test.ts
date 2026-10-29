import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { resolveAirport } from "../src/resolve.ts";
import { assertDataset } from "../src/validate.ts";
import type { Dataset } from "../src/types.ts";

const read=(path:string)=>JSON.parse(readFileSync(new URL(path,import.meta.url),"utf8"));
const base:Dataset=read("../data/airports.json");
const pending:Dataset=read("../research/evidence/markets/generated/proposed-data.json");
const hypothetical=structuredClone(pending);
const published=new Set(base.assignments.map(a=>a.assignmentId));
for(const s of hypothetical.sources)if(s.verificationStatus==="pending")s.verificationStatus="verified";
for(const a of hypothetical.assignments)if(!published.has(a.assignmentId)){
  a.verificationStatus="verified";a.verifiedOn="2026-10-29";
}

describe("priority-market historical review hypotheses",()=>{
  it("resolves both Murcia physical sites while preserving pending-only formal status",()=>{
    assertDataset(pending);assertDataset(hypothetical);
    for(const [iata,icao] of [["MJV","LELC"],["RMU","LEMI"]]){
      for(const date of ["2019-08-02","2021-06-15","2026-10-28"]){
        const r=resolveAirport(hypothetical,iata!,date);
        expect(r.status).toBe("resolved");
        expect(r.airport?.airportId).toBe(resolveAirport(hypothetical,icao!,date,"ICAO").airport?.airportId);
        expect(resolveAirport(pending,iata!,date).status).toBe("uncertain");
      }
      for(const date of ["2019-08-01","2019-01-15","2026-10-29"])
        expect(resolveAirport(hypothetical,iata!,date).status).toBe("uncertain");
    }
    expect(resolveAirport(hypothetical,"MJV","2021-06-15").airport?.airportId)
      .not.toBe(resolveAirport(hypothetical,"RMU","2021-06-15").airport?.airportId);
  });

  it("does not turn Chinese association rows, guide years or openings into resolved dates",()=>{
    for(const code of ["AKA","ENY","DAX","DZH","LYG","YBP","JNZ"])
      for(const date of ["2015-01-01","2022-05-19","2023-07-01","2026-10-29"])
        expect(resolveAirport(hypothetical,code,date).status).toBe("uncertain");
    expect(pending.assignments.some(a=>a.code==="KXWA")).toBe(false);
    expect(pending.assignments.some(a=>a.code==="KDXZ")).toBe(false);
    expect(pending.assignments.some(a=>a.code==="KSGU")).toBe(false);
    expect(base).toEqual(read("./curated-0.8.0.json"));
  });

  it("separates complete different-code replacement from unresolved same-IATA transfers",()=>{
    const m=read("../research/evidence/markets/generated/metrics.json");
    expect(m.completeSameIataCrossSiteChains).toBe(0);
    expect(m.completeDifferentIataReplacementChains).toBe(1);
    expect(m.incrementalPotentialResolvedQueries.IATA).toBeGreaterThan(0);
    expect(m.changedPublishedResolvedQueries).toBe(0);
    expect(m.formalNewResolvedQueries).toBe(0);
  });
});
