#!/usr/bin/env python3
"""Compile self-contained teaching tasks. Offline only; never submits work."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
from curriculum import CASES, source

ROOT = Path(__file__).resolve().parent
BASE = 'python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f'
INSTALL = ('RUN apt-get update && apt-get install -y --no-install-recommends '
           'bash ca-certificates curl git && rm -rf /var/lib/apt/lists/*\n')
APP_TEMPLATE = '''"""The same service adapter calls every policy module. No network is used."""
import importlib
import json
import sys

MODULES = %r

def handle(module, request):
    if module not in MODULES:
        raise ValueError('Unknown policy module')
    return importlib.import_module(module).decide(request)

if __name__ == '__main__':
    print(json.dumps(handle(sys.argv[1], json.loads(sys.argv[2]))))
'''


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def canonical(value):
    return json.dumps(value, indent=2, sort_keys=True) + '\n'


def build(destination, cases=None):
    cases = CASES if cases is None else cases
    if destination.exists():
        raise SystemExit('Destination already exists; use a fresh directory, never overwrite a learner workspace.')
    destination.mkdir(parents=True)
    manifest = {'schema': 'synth.tutorial-inputs.v1', 'license': 'MIT', 'kind': 'authored teaching collection, not historical PRs',
                'split_policy': 'Group by policy module: buggy and clean siblings never cross splits.', 'tasks': []}
    for case in cases:
        for variant in ('regression', 'refactor'):
            name = case['name'] + '-' + variant
            task = destination / 'tasks' / name
            env, tests = task / 'environment', task / 'tests'
            before = source(case['before'])
            after = source(case['after'] if variant == 'regression' else case['clean'])
            for module in cases:
                body = after if module is case else source(module['before'])
                write(env / (module['name'] + '.py'), body)
            write(env / 'app.py', APP_TEMPLATE % [c['name'] for c in cases])
            write(env / 'POLICY.md', '\n\n'.join('## ' + c['name'] + '\n\n' + c['policy'] for c in cases) + '\n')
            write(env / 'README.md', '# DispatchDesk\n\nA small in-memory service for organization operations.\n'
                  'app.py dispatches JSON requests to each policy module. There are no external callers or database rules.\n'
                  'Read POLICY.md for the authoritative behavior. Review only the proposed change; other modules provide context.\n'
                  'Use: python3 app.py MODULE INPUT_JSON\nThis is an authored teaching project, not a production service.\n')
            write(env / 'change.diff', ''.join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                  fromfile='a/' + case['name'] + '.py', tofile='b/' + case['name'] + '.py')))
            # Explicit finite interface avoids rewarding unsupported/out-of-contract
            # counterexamples. The inputs contain no expected answers.
            write(env / 'INPUTS.json', canonical(case['domain']))
            write(env / 'LICENSE', (ROOT / 'LICENSE').read_text())
            write(env / 'Dockerfile', f'FROM {BASE}\n' + INSTALL +
                  'RUN useradd --create-home --uid 1000 reviewer && mkdir -p /app /logs/artifacts && chown reviewer:reviewer /logs/artifacts\n'
                  'COPY *.py *.md *.json LICENSE /app/\nCOPY change.diff /app/\nWORKDIR /app\n')
            reference = {'path': case['name'] + '.py', 'buggy': variant == 'regression',
                         'root_cause': case['root'] if variant == 'regression' else 'No policy regression.',
                         'policy': case['policy'], 'domain': case['domain']}
            write(tests / 'reference.json', canonical(reference))
            write(tests / 'before.py', before)
            write(tests / 'after.py', after)
            write(tests / 'grade.py', (ROOT / 'grade.py').read_text())
            write(tests / 'test.sh', '#!/bin/sh\nset -eu\npython3 /tests/grade.py\n')
            write(tests / 'Dockerfile', f'FROM {BASE}\n' + INSTALL + 'COPY *.py *.json test.sh /tests/\nWORKDIR /tests\n')
            write(task / 'task.toml', 'version = "1.0"\n\n[metadata]\nname = ' + json.dumps(name) +
                  '\ndescription = "Review one DispatchDesk change against its policy."\n\n'
                  '[agent]\nuser = "reviewer"\ntimeout_sec = 240\n\n'
                  '[verifier]\ntimeout_sec = 180\nenvironment_mode = "separate"\n\n'
                  '[verifier.environment]\nworkdir = "/tests"\n\n'
                  '[environment]\ncpus = 1\nmemory_mb = 4096\n')
            write(task / 'instruction.md', '# Review the proposed DispatchDesk change\n\n'
                  'Review /app/change.diff against /app/POLICY.md and the caller in /app/app.py. The full small source tree is available. '
                  'Some changes are correct. Report consequential regressions introduced by this change, not pre-existing issues or style suggestions. '
                  'Do not modify source. Do not read /tests or assessment material. Use only the task workspace and your output directory.\n\n'
                  'This bounded teaching interface accepts the inputs in /app/INPUTS.json. Choose a counterexample from that list; '
                  'derive the expected result from the policy. It lists inputs, not answers.\n\n'
                  'Write /logs/artifacts/review.json as {"findings": [...]} with one entry per distinct root cause. '
                  'Each entry has path (relative source filename), title, explanation (actual failure and consequence), and '
                  'counterexample {"input": REQUEST_OBJECT, "expected": POLICY_RESULT}. Use {"findings": []} if no regression is supported. '
                  'A valid JSON file alone does not establish a correct review. You have four minutes; produce the file before time expires.\n')
            files = {str(p.relative_to(task)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(task.rglob('*')) if p.is_file()}
            manifest['tasks'].append({'name': name, 'group': case['name'], 'split': case['split'], 'level': case.get('level', 'core'), 'variant': variant,
                                      'files': files})
    for filename in ('LICENSE', 'grade.py', 'curriculum.py', 'build.py'):
        shutil.copyfile(ROOT / filename, destination / filename)
    write(destination / 'manifest.json', canonical(manifest))
    print(f'Built {len(manifest["tasks"])} tasks with grouped practice/held-out splits at {destination}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    build(parser.parse_args().destination)
