"""Dispatch the current formal version without extending legacy country grants."""
import json
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[2]
data = json.loads((ROOT / 'data/airports.json').read_text())
if data['dataVersion'] == '0.12.0':
    subprocess.run(['python3', 'scripts/evidence/global_code_admission.py'], cwd=ROOT, check=True)
elif data['dataVersion'] == '0.11.0':
    subprocess.run(['python3', 'scripts/evidence/project_admission.py'], cwd=ROOT, check=True)
    subprocess.run(['node', 'scripts/evidence/admission_0110_coverage.ts', 'validate'], cwd=ROOT, check=True)
elif data['dataVersion'] == '0.10.0':
    if data != json.loads((ROOT / 'test/curated-0.10.0.json').read_text()):
        raise ValueError('Legacy formal dataset differs from its independently validated snapshot')
else:
    raise ValueError('No active project admission for this data version')
