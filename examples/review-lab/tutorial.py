#!/usr/bin/env python3
"""Transparent, bounded CLI launcher. POSIX Python 3.10+; no SDK or daemon.

All remote operations use the released `synth` executable and normal customer
authentication. State lives only in the workspace. An uncertain write is NEVER
automatically repeated. Inspect the receipt or resolve it before continuing.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
from build import build

ROOT = Path(__file__).resolve().parent
TERMINAL = {'succeeded', 'failed', 'cancelled'}


def atomic(path, data):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def cli(args):
    result = subprocess.run(['synth', *args], capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'CLI request failed')
    return json.loads(result.stdout)


def identity():
    status = cli(['status', '--json'])
    if not status.get('request_authenticated') or status.get('service_key_active'):
        raise RuntimeError('Use normal customer sign-in, not a service key. Run synth login and retry the read-only status check.')
    # Production is not a qualification target for this release of the lab.
    endpoint = status.get('api_base_url', '').rstrip('/')
    if endpoint == 'https://sprites-gateway.api.synthlabs.ai':
        raise RuntimeError('This lab is qualified for provisioned Dev accounts only. Do not switch endpoints using this script; ask your organization for the supported access setup.')
    return {k: status[k] for k in ('user_id', 'org', 'api_base_url')}


@contextmanager
def workspace(path):
    with (path/'state.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another launcher is using this workspace; do not start a second copy.')
        state = json.loads((path/'state.json').read_text())
        try:
            yield state
        finally:
            atomic(path/'state.json', state)


def mutate(path, state, label, args, slots=0):
    existing = state['operations'].get(label)
    if existing:
        if existing['args'] != args:
            raise RuntimeError('This operation name already refers to different inputs. Keep the original; use a new experiment name.')
        if existing['state'] == 'receipt':
            return existing['receipt']
        raise RuntimeError(f'{label} has an uncertain or failed submission. Inspect operations/{label}.json; never blindly retry.')
    if identity() != state['identity']:
        raise RuntimeError('Customer, organization or connection changed; refusing to act on another context.')
    if state['reserved_trials'] + slots > state['max_trials']:
        raise RuntimeError('The explicit workspace work limit would be exceeded. Do not silently increase it.')
    record = {'args': args, 'slots': slots, 'state': 'reserved'}
    state['reserved_trials'] += slots
    state['operations'][label] = record
    atomic(path/'state.json', state)  # durable reservation BEFORE the request
    atomic(path/'operations'/f'{label}.json', record)
    try:
        receipt = cli(args)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        record.update(state='uncertain-or-rejected', error=str(error))
        atomic(path/'state.json', state)
        atomic(path/'operations'/f'{label}.json', record)
        raise
    record.update(state='receipt', receipt=receipt)
    atomic(path/'state.json', state)
    atomic(path/'operations'/f'{label}.json', record)
    return receipt


def validate_label(label):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', label):
        raise RuntimeError('Use a lowercase operation name of at most 48 letters, digits or hyphens.')


def freeze_profile(source, target, expected_hash):
    if source.is_symlink():
        raise RuntimeError('Use an ordinary profile file inside the workspace, not a symlink.')
    if not target.exists():
        shutil.copyfile(source, target)
    if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != expected_hash:
        raise RuntimeError('Frozen profile bytes changed; preserve the original experiment and investigate before submitting.')


def prepare(path, max_trials, confirm_dev):
    if not confirm_dev or not 1 <= max_trials <= 1000:
        raise RuntimeError('Confirm your provisioned Dev context with --confirm-dev and choose --max-trials between 1 and 1000.')
    account = identity()
    path.mkdir(parents=True, exist_ok=False)
    (path/'operations').mkdir()
    (path/'profiles').mkdir()
    build(path/'inputs')
    for filename in ('reviewer.json', 'reviewer-evidence.json', 'reviewer-readonly.json', 'learner.json', 'learner-small.json', 'judge.json'):
        shutil.copyfile(ROOT/filename, path/'profiles'/filename)
    state = {'schema': 'synth.tutorial-workspace.v1', 'identity': account,
             'namespace': 'tutorial-' + uuid.uuid4().hex[:12], 'max_trials': max_trials,
             'reserved_trials': 0, 'operations': {}, 'tasks': {}, 'runs': {}}
    atomic(path/'state.json', state)
    print(f'Prepared {path}; no tasks published and no paid trials submitted. Limit: {max_trials} trial slots.')


def launch(path, state, options):
    validate_label(options.name)
    manifest = json.loads((path/'inputs/manifest.json').read_text())
    tasks = [t for t in manifest['tasks'] if t['split'] == options.split and
             (t['name'] == options.only_task if options.only_task else t.get('level', 'core') == 'core')]
    if not tasks:
        raise RuntimeError('No matching task in that split; inspect inputs/manifest.json.')
    trials = options.trials_per_task
    if not 1 <= trials <= 100:
        raise RuntimeError('trials-per-task must be between 1 and 100')
    training = options.batches is not None
    if training:
        if options.split != 'practice' or not 1 <= options.batches <= 200 or not 1 <= options.tasks_per_batch <= len(tasks):
            raise RuntimeError('Training uses practice only, with positive bounded batches/tasks.')
        slots = options.batches * options.tasks_per_batch * trials
        plan = {'num_batches': options.batches, 'batch': {'tasks': options.tasks_per_batch, 'trials_per_task': trials}}
    else:
        slots = len(tasks) * trials
        plan = {'trials_per_task': trials}
    if slots > 1000 or (training and options.tasks_per_batch * trials > 100):
        raise RuntimeError('Plan exceeds the released managed-run limit.')
    if state['reserved_trials'] + slots > state['max_trials'] and options.name not in state['runs']:
        raise RuntimeError('Plan exceeds this workspace work limit.')
    actor = path/'profiles'/options.actor
    judge = path/'profiles'/'judge.json'
    if not actor.is_file() or actor.is_symlink() or actor.parent.resolve() != (path/'profiles').resolve():
        raise RuntimeError('Actor must name one file inside this workspace profiles directory.')
    preview = {'operation': 'training' if training else 'evaluation', 'task_count': len(tasks),
               'task_names': [t['name'] for t in tasks], 'planned_slots': slots, 'plan': plan,
               'actor_sha256': hashlib.sha256(actor.read_bytes()).hexdigest(),
               'judge_sha256': hashlib.sha256(judge.read_bytes()).hexdigest() if options.judge else None}
    print(json.dumps(preview, indent=2))
    if not options.execute:
        print('Preview only. Add --execute after reviewing the workload. Closing this page or rerunning status never submits work.')
        return
    if options.name in state['runs']:
        raise RuntimeError('Run name already submitted. Use status; do not repeat launch.')
    frozen = path/'operations'/(options.name + '-inputs.json')
    if frozen.exists():
        if json.loads(frozen.read_text()) != preview:
            raise RuntimeError('Inputs changed after preparation. Preserve the original experiment.')
    else:
        atomic(frozen, preview)
    for task in tasks:
        # Verify immutable inputs again before publication; no hidden edits.
        task_dir = path/'inputs/tasks'/task['name']
        actual = {str(p.relative_to(task_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in task_dir.rglob('*') if p.is_file()}
        if actual != task['files']:
            raise RuntimeError('Task differs from its manifest; rebuild or explicitly version the adaptation.')
        label = 'task-' + task['name']
        receipt = mutate(path, state, label, ['task', 'upload', str(task_dir), '--name', state['namespace']+'-'+task['name'], '--json'])
        state['tasks'][task['name']] = receipt['version']['immutable_ref']
    dataset_key = options.split + ('-' + options.only_task if options.only_task else '')
    dataset_args = ['dataset', 'create', state['namespace']+'-'+dataset_key, '--json']
    for task in tasks:
        dataset_args.extend(['--task', state['tasks'][task['name']]])
    dataset = mutate(path, state, 'dataset-'+dataset_key, dataset_args)
    dataset_ref = dataset['version']['immutable_ref']
    # Use frozen profile copies so uncertain requests always retain exact bytes.
    actor_copy = path/'operations'/(options.name+'-actor.json')
    freeze_profile(actor, actor_copy, preview['actor_sha256'])
    args = ['train' if training else 'run', 'start', '--dataset', dataset_ref,
            '--actor', '@'+str(actor_copy), '--plan', json.dumps(plan, sort_keys=True),
            '--idempotency-key', state['namespace']+'-'+options.name, '--json']
    if options.judge:
        judge_copy = path/'operations'/(options.name+'-judge.json')
        freeze_profile(judge, judge_copy, preview['judge_sha256'])
        args.extend(['--judge', '@'+str(judge_copy)])
    receipt = mutate(path, state, 'run-'+options.name, args, slots)
    state['runs'][options.name] = {'id': receipt['run_id'], 'planned_slots': slots}
    print(json.dumps(receipt, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('prepare')
    init.add_argument('--max-trials', type=int, required=True)
    init.add_argument('--confirm-dev', action='store_true')
    run = sub.add_parser('launch')
    run.add_argument('--name', required=True)
    run.add_argument('--split', choices=['practice', 'held-out'], required=True)
    run.add_argument('--actor', default='reviewer.json')
    run.add_argument('--only-task', help='One exact task name in the selected split, for an explicitly bounded canary')
    run.add_argument('--trials-per-task', type=int, default=2)
    run.add_argument('--judge', action='store_true')
    run.add_argument('--batches', type=int)
    run.add_argument('--tasks-per-batch', type=int, default=2)
    run.add_argument('--execute', action='store_true')
    sub.add_parser('status')
    sub.add_parser('cleanup')
    cancel = sub.add_parser('cancel')
    cancel.add_argument('name')
    cancel.add_argument('--yes', action='store_true', required=True)
    export = sub.add_parser('export')
    export.add_argument('name')
    options = parser.parse_args()
    path = options.workspace.resolve()
    if options.command == 'prepare':
        prepare(path, options.max_trials, options.confirm_dev)
        return
    with workspace(path) as state:
        if options.command == 'launch':
            launch(path, state, options)
        elif options.command in {'status', 'cleanup'}:
            print(json.dumps({'reserved_trials': state['reserved_trials'], 'max_trials': state['max_trials'],
                              'unfinished_receipts': [k for k,v in state['operations'].items() if v['state']!='receipt']}, indent=2))
            unavailable = False
            for name, run in state['runs'].items():
                try:
                    result = cli(['run', 'show', run['id'], '--json'])
                    run['latest_state'] = result['run']['state']
                except (RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
                    unavailable = True
                    run['latest_state'] = None
                    print(json.dumps({'name': name, 'error': str(error)}, indent=2))
                    continue
                print(json.dumps({'name': name, 'run': result['run']}, indent=2))
            if unavailable:
                raise RuntimeError('Some run states are unavailable. No cleanup was confirmed; retry this read-only check.')
            if options.command == 'cleanup':
                if any(v['state'] != 'receipt' for v in state['operations'].values()):
                    raise RuntimeError('Uncertain operation remains; reconcile its identity before cleanup.')
                if any(r.get('latest_state') not in TERMINAL for r in state['runs'].values()):
                    raise RuntimeError('A run is not terminal. Cancel it by name, then check again.')
                print('Owned runs are terminal. No new cancellation or work submitted. Immutable private task/dataset versions and run evidence remain in your account; this CLI has no registry-delete command. Keep this workspace as the recovery record. No global files or other runs were touched.')
        else:
            run = state['runs'][options.name]
            current = cli(['run', 'show', run['id'], '--json'])
            if options.command == 'cancel':
                if current['run']['state'] in TERMINAL:
                    print('Already terminal; no cancellation submitted.')
                else:
                    print(json.dumps(mutate(path, state, 'cancel-'+options.name,
                        ['run', 'cancel', run['id'], '--yes', '--json']), indent=2))
                    print('Cancellation requested, not yet proven settled. Use status for terminal readback.')
            else:
                if current['run']['state'] not in TERMINAL:
                    raise RuntimeError('Export after the run is terminal; status is read-only.')
                target = path/'evidence'/options.name
                if target.exists():
                    raise RuntimeError('Evidence already exists; inspect it instead of overwriting.')
                target.parent.mkdir(exist_ok=True)
                subprocess.run(['synth', 'run', 'export', run['id'], '--output', str(target)], check=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
