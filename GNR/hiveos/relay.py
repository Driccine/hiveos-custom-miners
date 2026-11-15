"""Loopback-only GNR work coordinator. Python 3.8+, no third-party packages.
Coalesces template requests, honors upstream backoff, never invents accepted shares.
Only the configured payout address and four mining endpoints are allowed.
"""
import email.utils
import hmac
import json
import math
import secrets
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote


class NodeError(Exception):
    def __init__(self, status, message, retry=0):
        super().__init__(message)
        self.status, self.retry = status, max(0, retry)


def retry_seconds(value, now=None):
    """Honor both forms of Retry-After; never cap a server-requested delay."""
    try:
        number = float(value)
        if math.isfinite(number):
            return max(0.0, number)
    except (ValueError, TypeError):
        pass
    try:
        date = email.utils.parsedate_to_datetime(value)
        return max(0.0, date.timestamp() - (time.time() if now is None else now))
    except (ValueError, TypeError, AttributeError, OverflowError):
        return 0.0


class Coordinator:
    def __init__(self, node, address, stop, poll=3.0, timeout=12.0, log=print,
                 clock=time.monotonic, fetch=None):
        self.node, self.address, self.stop = node.rstrip('/'), address, stop
        self.poll, self.timeout, self.log, self.clock = poll, timeout, log, clock
        self._fetch_override = fetch
        self._state_lock = threading.Lock()
        self._template_lock = threading.Lock()
        self._read_lock = threading.Lock()
        self._submit_lock = threading.Lock()
        self._blocked_until = 0.0
        self._failures = 0
        self._next_template = 0.0
        self._template = None
        self._template_error = None
        self._reads = {}
        self._jobs = OrderedDict()
        self._last_submit = -1e9
        self._counts = Counter()
        # No environment proxy for a loopback/private node; explicit destination only.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _count(self, key):
        with self._state_lock:
            self._counts[key] += 1

    def remaining_backoff(self):
        with self._state_lock:
            return max(0.0, self._blocked_until - self.clock())

    def metrics(self):
        with self._state_lock:
            result = dict(self._counts)
            result['backoff_seconds'] = round(max(0.0, self._blocked_until - self.clock()), 1)
            result['template_interval_seconds'] = self.poll
            return result

    def _raw_fetch(self, path, payload):
        body = None if payload is None else json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(self.node + path, data=body, headers={
            'Content-Type': 'application/json', 'User-Agent': 'gnr-hiveos/1.2.0'})
        try:
            response = self._opener.open(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            data = response.read(262145)
            if len(data) > 262144:
                raise NodeError(502, 'Node response too large')
            try:
                value = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                value = {'error': 'Node returned non-JSON data'}
                if 200 <= response.code < 300:
                    raise NodeError(502, value['error'])
            return response.code, response.headers, value

    def _request(self, path, payload=None):
        if self.stop.is_set():
            raise NodeError(503, 'Miner stopping')
        remaining = self.remaining_backoff()
        if remaining > 0:
            self._count('backoff_local_replies')
            raise NodeError(429, 'Shared node backoff; no new upstream request', remaining)
        category = ('template_requests' if path.endswith('/template') else
                    'submit_requests' if path.endswith('/submit') else 'read_requests')
        self._count(category)
        try:
            code, headers, value = (self._fetch_override or self._raw_fetch)(path, payload)
        except (OSError, urllib.error.URLError, NodeError) as exc:
            with self._state_lock:
                self._failures += 1
                delay = min(60.0, 2.0 ** min(self._failures, 6))
                self._blocked_until = max(self._blocked_until, self.clock() + delay)
                self._counts['transport_errors'] += 1
            # Do not replay a submit after an ambiguous transport failure.
            raise NodeError(502, 'Node transport failure; submit not replayed: ' + str(exc), delay)
        if code == 429 or code >= 500:
            with self._state_lock:
                self._failures += 1
                delay = max(retry_seconds(headers.get('Retry-After')),
                            min(120.0, 2.0 ** min(self._failures + 1, 7)))
                self._blocked_until = max(self._blocked_until, self.clock() + delay)
                self._counts['upstream_429' if code == 429 else 'upstream_5xx'] += 1
            self.log('GNR RELAY | upstream HTTP %s: pause %.1fs for the whole rig' % (code, delay))
            raise NodeError(code, 'Upstream requested backoff', delay)
        if not 200 <= code < 300:
            message = value.get('error', 'Node refused request') if isinstance(value, dict) else 'Node refused request'
            raise NodeError(code, str(message))
        if not isinstance(value, dict):
            raise NodeError(502, 'Node JSON must be an object')
        with self._state_lock:
            self._failures = 0
        return value

    def template(self, address):
        if address != self.address:
            raise NodeError(403, 'Payout address differs from Flight Sheet')
        # One thread refreshes a shared template; the other 11 reuse it.
        with self._template_lock:
            now = self.clock()
            if self.remaining_backoff() > 0:
                raise NodeError(429, 'Shared node backoff', self.remaining_backoff())
            if now < self._next_template:
                if self._template is not None:
                    self._count('template_cache_hits')
                    return self._template
                err = self._template_error
                raise NodeError(err.status if err else 503,
                                str(err) if err else 'Waiting for fresh work',
                                max(self._next_template - now, err.retry if err else 0))
            # A failed refresh invalidates old work: never serve an expired cache.
            self._template = None
            self._next_template = now + self.poll
            try:
                value = self._request('/v1/mining/template', {'address': address})
                for key in ('job_id', 'height', 'pow_hash', 'share_difficulty', 'epoch', 'chain_seed'):
                    if key not in value:
                        raise NodeError(502, 'Missing work field: ' + key)
                if value.get('network', 'mainnet') != 'mainnet':
                    raise NodeError(502, 'Wrong mining network')
                job = value['job_id']
                if isinstance(job, bool) or not isinstance(job, int) or not 0 <= job < 2**64:
                    raise NodeError(502, 'Invalid job_id')
                self._template, self._template_error = value, None
                self._jobs[job] = True
                self._jobs.move_to_end(job)
                while len(self._jobs) > 256:
                    self._jobs.popitem(last=False)
                return value
            except NodeError as exc:
                self._template_error = exc
                self._next_template = max(self._next_template, self.clock() + min(30, max(2, exc.retry)))
                raise

    def read(self, path):
        if path not in ('/v1/info', '/v1/miner/' + quote(self.address, safe='')):
            raise NodeError(404, 'Endpoint disabled')
        with self._read_lock:
            now = self.clock()
            cached = self._reads.get(path)
            if cached and now < cached[0]:
                return cached[1]
            value = self._request(path)
            self._reads[path] = (self.clock() + 30, value)
            return value

    def submit(self, value):
        if not isinstance(value, dict) or set(value) != {'job_id', 'nonce'}:
            raise NodeError(400, 'Expected job_id and nonce only')
        if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < 2**64 for v in value.values()):
            raise NodeError(400, 'job_id and nonce must be unsigned integers')
        with self._template_lock:
            if value['job_id'] not in self._jobs:
                raise NodeError(400, 'Unknown local job')
        # Bounded wait stays below the official miner's 60-second HTTP timeout.
        deadline = self.clock() + 48
        if not self._submit_lock.acquire(timeout=5):
            raise NodeError(503, 'Submission queue busy; no acceptance claimed')
        try:
            for attempt in range(2):
                delay = max(self.remaining_backoff(), 0.1 - (self.clock() - self._last_submit))
                if delay > 0:
                    if self.clock() + delay + self.timeout >= deadline:
                        raise NodeError(429, 'Node backoff exceeds share retry window', delay)
                    if self.stop.wait(delay):
                        raise NodeError(503, 'Miner stopping')
                self._last_submit = self.clock()
                try:
                    result = self._request('/v1/mining/submit', value)
                except NodeError as exc:
                    # Only HTTP 429 is definitely rejected before validation by guard.rs.
                    if exc.status == 429 and attempt == 0:
                        continue
                    raise
                if result.get('accepted') is True:
                    self._count('accepted_shares')
                    if result.get('kind') == 'block':
                        self._count('accepted_blocks')
                        with self._template_lock:
                            self._template = None  # new tip, keep minimum request interval
                else:
                    self._count('rejected_shares')
                return result  # unchanged authoritative node response
            raise NodeError(503, 'Share not accepted')
        finally:
            self._submit_lock.release()


