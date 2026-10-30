"""Export bounded pending-review packets and validate proposed bulk admissions offline."""
import argparse
import datetime
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from common import ROOT, canonical, checked, digest, read_jsonl, research_baseline_path, write_json
from triage import OUT

sys.path.insert(0, str(ROOT / 'scripts/discovery'))
from review import CLAIMS, validate_batch_series


def packets(groups, reviewed_on, base_commit, maximum_events=20):
    """Unlimited batches, each subject to the existing <=20-event validation."""
    if not 1 <= maximum_events <= 20:
        raise ValueError('Each batch must contain 1..20 events')
    datetime.date.fromisoformat(reviewed_on)
    config = json.loads((ROOT / 'research/discovery/sources.json').read_text())
    sources = {s['id']: s for s in config['sources']}
    chunk = []
    batch_number = 0

    def packet(events, number):
        sids = sorted({m['sourceId'] for g in events for m in g['members']})
        batch = {
            'formatVersion': 1, 'batchId': f'bulk-proposal-{number}', 'reviewedOn': reviewed_on,
            'baseCommit': base_commit, 'preparationOnly': True,
            'selection': {'maximumEvents': maximum_events, 'eventCount': len(events),
                          'policy': 'Deterministic source-transition triage. Pending evidence review, not a completed admission.'},
            'statusCounts': {'pending_review': len(events), 'ready_to_admit': 0, 'excluded': 0, 'insufficient_evidence': 0},
            'admission': {'airports': 0, 'assignments': 0, 'names': 0, 'formalSources': 0},
            'sources': [{
                'sourceId': sid, 'url': sources[sid]['url'] + '/tree/' + sources[sid]['revision'],
                'sourceType': 'secondary', 'accessedOn': reviewed_on,
                'supportedFacts': ['Pinned secondary-source record revisions only.'],
                'limitations': ['No historical effective dates or independent confirmation established.'],
                'accessResult': 'Offline mechanical inspection of repository-controlled hash-checked discovery artifacts.',
                'license': {'id': sources[sid]['license'], 'note': 'Original upstream data license; primary-source documents not redistributed.'},
            } for sid in sids],
            'events': [], 'nextBatch': [],
        }
        for group in events:
            group_sources = sorted({m['sourceId'] for m in group['members']})
            batch['events'].append({
                'eventGroupId': group['eventGroupId'], 'label': group['name'], 'reviewedOn': reviewed_on,
                'status': 'pending_review', 'candidateIds': group['candidateIds'], 'relatedCandidateIds': [],
                'sourceIds': group_sources,
                'claims': {key: {'conclusion': 'Not established; claim-specific authoritative review required.',
                                 'evidenceType': 'indirect', 'sourceIds': group_sources} for key in sorted(CLAIMS)},
                'continuityInference': {'evidenceType': 'continuity_inference', 'usedForAdmission': False,
                                        'note': 'Source commits do not create continuous historical validity.'},
                'evidenceGaps': group['evidenceGaps'], 'conflicts': ['Directory correction versus real-world event has not been independently adjudicated.'],
                'exclusionReason': None, 'nextAction': group['nextAction'],
                'admittedAirportIds': [], 'admittedAssignmentIds': [], 'admittedNameIds': [],
            })
        return batch

    for group in groups:
        if group['status'] == 'existing_review':
            continue
        chunk.append(group)
        if len(chunk) == maximum_events:
            batch_number += 1
            yield packet(chunk, batch_number)
            chunk = []
    if chunk:
        yield packet(chunk, batch_number + 1)


