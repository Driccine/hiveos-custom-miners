#!/usr/bin/env python3
"""ORU SOLO coordinator: standard-library JSON-RPC, canonical GBT and our CUDA/CPU engine.
No commercial miner code. No pool/Stratum support in this release.
"""
import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from rgrpow import digest_header, scan_nonces

EXPECTED_GENESIS = "e2ce92cfef740f92e8cc84a8541d8e760c776c668afd9b61740b3a4315241468"
BECH32_CHARS = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def sha256d(b):
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()

def compact_size(n):
    if n < 0:
        raise ValueError("negative count")
    if n < 253:
        return bytes([n])
    if n <= 65535:
        return b"\xfd" + n.to_bytes(2,"little")
    if n <= 0xffffffff:
        return b"\xfe" + n.to_bytes(4,"little")
    return b"\xff" + n.to_bytes(8,"little")

def read_compact(b, p):
    if p >= len(b):
        raise ValueError("short varint")
    flag = b[p]; p += 1
    nbytes = (0 if flag < 253 else {253: 2,254: 4,255: 8}[flag])
    if p + nbytes > len(b):
        raise ValueError("short varint value")
    n = flag if not nbytes else int.from_bytes(b[p:p+nbytes],"little")
    if (flag == 253 and n < 253) or (flag == 254 and n <= 65535) or (flag == 255 and n <= 0xffffffff):
        raise ValueError("nonminimal varint")
    return n,p+nbytes

def bech32_polymod(values):
    chk=1
    for v in values:
        top=chk>>25
        chk=((chk&0x1ffffff)<<5)^v
        for i,g in enumerate((0x3b6a57b2,0x26508e6d,0x1ea119fa,0x3d4233dd,0x2a1462b3)):
            if (top>>i)&1: chk^=g
    return chk

def bech32_decode_v0(addr):
    if not addr or addr != addr.lower() or not addr.startswith("rg1q"):
        raise ValueError("mainnet ORU address must begin rg1q, lowercase")
    sep=addr.rfind("1")
    hrp=addr[:sep]; rest=addr[sep+1:]
    if hrp != "rg" or len(rest)<7 or any(c not in BECH32_CHARS for c in rest):
        raise ValueError("bad bech32 address")
    values=[BECH32_CHARS.index(c) for c in rest]
    expanded=[ord(c)>>5 for c in hrp]+[0]+[ord(c)&31 for c in hrp]
    if bech32_polymod(expanded+values) != 1 or values[0]!=0:
        raise ValueError("bad ORU Bech32 checksum or witness version")
    data=values[1:-6]; acc=0;bits=0;out=[]
    for v in data:
        acc=(acc<<5)|v;bits+=5
        if bits>=8:
            bits-=8;out.append((acc>>bits)&255)
    if bits>=5 or ((acc<< (8-bits))&255):
        raise ValueError("bad bech32 padding")
    if len(out)!=20: raise ValueError("expected v0 P2WPKH with 20-byte program")
    return b"\x00\x14"+bytes(out)

def coinbase_txid_and_payout(tx):
    """Validate and strip BIP141 witness WITHOUT rewriting the wire transaction."""
    if len(tx)<64 or tx[4:6]!=b"\x00\x01":
        raise ValueError("GBT coinbase must use canonical witness serialization")
    p=6
    ins,p=read_compact(tx,p)
    if ins!=1: raise ValueError("coinbase must have one input")
    if p+36>len(tx) or tx[p:p+32]!=bytes(32) or tx[p+32:p+36]!=b"\xff"*4:
        raise ValueError("coinbase prevout invalid")
    p+=36
    slen,p=read_compact(tx,p)
    if slen>100 or p+slen+4>len(tx):
        raise ValueError("coinbase scriptSig invalid")
    sig=tx[p:p+slen];p+=slen
    if tx[p:p+4]!=b"\xff"*4: raise ValueError("coinbase sequence invalid")
    p+=4
    outs,p=read_compact(tx,p)
    if outs<2 or outs>8: raise ValueError("coinbase outputs invalid")
    payout_value=None;payout_script=None
    for i in range(outs):
        if p+8>len(tx):raise ValueError("coinbase value truncated")
        value=int.from_bytes(tx[p:p+8],"little");p+=8
        size,p=read_compact(tx,p)
        if size>256 or p+size>len(tx):raise ValueError("coinbase script truncated")
        spk=tx[p:p+size];p+=size
        if i==0: payout_value=value;payout_script=spk
    pre_witness_end=p
    for _ in range(ins):
        items,p=read_compact(tx,p)
        if items>4:raise ValueError("witness item count invalid")
        for _ in range(items):
            sz,p=read_compact(tx,p)
            if sz>256 or p+sz>len(tx):raise ValueError("witness oversized")
            p+=sz
    if p+4!=len(tx):raise ValueError("coinbase locktime/trailing bytes invalid")
    txid=sha256d(tx[:4]+tx[6:pre_witness_end]+tx[-4:])
    return txid,sig,payout_value,payout_script

