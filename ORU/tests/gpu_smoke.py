#!/usr/bin/env python3
"""CUDA smoke test, run on the real NVIDIA rig after building the native miner."""
import argparse
import hashlib
import pathlib
import subprocess
import sys

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
from rgrpow import digest_header

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bin",default="./ORU/oru-cuda")
    parser.add_argument("--device",type=int,default=0)
    args=parser.parse_args()
    binary=str(pathlib.Path(args.bin).resolve())
    header=bytes(76)+b"\0"*4
    def launch(target,start,count):
        r=subprocess.run([binary,"--header",header.hex(),"--target",target,
             "--start",str(start),"--count",str(count),"--device",str(args.device)],
             capture_output=True,text=True,check=True,timeout=120)
        return r.stdout.strip()
    result=launch("ff"*32,123,256)
    print("All-accept CUDA test:",result)
    parts=result.split()
    if len(parts)!=3 or parts[0]!="FOUND":raise RuntimeError("CUDA must return FOUND")
    nonce=int(parts[1])
    if not 123 <= nonce < 379:raise RuntimeError("returned nonce outside tested interval")
    computed=digest_header(header[:76]+nonce.to_bytes(4,"little"))
    expected=hashlib.sha3_256(b"RGRPOW01"+header[:76]+nonce.to_bytes(4,"little")).digest()
    if computed!=expected:raise RuntimeError("CUDA test nonce failed CPU verification")
    result=launch("00"*32,0,1024)
    print("No-accept CUDA test:",result)
    if result!="NONE 1024":raise RuntimeError("CUDA rejected-target test failed")
    print("CUDA smoke tests passed on device",args.device)
    print("NOTE: this checks candidate handling, NOT GPU SHA3 digests for arbitrary nonces.")

if __name__=="__main__":
    main()
