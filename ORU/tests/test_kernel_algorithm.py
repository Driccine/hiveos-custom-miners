"""CPU simulation of the CUDA Keccak round schedule against independent hashlib.
This does not replace compilation or an actual NVIDIA device test.
"""
import hashlib
import pathlib
import random
import re
import unittest

SOURCE=(pathlib.Path(__file__).resolve().parents[1]/"src"/"cuda"/"oru_cuda.cu").read_text()
MASK=(1<<64)-1

def values(symbol):
    match=re.search(r"\b"+re.escape(symbol)+r"\[24\]\s*=\s*\{([^}]+)\}",SOURCE,re.S)
    if not match:
        raise ValueError("CUDA constant missing: "+symbol)
    tokens=[x.strip().replace("ULL","").replace("U","") for x in match.group(1).split(",") if x.strip()]
    a=[int(v,0) for v in tokens]
    if len(a)!=24:
        raise ValueError("bad CUDA constant array length: "+symbol)
    return a

RC=values("d_rc")
ROT=values("d_rotation")
PI=values("d_pi")

def rol(x,n):
    return ((x<<n)|(x>>(64-n)))&MASK

def simulate_cuda_digest(header):
    if len(header)!=80:raise ValueError("need 80-byte header")
    buf=b"RGRPOW01"+header
    a=[0]*25
    for i in range(11):
        a[i]=int.from_bytes(buf[i*8:i*8+8],"little")
    a[11]^=0x06
    a[16]^=0x8000000000000000
    for rc in RC:
        bc=[a[x]^a[x+5]^a[x+10]^a[x+15]^a[x+20] for x in range(5)]
        for x in range(5):
            t=bc[(x+4)%5]^rol(bc[(x+1)%5],1)
            for y in range(0,25,5):a[y+x]^=t
        last=a[1]
        for idx,rotation in zip(PI,ROT):
            tmp=a[idx]
            a[idx]=rol(last,rotation)
            last=tmp
        for y in range(0,25,5):
            bc=a[y:y+5]
            for x in range(5):
                a[y+x]^=(~bc[(x+1)%5])&bc[(x+2)%5]
                a[y+x]&=MASK
        a[0]^=rc
    return b"".join(x.to_bytes(8,"little") for x in a[:4])

class KernelAlgorithmTests(unittest.TestCase):
    def test_constants_have_correct_length(self):
        self.assertEqual(len(RC),24)
        self.assertEqual(len(ROT),24)
        self.assertEqual(len(PI),24)
    def test_known_headers(self):
        for nonce in (0,1,123456,0xffffffff):
            header=bytes(range(76))+nonce.to_bytes(4,"little")
            expected=hashlib.sha3_256(b"RGRPOW01"+header).digest()
            self.assertEqual(simulate_cuda_digest(header),expected,nonce)
    def test_random_headers(self):
        rng=random.Random(1234)
        for _ in range(20):
            header=rng.randbytes(80)
            self.assertEqual(simulate_cuda_digest(header),hashlib.sha3_256(b"RGRPOW01"+header).digest())

if __name__=="__main__":
    unittest.main()
