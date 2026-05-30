#!/usr/bin/env python3
"""Simple smoke test for the CSUF Scheduler API.

This script uses only the standard library so it doesn't add extra deps.
It performs a few basic checks against a running local server (default http://127.0.0.1:5000):
 - GET /api/users (expects 200 + JSON list)
 - GET /api/shifts (expects 200 + JSON list)
 - POST /api/shifts (creates a shift) -> expects 201
 - GET /api/shifts and verify the created shift is present

Usage:
  python backend/smoke_test.py

You can set BASE_URL env var to point to a different host (e.g., http://0.0.0.0:5000)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from urllib import request, error
from http.cookiejar import CookieJar


BASE = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')
cookies = CookieJar()
opener = request.build_opener(request.HTTPCookieProcessor(cookies))


def do_get(path: str):
    url = BASE.rstrip('/') + path
    req = request.Request(url, method='GET')
    try:
        with opener.open(req, timeout=5) as resp:
            body = resp.read()
            return resp.getcode(), body
    except error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode()


def do_post(path: str, payload: dict):
    url = BASE.rstrip('/') + path
    data = json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with opener.open(req, timeout=5) as resp:
            body = resp.read()
            return resp.getcode(), body
    except error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode()


def expect_ok(code, body, desc=''):
    ok = code == 200
    print(f"[{'PASS' if ok else 'FAIL'}] {desc} -> code={code}")
    if not ok:
        print(body.decode(errors='ignore'))
    return ok


def main():
    print('CSUF Scheduler smoke test — contacting', BASE)

    ok = True

    # Login first as admin
    login_payload = {'email': 'admin@csuf.edu', 'password': 'password'}
    code, body = do_post('/api/users/login', login_payload)
    if code != 200:
        print('[FAIL] Login as admin@csuf.edu -> code', code)
        print(body.decode(errors='ignore'))
        ok = False
    else:
        print('[PASS] Login as admin@csuf.edu')

    # GET /api/users - requires auth now
    code, body = do_get('/api/users')
    try:
        data = json.loads(body) if body else []
    except json.JSONDecodeError:
        data = None
    if code != 200 or data is None:
        print('[FAIL] GET /api/users', code)
        print(body.decode(errors='ignore'))
        ok = False
    else:
        print(f'[PASS] GET /api/users -> {len(data)} users')

    # GET /api/shifts
    code, body = do_get('/api/shifts')
    try:
        shifts = json.loads(body) if body else []
    except json.JSONDecodeError:
        shifts = None
    if code != 200 or shifts is None:
        print('[FAIL] GET /api/shifts', code)
        print(body.decode(errors='ignore'))
        ok = False
    else:
        print(f'[PASS] GET /api/shifts -> {len(shifts)} shifts')

    # POST /api/shifts (create a unique shift) - requires auth now
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {"date": tomorrow, "start_time": "09:00", "end_time": "11:00"}
    code, body = do_post('/api/shifts', payload)
    if code != 201:
        print('[FAIL] POST /api/shifts expected 201, got', code)
        print(body.decode(errors='ignore'))
        ok = False
    else:
        print('[PASS] POST /api/shifts -> created')

    # Wait briefly then confirm the shift exists
    time.sleep(0.7)
    code, body = do_get('/api/shifts')
    found = False
    try:
        all_shifts = json.loads(body) if body else []
        for s in all_shifts:
            if s.get('date') == tomorrow and s.get('start_time') == '09:00' and s.get('end_time') == '11:00':
                found = True
                break
    except json.JSONDecodeError:
        all_shifts = None

    if not found:
        print('[FAIL] Created shift not found in GET /api/shifts')
        ok = False
    else:
        print('[PASS] Created shift found in list')

    print('\nSmoke test ' + ('PASSED' if ok else 'FAILED'))
    sys.exit(0 if ok else 2)


if __name__ == '__main__':
    main()
