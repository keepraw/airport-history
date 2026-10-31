"""Print an exact rule grant text or record an independently fetched Owner comment."""
import argparse
import json
from pathlib import Path

from runtime import PUBLIC, authority_text, authorize, checked_bindings, legacy, load, policy, private_path, write


def record(kind, url, output, existing=None):
    p = policy(kind)
    target = private_path(output, new=True)
    approval = legacy.read_owner_comment(url, authority_text(p))
    registry = load(existing or PUBLIC / 'authorizations.json')
    registry['authorizations'] = [g for g in registry['authorizations'] if g['policyKey'] != p['policyKey']]
    registry['authorizations'].append({'policyKey': p['policyKey'], 'bindings': checked_bindings(p), 'approval': approval})
    authorize(p, registry)
    write(target, registry)
    return {'rule': p['policyKey'], 'recordedOwnerComment': approval['html_url'],
            'output': str(target), 'productionFilesWritten': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['text', 'record'])
    parser.add_argument('--rule', choices=['identity', 'kr-code'], required=True)
    parser.add_argument('--comment-url')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--registry', type=Path, help='Preserve previously recorded independent rule grants')
    args = parser.parse_args()
    if args.command == 'text':
        print(authority_text(policy(args.rule)))
    else:
        if args.output is None: parser.error('--output in ignored work/ is required')
        print(json.dumps(record(args.rule, args.comment_url, args.output, args.registry)))
