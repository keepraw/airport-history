/** Research-only admission differential; never changes the formal dataset. */
import {readFileSync, writeFileSync} from 'node:fs';
import {assertDataset} from '../../src/validate.ts';
import {resolveAirport} from '../../src/resolve.ts';
import {dateNumber} from '../../src/time.ts';
import type {Dataset} from '../../src/types.ts';
const dir=process.argv[2]??'research/evidence/global-public-data';
const baseline:Dataset=JSON.parse(readFileSync('data/airports.json','utf8'));
const proposal=JSON.parse(readFileSync(`${dir}/admission-proposal.json`,'utf8'));
if(baseline.dataVersion!=='0.12.0'||baseline.schemaVersion!=='3.0.0')throw new Error('Unexpected baseline');
const pending:Dataset=JSON.parse(readFileSync(`${dir}/proposed-data.json`,'utf8'));
const simulated=structuredClone(pending);
const oldAssignments=new Set(baseline.assignments.map(a=>a.assignmentId)),oldSources=new Set(baseline.sources.map(s=>s.sourceId));
for(const source of simulated.sources)if(!oldSources.has(source.sourceId))source.verificationStatus='verified';
for(const assignment of simulated.assignments)if(!oldAssignments.has(assignment.assignmentId)){assignment.verificationStatus='verified';assignment.verifiedOn='2026-11-10';}
for(const key of ['airports','assignments','sources','names'] as const){
 for(const row of baseline[key])if(!pending[key].some(p=>JSON.stringify(p)===JSON.stringify(row)))throw new Error(`Baseline ${key} changed`);
}
assertDataset(pending);assertDataset(simulated);
const codes:{scheme:'IATA'|'ICAO',code:string}[]=JSON.parse(readFileSync(`${dir}/resolver-query-codes.json`,'utf8'));
for(const a of simulated.assignments)if(!codes.some(c=>c.code===a.code&&c.scheme===a.scheme))codes.push({scheme:a.scheme,code:a.code});
const from=dateNumber('1970-01-01'),to=dateNumber('2026-11-11');
const outcomes:Record<string,number>={};let calls=0,gains=0,uncertain=0,notfound=0,changed=0,conflicts=0,newUncertain=0;
for(const {scheme,code} of codes){
 const cuts=new Set([from,to]);
 for(const a of simulated.assignments.filter(a=>a.scheme===scheme&&a.code===code)){
  for(const b of [a.validFrom,a.validTo])for(const d of [b.earliest,b.latest])if(d){const n=dateNumber(d);if(n>from&&n<to)cuts.add(n);}
 }
 const sorted=[...cuts].sort((a,b)=>a-b);
 for(let i=0;i<sorted.length-1;i++){
  const date=new Date(sorted[i]!*86400000).toISOString().slice(0,10),days=sorted[i+1]!-sorted[i]!;
  const b=resolveAirport(baseline,code,date,scheme),a=resolveAirport(simulated,code,date,scheme);calls+=2;
  // Resolver status and identity are invariant within assignment-boundary partitions.
  outcomes[b.status]=(outcomes[b.status]??0)+days;
  if(a.status==='resolved'&&b.status!=='resolved'){gains+=days;if(b.status==='uncertain')uncertain+=days;if(b.status==='not_found')notfound+=days;}
  if(b.status==='resolved'&&(a.status!=='resolved'||a.airport?.airportId!==b.airport?.airportId))changed+=days;
  if(a.status==='conflict'&&b.status!=='conflict')conflicts+=days;
  if(a.status==='uncertain'&&b.status==='not_found')newUncertain+=days;
 }
}
if(changed||conflicts)throw new Error('Proposal changes existing resolved answers or creates conflicts');
const report={baselineDataVersion:baseline.dataVersion,horizon:['1970-01-01','2026-11-10'],eligibleOverlayAssignments:simulated.assignments.length-baseline.assignments.length,uniqueSchemeCodeKeys:codes.length,actualResolverCalls:calls,baselineCodeDateQueryCells:outcomes,newResolvedCodeDateQueries:gains,uncertainToResolved:uncertain,notFoundToResolved:notfound,existingResolvedAnswersChanged:changed,newConflicts:conflicts,notFoundToUncertainNotCoverageGain:newUncertain,realHistoricalFlightRecords:null,unit:'Synthetic namespace/code/day query cells; boundary-partition weighted exact resolver results, never actual flight counts.',limitation:'Conditional Owner-approved hypothesis for the FAA bounded proposals only. Pending proposal is not production data. No authorization or verification state is written into formal data.'};
writeFileSync(`${dir}/resolver-diff.json`,JSON.stringify(report,null,2)+'\n');
const coverage=JSON.parse(readFileSync(`${dir}/coverage-report.json`,'utf8'));coverage.productionResolver=report;writeFileSync(`${dir}/coverage-report.json`,JSON.stringify(coverage,null,2)+'\n');
console.log(JSON.stringify(report));
