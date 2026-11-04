"""Human Admission v1: synthetic end-to-end and negative tests.

Everything here is fictional (Ardenia, Borovia, Calderra; ZQ*/ZZ* codes) and runs
in a disposable clone under ignored work/. Owner comments and original downloads
are simulated in-process only; the production CLI has no switch for either.
"""
import copy
import re
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWED_ON = '2026-11-04'
VERSION = '0.11.0'
APPROVAL_URL = 'https://github.com/keepraw/airport-history/issues/999#issuecomment-123456789'

A1, A2, B1, C1 = ('apt_00000000-0000-4000-8000-0000000000a1', 'apt_00000000-0000-4000-8000-0000000000a2',
                  'apt_00000000-0000-4000-8000-0000000000b1', 'apt_00000000-0000-4000-8000-0000000000c1')

# Fictional originals: url -> (extractor, text, [(quote, recordIds, dates)])
ARDENIA = ['hv1t-a1-iata-zqa', 'hv1t-a2-iata-zqa', 'hv1t-a1-icao-zzqa', 'hv1t-a2-icao-zzqb', A1, A2]
BOROVIA = ['hv1t-b1-icao-zzra', 'hv1t-b1-icao-zzrb', 'hv1t-b1-iata-zqr', 'hv1t-b1-name-central', B1]
DOCS = {
    'hv1t-ardenia-gazette-2019': ('https://example.org/ardenia/gazette-7-2019.txt', 'utf8-text', 'ardenia',
        'Ardenia Civil Aviation Gazette No. 7 of 2019.\nWith effect from 1 June 2019 the code ZQA is transferred '
        'from Ardenia Old Field to Ardenia New International Airport.\n',
        [('With effect from 1 June 2019 the code ZQA is transferred', ARDENIA, [('code_effective', '2019-06-01')])]),
    'hv1t-ardenia-aip-2018': ('https://example.org/ardenia/aip-2018-03-01.txt', 'utf8-text', 'ardenia',
        'Ardenia AIP edition effective 2018-03-01.\nAD 1.3\nARDENIA OLD FIELD ZZQA ZQA lat 10.10 lon 20.10\n'
        'ARDENIA NEW INTERNATIONAL ZZQB lat 10.30 lon 20.40\n',
        [('ARDENIA OLD FIELD ZZQA ZQA lat 10.10 lon 20.10', ARDENIA, [('observed_in_force', '2018-03-01')]),
         ('ARDENIA NEW INTERNATIONAL ZZQB lat 10.30 lon 20.40', ARDENIA, [('observed_in_force', '2018-03-01')])]),
    'hv1t-ardenia-aip-2024': ('https://example.org/ardenia/aip-2024-01-15.txt', 'utf8-text', 'ardenia',
        'Ardenia AIP edition effective 2024-01-15.\nAD 1.3\nARDENIA OLD FIELD ZZQA\nARDENIA NEW INTERNATIONAL ZZQB ZQA\n',
        [('ARDENIA OLD FIELD ZZQA', ARDENIA, [('observed_in_force', '2024-01-15')]),
         ('ARDENIA NEW INTERNATIONAL ZZQB ZQA', ARDENIA, [('observed_in_force', '2024-01-15')])]),
    'hv1t-borovia-notice-2020': ('https://example.org/borovia/notice-12-2020.html', 'html-text', 'borovia',
        '<html><body><h1>Borovia CAA Notice 12/2020</h1><p>Effective 1 March 2020 the ICAO indicator of Borovia '
        'Central Airport changes from ZZRA to ZZRB and its official name becomes Queen Mira International Airport.</p>'
        '</body></html>',
        [('Effective 1 March 2020 the ICAO indicator of Borovia Central Airport changes from ZZRA to ZZRB', BOROVIA,
          [('code_effective', '2020-03-01'), ('name_effective', '2020-03-01'), ('capture', '2026-11-04')])]),
    'hv1t-borovia-aip-2016': ('https://example.org/borovia/aip-2016-05-05.txt', 'utf8-text', 'borovia',
        'Borovia AIP edition effective 2016-05-05.\nBOROVIA CENTRAL AIRPORT ZZRA ZQR lat 30.00 lon 40.00\n',
        [('BOROVIA CENTRAL AIRPORT ZZRA ZQR lat 30.00 lon 40.00', BOROVIA, [('observed_in_force', '2016-05-05')])]),
    'hv1t-borovia-aip-2025': ('https://example.org/borovia/aip-2025-02-20.txt', 'utf8-text', 'borovia',
        'Borovia AIP edition effective 2025-02-20.\nQUEEN MIRA INTERNATIONAL AIRPORT ZZRB ZQR\n',
        [('QUEEN MIRA INTERNATIONAL AIRPORT ZZRB ZQR', BOROVIA, [('observed_in_force', '2025-02-20')])]),
    'hv1t-calderra-aip-2023': ('https://example.org/calderra/aip-2023-09-09.txt', 'utf8-text', 'calderra',
        'Calderra AIP edition effective 2023-09-09.\nAD 2 CALDERRA FIELD reference point lat 50.00 lon 60.00\n',
        [('AD 2 CALDERRA FIELD reference point lat 50.00 lon 60.00', [C1], [('observed_in_force', '2023-09-09')])]),
}


def h(data):
    return hashlib.sha256(data).hexdigest()


