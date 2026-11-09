"""Validate this research packet offline; --originals also checks retained private bytes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts/evidence'))
from global_code_audit import ranked_rows

def read(path):
    return json.loads(path.read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def relative(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Escaping evidence path')
    return path

def validate(originals=False):
    sources = read(DIRECTORY / 'source-acquisition.json')['sources']
    assert len({s['sourceId'] for s in sources}) == len(sources)
    acquired = [s for s in sources if s['accessResult'] == 'original_acquired']
    assert len({s['originalSha256'] for s in acquired}) == len(acquired)
    for source in acquired:
        for field in ('originalSha256', 'extractedTextSha256', 'normalizedTextSha256', 'excerptSha256'):
            assert re.fullmatch('[a-f0-9]{64}', source[field]), (source['sourceId'], field)
        assert source['rights']['fullRedistribution'] == 'not_established'
        path = relative(DIRECTORY, source['excerptPath'])
        assert digest(path) == source['excerptSha256']
        excerpt = read(path)
        for field in ('originalSha256', 'extractedTextSha256', 'normalizedTextSha256'):
            assert excerpt[field] == source[field]
        for span in excerpt['spans']:
            assert len(span['quote']) == span['characterEnd'] - span['characterStart']
            assert hashlib.sha256(span['quote'].encode()).hexdigest() == span['quoteSha256']
        if originals:
            for path_field, sha_field in [('privateOriginalPath', 'originalSha256'),
                    ('privateExtractedTextPath', 'extractedTextSha256'),
                    ('privateNormalizedTextPath', 'normalizedTextSha256')]:
                path = relative(ROOT, source[path_field])
                assert path.is_relative_to(ROOT / 'work'), 'Original outside ignored custody'
                assert digest(path) == source[sha_field], source['sourceId']
            text = relative(ROOT, source['privateNormalizedTextPath']).read_text()
            for span in excerpt['spans']:
                assert text[span['characterStart']:span['characterEnd']] == span['quote']
    reused = read(DIRECTORY / 'reused-evidence.json')['sources']
    for source in reused:
        assert digest(relative(ROOT, source['receiptPath'])) == source['receiptFileSha256']
        assert source['rawBytesReverifiedThisRun'] is False
        if source.get('excerptPath'):
            assert digest(relative(ROOT, source['excerptPath'])) == source['excerptSha256']
    ranked = {row['eventGroupId']: row for row in ranked_rows()}
    events = read(DIRECTORY / 'assessments.json')['events']
    ids = [event['eventGroupId'] for event in events]
    assert len(ids) == len(set(ids))
    for event in events:
        row = ranked[event['eventGroupId']]
        assert event['candidateId'] == row['candidateId']
        assert event['globalRanking']['rank'] == row['rank']
        assert event['globalRanking']['priorityTier'] == row['priorityTier']
        assert event['rankedPriorityScore'] == row['priorityScore']
        assert event['formalAdmission']['eligible'] is False
        assert set(event['sourceIds']).issubset({s['sourceId'] for s in sources + reused})
    batches = read(DIRECTORY / 'review-batches.json')['batches']
    batched = [gid for batch in batches for gid in batch['eventGroupIds']]
    assert len(batched) == len(set(batched)) and set(batched) == set(ids)
    assert all(len(batch['eventGroupIds']) <= batch['maximumEvents'] <= 20 for batch in batches)
    claims = read(DIRECTORY / 'claims.json')
    assert not any(claims[key] for key in ['sources', 'airports', 'assignments', 'claims'])
    summary = read(DIRECTORY / 'summary.json')
    actual = sum(event['globalRanking']['priorityTier'] == 'high' and
        event['researchStatus'] == 'original_or_locked_evidence_inspected' for event in events)
    assert summary['highValueGroupsActuallyResearched'] == actual
    assert summary['canonicalEventGroups'] == len(events)
    assert summary['newOriginalsObtained'] == len(acquired)
    assert summary['newFormalIATAAssignments'] == summary['newFormalICAOAssignments'] == 0
    return {'formatVersion': 1, 'mode': 'private_originals_replayed' if originals else 'offline_public_receipts',
        'canonicalEventGroups': len(events), 'highValueOriginalOrLockedEvidenceCases': actual,
        'acquiredOriginalsWithTripleHash': len(acquired), 'reusedSourceReceiptsChecked': len(reused),
        'sourceFamiliesNotAuthority': True, 'formalAdmissions': 0, 'rawByteAcquisitionPerformed': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--originals', action='store_true')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report = validate(args.originals)
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.write:
        (DIRECTORY / 'validation.json').write_text(text)
    print(text, end='')