def validate_admission(base, proposed, batches, dossier, *, policy_context=None):
    """Validate the review/evidence gate before writing a reviewable proposed dataset.

    Human review is the default. A policy receipt must pass the separate owner
    authorization and deterministic re-evaluation gate before it can replace it.
    """
    validate_batch_series(batches)
    policy_ids = set()
    if policy_context is not None:
        sys.path.insert(0, str(ROOT / 'scripts/evidence'))
        from policy_gate import validate_context
        policy_ids = validate_context(base, proposed, batches, dossier, policy_context)
    if proposed['schemaVersion'] != base['schemaVersion']:
        raise ValueError('Bulk admissions cannot change the historical schema')
    if proposed['dataVersion'] == base['dataVersion']:
        raise ValueError('A formal admission needs a new historical dataVersion')
    additions = {}
    identifiers = {'airports': 'airportId', 'assignments': 'assignmentId', 'names': 'nameId', 'sources': 'sourceId'}
    for collection, id_field in identifiers.items():
        old = {r[id_field]: r for r in base[collection]}
        new = {r[id_field]: r for r in proposed[collection]}
        if len(new) != len(proposed[collection]) or any(new.get(key) != value for key, value in old.items()):
            raise ValueError('Bulk admission changes or duplicates existing permanent records')
        additions[collection] = {key: value for key, value in new.items() if key not in old}
    ready = [e for b in batches for e in b['events'] if e['status'] == 'ready_to_admit']
    if any(b.get('preparationOnly') for b in batches):
        raise ValueError('Prepared packets must receive explicit claim review before admission')
    for collection, field in [('airports', 'admittedAirportIds'), ('assignments', 'admittedAssignmentIds'), ('names', 'admittedNameIds')]:
        ids = [key for event in ready for key in event[field]]
        if len(ids) != len(set(ids)) or set(ids) != set(additions[collection]):
            raise ValueError('Proposed additions and ready-to-admit review mappings disagree')
    official = {s['sourceId']: s for s in proposed['sources']}
    original_families = {'ourairports', 'airport-codes', 'airport-codes-raw', 'airportsdata', 'mwgg', 'lineage_unestablished'}
    all_dossier_ids = [d['recordId'] for d in dossier]
    if len(all_dossier_ids) != len(set(all_dossier_ids)):
        raise ValueError('Duplicate evidence dossier record')
    for collection in ('airports', 'assignments', 'names'):
        for record_id, record in additions[collection].items():
            entry = next((d for d in dossier if d['recordId'] == record_id), None)
            if entry and entry.get('reviewMode') in ('policy', 'batch'):
                mode = entry['reviewMode']
                if (record_id not in policy_ids or entry.get('decision') != mode + '_accepted' or
                        entry.get('reviewer') != (None if mode == 'policy' else 'keepraw')):
                    raise ValueError('Admission lacks valid policy authorization')
            elif entry is None or entry.get('decision') != 'accepted' or not entry.get('reviewer'):
                raise ValueError('Admission lacks explicit human claim review')
            event = next(e for e in ready if record_id in sum((e[k] for k in ('admittedAirportIds', 'admittedAssignmentIds', 'admittedNameIds')), []))
            claim = 'physicalIdentity' if collection == 'airports' else 'historicalNames' if collection == 'names' else record['scheme'].lower()
            evidence_ids = set(event['claims'][claim]['sourceIds'])
            record_sources = set(record['sourceIds']) if collection != 'airports' else set(record['coordinates']['sourceIds'])
            dated_primary = False
            for observation in entry.get('observations', []):
                source = official.get(observation.get('sourceId'))
                if source is None or source['sourceId'] not in evidence_ids & record_sources:
                    raise ValueError('Dossier source is not linked to the admitted claim and record')
                if source['verificationStatus'] != 'verified' or source['sourceType'] != 'primary':
                    continue
                date = datetime.date.fromisoformat(observation['observedOn'])
                if date > datetime.date.fromisoformat(event['reviewedOn']):
                    raise ValueError('Observation postdates its claim review')
                if not observation.get('sourceFamily') or observation['sourceFamily'] in original_families:
                    raise ValueError('Directory derivatives cannot supply independent primary confirmation')
                if observation.get('independentOriginal') is not True or not observation.get('claimScope') or not observation.get('basis'):
                    raise ValueError('Missing original-publication provenance or claim scope')
                dated_primary = True
            if not dated_primary:
                raise ValueError('Bulk admission requires a reviewed dated original primary observation')
            if collection in ('assignments', 'names') and (not entry.get('boundaryAssessment') or not entry.get('continuityAssessment')):
                raise ValueError('Historical intervals need explicit boundary and continuity assessments')
    if not any(additions[k] for k in ('airports', 'assignments', 'names')):
        raise ValueError('No historical facts proposed for admission')
    return {key: len(value) for key, value in additions.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--output', type=Path, required=True)
    prepare.add_argument('--date', required=True)
    prepare.add_argument('--base-commit', required=True)
    prepare.add_argument('--maximum-events', type=int, default=20)
    admit = sub.add_parser('validate')
    admit.add_argument('--batches', type=Path, required=True)
    admit.add_argument('--dataset', type=Path, required=True)
    admit.add_argument('--dossier', type=Path, required=True)
    admit.add_argument('--output', type=Path, required=True)
    admit.add_argument('--base-dataset', type=Path,
                       help='Replay against an immutable published snapshot; policy replay selects its frozen baseline')
    admit.add_argument('--policy-context', type=Path, help='Exact authorized policy receipt, including original-verification record')
    args = parser.parse_args()
    if args.command == 'prepare':
        if args.output.exists() and any(args.output.iterdir()):
            raise ValueError('Use an empty output directory to prevent stale or overwritten review packets')
        lock = json.loads((OUT / 'manifest.json').read_text())
        checked(OUT / 'groups.jsonl.gz', lock['files']['groups.jsonl.gz']['sha256'])
        count, events = 0, 0
        # Validate each independent batch before writing; global group/candidate uniqueness is
        # guaranteed by the triage primary keys and checked by reference validation.
        for batch in packets(read_jsonl(OUT / 'groups.jsonl.gz'), args.date, args.base_commit, args.maximum_events):
            validate_batch_series([batch])
            write_json(args.output / (batch['batchId'] + '.json'), batch)
            count += 1
            events += len(batch['events'])
        write_json(args.output / 'packet-manifest.lock', {
            'preparedOn': args.date, 'baseCommit': args.base_commit, 'events': events, 'batches': count,
            'maximumEventsPerBatch': args.maximum_events, 'evidenceStatus': 'pending_review_only',
            'groupsSha256': lock['files']['groups.jsonl.gz']['sha256'],
            'files': {p.name: digest(p) for p in sorted(args.output.glob('*.json'))},
        })
        print(f'Prepared {count} pending-review batches; no historical facts admitted.')
    else:
        base_path = ROOT / 'data/airports.json'
        if args.policy_context is not None:
            sys.path.insert(0, str(ROOT / 'scripts/evidence'))
            from policy_review import inputs
            pinned_base = ROOT / inputs()[1]['baseline']['path']
            if args.base_dataset is not None and args.base_dataset.resolve() != pinned_base.resolve():
                raise ValueError('Policy replay requires its frozen published baseline')
            base_path = pinned_base
        elif args.base_dataset is not None:
            baselines = {
                research_baseline_path().resolve(): '31c5735b333881d7afdd527fe4af1db8e28413d5bba114fbf88a4aad0809cff7',
                (ROOT / 'test/curated-0.8.0.json').resolve(): 'b7880507c50cf8f993c98b3ec66f34e6433c452d7637eea7c6bfe61edbf166a3',
                (ROOT / 'test/curated-0.9.0.json').resolve(): '1beec87eac60c8f844a5756073811edadbfb6d4a831fb4f03ce5552796ce539b',
            }
            base_path = args.base_dataset.resolve()
            if base_path not in baselines:
                raise ValueError('Admission replay requires the immutable reviewed baseline')
            checked(base_path, baselines[base_path])
        base = json.loads(base_path.read_text())
        proposed = json.loads(args.dataset.read_text())
        batches = [json.loads(p.read_text()) for p in sorted(args.batches.glob('*.json'))]
        existing = [json.loads(p.read_text()) for p in sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
        validate_batch_series([*existing, *batches])
        dossier = json.loads(args.dossier.read_text())
        context = json.loads(args.policy_context.read_text()) if args.policy_context else None
        counts = validate_admission(base, proposed, batches, dossier, policy_context=context)
        # Use the SAME schema and semantic gate as the historical dataset, including
        # overlap/evidence checks. Output is a proposal; never overwrite curated data.
        validation = '''import {readFileSync} from "node:fs";
import {assertDataset} from "./src/validate.ts";
assertDataset(JSON.parse(readFileSync(process.argv[1], "utf8")));'''
        subprocess.run(['node', '--input-type=module', '-e', validation, str(args.dataset.resolve())], cwd=ROOT, check=True)
        if args.output.resolve() == (ROOT / 'data/airports.json').resolve():
            raise ValueError('Write a reviewable proposal; curated replacement is a separate reviewed edit')
        write_json(args.output, proposed)
        print(canonical({'validatedProposedAdditions': counts, 'output': str(args.output)}))


if __name__ == '__main__':
    main()