def load_core(root):
    spec = importlib.util.spec_from_file_location('human_core_' + h(str(root).encode())[:8], root / 'admission/human-v1/core.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_cli(root, core):
    import sys
    sys.modules['core'] = core
    spec = importlib.util.spec_from_file_location('human_cli_' + h(str(root).encode())[:8], root / 'admission/human-v1/human.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---- namespacing: every run uses codes/IDs derived from the base dataVersion, so
# the suite stays valid on any later main, including after earlier human releases.
ns, ids = {}, {}
_CODE = re.compile(r'\b(ZZ?)([QR])([A-Z]?)\b')


def L(value):
    if isinstance(value, str):
        shift = ns['shift']
        value = _CODE.sub(lambda m: m[1] + chr(ord(m[2]) + shift) + m[3], value)
        value = value.replace('hv1t-', 'hv1t%d-' % ns['minor']).replace('synthetic-three-country-1',
                                                                    'synthetic-three-country-%d' % ns['minor'])
        return re.sub(r'0000000000(a1|a2|b1|c1)\b', lambda m: '%010x%s' % (ns['minor'], m[1]), value)
    if isinstance(value, list):
        return [L(v) for v in value]
    if isinstance(value, tuple):
        return tuple(L(v) for v in value)
    if isinstance(value, dict):
        return {L(k): L(v) for k, v in value.items()}
    return value


def configure(base_version):
    major, minor, _ = map(int, base_version.split('.'))
    ns.update(minor=minor, shift=2 * (minor - 10), base=base_version, version='%d.%d.0' % (major, minor + 1),
              after='%d.%d.0' % (major, minor + 2))
    ids.update({k: L(v) for k, v in (('A1', A1), ('A2', A2), ('B1', B1), ('C1', C1))})


def originals(core):
    return {L(url): L(text).encode() for (url, _, _, text, _) in DOCS.values()}


def localized_spec(core):
    s = L(spec(core))
    s['targetDataVersion'] = ns['version']
    docs = {L(sid): L(doc) for sid, doc in DOCS.items()}
    for entry in s['evidence']['lock']['sources']:
        url, extractor, _, text, _ = docs[entry['sourceId']]
        body = core.extract(text.encode(), extractor)
        entry.update(originalSha256=h(text.encode()), textSha256=h(body.encode()))
        for c in entry['citations']:
            start = body.index(c['quote'])
            c.update(characterStart=start, characterEnd=start + len(c['quote']), quoteSha256=h(c['quote'].encode()))
    return s


def window(earliest, latest, precision='unknown'):
    return {'earliest': earliest, 'latest': latest, 'precision': precision}


def airport(airport_id, name, lat, lon, sids):
    return {'airportId': airport_id,
            'coordinates': {'note': 'Fictional reference point.', 'sourceIds': sids, 'status': 'reference',
                            'value': {'latitude': lat, 'longitude': lon}},
            'externalIds': {}, 'name': {'note': 'Display label only.', 'sourceIds': sids, 'status': 'reference', 'value': name},
            'timezone': {'note': 'No timezone claim.', 'sourceIds': [], 'status': 'unknown', 'value': None}}


def assignment(aid, airport_id, scheme, code, start, end, sids):
    return {'airportId': airport_id, 'assignmentId': aid, 'code': code, 'evidenceType': 'continuity_inference',
            'note': 'Fictional test assignment.', 'scheme': scheme, 'sourceIds': sids, 'validFrom': start, 'validTo': end,
            'verificationStatus': 'verified', 'verifiedOn': REVIEWED_ON}


def spec(core):
    extract = core.extract
    sources, lock, review_sources = [], [], []
    for sid, (url, extractor, country, text, cites) in DOCS.items():
        body = extract(text.encode(), extractor)
        citations = []
        for quote, ids, dates in cites:
            start = body.index(quote)
            citations.append({'recordIds': ids, 'quote': quote, 'characterStart': start, 'characterEnd': start + len(quote),
                              'quoteSha256': h(quote.encode()), 'dates': [{'kind': k, 'date': d} for k, d in dates]})
        lock.append({'sourceId': sid, 'url': url, 'publisher': country + ' civil aviation authority (fictional)',
                     'independenceKey': country + '-caa', 'originalSha256': h(text.encode()), 'textSha256': h(body.encode()),
                     'extractor': extractor, 'rights': {'licenseId': 'LicenseRef-Fictional-Test', 'redistribution': 'citation-only'},
                     'publicationDate': None, 'effectiveDate': None, 'observedOn': '2026-11-03', 'citations': citations})
        sources.append({'accessedOn': '2026-11-03', 'license': {'id': 'LicenseRef-Fictional-Test', 'note': 'Fictional test fixture.', 'url': url},
                        'note': 'Fictional original.', 'sourceId': sid, 'sourceType': 'primary', 'title': sid, 'url': url,
                        'verificationStatus': 'verified'})
        review_sources.append({'sourceId': sid, 'url': url, 'sourceType': 'primary', 'accessedOn': REVIEWED_ON,
                               'supportedFacts': ['Fictional facts.'], 'limitations': ['Fictional.'],
                               'accessResult': 'Simulated in-process acquisition.',
                               'license': {'id': 'LicenseRef-Fictional-Test', 'note': 'Fictional.'}})
    g, a18, a24 = 'hv1t-ardenia-gazette-2019', 'hv1t-ardenia-aip-2018', 'hv1t-ardenia-aip-2024'
    n20, b16, b25, c23 = 'hv1t-borovia-notice-2020', 'hv1t-borovia-aip-2016', 'hv1t-borovia-aip-2025', 'hv1t-calderra-aip-2023'
    airports = [airport(A1, 'Ardenia Old Field', 10.10, 20.10, [a18]), airport(A2, 'Ardenia New International', 10.30, 20.40, [a18]),
                airport(B1, 'Queen Mira International Airport', 30.00, 40.00, [b16]),
                airport(C1, 'Calderra Field', 50.00, 60.00, [c23])]
    assignments = [
        assignment('hv1t-a1-iata-zqa', A1, 'IATA', 'ZQA', window(None, '2018-03-01'), window('2019-06-01', '2019-06-02', 'day'), [a18, g]),
        assignment('hv1t-a2-iata-zqa', A2, 'IATA', 'ZQA', window('2019-06-01', '2019-06-02', 'day'), window('2024-01-15', None), [g, a24]),
        assignment('hv1t-a1-icao-zzqa', A1, 'ICAO', 'ZZQA', window(None, '2018-03-01'), window('2024-01-15', None), [a18, a24]),
        assignment('hv1t-a2-icao-zzqb', A2, 'ICAO', 'ZZQB', window(None, '2018-03-01'), window('2024-01-15', None), [a18, a24]),
        assignment('hv1t-b1-icao-zzra', B1, 'ICAO', 'ZZRA', window(None, '2016-05-05'), window('2020-03-01', '2020-03-02', 'day'), [b16, n20]),
        assignment('hv1t-b1-icao-zzrb', B1, 'ICAO', 'ZZRB', window('2020-03-01', '2020-03-02', 'day'), window('2025-02-20', None), [n20, b25]),
        assignment('hv1t-b1-iata-zqr', B1, 'IATA', 'ZQR', window(None, '2016-05-05'), window('2025-02-20', None), [b16, b25]),
    ]
    names = [{'airportId': B1, 'evidenceType': 'continuity_inference', 'kind': 'official', 'language': 'en',
              'name': 'Borovia Central Airport', 'nameId': 'hv1t-b1-name-central', 'note': 'Fictional historical name.',
              'sourceIds': [b16, n20], 'validFrom': window(None, '2016-05-05'),
              'validTo': window('2020-03-01', '2020-03-02', 'day'), 'verificationStatus': 'verified', 'verifiedOn': REVIEWED_ON}]

    def basis(bound, sid, kind, date):
        return {'bound': bound, 'sourceId': sid, 'kind': kind, 'date': date}

    bounds = {
        'hv1t-a1-iata-zqa': [basis('validFrom.latest', a18, 'observed_in_force', '2018-03-01'),
                             basis('validTo.earliest', g, 'code_effective', '2019-06-01'),
                             basis('validTo.latest', g, 'code_effective', '2019-06-01')],
        'hv1t-a2-iata-zqa': [basis('validFrom.earliest', g, 'code_effective', '2019-06-01'),
                             basis('validFrom.latest', g, 'code_effective', '2019-06-01'),
                             basis('validTo.earliest', a24, 'observed_in_force', '2024-01-15')],
        'hv1t-a1-icao-zzqa': [basis('validFrom.latest', a18, 'observed_in_force', '2018-03-01'),
                              basis('validTo.earliest', a24, 'observed_in_force', '2024-01-15')],
        'hv1t-a2-icao-zzqb': [basis('validFrom.latest', a18, 'observed_in_force', '2018-03-01'),
                              basis('validTo.earliest', a24, 'observed_in_force', '2024-01-15')],
        'hv1t-b1-icao-zzra': [basis('validFrom.latest', b16, 'observed_in_force', '2016-05-05'),
                              basis('validTo.earliest', n20, 'code_effective', '2020-03-01'),
                              basis('validTo.latest', n20, 'code_effective', '2020-03-01')],
        'hv1t-b1-icao-zzrb': [basis('validFrom.earliest', n20, 'code_effective', '2020-03-01'),
                              basis('validFrom.latest', n20, 'code_effective', '2020-03-01'),
                              basis('validTo.earliest', b25, 'observed_in_force', '2025-02-20')],
        'hv1t-b1-iata-zqr': [basis('validFrom.latest', b16, 'observed_in_force', '2016-05-05'),
                             basis('validTo.earliest', b25, 'observed_in_force', '2025-02-20')],
        'hv1t-b1-name-central': [basis('validFrom.latest', b16, 'observed_in_force', '2016-05-05'),
                                 basis('validTo.earliest', n20, 'name_effective', '2020-03-01'),
                                 basis('validTo.latest', n20, 'name_effective', '2020-03-01')],
    }
    family = {'ardenia': 'fictional-ardenia-caa', 'borovia': 'fictional-borovia-caa', 'calderra': 'fictional-calderra-caa'}

    def entry(record_id, sids, interval):
        e = {'recordId': record_id, 'decision': 'accepted', 'reviewer': 'keepraw',
             'reviewBasis': 'Effective only with the recorded Owner comment bound to this batch manifest.',
             'observations': [{'sourceId': s, 'observedOn': '2026-11-03', 'sourceFamily': family[DOCS[s][2]],
                               'independentOriginal': True, 'claimScope': 'fictional', 'basis': 'fictional'} for s in sids],
             'boundBasis': bounds.get(record_id, []), 'approvedFieldUpgrades': []}
        if interval:
            e['boundaryAssessment'] = 'Bounds follow cited dates only.'
            e['continuityAssessment'] = 'Continuity between cited observations is an inference.'
        return e

    dossier = [entry(a['airportId'], a['coordinates']['sourceIds'], False) for a in airports]
    dossier += [entry(a['assignmentId'], a['sourceIds'], True) for a in assignments]
    dossier += [entry(n['nameId'], n['sourceIds'], True) for n in names]

    def event(gid, label, sids, airport_ids, assignment_ids, name_ids, status='ready_to_admit'):
        claims = {c: {'conclusion': 'Fictional %s review.' % c, 'evidenceType': 'continuity_inference', 'sourceIds': sids}
                  for c in ('physicalIdentity', 'iata', 'icao', 'historicalBoundary', 'historicalNames', 'closureAndReplacement')}
        return {'eventGroupId': gid, 'label': label, 'reviewedOn': REVIEWED_ON, 'status': status,
                'candidateIds': ['cand_hv1test_' + gid], 'relatedCandidateIds': [], 'sourceIds': sids, 'claims': claims,
                'continuityInference': {'evidenceType': 'continuity_inference', 'usedForAdmission': status == 'ready_to_admit',
                                        'note': 'Fictional.'},
                'evidenceGaps': [] if status == 'ready_to_admit' else ['Only a press report; no original.'],
                'conflicts': ['None identified in fiction.'], 'exclusionReason': None if status == 'ready_to_admit' else 'No original evidence.',
                'nextAction': 'Admit listed records only.' if status == 'ready_to_admit' else 'Find an original.',
                'admittedAirportIds': airport_ids, 'admittedAssignmentIds': assignment_ids, 'admittedNameIds': name_ids}

    events = [
        event('hv1t-ardenia-relocation', 'Ardenia relocation', [g, a18, a24], [A1, A2],
              ['hv1t-a1-iata-zqa', 'hv1t-a2-iata-zqa', 'hv1t-a1-icao-zzqa', 'hv1t-a2-icao-zzqb'], []),
        event('hv1t-borovia-recode', 'Borovia ICAO change and rename', [n20, b16, b25], [B1],
              ['hv1t-b1-icao-zzra', 'hv1t-b1-icao-zzrb', 'hv1t-b1-iata-zqr'], ['hv1t-b1-name-central']),
        event('hv1t-calderra-identity', 'Calderra physical identity only', [c23], [C1], [], []),
        event('hv1t-calderra-iata-claim', 'Calderra IATA claim', [c23], [], [], [], status='excluded'),
    ]
    return {'format': 'human-admission@1', 'batchId': 'synthetic-three-country-1', 'targetDataVersion': VERSION,
            'reviewedOn': REVIEWED_ON,
            'records': {'airports': airports, 'assignments': assignments, 'names': names, 'sources': sources},
            'events': events, 'evidence': {'lock': {'format': 'human-admission@1', 'sources': lock}, 'reviewSources': review_sources},
            'dossier': dossier,
            'excluded': [{'recordId': 'hv1t-c1-iata-zqc', 'recordType': 'assignment', 'reason': 'Press report only; no original.'}]}


class FakeGitHub:
    def __init__(self, body, login='keepraw', user_id=49091395):
        self.body, self.login, self.user_id = body, login, user_id

    def __call__(self, path):
        if path == 'repos/keepraw/airport-history':
            return {'owner': {'login': 'keepraw', 'id': 49091395}}
        return {'html_url': APPROVAL_URL, 'issue_url': 'https://api.github.com/repos/keepraw/airport-history/issues/999',
                'user': {'login': self.login, 'id': self.user_id, 'type': 'User'}, 'body': self.body,
                'created_at': '2026-11-04T01:00:00Z', 'updated_at': '2026-11-04T01:00:00Z'}


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def make_env(cls):
    """A disposable clone whose origin is a local bare repository standing in for GitHub main."""
    (ROOT / 'work').mkdir(exist_ok=True)
    cls.tmp = tempfile.TemporaryDirectory(prefix='human-v1-test-', dir=ROOT / 'work')
    cls.root = root = Path(cls.tmp.name) / 'repo'
    subprocess.run(['git', 'clone', '-q', '--no-hardlinks', str(ROOT), str(root)], check=True)
    head = git(ROOT, 'rev-parse', 'HEAD')
    subprocess.run(['git', 'checkout', '-q', head], cwd=root, check=True)
    # Test the working-tree Human v1 code (identical to HEAD in CI).
    shutil.rmtree(root / 'admission/human-v1', ignore_errors=True)
    shutil.copytree(ROOT / 'admission/human-v1', root / 'admission/human-v1', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(ROOT / '.github/workflows/human-admission.yml', root / '.github/workflows/human-admission.yml')
    base_version = json.loads((root / 'data/airports.json').read_text())['dataVersion']
    # A disposable tree whose data was reset below an existing human release (e.g. an
    # isolated policy rehearsal) must not see that later release as a competing batch.
    for later in (root / 'research/admissions').glob('*/human-v1'):
        if tuple(map(int, later.parent.name.split('.'))) > tuple(map(int, base_version.split('.'))):
            shutil.rmtree(later)
    for k, v in (('user.name', 'keepraw'), ('user.email', '49091395+keepraw@users.noreply.github.com')):
        subprocess.run(['git', 'config', '--local', k, v], cwd=root, check=True)
    for args in (['add', '-A'], ['commit', '-q', '--allow-empty', '-m', 'test base']):
        subprocess.run(['git', *args], cwd=root, check=True)
    cls.base = git(root, 'rev-parse', 'HEAD')
    cls.origin = Path(cls.tmp.name) / 'origin.git'
    subprocess.run(['git', 'init', '-q', '--bare', str(cls.origin)], check=True)
    subprocess.run(['git', 'remote', 'set-url', 'origin', str(cls.origin)], cwd=root, check=True)
    subprocess.run(['git', 'push', '-q', 'origin', cls.base + ':refs/heads/main'], cwd=root, check=True)
    subprocess.run(['git', 'fetch', '-q', 'origin', '+refs/heads/main:refs/remotes/origin/main'], cwd=root, check=True)
    (root / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
    with (root / '.git/info/exclude').open('a') as exclude:
        exclude.write('\nnode_modules\n')
    cls.core = load_core(root)
    cls.cli = load_cli(root, cls.core)
    configure(base_version)
    cls.spec = localized_spec(cls.core)
    (root / 'work').mkdir(exist_ok=True)
    cls.spec_path = root / 'work/spec.json'
    cls.spec_path.write_text(json.dumps(cls.spec))
    files = originals(cls.core)
    cls.fetch = staticmethod(lambda url: files[url])
    cls.bundle = cls.cli.prepare(cls.spec_path, cls.base)
    cls.cli.verify_originals(ns['version'], cls.fetch)
    cls.manifest, cls.result = cls.cli.build(ns['version'])
    cls.text = cls.core.approval_text(cls.manifest)
    cls.cli.record_approval(ns['version'], APPROVAL_URL, FakeGitHub(cls.text))
    cls.snapshot = {p: p.read_bytes() for p in cls.bundle.rglob('*') if p.is_file()}


def set_main(cls, commit):
    """Move the stand-in GitHub main and the clone's view of it."""
    subprocess.run(['git', 'push', '-q', '--force', 'origin', commit + ':refs/heads/main'], cwd=cls.root, check=True)
    subprocess.run(['git', 'fetch', '-q', 'origin', '+refs/heads/main:refs/remotes/origin/main'], cwd=cls.root, check=True)


def side_commit(cls, parent, message):
    """An unrelated main commit (no data change) on top of ``parent``."""
    tree = git(cls.root, 'rev-parse', parent + '^{tree}')
    return git(cls.root, 'commit-tree', tree, '-p', parent, '-m', message)


class HumanAdmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        make_env(cls)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def tearDown(self):
        for p in list(self.bundle.rglob('*')):
            if p.is_file() and p not in self.snapshot:
                p.unlink()
        for p, data in self.snapshot.items():
            p.write_bytes(data)

    def refused(self, message, fn, *args, **kwargs):
        with self.assertRaises(self.core.AdmissionError) as ctx:
            fn(*args, **kwargs)
        self.assertIn(message, str(ctx.exception))

    def validate(self, reader=None):
        return self.core.validate_bundle(self.bundle, reader=reader or FakeGitHub(self.text), root=self.root)

    def inputs(self):
        b = self.core.load_bundle(self.bundle)
        base = json.loads((self.root / 'data/airports.json').read_text())
        records = b['records']['records']
        return base, b, records, self.core.validate_evidence_lock(b['evidence-lock'], records)

    # ------------------------------------------------------------ success --
    def test_full_three_country_batch(self):
        proof = self.validate()
        m = proof['manifest']
        self.assertEqual(m['counts'], {'airports': 4, 'assignments': 7, 'names': 1, 'sources': 7})
        self.assertEqual(proof['approval']['author'], {'login': 'keepraw', 'id': 49091395})
        cov = proof['gate']['coverage']
        self.assertGreater(cov['newResolved'], 0)
        self.assertEqual((cov['changedPublishedResolved'], cov['changedExistingAnswers'], cov['newConflicts']), (0, 0, 0))
        self.assertFalse(cov['formalCoverage'])
        candidate = json.loads((self.bundle / 'proposed-data.json').read_text())
        codes = [(a['code'], a['airportId']) for a in candidate['assignments']]
        self.assertIn((L('ZQA'), ids['A1']), codes)
        self.assertIn((L('ZQA'), ids['A2']), codes)  # same code, two physical airports, disjoint history
        self.assertEqual({c for c, a in codes if a == ids['B1']}, set(L(['ZZRA', 'ZZRB', 'ZQR'])))  # several codes, one airport
        self.assertNotIn(L('hv1t-c1-iata-zqc'), json.dumps(candidate))  # excluded candidate stays out
        self.assertNotIn(ids['C1'], {a for _, a in codes})  # identity-only record
        self.assertEqual(len(m['recordIds']['names']), 1)
        text = self.text
        for rid in (ids['A1'], ids['A2'], ids['B1'], ids['C1'], L('hv1t-b1-name-central'), L('hv1t-c1-iata-zqc')):
            self.assertIn(rid, text)
        self.assertNotIn('*', text.split('\n', 1)[1])

    def test_submit_creates_formal_commit_without_merging(self):
        original = self.core.github
        self.core.github = FakeGitHub(self.text)
        try:
            branch = self.cli.submit(ns['version'])
        finally:
            self.core.github = original
        try:
            data = json.loads((self.root / 'data/airports.json').read_text())
            self.assertEqual(data['dataVersion'], ns['version'])
            self.assertEqual((self.root / ('test/curated-%s.json' % ns['version'])).read_bytes(), (self.root / 'data/airports.json').read_bytes())
            self.assertEqual(json.loads((self.root / 'package.json').read_text())['version'], ns['version'])
            self.assertFalse((self.root / '.github/workflows/ci.yml').exists())
            self.assertTrue((self.root / '.github/workflows/human-admission.yml').exists())
            ident = subprocess.check_output(['git', 'log', '-1', '--format=%an <%ae>|%cn <%ce>'], cwd=self.root, text=True).strip()
            self.assertEqual(ident, 'keepraw <49091395+keepraw@users.noreply.github.com>|keepraw <49091395+keepraw@users.noreply.github.com>')
            self.assertEqual(subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=self.root, text=True).strip(), self.base)
        finally:
            subprocess.run(['git', 'checkout', '-q', '--detach', self.base], cwd=self.root, check=True)
            subprocess.run(['git', 'branch', '-q', '-D', branch], cwd=self.root, check=True)
            for p, data in self.snapshot.items():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)

    # ----------------------------------------------------------- refusals --
    def test_01_no_owner_approval(self):
        (self.bundle / 'approval.json').unlink()
        self.refused('No Owner approval', self.validate)

    def test_02_wrong_approver(self):
        self.refused('not by Owner keepraw', self.validate, FakeGitHub(self.text, login='someone-else', user_id=1))
        self.refused('not by Owner keepraw', self.validate, FakeGitHub(self.text, user_id=49091396))

    def test_03_inexact_approval_text(self):
        self.refused('does not exactly match', self.validate, FakeGitHub(self.text.replace('exactly', 'all')))
        self.refused('does not exactly match', self.validate, FakeGitHub('approve all'))

    def test_04_candidate_hash_changed(self):
        path = self.bundle / 'proposed-data.json'
        data = json.loads(path.read_text())
        data['assignments'][-1]['note'] = 'edited after approval'
        path.write_text(json.dumps(data))
        self.refused('Bundle file changed after build: candidateSha256', self.validate)

    def test_05_base_main_or_data_changed(self):
        path = self.bundle / 'manifest.json'
        m = json.loads(path.read_text())
        m['baseDataSha256'] = '0' * 64
        path.write_text(json.dumps(m))
        self.refused('Base main or base data hash changed', self.validate)
        m['baseCommit'] = '1' * 40
        path.write_text(json.dumps(m))
        self.refused('not part of published main', self.validate)

    def test_06_unapproved_record_mixed_in(self):
        base, b, records, sources = self.inputs()
        candidate = copy.deepcopy(b['proposed-data'])
        extra = copy.deepcopy(candidate['airports'][-1])
        extra['airportId'] = 'apt_00000000-0000-4000-8000-0000000000d1'
        candidate['airports'].append(extra)
        self.refused('not exactly the published base plus the approved records',
                     self.core.gate, base, candidate, records, b['batches'], b['dossier'], sources)

    def test_07_existing_formal_record_deleted_or_changed(self):
        base, b, records, sources = self.inputs()
        for mutate in (lambda c: c['airports'].pop(0), lambda c: c['assignments'][0].update(note='rewritten')):
            candidate = copy.deepcopy(b['proposed-data'])
            mutate(candidate)
            self.refused('not exactly the published base', self.core.gate, base, candidate, records, b['batches'], b['dossier'], sources)
        # The reused original gate refuses it independently of the exactness check.
        from admissions import validate_admission
        candidate = copy.deepcopy(b['proposed-data'])
        candidate['airports'][0]['name']['note'] = 'rewritten'
        with self.assertRaisesRegex(ValueError, 'changes or duplicates existing permanent records'):
            validate_admission(base, candidate, b['batches'], b['dossier'])

    def test_08_duplicate_identifiers(self):
        s = copy.deepcopy(self.spec)
        s['records']['assignments'].append(copy.deepcopy(s['records']['assignments'][0]))
        self.refused('Duplicate record ID', self.core.record_list, s)
        base, b, records, sources = self.inputs()
        records = copy.deepcopy(records)
        existing = base['sources'][0]['sourceId']
        next(r for r in records if r['collection'] == 'sources')['record']['sourceId'] = existing
        self.refused('Duplicate sourceId', self.core.gate, base, self.core.build_candidate(base, records, ns['version']),
                     records, b['batches'], b['dossier'], sources)

    def test_09_conflicting_code_windows_on_different_airports(self):
        base, b, records, sources = self.inputs()
        records = copy.deepcopy(records)
        r = next(r for r in records if r['id'] == L('hv1t-a1-iata-zqa'))['record']
        r['validTo'] = {'earliest': '2024-01-15', 'latest': None, 'precision': 'unknown'}
        r['sourceIds'] = [L('hv1t-ardenia-aip-2018'), L('hv1t-ardenia-aip-2024')]
        dossier = copy.deepcopy(b['dossier'])
        e = next(d for d in dossier if d['recordId'] == L('hv1t-a1-iata-zqa'))
        e['boundBasis'] = [x for x in e['boundBasis'] if x['bound'] == 'validFrom.latest'] + [
            {'bound': 'validTo.earliest', 'sourceId': L('hv1t-ardenia-aip-2024'), 'kind': 'observed_in_force', 'date': '2024-01-15'}]
        e['observations'] = [o for o in e['observations'] if o['sourceId'] != L('hv1t-ardenia-gazette-2019')] + [
            dict(e['observations'][0], sourceId=L('hv1t-ardenia-aip-2024'))]
        self.refused('Conflicting assignments', self.core.gate, base, self.core.build_candidate(base, records, ns['version']),
                     records, b['batches'], dossier, sources)

    def test_10_original_bytes_changed(self):
        b = self.core.load_bundle(self.bundle)
        changed = lambda url: originals(self.core)[url] + b' '
        self.refused('Original bytes changed', self.core.verify_originals, b['evidence-lock'], b['records']['records'],
                     self.root / 'work/o', changed)

    def test_11_citation_position_mismatch(self):
        b = self.core.load_bundle(self.bundle)
        lock = copy.deepcopy(b['evidence-lock'])
        c = lock['sources'][0]['citations'][0]
        c['characterStart'] += 1
        c['characterEnd'] += 1
        self.refused('Citation position/content mismatch', self.core.verify_originals, lock, b['records']['records'],
                     self.root / 'work/o', self.fetch)
        # A receipt for another lock does not count either.
        self.refused('missing, stale', self.core.check_receipt, b['original-verification'], lock)
        self.refused('missing, stale', self.core.check_receipt, None, lock)

    def test_12_unproven_time_range(self):
        base, b, records, sources = self.inputs()
        candidate = b['proposed-data']
        dossier = copy.deepcopy(b['dossier'])
        e = next(d for d in dossier if d['recordId'] == L('hv1t-b1-icao-zzrb'))
        e['boundBasis'] = [x for x in e['boundBasis'] if x['bound'] != 'validTo.earliest']
        self.refused('Unproven interval bound validTo.earliest', self.core.gate, base, candidate, records, b['batches'], dossier, sources)
        dossier = copy.deepcopy(b['dossier'])
        e = next(d for d in dossier if d['recordId'] == L('hv1t-b1-icao-zzrb'))
        for x in e['boundBasis']:
            if x['bound'].startswith('validFrom'):
                x.update(kind='capture', date='2026-11-04')
        self.refused('cannot bound a code/name interval', self.core.gate, base, candidate, records, b['batches'], dossier, sources)

    def test_13_unapproved_timezone_or_official_name_upgrade(self):
        base, b, records, sources = self.inputs()
        for field, value in (('timezone', {'note': 'x', 'sourceIds': [L('hv1t-calderra-aip-2023')], 'status': 'verified',
                                           'value': 'Etc/GMT-4'}),
                             ('name', {'note': 'x', 'sourceIds': [L('hv1t-calderra-aip-2023')], 'status': 'verified',
                                       'value': 'Calderra Field'})):
            changed = copy.deepcopy(records)
            next(r for r in changed if r['id'] == ids['C1'])['record'][field] = value
            self.refused('Unapproved', self.core.check_fields, changed, b['dossier'])

    def test_14_cross_batch_permanent_identity_conflict(self):
        other = self.root / ('research/admissions/%s/human-v1' % ns['after'])
        other.mkdir(parents=True)
        try:
            (other / 'records.json').write_text(json.dumps({'records': []}))
            self.refused('Another human admission batch is active', self.validate)
        finally:
            shutil.rmtree(other.parent)
        published = self.root / 'research/admissions/0.0.1/human-v1'  # an earlier, published version
        published.mkdir(parents=True)
        try:
            (published / 'records.json').write_text(json.dumps({'records': [{'collection': 'airports', 'id': ids['A1'], 'record': {}}]}))
            self.refused('Permanent identifier reused across batches', self.validate)
        finally:
            shutil.rmtree(published.parent)

    def test_15_executor_changed_after_approval(self):
        path = self.root / 'admission/human-v1/core.py'
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n# changed\n')
            self.refused('Executor changed', self.validate)
        finally:
            path.write_bytes(original)

    # ------------------------------------------------- baseline freshness --
    def test_16_main_unchanged_passes(self):
        self.assertEqual(self.core.require_fresh(self.cli.load(self.bundle / 'manifest.json')['baseCommit'], self.root),
                         self.base)
        self.assertIsNotNone(self.validate()['approval'])

    def test_17_main_advanced_voids_pending_batch(self):
        set_main(self, side_commit(self, self.base, 'unrelated main change'))
        try:
            for step in (lambda: self.cli.verify_originals(ns['version'], self.fetch), lambda: self.cli.build(ns['version']),
                         lambda: self.cli.record_approval(ns['version'], APPROVAL_URL, FakeGitHub(self.text)),
                         lambda: self.cli.submit(ns['version']), self.validate):
                self.refused('Published main advanced', step)
            self.assertTrue((self.bundle / 'approval.json').exists())  # refused before touching the bundle
            self.refused('prepared on the current published main', self.cli.prepare, self.spec_path, self.base)
        finally:
            set_main(self, self.base)

    # ------------------------------------------ original-verification receipt --
    def receipt_mutations(self):
        def verified_at(r):
            r['verifiedAt'] = '2026-01-02T03:04:05+00:00'

        def byte_count(r):
            r['sources'][0]['bytes'] += 1

        def extractor(r):
            r['sources'][0]['extractor'] = 'pdftotext-layout' if r['sources'][0]['extractor'] != 'pdftotext-layout' else 'utf8-text'

        def drop(r):
            r['sources'].pop()

        return {'verifiedAt': verified_at, 'bytes': byte_count, 'extractor': extractor, 'drop-source': drop}

    def test_18_receipt_edits_void_approval(self):
        path = self.bundle / 'original-verification.json'
        original = json.loads(path.read_text())
        self.assertIn('original-verification-sha256:' + self.core.sha(original), self.text)
        lock = json.loads((self.bundle / 'evidence-lock.json').read_text())
        for name, mutate in self.receipt_mutations().items():
            with self.subTest(name):
                receipt = copy.deepcopy(original)
                mutate(receipt)
                path.write_text(json.dumps(receipt))
                self.refused('Bundle file changed after build: originalVerificationSha256', self.validate)
                if name in ('extractor', 'drop-source'):  # detached from the lock: refused on its own too
                    self.refused('Receipt', self.core.check_receipt, receipt, lock)
        path.write_text(json.dumps(original))
        for value in (0, '12', True):  # bytes must be a positive integer
            receipt = copy.deepcopy(original)
            receipt['sources'][0]['bytes'] = value
            self.refused('Receipt detached', self.core.check_receipt, receipt, lock)
        for bad in ({**original, 'extra': 1}, {k: v for k, v in original.items() if k != 'note'}):
            self.refused('missing, stale', self.core.check_receipt, bad, lock)

    def test_19_replaced_receipt_for_same_lock_voids_approval(self):
        import time
        old_receipt = json.loads((self.bundle / 'original-verification.json').read_text())
        time.sleep(1.1)  # a later live verification of the very same lock
        other = self.core.verify_originals(json.loads((self.bundle / 'evidence-lock.json').read_text()),
                                           json.loads((self.bundle / 'records.json').read_text())['records'],
                                           self.root / 'work/o2', self.fetch)
        self.assertEqual(other['evidenceLockSha256'], old_receipt['evidenceLockSha256'])
        self.assertNotEqual(self.core.sha(other), self.core.sha(old_receipt))
        (self.bundle / 'original-verification.json').write_text(json.dumps(other))
        self.refused('Bundle file changed after build: originalVerificationSha256', self.validate)

    def test_20_reverification_requires_rebuild_and_new_approval(self):
        import time
        time.sleep(1.1)
        self.cli.verify_originals(ns['version'], self.fetch)
        for gone in ('approval.json', 'manifest.json', 'approval-text.txt'):
            self.assertFalse((self.bundle / gone).exists(), gone)
        manifest, _ = self.cli.build(ns['version'])
        new_text = self.core.approval_text(manifest)
        self.assertNotEqual(manifest['originalVerificationSha256'], self.manifest['originalVerificationSha256'])
        self.assertNotEqual(new_text, self.text)
        self.refused('does not exactly match', self.cli.record_approval, ns['version'], APPROVAL_URL, FakeGitHub(self.text))
        self.cli.record_approval(ns['version'], APPROVAL_URL, FakeGitHub(new_text))
        self.assertIsNotNone(self.validate(FakeGitHub(new_text))['approval'])

    def test_wildcard_and_country_wide_specs_refused(self):
        s = copy.deepcopy(self.spec)
        s['batchId'] = 'approve-all-1'
        self.refused('Wildcard', self.core.validate_spec, s)
        s = copy.deepcopy(self.spec)
        s['records']['airports'][0]['airportId'] = 'apt_*'
        self.refused('Exact record ID', self.core.validate_spec, s)
        s = copy.deepcopy(self.spec)
        s['excluded'].append({'recordId': ids['A1'], 'recordType': 'airport', 'reason': 'x'})
        self.refused('also listed for admission', self.core.validate_spec, s)

    def test_rebuild_voids_approval(self):
        self.cli.build(ns['version'])
        self.assertFalse((self.bundle / 'approval.json').exists())
        self.refused('No Owner approval', self.validate)

    def test_cli_has_no_bypass_switch(self):
        source = (self.root / 'admission/human-v1/human.py').read_text()
        for word in ('--skip', '--offline-approval', '--no-verify', '--force', '--test', 'fixture'):
            self.assertNotIn(word, source)

class Recorder:
    """Records the router's command groups instead of executing them (the full run is the route E2E)."""
    def __init__(self, nested=None):
        self.groups, self.nested = [], nested

    def __call__(self, commands, cwd):
        self.groups.append((Path(cwd), list(commands)))
        if self.nested and commands == ['python3 admission/human-v1/human.py ci']:
            self.nested(Path(cwd))


class HumanReleaseLineageTest(unittest.TestCase):
    """Data PR CI, main push CI and recursive replay against a stand-in GitHub main."""

    @classmethod
    def setUpClass(cls):
        make_env(cls)
        cls.version = ns['version']
        original = cls.core.github
        cls.core.github = FakeGitHub(cls.text)
        try:
            cls.branch = cls.cli.submit(cls.version)
        finally:
            cls.core.github = original
        cls.data = git(cls.root, 'rev-parse', 'HEAD')
        tree = git(cls.root, 'rev-parse', cls.data + '^{tree}')
        # GitHub's pull_request checkout: a test merge whose first parent is the main tip.
        cls.merge = git(cls.root, 'commit-tree', tree, '-p', cls.base, '-p', cls.data, '-m', 'Merge data PR')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        set_main(self, self.base)

    def at(self, commit):
        subprocess.run(['git', 'checkout', '-q', '--detach', '--force', commit], cwd=self.root, check=True)

    def lineage(self):
        return self.core.check_release_lineage(json.loads((self.core.bundle_dir(self.version, self.root) / 'manifest.json').read_text()),
                                               self.root)

    def refused(self, message, fn, *args):
        with self.assertRaises(self.core.AdmissionError) as ctx:
            fn(*args)
        self.assertIn(message, str(ctx.exception))

    def test_a_pr_ci_on_current_main(self):
        self.at(self.merge)
        self.assertEqual(self.lineage()['publishingCommit'], self.merge)
        self.at(self.data)  # the data branch itself
        self.assertEqual(self.lineage()['publishingCommit'], self.data)

    def test_b_old_pr_rerun_after_main_advanced(self):
        advanced = side_commit(self, self.base, 'unrelated main change')
        set_main(self, advanced)
        self.at(self.merge)  # a re-run keeps the original test-merge SHA
        self.refused('Published main advanced', self.lineage)
        tree = git(self.root, 'rev-parse', self.data + '^{tree}')
        fresh_merge = git(self.root, 'commit-tree', tree, '-p', advanced, '-p', self.data, '-m', 'Merge on new main')
        self.at(fresh_merge)
        self.refused('Published main advanced', self.lineage)

    def test_c_main_push_after_merge(self):
        tree = git(self.root, 'rev-parse', self.data + '^{tree}')
        squash = git(self.root, 'commit-tree', tree, '-p', self.base, '-m', 'Squash data PR')
        later = side_commit(self, self.merge, 'later unrelated main commit')
        for head, publisher in ((self.merge, self.merge), (squash, squash), (self.data, self.data), (later, self.merge)):
            set_main(self, head)
            self.at(head)
            result = self.lineage()
            self.assertEqual((result['publishingCommit'], result['baseCommit']), (publisher, self.base))
        advanced = side_commit(self, self.base, 'unrelated main change')
        bad = git(self.root, 'commit-tree', tree, '-p', advanced, '-p', self.data, '-m', 'Merged onto a newer main')
        set_main(self, bad)
        self.at(bad)
        self.refused('not on its approved base', self.lineage)

    RECURSE = ['python3 admission/human-v1/human.py ci']

    def route(self, core, text):
        """Run ``core.ci()`` with commands recorded, following recursive replays of earlier human releases.

        Returns one (root, dataVersion, groups) level per release, newest first, down to the
        frozen tree that is not a human release and so runs the legacy list. Each earlier
        release is checked by its own router with its own approval text (simulated here).
        """
        levels = []

        def nested(frozen_root):
            inner = load_core(frozen_root)
            version = inner.load(frozen_root / 'data/airports.json')['dataVersion']
            manifest = inner.load(inner.bundle_dir(version, frozen_root) / 'manifest.json')
            levels.extend(self.route(inner, inner.approval_text(manifest)))

        recorder = Recorder(nested)
        original_run, original_github = core.run_all, core.github
        core.run_all, core.github = recorder, FakeGitHub(text)
        try:
            core.ci()
        finally:
            core.run_all, core.github = original_run, original_github
        version = core.load(core.ROOT / 'data/airports.json')['dataVersion']
        return [(core.ROOT, version, recorder.groups)] + levels

    def check_levels(self, levels):
        legacy = self.core.LEGACY_CURRENT_COMMANDS
        self.assertGreaterEqual(len(levels), 1)
        for index, (root, _, groups) in enumerate(levels):
            (frozen_cwd, frozen), (current_cwd, current) = groups
            self.assertNotEqual(frozen_cwd, root)
            self.assertEqual(current_cwd, root)
            if index + 1 < len(levels):
                self.assertEqual(frozen, self.RECURSE)  # an earlier human release: its own router replays it
                self.assertEqual(levels[index + 1][0], frozen_cwd)
            else:
                self.assertEqual(sorted(frozen), sorted(legacy))  # every legacy check, unchanged, in the frozen tree
                for pinned in self.core.DATA_PINNED:
                    self.assertIn(pinned, frozen)
            for pinned in self.core.DATA_PINNED:
                self.assertNotIn(pinned, current)
            expected = [e for c in dict.fromkeys(legacy)
                        for e in self.core.CURRENT_REPLACEMENTS.get(c, [] if c in self.core.DATA_PINNED else [c])]
            self.assertEqual(current, expected)

    def test_d_ci_routes_pinned_checks_to_frozen_tree(self):
        set_main(self, self.merge)
        self.at(self.merge)
        levels = self.route(self.core, self.text)
        self.assertEqual(levels[0][1], self.version)
        # The starting tree may itself already carry earlier human releases (e.g. on a later main).
        self.check_levels(levels)

    def test_e_stale_batch_after_first_merge(self):
        """Two batches prepared on one main: once the first is merged the other cannot proceed."""
        set_main(self, self.merge)
        self.at(self.base)  # the second branch still sits on the old main with its approved bundle
        stale = self.core.bundle_dir(self.version, self.root)
        for p, data in self.snapshot.items():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        snapshot = {p: p.read_bytes() for p in stale.rglob('*') if p.is_file()}
        self.assertTrue((stale / 'approval.json').exists())
        self.refused('Published main advanced', self.core.validate_bundle, stale)
        self.refused('Published main advanced', self.cli.submit, self.version)
        for p, data in snapshot.items():  # the CLI refused before touching anything
            self.assertEqual(p.read_bytes(), data)
        subprocess.run(['git', 'clean', '-qfd', str(stale)], cwd=self.root, check=True)
        # Re-preparing the same permanent IDs on the new main is refused.
        self.at(self.merge)
        spec = copy.deepcopy(self.spec)
        spec['targetDataVersion'], spec['batchId'] = ns['after'], spec['batchId'] + '-again'
        path = self.root / 'work/spec-again.json'
        path.write_text(json.dumps(spec))
        self.refused('Permanent identifier reused across batches', self.cli.prepare, path)

    def test_f_rights_audit_runs_for_real_on_the_release_tree(self):
        """Regression (route-e2e on ad15f0a): the legacy rights command reaches the 0.10.0
        priority-markets lock indirectly, so it is frozen-only; the current-tree replacement
        runs the same unmodified audits and still rejects every tampering it guards."""
        set_main(self, self.merge)
        self.at(self.merge)
        legacy = 'python3 scripts/evidence/korea_readiness.py rights'
        self.assertIn(legacy, self.core.DATA_PINNED)
        self.assertEqual(self.core.CURRENT_REPLACEMENTS[legacy], ['python3 admission/human-v1/rights.py'])

        def run(command):
            return subprocess.run(command, shell=True, cwd=self.root, capture_output=True, text=True)

        old = run(legacy)
        self.assertNotEqual(old.returncode, 0)
        self.assertIn('Protected baseline changed: data/airports.json', old.stderr)
        ok = run('python3 admission/human-v1/rights.py')
        self.assertEqual(ok.returncode, 0, ok.stderr)
        result = json.loads(ok.stdout.strip().splitlines()[-1])
        self.assertEqual(result['restrictedReachableBlobs'], 0)
        self.assertGreater(result['koreaNewReachableBlobsChecked'], 0)
        self.assertGreater(result['newMarketHistoricalBlobsChecked'], 0)
        self.assertFalse(result['fullOriginalsAndExtractionsAdded'])

        def tampered(path, change, message):
            target = self.root / path
            raw = target.read_bytes()
            try:
                target.write_bytes(change(raw))
                bad = run('python3 admission/human-v1/rights.py')
                self.assertNotEqual(bad.returncode, 0)
                self.assertIn(message, bad.stderr)
            finally:
                target.write_bytes(raw)

        def drop_airport(raw):
            data = json.loads(raw)
            data['airports'] = data['airports'][:-1]
            return (json.dumps(data, indent=2) + '\n').encode()

        def bump(raw):
            data = json.loads(raw)
            data['version'] = data['version'] + '-x'
            return (json.dumps(data, indent=2) + '\n').encode()

        tampered('pnpm-lock.yaml', lambda raw: raw + b'\n', 'Protected baseline changed: pnpm-lock.yaml')
        tampered('data/airports.json', drop_airport, 'Published data detached from its approved candidate')
        tampered('package.json', bump, 'package.json version detached from data')
        private = self.root / 'work/private-original.raw'
        private.parent.mkdir(exist_ok=True)
        private.write_bytes(b'restricted original bytes')
        try:
            subprocess.run(['git', 'add', '-f', str(private)], cwd=self.root, check=True)
            bad = run('python3 admission/human-v1/rights.py')
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('Private acquisition cache staged', bad.stderr)
        finally:
            subprocess.run(['git', 'rm', '-q', '--cached', '-f', str(private)], cwd=self.root, check=True)
            private.unlink()

    def test_z_recursive_replay_of_earlier_human_release(self):
        """A second human release replays the first one recursively in its frozen tree."""
        set_main(self, self.merge)
        self.at(self.merge)
        first_text, first_version = self.text, self.version
        configure(first_version)
        spec2 = localized_spec(self.core)
        path = self.root / 'work/spec-2.json'
        path.write_text(json.dumps(spec2))
        files = originals(self.core)
        self.cli.prepare(path)
        self.cli.verify_originals(ns['version'], lambda url: files[url])
        manifest2, _ = self.cli.build(ns['version'])
        text2 = self.core.approval_text(manifest2)
        self.cli.record_approval(ns['version'], APPROVAL_URL, FakeGitHub(text2))
        original = self.core.github
        self.core.github = FakeGitHub(text2)
        try:
            self.cli.submit(ns['version'])
        finally:
            self.core.github = original
        data2 = git(self.root, 'rev-parse', 'HEAD')
        tree2 = git(self.root, 'rev-parse', data2 + '^{tree}')
        merge2 = git(self.root, 'commit-tree', tree2, '-p', self.merge, '-p', data2, '-m', 'Merge second data PR')
        set_main(self, merge2)
        self.at(merge2)
        levels = self.route(self.core, text2)
        self.assertEqual([v for _, v, _ in levels[:2]], [ns['version'], first_version])
        self.check_levels(levels)  # second release -> first release (recursively) -> ... -> legacy frozen tree


if __name__ == '__main__':
    unittest.main()
