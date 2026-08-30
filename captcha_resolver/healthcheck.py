#!/usr/bin/env python3
"""Read-only health check for the configured captcha integration."""

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from captcha_resolver.web_solver import WebSolver


def status(name, ok, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"[{'OK' if ok else 'FAIL'}] {name}{suffix}")
    return ok


async def run(config_path):
    with open(config_path, 'r', encoding='utf-8') as file:
        settings = json.load(file)

    captcha = settings.get('captcha', {})
    service = str(captcha.get('service', '2captcha')).lower()
    api_key = str(captcha.get('api_key', '')).strip()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = captcha.get('model_path', '')
    resolved_model_path = (
        model_path if os.path.isabs(model_path)
        else os.path.join(project_root, model_path)
    )

    checks = [
        status('captcha enabled', captcha.get('enabled') is True),
        status('supported service', service in ('2captcha', 'yescaptcha'), service),
        status('API key configured', bool(api_key)),
        status('resolver runner exists', os.path.isfile(
            os.path.join(os.path.dirname(__file__), 'resolver_runner.py')
        )),
        status('main entry point exists', os.path.isfile(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
        )),
    ]

    if captcha.get('enable_image', True):
        checks.append(status('ONNX model exists', os.path.isfile(resolved_model_path), model_path))

    if api_key and service in ('2captcha', 'yescaptcha'):
        solver = WebSolver(api_key=api_key, service=service)
        balance = await solver.get_balance()
        api_ok = solver.last_error is None
        checks.append(status('solver API reachable/authenticated', api_ok,
                             solver.last_error or 'credentials accepted'))
        checks.append(status('solver balance sufficient', balance >= solver.min_balance,
                             'sufficient' if balance >= solver.min_balance else 'too low'))

    print('\nSecrets were not printed. No captcha task was created and no fee was charged.')
    return 0 if all(checks) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='settings.json')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.config)))


if __name__ == '__main__':
    main()
