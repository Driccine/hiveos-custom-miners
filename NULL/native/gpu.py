# SPDX-License-Identifier: MIT
import ctypes as C
import hashlib
from pathlib import Path
import struct
import threading
import pow as proof

U8P = C.POINTER(C.c_uint8)
U32P = C.POINTER(C.c_uint32)
ERRLEN = 1024


class NativeStats(C.Structure):
    _fields_ = [('seconds', C.c_double), ('dropped', C.c_uint64),
                ('candidates', C.c_uint32), ('truncated', C.c_uint32),
                ('memory_bytes', C.c_uint64), ('stages_ms', C.c_double * 6)]


def buffer(data):
    return (C.c_uint8 * len(data)).from_buffer_copy(data)


def load(path=None):
    lib = C.CDLL(str(path or Path(__file__).with_name('libnullcuda.so')))
    lib.nn_abi.restype = C.c_int
    if lib.nn_abi() != 1: raise RuntimeError('Unknown CUDA ABI')
    lib.nn_create.argtypes = [C.c_int, C.c_int, C.c_uint, C.c_char_p, C.c_size_t]
    lib.nn_create.restype = C.c_void_p
    lib.nn_destroy.argtypes = [C.c_void_p]; lib.nn_destroy.restype = None
    lib.nn_cancel.argtypes = [C.c_void_p]; lib.nn_cancel.restype = None
    lib.nn_solve.argtypes = [C.c_void_p, U8P, U8P, U32P, C.c_uint,
                             C.POINTER(NativeStats), C.c_char_p, C.c_size_t]
    lib.nn_solve.restype = C.c_int
    lib.nn_device_count.argtypes = [C.c_char_p, C.c_size_t]; lib.nn_device_count.restype = C.c_int
    lib.nn_hash_host.argtypes = [U8P, U8P, C.c_int, C.c_uint, U8P]
    lib.nn_hash_host.restype = C.c_int
    lib.nn_hash_gpu.argtypes = [C.c_int, U8P, U8P, C.c_int, C.c_uint, U8P, C.c_char_p, C.c_size_t]
    lib.nn_hash_gpu.restype = C.c_int
    return lib


class Solver:
    def __init__(self, device, n=144, slots=64, lib=None):
        self.lib = lib or load(); self.n = n; self.device = device
        self.lock = threading.Lock(); self.ptr = None
        err = C.create_string_buffer(ERRLEN)
        self.ptr = self.lib.nn_create(device, n, slots, err, ERRLEN)
        if not self.ptr: raise RuntimeError(err.value.decode(errors='replace'))

    def close(self):
        with self.lock:
            if self.ptr:
                self.lib.nn_destroy(self.ptr); self.ptr = None

    def cancel(self):
        # Caller owns lifecycle: do not call after close.
        if self.ptr: self.lib.nn_cancel(self.ptr)

    def solve(self, input_bytes, nonce):
        if len(input_bytes) != 113 or len(nonce) != 32:
            raise ValueError('wrong input/nonce length')
        with self.lock:
            if not self.ptr: raise RuntimeError('solver closed')
            indices = (C.c_uint32 * (256*32))(); stats = NativeStats()
            err = C.create_string_buffer(ERRLEN)
            rc = self.lib.nn_solve(self.ptr, buffer(input_bytes), buffer(nonce), indices,
                                   256, C.byref(stats), err, ERRLEN)
            if rc < 0: raise RuntimeError(err.value.decode(errors='replace'))
            meta = {key: getattr(stats,key) for key in ('seconds','dropped','candidates','truncated','memory_bytes')}
            meta['stages_ms'] = list(stats.stages_ms); meta['cancelled'] = rc == 1
            if rc == 1: return [], meta
            valid = set()
            for i in range(stats.candidates):
                solution = proof.pack(list(indices[i*32:(i+1)*32]), self.n)
                if proof.verify(input_bytes, nonce, solution, self.n): valid.add(solution)
            meta['filtered_candidates'] = stats.candidates - len(valid)
            return sorted(valid), meta

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


def selftest(device, lib=None):
    """Required before benchmarking/mining; fails rather than silently using CPU."""
    lib = lib or load()
    h = bytes(range(113)); nonce = bytes(range(32)); count = 32
    for n in (48,144):
        out = (C.c_uint8 * (64*count))(); err = C.create_string_buffer(ERRLEN)
        rc = lib.nn_hash_gpu(device, buffer(h), buffer(nonce), n, count, out, err, ERRLEN)
        if rc: raise RuntimeError('GPU hash self-test: ' + err.value.decode(errors='replace'))
        length = (512//n)*n//8
        for group in range(count):
            expected = hashlib.blake2b(h+nonce+struct.pack('<I',group),digest_size=length,
                                        person=proof.PREFIX+struct.pack('<II',n,5)).digest()
            if bytes(out[group*64:group*64+length]) != expected:
                raise RuntimeError('GPU BLAKE2b mismatch for n=%d group=%d' % (n,group))
    total = 0
    with Solver(device, n=48, lib=lib) as solver:
        for value in range(1,5):
            header = bytes(113); nonce = bytes([value])*32
            expected = proof.tiny_solve(header,nonce)
            got, meta = solver.solve(header,nonce)
            if meta['dropped'] or meta['truncated'] or set(got) != expected:
                raise RuntimeError('CUDA collision/reconstruction self-test failed')
            total += len(got)
    if not total: raise RuntimeError('Self-test produced no positive proof')
    return {'device':device,'hash_vectors':64,'tiny_solutions':total,'passed':True}
