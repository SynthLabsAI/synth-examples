#!/usr/bin/env python3
"""Package an explicitly specified policy case. Does not assert realism."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from build import build


def scaffold(specification, destination):
    case = json.loads(specification.read_text())
    required = {'name', 'policy', 'before', 'after', 'clean', 'domain', 'root', 'provenance', 'privacy_review'}
    if not required.issubset(case):
        raise ValueError('Missing fields: ' + ', '.join(sorted(required - case.keys())))
    if not isinstance(case['name'], str) or not re.fullmatch(r'[a-z][a-z_]{0,30}', case['name']):
        raise ValueError('name must be a safe Python module name')
    for key in required - {'domain'}:
        if not isinstance(case[key], str) or not case[key].strip():
            raise ValueError(key + ' must be a nonempty string')
    if not isinstance(case['domain'], list) or not case['domain'] or not all(isinstance(x, dict) for x in case['domain']):
        raise ValueError('domain must supply nonempty finite JSON input objects')
    case['split'] = 'practice'
    # Source is packaged as data, never executed on the author's machine here.
    build(destination, [case])
    (destination/'author-declaration.json').write_text(json.dumps({
        'provenance': case['provenance'], 'privacy_review': case['privacy_review'],
        'qualification': 'UNVERIFIED: independently check policy, context, witnesses and assessor before use'
    }, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('specification', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    scaffold(args.specification, args.destination)
