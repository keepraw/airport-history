"""Private-byte verification and explicitly separate offline receipt replay.

An offline receipt is a recorded mechanical attestation, not evidence that the
current process fetched originals, a human signature, or a source-reading claim.
"""
import argparse
import hashlib
from pathlib import Path
import urllib.request

from policy_review import ROOT, DIRECTORY, inputs, evaluate, citation, sha, require, write_json, load
from policy_executor import fingerprint


def required_sources(decisions):
    sources = inputs()[6]
    ids = {sid for d in decisions if d['sample'] == 'unpublished' and d['risk'] in ('low', 'medium')
           for sid in d['sourceIds']}
    ids |= {sources[sid]['editionAnchorSourceId'] for sid in list(ids)}
    require(ids, 'No original evidence selected')
    return [sources[sid] for sid in sorted(ids)]


def expected_verification(decisions):
    policy, lock, *_ = inputs()
    rows = []
    for s in required_sources(decisions):
        excerpt = citation(s)
        rows.append({k: s[k] for k in ('sourceId', 'url', 'originalSha256', 'textOriginalSha256',
            'excerptSha256', 'editionEffectiveDate', 'originalPublicationKey')})
        rows[-1]['checkedCitationSha256'] = sha(excerpt['spans'])
        rows[-1]['checkedCitationCount'] = len(excerpt['spans'])
    return {'formatVersion': 1, 'verificationMode': 'private_original_replay',
        'meaning': 'Recorded private byte/hash/extraction/citation verification; offline replay does not reacquire bytes.',
        'recordedBy': 'policy-originals-cli', 'executorSha256': fingerprint()['executorSha256'],
        'policySha256': policy['policySha256'], 'inputSha256': sha(lock),
        'baselineSha256': lock['baseline']['sha256'], 'sources': rows}


def verify_originals(decisions, *, fetch=False):
    from global_batch import extract
    for s in required_sources(decisions):
        path = ROOT / s['privateOriginalPath']
        require(path.resolve().is_relative_to(ROOT / 'work'), 'Original must remain in private work/')
        if fetch:
            raw = urllib.request.urlopen(s['url'], timeout=45).read()
            require(hashlib.sha256(raw).hexdigest() == s['originalSha256'], 'Fetched original has changed')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == s['originalSha256'], 'Original replay hash mismatch')
        text = extract(raw)
        require(hashlib.sha256(text.encode()).hexdigest() == s['textOriginalSha256'], 'Original extraction mismatch')
        for q in citation(s)['spans']:
            target = raw.decode('utf-8') if q['kind'] == 'raw_html' else ' '.join(text.split())
            require(target[q['characterStart']:q['characterEnd']] == q['quote'], 'Original citation replay mismatch')
    return expected_verification(decisions)


def validate_offline(record, decisions):
    require(record == expected_verification(decisions), 'Missing, altered or stale original verification receipt')
    return {'verificationMode': 'offline_receipt_replay', 'originalBytesObtainedHere': False,
            'verifiedReceiptSha256': sha(record), 'sourceCount': len(record['sources'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'offline'))
    parser.add_argument('--fetch', action='store_true', help='Explicit network acquisition into ignored work/')
    args = parser.parse_args()
    require(not args.fetch or args.command == 'verify', 'Offline replay cannot fetch originals')
    decisions = evaluate()
    for risk in ('low', 'medium'):
        selected = [d for d in decisions if d['sample'] == 'unpublished' and d['risk'] == risk]
        if not selected: continue
        path = DIRECTORY / 'verification' / f'{risk}.json'
        if args.command == 'verify':
            write_json(path, verify_originals(selected, fetch=args.fetch))
            print(f'{risk}: actual private originals, extraction hashes and every exact citation checked')
        else:
            result = validate_offline(load(path), selected)
            print(f'{risk}: {result}; no original-byte acquisition claimed by this process')


if __name__ == '__main__': main()
