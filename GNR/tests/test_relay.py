"""Regression tests with fake GPU clients / fake node; never real mining or coins."""
import concurrent.futures
import importlib.util
import json
import math
from pathlib import Path
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'hiveos'))
import relay
import runtime as gnr

ADDRESS = 'gnr1' + 'q' * 2600
WORK = {'job_id': 100, 'height': 15926, 'pow_hash': 'ab' * 32,
        'share_difficulty': '20', 'epoch': 0, 'chain_seed': 'cd' * 32, 'network': 'mainnet'}


class Clock:
    def __init__(self): self.now = 100.0
    def __call__(self): return self.now
    def advance(self, value): self.now += value


class FakeStop:
    def __init__(self, clock): self.clock, self.stopped = clock, False
    def is_set(self): return self.stopped
    def set(self): self.stopped = True
    def wait(self, delay): self.clock.advance(delay); return self.stopped


class Node:
    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()
        self.code = 200
        self.headers = {}
        self.reject = False
    def __call__(self, path, payload):
        with self.lock:
            self.calls.append((path, payload))
        if self.code != 200:
            return self.code, self.headers, {'error': 'too many requests from your address; slow down'}
        if path.endswith('/template'):
            return 200, {}, dict(WORK)
        if path.endswith('/submit'):
            return 200, {}, {'accepted': not self.reject, 'kind': 'share', 'height': 15926}
        if path == '/v1/info':
            return 200, {}, {'network': 'mainnet', 'height': 15926, 'hashrate': 1000}
        return 200, {}, {'unpaid': 100}


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.clock, self.node = Clock(), Node()
        self.stop = FakeStop(self.clock)
        self.c = relay.Coordinator('https://example.invalid', ADDRESS, self.stop,
                                   clock=self.clock, fetch=self.node, log=lambda *a: None)

    def test_12_simultaneous_clients_one_template(self):
        barrier = threading.Barrier(12)
        def client(_): barrier.wait(); return self.c.template(ADDRESS)
        with concurrent.futures.ThreadPoolExecutor(12) as pool:
            results = list(pool.map(client, range(12)))
        self.assertTrue(all(r == WORK for r in results))
        self.assertEqual(len(self.node.calls), 1)
        self.assertEqual(self.c.metrics()['template_cache_hits'], 11)

    def test_360_local_requests_at_one_instant_one_upstream(self):
        with concurrent.futures.ThreadPoolExecutor(12) as pool:
            list(pool.map(lambda _: self.c.template(ADDRESS), range(360)))
        self.assertEqual(len(self.node.calls), 1)

    def test_sixty_seconds_12_clients_rate_budget(self):
        for tick in range(600):
            for _ in range(12): self.c.template(ADDRESS)
            self.clock.advance(0.1)
        self.assertLessEqual(len(self.node.calls), 21)
        self.assertGreaterEqual(len(self.node.calls), 19)

    def test_refresh_replaces_job(self):
        self.c.template(ADDRESS)
        self.clock.advance(3.1)
        self.c.template(ADDRESS)
        self.assertEqual(len(self.node.calls), 2)

    def test_429_is_shared_and_honors_retry_after(self):
        self.node.code, self.node.headers = 429, {'Retry-After': '10'}
        for _ in range(12):
            with self.assertRaises(relay.NodeError): self.c.template(ADDRESS)
        self.assertEqual(len(self.node.calls), 1)
        self.assertGreaterEqual(self.c.remaining_backoff(), 10)
        self.clock.advance(9)
        with self.assertRaises(relay.NodeError): self.c.template(ADDRESS)
        self.assertEqual(len(self.node.calls), 1)
        self.clock.advance(1.1)
        self.node.code = 200
        self.assertEqual(self.c.template(ADDRESS), WORK)
        self.assertEqual(len(self.node.calls), 2)

    def test_no_expired_template_during_backoff(self):
        self.c.template(ADDRESS)
        self.clock.advance(4)
        self.node.code, self.node.headers = 429, {'Retry-After': '10'}
        with self.assertRaises(relay.NodeError): self.c.template(ADDRESS)
        with self.assertRaises(relay.NodeError): self.c.template(ADDRESS)
        self.assertIsNone(self.c._template)

    def test_different_wallet_not_forwarded(self):
        with self.assertRaises(relay.NodeError): self.c.template('gnr1other')
        self.assertEqual(self.node.calls, [])

    def test_read_cache(self):
        for _ in range(12): self.c.read('/v1/info')
        self.assertEqual(len(self.node.calls), 1)
        self.clock.advance(31)
        self.c.read('/v1/info')
        self.assertEqual(len(self.node.calls), 2)

    def test_transaction_endpoint_blocked(self):
        with self.assertRaises(relay.NodeError): self.c.read('/v1/tx')
        self.assertEqual(self.node.calls, [])

    def test_unknown_job_not_forwarded(self):
        with self.assertRaises(relay.NodeError): self.c.submit({'job_id': 7, 'nonce': 2})
        self.assertEqual(self.node.calls, [])

    def test_invalid_submission_not_forwarded(self):
        self.c.template(ADDRESS)
        for value in ({'job_id': True, 'nonce': 3}, {'job_id': 100, 'nonce': -1},
                      {'job_id': 100, 'nonce': 2**64}, {'job_id': 100},
                      {'job_id': 100, 'nonce': 1, 'address': 'other'}):
            with self.assertRaises(relay.NodeError): self.c.submit(value)
        self.assertEqual(len(self.node.calls), 1)

    def test_accepted_response_is_authoritative(self):
        self.c.template(ADDRESS)
        response = self.c.submit({'job_id': 100, 'nonce': 23})
        self.assertEqual(response, {'accepted': True, 'kind': 'share', 'height': 15926})
        self.assertEqual(self.c.metrics()['accepted_shares'], 1)

    def test_rejected_response_not_made_accepted(self):
        self.c.template(ADDRESS)
        self.node.reject = True
        self.assertFalse(self.c.submit({'job_id': 100, 'nonce': 23})['accepted'])
        self.assertEqual(self.c.metrics().get('accepted_shares', 0), 0)

    def test_429_submit_retried_once_after_delay(self):
        self.c.template(ADDRESS)
        attempts = []
        def fetch(path, payload):
            attempts.append(self.clock())
            if len(attempts) == 1: return 429, {'Retry-After': '10'}, {'error': 'slow down'}
            return 200, {}, {'accepted': True, 'kind': 'share'}
        self.c._fetch_override = fetch
        self.assertTrue(self.c.submit({'job_id': 100, 'nonce': 24})['accepted'])
        self.assertEqual(len(attempts), 2)
        self.assertGreaterEqual(attempts[1] - attempts[0], 10)

    def test_ambiguous_submit_transport_failure_not_retried(self):
        self.c.template(ADDRESS)
        attempts = []
        def fetch(path, payload): attempts.append(path); raise OSError('connection lost')
        self.c._fetch_override = fetch
        with self.assertRaises(relay.NodeError): self.c.submit({'job_id': 100, 'nonce': 24})
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.c.metrics().get('accepted_shares', 0), 0)

    def test_very_long_retry_after_not_capped(self):
        self.node.code, self.node.headers = 429, {'Retry-After': '3600'}
        with self.assertRaises(relay.NodeError): self.c.template(ADDRESS)
        self.assertEqual(self.c.remaining_backoff(), 3600)

    def test_retry_after_date(self):
        self.assertEqual(relay.retry_seconds('Thu, 01 Jan 1970 00:02:00 GMT', now=100), 20)
        self.assertEqual(relay.retry_seconds('garbage'), 0)

    def test_wrong_network_is_not_served(self):
        self.c._fetch_override = lambda *a: (200, {}, dict(WORK, network='testnet'))
        with self.assertRaises(relay.NodeError): self.c.template(ADDRESS)
        self.assertIsNone(self.c._template)

    def test_block_invalidates_template_without_burst(self):
        self.c.template(ADDRESS)
        self.c._fetch_override = lambda *a: (200, {}, {'accepted': True, 'kind': 'block'})
        self.c.submit({'job_id': 100, 'nonce': 24})
        self.assertEqual(self.c.metrics()['accepted_blocks'], 1)
        with self.assertRaises(relay.NodeError): self.c.template(ADDRESS)
        self.assertEqual(self.c.metrics()['template_requests'], 1)

    def test_config_safe_defaults(self):
        cfg = gnr.config_from_env({'GNR_WALLET': ADDRESS})
        self.assertEqual(cfg['node_poll'], 3)
        self.assertEqual(cfg['cpu_threads'], 1)
        self.assertEqual(cfg['start_delay'], 1.5)

    def test_config_extra_options(self):
        c = gnr.config_from_env({'GNR_WALLET': ADDRESS, 'GNR_EXTRA': '--devices 0,2 --node-poll 5 --cpu-threads 2'})
        self.assertEqual(c['devices'], [0, 2])
        self.assertEqual(c['node_poll'], 5)

    def test_invalid_poll_rejected(self):
        for option in ('--node-poll 0', '--node-poll nan', '--node-poll inf',
                       '--cpu-threads 0', '--start-delay -1'):
            with self.assertRaises(ValueError):
                gnr.config_from_env({'GNR_WALLET': ADDRESS, 'GNR_EXTRA': option})


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.node = Node()
        self.stop = threading.Event()
        self.c = relay.Coordinator('https://example.invalid', ADDRESS, self.stop,
                                   fetch=self.node, log=lambda *a: None)
        self.r = relay.Relay(self.c)
        self.url = self.r.start()
    def tearDown(self):
        self.stop.set()
        self.r.close()
    def request(self, path, value=None):
        data = None if value is None else json.dumps(value).encode()
        with urllib.request.urlopen(urllib.request.Request(self.url + path, data=data), timeout=5) as response:
            return json.load(response)
    def test_12_gpu_clients_sharing_real_local_http(self):
        barrier = threading.Barrier(12)
        def worker(i):
            barrier.wait()
            for _ in range(20): self.request('/v1/mining/template', {'address': ADDRESS})
            return self.request('/v1/mining/submit', {'job_id': 100, 'nonce': i})
        with concurrent.futures.ThreadPoolExecutor(12) as pool:
            results = list(pool.map(worker, range(12)))
        self.assertTrue(all(r['accepted'] for r in results))
        self.assertLessEqual(self.c.metrics()['template_requests'], 2)
        self.assertEqual(self.c.metrics()['submit_requests'], 12)
        self.assertEqual(self.c.metrics()['accepted_shares'], 12)
    def test_bound_only_to_loopback(self):
        self.assertEqual(self.r.server.server_address[0], '127.0.0.1')
    def test_missing_token_rejected(self):
        base = 'http://127.0.0.1:%s' % self.r.server.server_address[1]
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + '/wrong/v1/info', timeout=2)
        self.assertEqual(e.exception.code, 404)
    def test_foreign_payout_over_http_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/v1/mining/template', {'address': 'gnr1foreign'})
        self.assertEqual(e.exception.code, 403)
    def test_disallowed_endpoint_over_http(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/v1/tx', {'transaction': 'forbidden'})
        self.assertEqual(e.exception.code, 404)


if __name__ == '__main__': unittest.main()