def bits_target(bits):
    n=int(bits,16)
    if n<0 or n>0xffffffff or n&0x00800000:
        raise ValueError("negative/invalid difficulty bits")
    size=n>>24;mantissa=n&0x007fffff
    target=(mantissa>>(8*(3-size))) if size<=3 else (mantissa<<(8*(size-3)))
    if not 0<target<(1<<256):raise ValueError("difficulty target out of range")
    return target

def merkle_from_leaves(leaves):
    if not leaves:raise ValueError("empty merkle leaves")
    while len(leaves)>1:
        if len(leaves)&1:leaves=leaves+[leaves[-1]]
        leaves=[sha256d(leaves[i]+leaves[i+1]) for i in range(0,len(leaves),2)]
    return leaves[0]

def prepare_work(tmpl, wallet):
    """Return (80-byte header, BE target hex, exact tx bytes).
    Fail closed if GBT immutable coinbase, subsidy payout, or merkle proof disagree.
    """
    if tmpl.get("rigor_coinbase_immutable") is not True:
        raise ValueError("node did not mark coinbase immutable")
    for forbidden in ("default_res_mint","paid_winner_txid","convergence_root"):
        if tmpl.get(forbidden) is not None: raise ValueError("retired field "+forbidden)
    if not isinstance(tmpl.get("height"),int) or tmpl["height"]<1:
        raise ValueError("invalid block height")
    coinbase=bytes.fromhex(tmpl["default_coinbase_tx"])
    txid,sig,value,spk=coinbase_txid_and_payout(coinbase)
    if sig.hex()!=tmpl["default_coinbase_scriptsig"].lower():
        raise ValueError("coinbase scriptSig mismatch")
    if spk!=bech32_decode_v0(wallet):
        raise ValueError("coinbase does not pay YOUR address; refusing to mine")
    if value != int(tmpl["coinbasevalue"]):
        raise ValueError("coinbase payment amount differs from template")
    if txid[::-1].hex()!=tmpl["default_coinbase_txid"].lower():
        raise ValueError("coinbase txid incorrect")
    txs=[bytes.fromhex(tx["data"]) for tx in tmpl["transactions"]]
    leaves=[txid]+[bytes.fromhex(tx["txid"])[::-1] for tx in tmpl["transactions"]]
    merkle=merkle_from_leaves(leaves)
    if merkle[::-1].hex()!=tmpl["merkleroot"].lower():
        raise ValueError("template merkle root mismatch")
    target=bits_target(tmpl["bits"])
    if int(tmpl["target"],16)!=target:
        raise ValueError("bits/target mismatch")
    version=int(tmpl["version"])
    stamp=int(tmpl["curtime"])
    if version<0 or version>0xffffffff or stamp<0 or stamp>0xffffffff:
        raise ValueError("header fields out of range")
    header=(version.to_bytes(4,"little")+
            bytes.fromhex(tmpl["previousblockhash"])[::-1]+
            merkle+stamp.to_bytes(4,"little")+
            int(tmpl["bits"],16).to_bytes(4,"little")+
            b"\x00"*4)
    if len(header)!=80: raise ValueError("wrong header length")
    return header, f"{target:064x}", [coinbase]+txs

class RPC:
    def __init__(self,url,user,password,timeout=20):
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("RPC URL must be HTTP(S)")
        self.url=url;self.user=user;self.password=password;self.timeout=timeout
    def call(self,method,params=None):
        body=json.dumps({"jsonrpc":"1.0","id":"oru-native","method":method,"params":params or []}).encode()
        auth=base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        req=urllib.request.Request(self.url,body,{"Content-Type":"application/json","Authorization":"Basic "+auth})
        with urllib.request.urlopen(req,timeout=self.timeout) as response:
            msg=json.load(response)
        if msg.get("error") is not None:raise RuntimeError(str(msg["error"]))
        return msg["result"]

def confirm_mainnet(rpc):
    info=rpc.call("getblockchaininfo")
    if info.get("chain")!="main":raise RuntimeError("not mainnet")
    if rpc.call("getblockhash",[0]).lower()!=EXPECTED_GENESIS:
        raise RuntimeError("incorrect RIGOR genesis; do not mine")
    if rpc.call("getconnectioncount")<1:raise RuntimeError("node has no peers")
    if info.get("initialblockdownload") is True:raise RuntimeError("node syncing; mining suspended")
    return info

