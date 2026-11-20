# SPDX-License-Identifier: MIT
"""Independent NULL proof validation. Never treats a GPU candidate as accepted work."""
import hashlib
import struct
from collections import defaultdict

PREFIX = b'nullPoW_'
BLOCK_PERSON = b'null_BlockHash__'
HEADER_LEN = 113
NONCE_LEN = 32


def params(n):
    if n not in (48, 96, 144):
        raise ValueError('unsupported reference parameters')
    return n // 6, 512 // n, (512 // n) * n // 8


def leaf(input_bytes, nonce, index, n=144):
    c, per, length = params(n)
    if len(nonce) != 32 or not 0 <= index < 1 << (c + 1):
        raise ValueError('invalid nonce or index')
    digest = hashlib.blake2b(input_bytes + nonce + struct.pack('<I', index // per),
                             digest_size=length, person=PREFIX + struct.pack('<II', n, 5)).digest()
    start = (index % per) * (n // 8)
    data = digest[start:start+n//8]
    return tuple(int.from_bytes(data[i*c//8:(i+1)*c//8], 'big') for i in range(6))


def pack(indices, n=144):
    c, _, _ = params(n)
    if len(indices) != 32:
        raise ValueError('32 indices required')
    out = 0
    for index in indices:
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < 1 << (c + 1):
            raise ValueError('index out of range')
        out = (out << (c + 1)) | index
    return out.to_bytes(32 * (c + 1) // 8, 'big')


def unpack(solution, n=144):
    c, _, _ = params(n)
    if len(solution) != 32 * (c + 1) // 8:
        raise ValueError('wrong solution length')
    value = int.from_bytes(solution, 'big')
    mask = (1 << (c + 1)) - 1
    return [(value >> ((31-i)*(c+1))) & mask for i in range(32)]


def verify(input_bytes, nonce, solution, n=144):
    try:
        indices = unpack(solution, n)
        if len(set(indices)) != 32:
            return False
        rows = [(leaf(input_bytes, nonce, index, n), (index,)) for index in indices]
        for _ in range(5):
            joined = []
            for i in range(0, len(rows), 2):
                ha, ia = rows[i]; hb, ib = rows[i+1]
                if ia[0] >= ib[0] or ha[0] != hb[0]:
                    return False
                joined.append((tuple(a ^ b for a, b in zip(ha[1:], hb[1:])), ia+ib))
            rows = joined
        return rows[0][0] == (0,)
    except (ValueError, TypeError, IndexError):
        return False


def block_hash(input_bytes, nonce, solution):
    if len(input_bytes) != 113 or len(nonce) != 32 or len(solution) != 100:
        raise ValueError('NULL mainnet needs 113-byte input, 32-byte nonce, 100-byte solution')
    return hashlib.blake2b(input_bytes + nonce + solution, digest_size=32, person=BLOCK_PERSON).digest()


def compact_target(bits):
    if not isinstance(bits, int) or bits < 0 or bits > 0xffffffff or bits & 0x800000:
        raise ValueError('invalid compact target')
    exponent, mantissa = bits >> 24, bits & 0x7fffff
    target = mantissa >> (8 * (3-exponent)) if exponent <= 3 else mantissa << (8*(exponent-3))
    if target <= 0 or target >= 1 << 256:
        raise ValueError('target outside uint256')
    return target


def header(version, prev, height, timestamp, commitment_root, tx_root, bits):
    if not 0 <= version <= 255 or not all(len(x) == 32 for x in (prev, commitment_root, tx_root)):
        raise ValueError('invalid header fields')
    compact_target(bits)
    return bytes([version]) + prev + struct.pack('<IQ', height, timestamp) + commitment_root + tx_root + struct.pack('<I', bits)


def tiny_solve(input_bytes, nonce):
    """Exhaustive (48,5) CPU oracle ONLY. Not a CPU mainnet fallback."""
    rows = [(leaf(input_bytes, nonce, i, 48), (i,)) for i in range(512)]
    for _ in range(5):
        buckets = defaultdict(list)
        for row in rows: buckets[row[0][0]].append(row)
        nxt = []
        for bucket in buckets.values():
            for i, (ha, ia) in enumerate(bucket):
                for hb, ib in bucket[i+1:]:
                    if set(ia).intersection(ib): continue
                    if ia[0] > ib[0]: a, b = ib, ia
                    else: a, b = ia, ib
                    nxt.append((tuple(x ^ y for x, y in zip(ha[1:], hb[1:])), a+b))
        rows = nxt
    return {pack(indices, 48) for h, indices in rows if h == (0,)}
