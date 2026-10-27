import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/discovery'))
from core import describe, history, patch_rows, read_candidates, rows_from_text, source_text
from scan import export, scan


class DiscoveryTest(unittest.TestCase):
    def test_multiline_csv_and_duplicate_keys(self):
        header, rows = rows_from_text('id,name,country\n1,"A\nB",NA\n', 'id')
        self.assertEqual(rows['1']['country'], 'NA')
        self.assertEqual(rows['1']['name'], 'A\nB')
        with self.assertRaises(ValueError):
            rows_from_text('id,name\n1,A\n1,B\n', 'id')
        with self.assertRaises((ValueError, csv.Error)):
            patch_rows('@@ -3 +3 @@\n-B",NA\n+C",NA\n', header, 'id', rows)
        _, data = rows_from_text('{"OLD":{"icao":"NEW","name":"Field"}}', 'icao', 'json')
        self.assertEqual(data['OLD']['icao'], 'NEW')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
            rows_from_text('{"A":{"icao":"A"},"A":{"icao":"B"}}', 'icao', 'json')

    def test_explicit_source_format_repair(self):
        source = {'csvRepairs': [{'id': 'eddb-continuation',
                                  'from': ',13.500667,\n"Europe/Berlin"',
                                  'to': ',13.500667,"Europe/Berlin"'}]}
        raw = 'icao,lon,tz\nEDDB,13.500667,\n"Europe/Berlin"\n'
        with self.assertRaises(ValueError):
            rows_from_text(raw, 'icao')
        repaired, applied = source_text(source, raw)
        self.assertEqual(applied, ['eddb-continuation'])
        self.assertEqual(rows_from_text(repaired, 'icao')[1]['EDDB']['tz'], 'Europe/Berlin')
        with self.assertRaises(ValueError):
            source_text(source, raw+raw)

    def test_classification_does_not_certify_rename_or_relocation(self):
        a = dict(id='1', iata_code='TSE', name='Astana', latitude_deg='51', longitude_deg='71', type='large_airport')
        b = dict(a, iata_code='NQZ', name='Nazarbayev')
        event = describe(a, b)
        self.assertEqual(event['types'], ['iata_change', 'possible_rename'])
        self.assertNotIn('record_added', event['types'])
        self.assertEqual(event['distanceKm'], 0)
        self.assertNotIn('possible_relocation', describe(a, dict(a, latitude_deg='51.00001'))['types'])
        self.assertIn('possible_relocation', describe(a, dict(a, latitude_deg='52'))['types'])
        self.assertEqual(describe({'City Code': 'BER', 'Airport Code': 'SXF'}, {})['types'], ['city_code_membership_change'])

    def test_all_commits_resumption_and_curation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / 'source.git'
            subprocess.run(['git', 'init', '-b', 'main', str(repo)], check=True, stdout=subprocess.DEVNULL)
            def git(*args, **kw):
                return subprocess.check_output(['git', '-C', str(repo), *args], **kw).decode().strip()
            git('config', 'user.name', 'keepraw')
            git('config', 'user.email', '49091395+keepraw@users.noreply.github.com')
            def commit(name, code, day):
                (repo / 'airports.csv').write_text(f'id,name,iata_code,iso_country,type\n1,{name},{code},KZ,large_airport\n2,Closed,,,closed\n')
                git('add', 'airports.csv')
                env = dict(os.environ, GIT_AUTHOR_DATE=f'2020-06-{day:02}T00:00:00Z', GIT_COMMITTER_DATE=f'2020-06-{day:02}T00:00:00Z')
                git('commit', '-m', 'test: record source revision', env=env)
                return git('rev-parse', 'HEAD')
            first = commit('A', 'TSE', 1)
            commit('B', 'TSE', 2)
            commit('A', 'TSE', 3)
            tip = commit('B', 'TSE', 4)
            source = dict(id='fixture', localRepository=str(repo), revision=tip,
                          path='airports.csv', key='id', url='https://example.invalid', license='Public-Domain')
            cache, out = root / 'cache', root / 'out'
            dataset = dict(airports=[], assignments=[], names=[])
            db, edges, latest = scan(source, cache)
            self.assertEqual(len(edges), 4)
            report = export(source, db, edges, latest, out, dataset, {})
            records = list(read_candidates(out, 'fixture'))
            rename = next(r for r in records if r['changes'].get('name') == ['A', 'B'])
            self.assertEqual(len(rename['observations']), 2)
            self.assertEqual(rename['time']['eventDate'], None)
            self.assertEqual(report['discovery']['rawCandidateObservations'], 4)  # closed baseline + three edits
            original = {p.name: p.read_bytes() for p in out.iterdir()}
            db.close()
            db, edges, latest = scan(source, cache)
            export(source, db, edges, latest, out, dataset, {})
            self.assertEqual(original, {p.name: p.read_bytes() for p in out.iterdir()})
            db.close()
            source['revision'] = commit('B', 'NQZ', 5)
            db, edges, latest = scan(source, cache)
            export(source, db, edges, latest, out, dataset,
                   {rename['candidateId']: {'status': 'insufficient_evidence', 'evidenceGaps': ['Need primary name decision.']}})
            updated = list(read_candidates(out, 'fixture'))
            retained = next(r for r in updated if r['candidateId'] == rename['candidateId'])
            self.assertEqual(retained['review']['status'], 'insufficient_evidence')
            self.assertEqual(len(updated), len(records)+1)
            db.close()
            # A target rewind must not silently include observations from its future.
            source['revision'] = first
            with self.assertRaises(subprocess.CalledProcessError):
                scan(source, cache)

    def test_merge_parent_history_and_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args]).decode().strip()
            git('init', '-b', 'main')
            git('config', 'user.name', 'keepraw')
            git('config', 'user.email', '49091395+keepraw@users.noreply.github.com')
            (repo / 'airports.csv').write_text('id,name\n1,A\n2,B\n')
            git('add', '.')
            git('commit', '-m', 'test: baseline')
            git('switch', '-c', 'side')
            (repo / 'airports.csv').write_text('id,name\n1,C\n2,B\n')
            git('commit', '-am', 'test: side revision')
            side = git('rev-parse', 'HEAD')
            git('switch', 'main')
            (repo / 'unrelated').write_text('x')
            git('add', '.')
            git('commit', '-m', 'test: unrelated change')
            git('merge', '--no-ff', 'side', '-m', 'test: merge source changes')
            git('rm', 'airports.csv')
            git('commit', '-m', 'test: remove source file')
            edges = history(repo, 'HEAD', 'airports.csv')
            self.assertIn(side, {e['commit'] for e in edges})
            self.assertTrue(any(len(e['parents']) == 2 for e in edges))
            self.assertEqual(edges[-1]['afterBlob'], '0'*40)
            source = dict(id='deleted', localRepository=str(repo), revision=git('rev-parse','HEAD'),
                          path='airports.csv', key='id', url='https://example.invalid')
            db, _, latest = scan(source, repo / 'cache')
            self.assertEqual(latest, {})
            self.assertEqual(db.execute('SELECT count(*) FROM entities').fetchone()[0], 2)
            db.close()

    def test_quarantine_never_bridges_unparsed_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args]).decode().strip()
            git('init', '-b', 'main')
            git('config', 'user.name', 'keepraw')
            git('config', 'user.email', '49091395+keepraw@users.noreply.github.com')
            for value in ['id,name\n1,A\n', 'id,name\n1,B\n1,Conflict\n', 'id,name\n1,C\n', 'id,name\n1,D\n']:
                (repo / 'airports.csv').write_text(value)
                git('add', 'airports.csv')
                git('commit', '-m', 'test: source with an ambiguous version')
            source = dict(id='quarantine', localRepository=str(repo), revision=git('rev-parse','HEAD'),
                          path='airports.csv', key='id', url='https://example.invalid', allowParseGaps=True)
            db, edges, latest = scan(source, Path(tmp) / 'cache')
            report = export(source, db, edges, latest, Path(tmp) / 'out',
                            dict(airports=[], assignments=[], names=[]), {})
            self.assertEqual(report['history']['blockedComparisons'], 2)
            self.assertEqual(report['history']['unparsedFileVersions'], 1)
            records = list(read_candidates(Path(tmp) / 'out', 'quarantine'))
            self.assertEqual([r['changes']['name'] for r in records], [['C','D']])
            db.close()


if __name__ == '__main__':
    unittest.main()
