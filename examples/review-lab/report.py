#!/usr/bin/env python3
"""Inspect verified terminal exports; no submissions, regrades or training."""
import argparse
import io
import json
from pathlib import Path
import statistics
import subprocess
import tarfile


def member_json(path, name):
    if not path.is_file():
        return None
    with tarfile.open(path) as archive:
        try:
            member = archive.getmember(name)
        except KeyError:
            return None
        if not member.isfile() or member.size > 1_000_000:
            raise ValueError('Unexpected artifact member; never extract arbitrary paths')
        return json.load(archive.extractfile(member))


def session_usage(lines):
    """Claude emits several blocks per message: count each message ID once."""
    messages = {}
    fields = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')
    for line in lines:
        record = json.loads(line)
        message = record.get('message', {})
        if record.get('type') != 'assistant' or not message.get('id') or not message.get('usage'):
            continue
        usage = {key: message['usage'].get(key, 0) for key in fields}
        if any(type(value) is not int or value < 0 for value in usage.values()):
            raise ValueError('Invalid usage count in retained session')
        # Stream updates can repeat or increase cumulative message counters.
        previous = messages.get(message['id'], dict.fromkeys(fields, 0))
        messages[message['id']] = {key: max(previous[key], usage[key]) for key in fields}
    if not messages:
        return None
    return {**{key: sum(row[key] for row in messages.values()) for key in fields},
            'messages': len(messages), 'source': 'retained Claude session; deduplicated message IDs'}


def judge_usage(path):
    if not path.is_file():
        return None
    with tarfile.open(path) as outer:
        try:
            nested = outer.getmember('judge/judge-session.tar')
        except KeyError:
            return None
        if not nested.isfile() or nested.size > 50_000_000:
            raise ValueError('Unexpected nested session; never extract arbitrary paths')
        with tarfile.open(fileobj=io.BytesIO(outer.extractfile(nested).read())) as inner:
            sessions = [item for item in inner.getmembers()
                        if item.name.startswith('judge-session/projects/') and item.name.endswith('.jsonl')]
            if not sessions:
                return None
            if len(sessions) != 1 or not sessions[0].isfile() or sessions[0].size > 40_000_000:
                raise ValueError('Ambiguous or oversized judge session')
            return session_usage(inner.extractfile(sessions[0]))


def actor_usage(path):
    trajectory = member_json(path, 'trajectory.json')
    metrics = trajectory.get('final_metrics') if trajectory else None
    if not metrics:
        return None
    return {'input_tokens': metrics.get('total_prompt_tokens'),
            'output_tokens': metrics.get('total_completion_tokens'),
            'cached_tokens': metrics.get('total_cached_tokens'),
            'steps': metrics.get('total_steps'), 'source': 'retained trajectory final_metrics'}


def collect(export):
    result = json.loads((export/'result.json').read_text())
    run_id = result['run_id']
    cache = export/'trials.json'
    if cache.exists():
        trials = json.loads(cache.read_text())
    else:
        trials, offset = [], 0
        while True:
            page = json.loads(subprocess.check_output(['synth', 'run', 'trials', run_id,
                '--json', '--limit', '200', '--offset', str(offset)], text=True, timeout=120))
            trials.extend(page['items'])
            if not page['has_more']:
                break
            offset += len(page['items'])
            if not page['items']:
                raise ValueError('Pagination did not advance')
        cache.write_text(json.dumps(trials, indent=2) + '\n')
    artifact_dir = export/'artifacts'
    evaluation = artifact_dir/'evaluation.json'
    metrics = {}
    if evaluation.exists():
        for item in json.loads(evaluation.read_text()).get('task_results', []):
            meta = item.get('metadata', {})
            name = meta.get('actor_artifacts', {}).get('name', '')
            if name.startswith('trial-') and name.endswith('-actor-artifacts.tar.gz'):
                metrics[name[6:-len('-actor-artifacts.tar.gz')]] = {key: meta.get(key) for key in
                    ('actor_wall_time_seconds', 'verifier_wall_time_seconds', 'environment_setup_wall_time_seconds')}
    rows = []
    for trial in trials:
        trial_id = trial['trial_id']
        reviewed = artifact_dir/f'role-{trial_id}-output-review'
        assessment = member_json(artifact_dir/f'trial-{trial_id}-judge-outputs.tar.gz', 'reward.json')
        rows.append({'trial_id': trial_id, 'task': trial['task'], 'sample': trial['sample_number'],
                     'state': trial['state'], 'result': trial.get('result'),
                     'review': json.loads(reviewed.read_text()) if reviewed.exists() else None,
                     'assessment': assessment, 'timing': metrics.get(trial_id, {}),
                     'usage': {'actor': actor_usage(artifact_dir/f'trial-{trial_id}-actor-session.tar.gz'),
                               'judge': judge_usage(artifact_dir/f'trial-{trial_id}-judge-outputs.tar.gz')}})
    rewards = [r['result']['reward']['value'] for r in rows
               if r['result'] and r['result'].get('reward', {}).get('present')]
    usage = {}
    for role in ('actor', 'judge'):
        observed = [row['usage'][role] for row in rows if row['usage'][role] is not None]
        usage[role] = {'trials_with_usage': len(observed), 'trials_without_usage': len(rows)-len(observed),
                       **{field: sum(row[field] for row in observed) if observed and all(row.get(field) is not None for row in observed) else None
                          for field in ('input_tokens', 'output_tokens')}}
    return {'schema': 'synth.tutorial-report.v1', 'run_id': run_id,
            'distinct_tasks': len({r['task'] for r in rows}), 'attempted_trials': len(rows),
            'scored_trials': len(rewards), 'missing_scores': len(rows)-len(rewards),
            'reward_mean': statistics.mean(rewards) if rewards else None,
            'usage': usage,
            'usage_note': 'Retained session counters, not a provider invoice. Input tokens sum repeated call contexts, not unique source text. Missing usage is unknown, not zero. Optimizer usage and sandbox billing are not included.',
            'billing_dollars': None, 'billing_note': 'No provider invoice in this export; unknown is not zero.',
            'semantic_verdict': 'REQUIRES_REVIEW: read every candidate and rationale before deciding.',
            'trials': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(args.export), indent=2))
