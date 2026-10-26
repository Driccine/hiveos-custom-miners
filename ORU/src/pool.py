#!/usr/bin/env python3
"""Independent ORU Stratum V1 pool client using our own CUDA RGRPOW01 kernel.

Experimental adapter. A successful TCP connection does not imply the pool will
accept the coinbase/header layout or share-difficulty convention.
No copied paid miner, dev fee, private keys, or RPC node dependency.
"""
import argparse
import hashlib
import json
import os
import queue
import socket
import ssl
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from urllib.parse import urlsplit

from rgrpow import digest_header, scan_nonces
from solo import bech32_decode_v0

# Conventional Bitcoin Stratum V1 diff1 (nBits 0x1d00ffff).
# A pool may choose an ORU-specific scale; use --diff1-target to override.
BITCOIN_DIFF1 = 0x00ffff << 208
MAX_NONCE = 0xffffffff
MAX_MESSAGE = 512 * 1024


def pool_endpoint(url):
    parts = urlsplit(url)
    if parts.scheme not in ("stratum+tcp", "stratum+ssl"):
        raise ValueError(
            "POOL mode requires stratum+tcp://host:port or stratum+ssl://host:port; "
            "https://.../rpc (such as GoZero) uses a different, unimplemented pool API"
        )
    if parts.path not in ("", "/") or parts.query or parts.fragment or not parts.hostname or not parts.port:
        raise ValueError("invalid Stratum endpoint: provide host:port only")
    return parts.hostname, parts.port, parts.scheme == "stratum+ssl"


def parse_target_hex(target):
    if not isinstance(target, str) or len(target) != 64:
        raise ValueError("target must be 64 hex characters")
    out = int(target, 16)
    if not 0 < out < 1 << 256:
        raise ValueError("target out of range")
    return out


def difficulty_target(difficulty, diff1=BITCOIN_DIFF1):
    try:
        d = Decimal(str(difficulty))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid pool difficulty") from exc
    if not d.is_finite() or d <= 0:
        raise ValueError("invalid pool difficulty")
    with localcontext() as context:
        context.prec = 90
        return max(1, min((1 << 256) - 1, int(Decimal(diff1) / d)))


def swap_words(prevhash):
    """Typical Stratum prevhash word order to canonical 32-byte LE header data."""
    b = bytes.fromhex(prevhash)
    if len(b) != 32:
        raise ValueError("prevhash must be 32 bytes")
    return b"".join(b[i:i+4][::-1] for i in range(0, 32, 4))


@dataclass(frozen=True)
class Job:
    identifier: str
    prev_hash: str
    coinbase1: str
    coinbase2: str
    branches: tuple
    version: str
    bits: str
    ntime: str
    clean: bool

    @classmethod
    def from_notify(cls, args):
        if not isinstance(args, list) or len(args) != 9:
            raise ValueError("expected 9-field Bitcoin Stratum V1 mining.notify")
        jid, prev, cb1, cb2, branches, version, bits, stamp, clean = args
        if not isinstance(jid, str) or len(jid) > 160:
            raise ValueError("invalid Stratum job ID")
        if not isinstance(branches, list) or len(branches) > 512:
            raise ValueError("invalid merkle branches")
        for x, n in [(prev, 32), (version, 4), (bits, 4), (stamp, 4)]:
            if not isinstance(x, str) or len(x) != n * 2:
                raise ValueError("incorrect Stratum header field size")
            bytes.fromhex(x)
        if any(not isinstance(x, str) or len(x) != 64 for x in branches):
            raise ValueError("invalid merkle branch length")
        for b in branches: bytes.fromhex(b)
        for s in (cb1, cb2):
            if not isinstance(s, str) or len(s) > 20000 or len(s) % 2:
                raise ValueError("invalid coinbase part")
            bytes.fromhex(s)
        if not isinstance(clean, bool):
            raise ValueError("invalid clean_jobs flag")
        return cls(jid, prev, cb1, cb2, tuple(branches), version, bits, stamp, clean)


