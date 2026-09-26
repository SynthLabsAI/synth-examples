"""No-spend tests of identity, bounds, receipts and interrupted operations."""
import copy
import argparse
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1] / 'examples/review-lab'
sys.path.insert(0, str(ROOT))
import tutorial

ACCOUNT = {'request_authenticated': True, 'service_key_active': False,
           'user_id': 'customer', 'org': 'organization', 'api_base_url': 'https://test.invalid'}


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'workspace'
        with patch.object(tutorial, 'cli', return_value=ACCOUNT):
            tutorial.prepare(self.path, 32, True)
        self.state = json.loads((self.path/'state.json').read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def test_prepare_is_offline_except_status_and_never_overwrites(self):
        self.assertEqual(self.state['reserved_trials'], 0)
        self.assertTrue((self.path/'profiles/reviewer.json').is_file())
        with patch.object(tutorial, 'cli', return_value=ACCOUNT):
            with self.assertRaises(FileExistsError):
                tutorial.prepare(self.path, 32, True)

    def test_reject_bad_bound_and_unconfirmed_context(self):
        for limit, confirm in [(0, True), (1001, True), (1, False)]:
            with self.assertRaises(RuntimeError):
                tutorial.prepare(self.path/'bad', limit, confirm)

    def test_no_service_key_no_production_no_anonymous(self):
        for change in [{'service_key_active': True}, {'request_authenticated': False},
                       {'api_base_url': 'https://sprites-gateway.api.synthlabs.ai'}]:
            with patch.object(tutorial, 'cli', return_value={**ACCOUNT, **change}):
                with self.assertRaises(RuntimeError):
                    tutorial.identity()

    def test_reservation_precedes_remote_write(self):
        def remote(args):
            if args[0] == 'status':
                return ACCOUNT
            disk = json.loads((self.path/'state.json').read_text())
            self.assertEqual(disk['reserved_trials'], 16)
            self.assertEqual(disk['operations']['run-test']['state'], 'reserved')
            return {'run_id': 'recorded-run'}
        with patch.object(tutorial, 'cli', side_effect=remote):
            receipt = tutorial.mutate(self.path, self.state, 'run-test', ['run', 'start'], 16)
        self.assertEqual(receipt['run_id'], 'recorded-run')

    def test_successful_replay_reuses_receipt_without_remote_call(self):
        self.state['operations']['test'] = {'args': ['task', 'upload'], 'state': 'receipt', 'receipt': {'id': 'one'}}
        with patch.object(tutorial, 'cli', side_effect=AssertionError('No remote call expected')):
            self.assertEqual(tutorial.mutate(self.path, self.state, 'test', ['task', 'upload']), {'id': 'one'})

    def test_timeout_is_retained_and_never_retried(self):
        with patch.object(tutorial, 'cli', side_effect=[ACCOUNT, subprocess.TimeoutExpired('synth', 120)]):
            with self.assertRaises(subprocess.TimeoutExpired):
                tutorial.mutate(self.path, self.state, 'run-test', ['run', 'start'], 16)
        state = json.loads((self.path/'state.json').read_text())
        self.assertEqual(state['reserved_trials'], 16)
        with patch.object(tutorial, 'cli', side_effect=AssertionError('No retry')):
            with self.assertRaises(RuntimeError):
                tutorial.mutate(self.path, state, 'run-test', ['run', 'start'], 16)

    def test_budget_and_identity_fail_before_write(self):
        with patch.object(tutorial, 'cli', return_value=ACCOUNT):
            with self.assertRaises(RuntimeError):
                tutorial.mutate(self.path, self.state, 'too-big', ['run', 'start'], 33)
        with patch.object(tutorial, 'cli', return_value={**ACCOUNT, 'org': 'other'}):
            with self.assertRaises(RuntimeError):
                tutorial.mutate(self.path, self.state, 'wrong-org', ['run', 'start'], 1)
        self.assertFalse(self.state['operations'])

    def test_names_cannot_escape_workspace(self):
        for label in ['../other', '/tmp/a', 'a.b', 'UPPER', 'a'*49]:
            with self.assertRaises(RuntimeError):
                tutorial.validate_label(label)

    def test_lock_refuses_overlap_and_preserves_on_error(self):
        with self.assertRaises(ValueError):
            with tutorial.workspace(self.path) as state:
                state['marker'] = 'durable'
                with self.assertRaises(RuntimeError):
                    with tutorial.workspace(self.path):
                        pass
                raise ValueError('interrupted')
        self.assertEqual(json.loads((self.path/'state.json').read_text())['marker'], 'durable')

    def options(self, **changes):
        values = dict(name='probe', split='practice', only_task=None,
            trials_per_task=2, batches=None, tasks_per_batch=2, actor='reviewer.json',
            judge=True, execute=False)
        return argparse.Namespace(**{**values, **changes})

    def test_preview_has_no_remote_operations(self):
        with patch.object(tutorial, 'cli', side_effect=AssertionError('Preview must be offline')):
            tutorial.launch(self.path, self.state, self.options())
        self.assertFalse(self.state['operations'])
        self.assertEqual(self.state['reserved_trials'], 0)

    def test_tampered_task_stops_before_any_upload(self):
        manifest = json.loads((self.path/'inputs/manifest.json').read_text())
        task = next(t for t in manifest['tasks'] if t['split']=='practice' and t['level']=='core')
        (self.path/'inputs/tasks'/task['name']/'instruction.md').write_text('changed')
        options = self.options()
        options.execute = True
        with patch.object(tutorial, 'cli', side_effect=AssertionError('No upload')):
            with self.assertRaisesRegex(RuntimeError, 'manifest'):
                tutorial.launch(self.path, self.state, options)

    def test_frozen_profile_rechecked_not_silently_reused(self):
        source = self.path/'profiles/reviewer.json'
        target = self.path/'operations/probe-actor.json'
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        tutorial.freeze_profile(source, target, digest)
        target.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'Frozen profile'):
            tutorial.freeze_profile(source, target, digest)

    def test_symlink_profile_refused(self):
        linked = self.path/'profiles/linked.json'
        linked.symlink_to(self.path/'profiles/reviewer.json')
        options = self.options()
        options.actor = 'linked.json'
        with self.assertRaisesRegex(RuntimeError, 'Actor must'):
            tutorial.launch(self.path, self.state, options)

    def test_heldout_training_refused_before_any_write(self):
        options = self.options()
        options.batches, options.split, options.execute = 1, 'held-out', True
        with patch.object(tutorial, 'cli', side_effect=AssertionError('No write')):
            with self.assertRaisesRegex(RuntimeError, 'practice only'):
                tutorial.launch(self.path, self.state, options)

    def test_only_task_never_expands_to_the_dataset(self):
        options = self.options()
        options.only_task = 'exports-regression'
        options.trials_per_task = 1
        with patch.object(tutorial, 'cli', side_effect=AssertionError('No write')):
            tutorial.launch(self.path, self.state, options)
        options.only_task = 'not-a-task'
        with self.assertRaisesRegex(RuntimeError, 'No matching task'):
            tutorial.launch(self.path, self.state, options)

    def test_cleanup_refuses_active_or_uncertain_owned_work(self):
        for unfinished, phase in [(True, 'succeeded'), (False, 'running')]:
            state = copy.deepcopy(self.state)
            state['runs'] = {'one': {'id': 'exact-owned-run'}}
            if unfinished:
                state['operations']['run-one'] = {'state': 'uncertain-or-rejected'}
            tutorial.atomic(self.path/'state.json', state)
            with patch.object(sys, 'argv', ['tutorial.py', str(self.path), 'cleanup']), \
                 patch.object(tutorial, 'cli', return_value={'run': {'state': phase}}) as read:
                with self.assertRaises(RuntimeError):
                    tutorial.main()
                read.assert_called_once_with(['run', 'show', 'exact-owned-run', '--json'])

    def test_terminal_cancel_is_a_read_not_another_mutation(self):
        state = copy.deepcopy(self.state)
        state['runs'] = {'one': {'id': 'exact-owned-run'}}
        tutorial.atomic(self.path/'state.json', state)
        with patch.object(sys, 'argv', ['tutorial.py', str(self.path), 'cancel', 'one', '--yes']), \
             patch.object(tutorial, 'cli', return_value={'run': {'state': 'cancelled'}}) as read:
            tutorial.main()
            read.assert_called_once_with(['run', 'show', 'exact-owned-run', '--json'])

    def test_status_and_cleanup_continue_after_failed_reads_without_claiming_success(self):
        for command in ('status', 'cleanup'):
            for error in (RuntimeError('unavailable'), ValueError('invalid JSON'),
                          subprocess.TimeoutExpired('synth', 120), KeyError('run')):
                with self.subTest(command=command, error=type(error).__name__):
                    state = copy.deepcopy(self.state)
                    state['runs'] = {
                        'one': {'id': 'first-run', 'latest_state': 'succeeded'},
                        'two': {'id': 'second-run'},
                    }
                    tutorial.atomic(self.path/'state.json', state)
                    output = io.StringIO()
                    with patch.object(sys, 'argv', ['tutorial.py', str(self.path), command]), \
                         patch.object(sys, 'stdout', output), \
                         patch.object(tutorial, 'cli', side_effect=[error, {'run': {'state': 'succeeded'}}]) as read:
                        with self.assertRaisesRegex(RuntimeError, 'Some run states are unavailable'):
                            tutorial.main()
                    self.assertEqual(read.call_count, 2)
                    self.assertEqual(read.call_args_list[1].args[0], ['run', 'show', 'second-run', '--json'])
                    saved = json.loads((self.path/'state.json').read_text())
                    self.assertIsNone(saved['runs']['one']['latest_state'])
                    self.assertEqual(saved['runs']['two']['latest_state'], 'succeeded')
                    self.assertIn('"error"', output.getvalue())
                    self.assertIn('"name": "two"', output.getvalue())
                    self.assertNotIn('Owned runs are terminal', output.getvalue())


if __name__ == '__main__':
    unittest.main()
