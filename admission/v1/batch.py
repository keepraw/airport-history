"""Data-driven Korean identity discovery and complete competition inventories."""
import gzip
from pathlib import Path

from runtime import ROOT, PUBLIC, load, sha
from evidence import old


def inventory(base, registry):
    items = []
    for airport in base['airports']:
        if airport['coordinates']['value'] is not None:
            entry = next((r for r in registry['identities'] if r['airportId'] == airport['airportId']), {})
            items.append({'inventoryId': airport['airportId'], 'siteKey': entry.get('siteKey'),
                'coordinates': airport['coordinates']['value'], 'status': 'formal',
                'codes': sorted(a['code'] for a in base['assignments'] if a['airportId'] == airport['airportId'])})
    formal_ids = {a['airportId'] for a in base['airports']}
    for entry in registry['identities']:
        if entry['airportId'] not in formal_ids:
            items.append({'inventoryId': entry['airportId'], 'siteKey': entry['siteKey'],
                          'coordinates': entry['coordinates'], 'status': 'pending', 'codes': []})
    # All pinned Korean reference locations, including closed and historical
    # hypotheses, participate. Reference rows are never promoted to authority.
    for path in sorted((ROOT / 'reference/generated').glob('records.*.jsonl.gz')):
        with gzip.open(path, 'rt') as f:
            for line in f:
                record = __import__('json').loads(line)
                codes = {v for v in record['identifiers'].values() if v} | {h['code'] for h in record['historicalIdentifiers']}
                if record['country'] != 'KR' and not any(code.startswith('RK') for code in codes):
                    continue
                for location in record['locations']:
                    if location['coordinates'] is None:
                        continue
                    items.append({'inventoryId': location['locationId'], 'referenceId': record['referenceId'],
                        'siteKey': None, 'coordinates': location['coordinates'], 'status': 'reference',
                        'historical': record['facilityType'] == 'closed' or location['kind'] != 'snapshot',
                        'codes': sorted({v for v in record['identifiers'].values() if v} |
                                        {h['code'] for h in record['historicalIdentifiers']}),
                        'name': record['name']})
    return sorted(items, key=lambda r: (r['inventoryId'], r.get('referenceId', '')))


def discover(competition):
    timeline = load(old.PACKET / 'aip-timeline.json')
    # This catalog is evidence metadata, never an allowlist in the classifier.
    # New airports use the same record shape and the same country rule grant.
    catalog = load(PUBLIC / 'candidate-catalog.json')
    candidates = []
    for row in catalog['candidates']:
        observations = []
        for edition in timeline['editions']:
            if edition['kind'] != 'AIRAC':
                continue
            observations.append({'sourceId': row['editionSources'][edition['amendment']],
                'effectiveUtc': edition['effectiveUtc'], 'aipName': row['aipName'], 'arpDms': row['arpDms']})
        candidates.append({'candidateKey': row['candidateKey'], 'country': catalog['country'],
            'issuerFamily': catalog['issuerFamily'], 'name': row['name'], 'observedCode': row['observedCode'],
            'observations': observations, 'independent': row['independent'],
            'editionControl': {'fromUtc': observations[0]['effectiveUtc'], 'toUtc': observations[-1]['effectiveUtc'],
                'expectedIntermediateEditions': ['AIP AMDT ' + e['amendment'] for e in timeline['editions'] if e['kind'] == 'ordinary'],
                'index': {'sourceId': 'kr-history', 'tokens': ['16 APR 2025', '14 MAY 2025']},
                'intermediateEditions': [{'edition': 'AIP AMDT ' + e['amendment'],
                    'sourceId': e['controlSourceIds'][2], 'tokens': ['5/25', '1 MAY 2025']}
                    for e in timeline['editions'] if e['kind'] == 'ordinary']},
            'riskReview': {'coverageSourceIds': row['riskSourceIds'], 'signals': []},
            'competitionInventorySha256': sha(competition)})
    return candidates
