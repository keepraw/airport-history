"""Read-only cross-repository experiment, pinned to the actually inspected Fly commit.

Use an existing checkout at the lock SHA. This command never fetches moving main,
installs Fly dependencies, or writes any file inside that checkout.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def git(checkout, *args):
    return subprocess.check_output(['git', '-C', str(checkout), *args], text=True).strip()


def main(checkout, maps=False):
    lock = json.loads((HERE / 'fly-source-lock.json').read_text())
    checkout = checkout.resolve()
    if git(checkout, 'rev-parse', 'HEAD') != lock['revision']:
        raise ValueError('Fly checkout does not match the pinned experiment SHA')
    before = git(checkout, 'status', '--porcelain', '--untracked-files=all')
    if before:
        raise ValueError('Use a clean read-only Fly checkout')
    for name, expected in lock['files'].items():
        if hashlib.sha256((checkout / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Fly source hash mismatch: ' + name)
    work = ROOT / 'work/compat'
    work.mkdir(parents=True, exist_ok=True)
    text = (HERE / 'cross-fly.test.template').read_text().replace('__DIRECTORY_PATH__', json.dumps(str(checkout / 'packages/core/data/airports.iata.json')))
    map_test = '''it('passes historical points into the actual Fly map projection and route path', () => {
      installAirportDirectory(rows);
      const old = resolveEndpoint(dataset, 'TAO', '2021-08-11', airportByIata).coordinates!.value!;
      const current = resolveEndpoint(dataset, 'TAO', '2021-08-13', airportByIata).coordinates!.value!;
      const destination = resolveEndpoint(dataset, 'HKG', '2021-08-11', airportByIata).coordinates!.value!;
      const oldPath = greatCirclePath({...old, iata:'TAO'}, {...destination, iata:'HKG'});
      const currentPath = greatCirclePath({...current, iata:'TAO'}, {...destination, iata:'HKG'});
      expect(oldPath).not.toBe(currentPath);
      expect(oldPath).not.toMatch(/NaN|Infinity/);
      expect(projectPoint(old)).not.toEqual(projectPoint(current));
    });'''
    if maps:
        dependency = work / 'runtime/node_modules/d3-geo/package.json'
        if not dependency.exists() or json.loads(dependency.read_text())['version'] != '3.1.1':
            raise ValueError('First run: npm install --prefix work/compat/runtime --ignore-scripts --no-audit --no-fund d3-geo@3.1.1')
    text = text.replace('__MAP_IMPORT__', "import { greatCirclePath, projectPoint } from '@fly-map';" if maps else '')
    text = text.replace('__MAP_TEST__', map_test if maps else '')
    (work / 'fly-cross.experiment.ts').write_text(text)
    tests = ['packages/core/tests/core.test.ts', 'packages/core/tests/routes.test.ts',
             'packages/core/tests/time-display.test.ts', 'apps/web/src/data/flight-editor.test.ts',
             'apps/web/src/data/csv-import.test.ts']
    if maps:
        tests.append('apps/web/src/data/map-geometry.test.ts')
    paths = [str(work / 'fly-cross.experiment.ts'), *[str(checkout / p) for p in tests]]
    # The existing runner/dependencies live in Airport History, with aliases to actual Fly code.
    # All Vite caches and generated tests stay inside Airport History/work.
    config = f'''import {{ defineConfig }} from 'vitest/config';
import {{ fileURLToPath }} from 'node:url';
export default defineConfig({{
  cacheDir: {json.dumps(str(work / 'cache'))},
  resolve: {{ alias: {{
    'vitest': fileURLToPath(import.meta.resolve('vitest')),
    '@fly-map': {json.dumps(str(checkout / 'apps/web/src/data/map-geometry.ts'))},
    'd3-geo': {json.dumps(str(work / 'runtime/node_modules/d3-geo/src/index.js'))},
    '@keepraw-fly/core/airport-directory': {json.dumps(str(checkout / 'packages/core/data/airports.iata.json'))},
    '@keepraw-fly/validator': {json.dumps(str(checkout / 'packages/validator/src/index.ts'))},
    'ajv-formats/dist/formats.js': fileURLToPath(import.meta.resolve('ajv-formats/dist/formats.js')),
    'ajv/dist/2020.js': fileURLToPath(import.meta.resolve('ajv/dist/2020.js')),
    'ajv': fileURLToPath(import.meta.resolve('ajv')),
    'ajv-formats': fileURLToPath(import.meta.resolve('ajv-formats')),
    '@keepraw-fly/core': {json.dumps(str(checkout / 'packages/core/src/index.ts'))},
    '@keepraw-fly/schema': {json.dumps(str(checkout / 'packages/schema/src/index.ts'))}
  }} }},
  server: {{ fs: {{ allow: {json.dumps([str(ROOT), str(checkout)])} }} }},
  test: {{ include: {json.dumps(paths)}, reporters: ['default', 'json'],
    outputFile: {{json: {json.dumps(str(work / 'results.json'))}}} }}
}});'''
    config_path = work / 'vitest.config.ts'
    config_path.write_text(config)
    result = subprocess.run(['pnpm', 'exec', 'vitest', 'run', '--config', str(config_path)], cwd=ROOT)
    if git(checkout, 'status', '--porcelain', '--untracked-files=all') != before:
        raise ValueError('Read-only experiment changed the Fly checkout')
    if result.returncode:
        raise SystemExit(result.returncode)
    print('Pinned Fly experiment passed; checkout remains clean at ' + lock['revision'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--maps', action='store_true')
    args = parser.parse_args()
    main(args.checkout, args.maps)