def build_header(job, extranonce1, extranonce2, prevhash_mode="swap-words"):
    coinbase = (bytes.fromhex(job.coinbase1) + extranonce1 + extranonce2 +
                bytes.fromhex(job.coinbase2))
    merkle = hashlib.sha256(hashlib.sha256(coinbase).digest()).digest()
    for raw in job.branches:
        branch = bytes.fromhex(raw)
        merkle = hashlib.sha256(hashlib.sha256(merkle + branch).digest()).digest()
    prev = bytes.fromhex(job.prev_hash)
    if prevhash_mode == "swap-words":
        prev = swap_words(job.prev_hash)
    elif prevhash_mode == "reverse":
        prev = prev[::-1]
    elif prevhash_mode != "raw":
        raise ValueError("unknown prevhash byte order")
    header = (bytes.fromhex(job.version)[::-1] + prev + merkle +
              bytes.fromhex(job.ntime)[::-1] + bytes.fromhex(job.bits)[::-1] + bytes(4))
    if len(header) != 80:
        raise AssertionError("wrong canonical header length")
    return header


def gpu_search(binary, header, target, nonce_start, count, device, timeout=120):
    cmd = [binary, "--header", header.hex(), "--target", f"{target:064x}",
           "--start", str(nonce_start), "--count", str(count), "--device", str(device)]
    run = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
    words = run.stdout.strip().split()
    if words == ["NONE", str(count)]:
        return None
    if len(words) == 3 and words[0] == "FOUND":
        nonce = int(words[1])
        if not 0 <= nonce <= MAX_NONCE:
            raise ValueError("invalid CUDA nonce")
        if int.from_bytes(digest_header(header[:76] + nonce.to_bytes(4, "little")), "little") > target:
            raise ValueError("CUDA share FAILED independent CPU verification")
        return nonce
    raise ValueError("unexpected CUDA response " + run.stdout[:150])


def try_work(binary, header, target, start, count, devices, cpu=False):
    if cpu:
        found = scan_nonces(header, f"{target:064x}", start, min(count, 100000))
        return [found.nonce] if found else [], min(count, 100000)
    candidates = []
    with ThreadPoolExecutor(max_workers=len(devices)) as pool:
        futures = [pool.submit(gpu_search, binary, header, target,
                               (start + i * count) & MAX_NONCE, count, gpu)
                   for i, gpu in enumerate(devices)]
        for future in futures:
            n = future.result()
            if n is not None:
                candidates.append(n)
    return candidates, count * len(devices)


class PoolConnection:
    def __init__(self, endpoint):
        host, port, use_tls = pool_endpoint(endpoint)
        self.host, self.port, self.use_tls = host, port, use_tls
        self.sock = None
        self.inbox = queue.Queue()
        self.identifier = 10
        self.sendlock = threading.Lock()

    def connect(self):
        s = socket.create_connection((self.host, self.port), timeout=15)
        if self.use_tls:
            s = ssl.create_default_context().wrap_socket(s, server_hostname=self.host)
        s.settimeout(None)
        self.sock = s
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buffer = bytearray()
        try:
            while True:
                raw = self.sock.recv(4096)
                if not raw:
                    raise EOFError("Pool disconnected")
                buffer.extend(raw)
                if len(buffer) > MAX_MESSAGE:
                    raise ValueError("Stratum message too long")
                while b"\n" in buffer:
                    line, _, trailing = buffer.partition(b"\n")
                    buffer = bytearray(trailing)
                    if line.strip():
                        message = json.loads(line)
                        if not isinstance(message, dict):
                            raise ValueError("invalid pool JSON message")
                        self.inbox.put(message)
        except (OSError, ValueError, EOFError) as exc:
            self.inbox.put({"__disconnected": str(exc)})

    def send(self, method, params, identifier=None):
        if identifier is None:
            self.identifier += 1
            identifier = self.identifier
        message = {"id": identifier, "method": method, "params": params}
        with self.sendlock:
            self.sock.sendall((json.dumps(message, separators=(",", ":")) + "\n").encode())
        return identifier

    def close(self):
        if self.sock:
            try: self.sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            self.sock.close()


