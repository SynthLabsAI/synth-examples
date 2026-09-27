#!/usr/bin/env python3
"""Read-only local prerequisite check. Does not prove server access or spend."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

EXPECTED = 'synth 0.0.1-alpha.62'
PRODUCTION = 'https://sprites-gateway.api.synthlabs.ai'


def invoke(args):
    try:
        result = subprocess.run(['synth', *args], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        raise ValueError('Synth CLI was not found on PATH; install CLI alpha.62: '
                         'https://synthlabs.mintlify.app/getting-started/install') from None
    if result.returncode:
        raise ValueError('synth ' + ' '.join(args[:2]) + ' failed; inspect that command before proceeding')
    return result.stdout


def check(directory, confirmed, runner=invoke):
    if not confirmed:
        raise ValueError('Use --confirm-dev only after your organization has provisioned Dev access')
    if sys.version_info < (3, 10):
        raise ValueError('Python 3.10 or later is required')
    version = runner(['version']).strip()
    if version != EXPECTED:
        raise ValueError('This example is qualified with ' + EXPECTED + '; inspect your installed release')
    status = json.loads(runner(['status', '--json']))
    if not isinstance(status, dict) or not status.get('request_authenticated') or status.get('service_key_active'):
        raise ValueError('Normal customer sign-in is required; this check does not sign you in')
    try:
        endpoint = urlsplit(status.get('api_base_url', ''))
        port = endpoint.port
        unsafe = (endpoint.scheme != 'https' or not endpoint.hostname
                  or endpoint.hostname.rstrip('.').lower() == urlsplit(PRODUCTION).hostname
                  or endpoint.username is not None or endpoint.password is not None
                  or bool(endpoint.query) or bool(endpoint.fragment)
                  or port == 0)
    except (AttributeError, TypeError, ValueError):
        unsafe = True
    if unsafe:
        raise ValueError('Use your provisioned Dev context; this check does not change the connection')
    profile = directory/'reviewer.json'
    if profile.is_symlink() or not profile.is_file():
        raise ValueError('Run this check beside the ordinary reviewer.json supplied in the project')
    runner(['agent', 'validate', '@'+str(profile)])
    return {'schema':'synth.example-readiness.v1', 'local_prerequisites':'passed',
            'cli':version, 'python':'.'.join(map(str,sys.version_info[:3])),
            'profile_sha256':hashlib.sha256(profile.read_bytes()).hexdigest(),
            'server_admission':'not tested', 'model_availability':'not tested',
            'paid_work_submitted':False,
            'next':'Follow the first-result tutorial. Only an actual accepted execution proves live compatibility.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-dev', action='store_true')
    options = parser.parse_args()
    try:
        print(json.dumps(check(Path(__file__).resolve().parent, options.confirm_dev), indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
