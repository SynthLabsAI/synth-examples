"""Counterexample correctness only; semantic prose assessment is separate."""
import argparse
import importlib.util
import json
from pathlib import Path


def load(path):
    spec = importlib.util.spec_from_file_location('policy_impl', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decide


def score(review, reference, before, after):
    findings = review.get('findings') if isinstance(review, dict) else None
    if not isinstance(findings, list):
        return {'reward': 0.0, 'rationale': 'Expected a findings array.'}
    if not reference['buggy']:
        return {'reward': float(not findings), 'rationale': 'This change preserves the stated contract; no finding earns full credit.'}
    if len(findings) != 1:
        return {'reward': 0.0, 'rationale': 'Report the root cause once; empty or duplicate findings receive no credit.'}
    finding = findings[0]
    if not isinstance(finding, dict) or finding.get('path') != reference['path']:
        return {'reward': 0.0, 'rationale': 'Identify the changed source file.'}
    if any(not isinstance(finding.get(k), str) or not finding[k].strip() for k in ('title', 'explanation')):
        return {'reward': 0.0, 'rationale': 'A title and explanation are required, but their meaning is not graded here.'}
    counterexample = finding.get('counterexample')
    if not isinstance(counterexample, dict) or set(counterexample) != {'input', 'expected'}:
        return {'reward': 0.0, 'rationale': 'Counterexample must have input and expected.'}
    # The tutorial uses a finite, explicitly specified input domain. Refuse
    # type-confused or outside-domain inputs instead of inventing semantics.
    encoded = json.dumps(counterexample['input'], sort_keys=True, separators=(',', ':'))
    domain = {json.dumps(x, sort_keys=True, separators=(',', ':')) for x in reference['domain']}
    if encoded not in domain:
        return {'reward': 0.0, 'rationale': 'Input is outside the documented finite tutorial domain.'}
    case = counterexample['input']
    expected, actual = before(case), after(case)
    same = lambda a, b: json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    valid = same(expected, counterexample['expected']) and not same(expected, actual)
    return {'reward': float(valid), 'rationale': 'Valid policy counterexample.' if valid else 'The supplied input/expected pair does not demonstrate a regression.',
            'expected': expected, 'actual': actual,
            'assessment_scope': 'executable counterexample, not prose quality'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='/tests')
    parser.add_argument('--review', default='/logs/artifacts/review.json')
    parser.add_argument('--output', default='/logs/verifier')
    args = parser.parse_args()
    root, output = Path(args.root), Path(args.output)
    reference = json.loads((root / 'reference.json').read_text())
    try:
        raw = Path(args.review).read_bytes()
        if len(raw) > 65536:
            raise ValueError('Review exceeds 64 KiB')
        review = json.loads(raw)
    except (OSError, ValueError):
        result = {'reward': 0.0, 'rationale': 'Missing, oversized or malformed review.'}
    else:
        result = score(review, reference, load(root / 'before.py'), load(root / 'after.py'))
    output.mkdir(parents=True, exist_ok=True)
    (output / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'reward.json').write_text(json.dumps({'reward': result['reward']}) + '\n')


if __name__ == '__main__':
    main()