class Miner:
    def __init__(self, args):
        self.args = args
        self.diff1 = parse_target_hex(args.diff1_target)
        self.wallet = args.wallet
        bech32_decode_v0(args.wallet)  # validate actual wallet checksum
        self.user = args.wallet + ("." + args.worker if args.worker else "")
        self.connection = None
        self.ex1 = None
        self.ex2_size = None
        self.ex2_counter = 0
        self.target = None
        self.next_target = None
        self.job = None
        self.accepted = 0
        self.rejected = 0
        self.pending = {}
        self.started = time.monotonic()
        self.scanned = 0

    def process(self, msg):
        if "__disconnected" in msg:
            raise ConnectionError(msg["__disconnected"])
        if msg.get("id") == 1:
            result = msg.get("result")
            if msg.get("error") or not isinstance(result, list) or len(result) < 3:
                raise RuntimeError("pool rejected subscribe: " + repr(msg.get("error")))
            self.ex1 = bytes.fromhex(result[1])
            self.ex2_size = int(result[2])
            if not 1 <= self.ex2_size <= 16:
                raise ValueError("invalid Stratum extranonce2 size")
            print(f"POOL subscribed, extranonce2_size={self.ex2_size}", flush=True)
        elif msg.get("id") == 2:
            if msg.get("error") or msg.get("result") is not True:
                raise RuntimeError("pool rejected wallet/worker authorization: " + repr(msg.get("error")))
            print("POOL authorization OK", flush=True)
        elif msg.get("id") in self.pending:
            request = self.pending.pop(msg["id"])
            if msg.get("result") is True and not msg.get("error"):
                self.accepted += 1
                print(f"POOL share accepted job={request} accepted={self.accepted} rejected={self.rejected}", flush=True)
            else:
                self.rejected += 1
                print(f"POOL share REJECTED job={request} error={msg.get('error')} accepted={self.accepted} rejected={self.rejected}", flush=True)
        if msg.get("method") == "mining.set_difficulty":
            params = msg.get("params")
            if not isinstance(params, list) or len(params) != 1:
                raise ValueError("invalid pool difficulty response")
            self.next_target = difficulty_target(params[0], self.diff1)
            print(f"POOL difficulty={params[0]} pending next job", flush=True)
        elif msg.get("method") == "mining.set_target":
            params = msg.get("params")
            if not isinstance(params, list) or len(params) != 1:
                raise ValueError("invalid pool target response")
            self.next_target = parse_target_hex(params[0])
            print(f"POOL explicit share target={params[0][:12]}...", flush=True)
        elif msg.get("method") == "mining.set_extranonce":
            params = msg.get("params")
            if not isinstance(params, list) or len(params) != 2:
                raise ValueError("invalid pool extranonce response")
            self.ex1 = bytes.fromhex(params[0])
            self.ex2_size = int(params[1])
            if not 1 <= self.ex2_size <= 16:
                raise ValueError("invalid extranonce2 size")
            self.ex2_counter = 0
            self.job = None
        elif msg.get("method") == "mining.notify":
            if self.ex1 is None or self.ex2_size is None:
                raise ValueError("received job before subscription completed")
            job = Job.from_notify(msg.get("params"))
            self.job = job
            if self.next_target is not None:
                self.target = self.next_target
            if self.target is None:
                raise ValueError("pool did not provide share difficulty or target before mining.notify")
            if job.clean:
                self.ex2_counter = 0
                self.pending.clear()
            print(f"POOL new job={job.identifier} clean={job.clean} target={self.target:064x}", flush=True)

    def listen(self, wait=0):
        if wait:
            try: self.process(self.connection.inbox.get(timeout=wait))
            except queue.Empty: return
        while True:
            try: msg = self.connection.inbox.get_nowait()
            except queue.Empty: break
            self.process(msg)

    def run_connection(self):
        self.ex1 = self.ex2_size = self.job = self.target = self.next_target = None
        self.pending.clear()
        self.connection = PoolConnection(self.args.pool)
        self.connection.connect()
        self.connection.send("mining.subscribe", ["oru-native/0.2.0-alpha"], identifier=1)
        self.connection.send("mining.authorize", [self.user, self.args.password], identifier=2)
        started_wait = time.monotonic()
        try:
            while self.ex1 is None or self.job is None:
                self.listen(wait=1)
                if time.monotonic() - started_wait > 45:
                    raise TimeoutError("no pool subscription/job in 45 seconds")
            start = 0
            while True:
                self.listen()
                job = self.job
                if job is None or self.target is None: self.listen(wait=0.1); continue
                extra = self.ex2_counter.to_bytes(self.ex2_size, "little")
                self.ex2_counter = (self.ex2_counter + 1) % (1 << (8 * self.ex2_size))
                header = build_header(job, self.ex1, extra, self.args.prevhash_mode)
                round_start = time.monotonic()
                tried = 0
                # Periodic extranonce2 refresh limits stales from pending new work.
                while time.monotonic() - round_start < self.args.refresh_seconds and tried < (1 << 32):
                    self.listen()
                    if self.job is not job or self.target is None:
                        break
                    count = min(self.args.chunk, (1 << 32) // len(self.args.devices))
                    candidates, attempts = try_work(self.args.cuda_bin, header, self.target,
                                                     start, count, self.args.devices, self.args.cpu)
                    for nonce in candidates:
                        digest = digest_header(header[:76] + nonce.to_bytes(4,"little"))
                        if int.from_bytes(digest,"little") > self.target:
                            raise ValueError("share validation failed")
                        nonce_hex = nonce.to_bytes(4,"little").hex()
                        request_id = self.connection.send(
                            "mining.submit",
                            [self.user, job.identifier, extra.hex(), job.ntime, nonce_hex],
                        )
                        self.pending[request_id] = job.identifier
                        print(f"POOL share submitted job={job.identifier} nonce={nonce_hex}", flush=True)
                    start = (start + attempts) & MAX_NONCE
                    tried += attempts
                    self.scanned += attempts
                    elapsed = max(time.monotonic() - self.started, 0.001)
                    if int(elapsed) % 10 == 0 and attempts:
                        print(f"avg_hs={self.scanned / elapsed:.0f} accepted={self.accepted} rejected={self.rejected}", flush=True)
                if not self.args.cpu:
                    time.sleep(0.02)
        finally:
            self.connection.close()

    def run(self):
        if not self.args.cpu and not os.path.isfile(self.args.cuda_bin):
            raise FileNotFoundError(f"CUDA executable not found: {self.args.cuda_bin}")
        while True:
            try: self.run_connection()
            except KeyboardInterrupt: raise
            except Exception as exc:
                print(f"POOL disconnected/error: {exc}; reconnecting", file=sys.stderr, flush=True)
                time.sleep(5)


def main():
    p=argparse.ArgumentParser(description="ORU original CUDA Stratum V1 pool miner (experimental)")
    p.add_argument("--pool",default=os.environ.get("ORU_POOL_URL", "stratum+tcp://rgr.ariabrain.com:3356"))
    p.add_argument("--wallet",default=os.environ.get("ORU_WALLET",""))
    p.add_argument("--worker",default=os.environ.get("ORU_WORKER","rig1"))
    p.add_argument("--password",default=os.environ.get("ORU_POOL_PASSWORD","x"))
    p.add_argument("--devices",type=lambda s:[int(x) for x in s.split(",")],default=[0])
    p.add_argument("--cuda-bin",default=os.environ.get("ORU_CUDA_BIN","./oru-cuda"))
    p.add_argument("--cpu",action="store_true",help="Slow independent CPU debug")
    p.add_argument("--chunk",type=int,default=262144)
    p.add_argument("--refresh-seconds",type=float,default=5.0)
    p.add_argument("--prevhash-mode",choices=("swap-words","reverse","raw"),default="swap-words")
    p.add_argument("--diff1-target",default=f"{BITCOIN_DIFF1:064x}",
                   help="Stratum diff1 numeric target hex; verify ORU pool convention")
    a=p.parse_args()
    if not a.wallet:p.error("wallet required")
    if not a.worker or len(a.worker) > 32 or any(x not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-." for x in a.worker):
        p.error("invalid worker name")
    if not a.devices or any(x<0 for x in a.devices) or len(set(a.devices))!=len(a.devices):
        p.error("invalid devices")
    if a.chunk<1 or a.chunk>0x1000000 or a.chunk*len(a.devices)>(1<<32) or a.refresh_seconds<=0:
        p.error("invalid chunk or refresh_seconds")
    try:
        pool_endpoint(a.pool)
        Miner(a).run()
    except KeyboardInterrupt:
        print("ORU pool stopped.",flush=True)
    except Exception as exc:
        print(f"ORU pool fatal: {exc}",file=sys.stderr,flush=True)
        raise SystemExit(2)

if __name__=="__main__": main()
