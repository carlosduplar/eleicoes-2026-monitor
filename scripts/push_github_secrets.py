#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Push selected environment variables to GitHub Actions secrets using the GH CLI.

Usage examples:
  # Dry-run (default) - shows which secrets would be set
  python scripts\push_github_secrets.py

  # Actually set secrets in the current repo
  python scripts\push_github_secrets.py --yes

  # Set secrets in a specific repo (owner/repo)
  python scripts\push_github_secrets.py --yes --repo myorg/myrepo

Notes:
- Does NOT print secret values. Uses `gh secret set NAME --body <value>`; ensure `gh` is installed and authenticated.
- Dry-run by default to avoid accidental writes.
- Do NOT commit actual secret values to the repository.
"""

import os
import sys
import argparse
import subprocess
import shutil

DEFAULT_SECRETS = [
    'NVIDIA_API_KEY',
    'OPENROUTER_API_KEY',
    'OLLAMA_API_KEY',
    'VERTEX_ACCESS_TOKEN',
    'XIAOMI_MIMO_API_KEY',
]


def check_gh():
    """Ensure gh CLI is available and the user is authenticated."""
    if shutil.which('gh') is None:
        sys.exit('gh CLI not found. Install from https://cli.github.com/ and authenticate with `gh auth login`.')
    try:
        subprocess.run(['gh', 'auth', 'status'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        sys.exit('gh CLI appears unauthenticated. Run `gh auth login` before continuing.')


def set_secret(name: str, value: str, repo: str | None = None) -> tuple[bool, str | None]:
    """Set a single secret via gh CLI. Returns (success, error_message)."""
    cmd = ['gh', 'secret', 'set', name, '--body', value]
    if repo:
        cmd += ['--repo', repo]
    try:
        # Do not capture stdout (avoid printing values). Capture stderr for diagnostics only.
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return True, None
    except subprocess.CalledProcessError as e:
        err = None
        try:
            err = e.stderr.decode().strip() if e.stderr else str(e)
        except Exception:
            err = str(e)
        return False, err


def main() -> int:
    parser = argparse.ArgumentParser(description='Push environment variables to GitHub secrets via gh CLI')
    parser.add_argument('--secrets', '-s', nargs='+', default=DEFAULT_SECRETS,
                        help='Names of environment variables to publish as GitHub secrets')
    parser.add_argument('--repo', '-r', help='Repository (owner/repo). If omitted, uses current repository context')
    parser.add_argument('--yes', '-y', action='store_true', help='Actually set secrets; without this the script does a dry run')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    check_gh()

    to_set = []
    for name in args.secrets:
        val = os.environ.get(name)
        if val:
            to_set.append((name, val))
        elif args.verbose:
            print(f"Skipping {name}: environment variable not set")

    if not to_set:
        print('No matching environment variables found. Nothing to do.')
        return 0

    print('Secrets to set (values hidden):')
    for name, _ in to_set:
        print(' -', name)

    if not args.yes:
        print('\nDry run. Re-run with --yes to actually push secrets.')
        return 0

    if sys.stdin.isatty():
        resp = input('Proceed to set these secrets in GitHub? [y/N]: ').strip().lower()
        if resp not in ('y', 'yes'):
            print('Aborted.')
            return 1

    errors = []
    for name, val in to_set:
        print(f'Setting {name}...', end='', flush=True)
        ok, err = set_secret(name, val, repo=args.repo)
        if ok:
            print(' done')
        else:
            print(' failed')
            errors.append((name, err))

    if errors:
        print('\nSome secrets failed to set:')
        for name, err in errors:
            print(f' - {name}: {err}')
        return 2

    print('All secrets set successfully.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