class Relay:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        token = secrets.token_hex(24)
        prefix = '/' + token
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def answer(self, code, value, retry=0):
                data = json.dumps(value, allow_nan=False).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Connection', 'close')
                if retry:
                    self.send_header('Retry-After', str(math.ceil(retry)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def handle_request(self, post):
                try:
                    parts = self.path.split('/', 2)
                    if len(parts) != 3 or not hmac.compare_digest(parts[1], token):
                        raise NodeError(404, 'Not found')
                    path = '/' + parts[2]
                    if post:
                        if self.headers.get('Transfer-Encoding'):
                            raise NodeError(400, 'Chunked requests disabled')
                        try:
                            length = int(self.headers.get('Content-Length', '0'))
                        except ValueError:
                            raise NodeError(400, 'Invalid body length')
                        if not 0 < length <= 16384:
                            raise NodeError(413, 'Invalid body size')
                        self.connection.settimeout(5)
                        try:
                            value = json.loads(self.rfile.read(length))
                        except (ValueError, UnicodeDecodeError):
                            raise NodeError(400, 'Invalid JSON')
                        if path == '/v1/mining/template':
                            if not isinstance(value, dict) or set(value) != {'address'}:
                                raise NodeError(400, 'Expected address only')
                            result = owner.coordinator.template(value['address'])
                        elif path == '/v1/mining/submit':
                            result = owner.coordinator.submit(value)
                        else:
                            raise NodeError(404, 'Endpoint disabled')
                    else:
                        result = owner.coordinator.read(path)
                    self.answer(200, result)
                except NodeError as exc:
                    self.answer(exc.status, {'error': str(exc)}, exc.retry)
                except Exception as exc:
                    owner.coordinator.log('GNR RELAY | local request error: ' + type(exc).__name__)
                    self.answer(500, {'error': 'Local relay error; no acceptance claimed'})

            def do_POST(self):
                self.handle_request(True)

            def do_GET(self):
                self.handle_request(False)

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            request_queue_size = 64

        self.server = Server(('127.0.0.1', 0), Handler)
        self.url = 'http://127.0.0.1:%d%s' % (self.server.server_address[1], prefix)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.1}, daemon=True)

    def start(self):
        self.thread.start()
        return self.url

    def close(self):
        if self.thread.is_alive():
            self.server.shutdown()
            self.thread.join(timeout=2)
        self.server.server_close()