def scan_gpu(binary,header,target,start,count,device):
    cmd=[binary,"--header",header.hex(),"--target",target,"--start",str(start),
         "--count",str(count),"--device",str(device)]
    proc=subprocess.run(cmd,capture_output=True,text=True,check=True,timeout=120)
    words=proc.stdout.strip().split()
    if not words:raise ValueError("GPU miner returned empty output")
    if words[0]=="NONE" and len(words)==2:return None
    if words[0]=="FOUND" and len(words)==3:
        nonce=int(words[1])
        if not 0<=nonce<=0xffffffff:raise ValueError("invalid nonce returned by CUDA")
        digest=digest_header(header[:76]+nonce.to_bytes(4,"little"))
        if int.from_bytes(digest,"little")>int(target,16):
            raise ValueError("CUDA candidate FAILED independent CPU SHA3 validation")
        return nonce
    raise ValueError("unexpected GPU output: "+proc.stdout[:200])

def mine_round(header,target,start,devices,binary,chunk,use_cpu):
    if use_cpu:
        found=scan_nonces(header,target,start,min(chunk,100000))
        return found.nonce if found else None, min(chunk,100000)
    with ThreadPoolExecutor(max_workers=len(devices)) as pool:
        futures=[pool.submit(scan_gpu,binary,header,target,
                   (start+i*chunk)&0xffffffff,chunk,device) for i,device in enumerate(devices)]
        results=[f.result() for f in futures]
    return next((x for x in results if x is not None),None), chunk*len(devices)

def run(args):
    if not args.cpu and not pathlib.Path(args.cuda_bin).is_file():
        raise SystemExit("CUDA binary missing: compile ORU/src/cuda/oru_cuda.cu first")
    rpc=RPC(args.rpc,args.rpc_user,args.rpc_password)
    confirm_mainnet(rpc)
    print("RIGOR mainnet verified; SOLO mining (no pool).",flush=True)
    start=0; rounds=0
    while True:
        tmpl=rpc.call("getblocktemplate",[{"rules":["segwit"],"coinbase_address":args.wallet}])
        header,target,txs=prepare_work(tmpl,args.wallet)
        height=tmpl["height"]
        tic=time.monotonic()
        tried=0
        while True:
            n,tries=mine_round(header,target,start,args.devices,args.cuda_bin,args.chunk,args.cpu)
            tried+=tries
            start=(start+tries)&0xffffffff
            if n is not None:
                solved=header[:76]+n.to_bytes(4,"little")
                block=solved+compact_size(len(txs))+b"".join(txs)
                print(f"ORU nonce found at height {height}, submitting...",flush=True)
                result=rpc.call("submitblock",[block.hex()])
                print("submitblock result:",repr(result),flush=True)
                break
            elapsed=time.monotonic()-tic
            if elapsed>=args.refresh_seconds or tried>=0x100000000:
                rate=tried/max(elapsed,0.0001)
                print(f"height={height} scanned={tried} avg_hs={rate:.0f} devices={args.devices}",flush=True)
                break
        rounds+=1
        if args.rounds and rounds>=args.rounds:return
        time.sleep(args.pause)

def main():
    p=argparse.ArgumentParser(description="Original ORU CUDA SOLO miner; needs a RIGOR full node")
    p.add_argument("--rpc",default=os.environ.get("ORU_RPC_URL","http://127.0.0.1:8761"))
    p.add_argument("--rpc-user",default=os.environ.get("ORU_RPC_USER",""))
    p.add_argument("--rpc-password",default=os.environ.get("ORU_RPC_PASSWORD",""))
    p.add_argument("--wallet",default=os.environ.get("ORU_WALLET",""))
    p.add_argument("--cuda-bin",default=os.environ.get("ORU_CUDA_BIN","./oru-cuda"))
    p.add_argument("--devices",type=lambda s:[int(v) for v in s.split(",")],default=[0])
    p.add_argument("--chunk",type=int,default=16777216)
    p.add_argument("--refresh-seconds",type=float,default=15.0)
    p.add_argument("--pause",type=float,default=0.25)
    p.add_argument("--rounds",type=int,default=0,help="0=infinite")
    p.add_argument("--cpu",action="store_true",help="Slow debug mode without NVIDIA")
    a=p.parse_args()
    if not a.wallet: p.error("ORU wallet address is required")
    if not a.devices or any(d<0 for d in a.devices) or len(set(a.devices))!=len(a.devices):
        p.error("devices must be a unique comma-separated list of nonnegative IDs")
    if a.chunk<1 or a.chunk*len(a.devices)>0x100000000 or a.refresh_seconds<=0:
        p.error("invalid chunk size or refresh period")
    try:run(a)
    except KeyboardInterrupt: print("\nStopped.",flush=True)
    except Exception as exc:
        print(f"ORU ERROR: {exc}",file=sys.stderr,flush=True)
        raise SystemExit(2)

if __name__=="__main__":main()
