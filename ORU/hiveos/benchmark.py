#!/usr/bin/env python3
"""Standalone comparison benchmark for original ORU CUDA kernel.
Measures end-to-end throughput, including process launch and memory transfers.
No pool, wallet, node or shares; target 0 is practically unachievable.
"""
import argparse
import csv
import pathlib
import statistics
import subprocess
import sys
import time

def devices_from_smi():
    try:
        p=subprocess.run(["nvidia-smi","--query-gpu=index,name","--format=csv,noheader"],
                         check=True,capture_output=True,text=True,timeout=15)
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        return [(0,"GPU 0 (not detected)")]
    out=[]
    for line in p.stdout.splitlines():
        i,sep,name=line.partition(",")
        if sep:
            try:out.append((int(i.strip()),name.strip()))
            except ValueError:pass
    return out or [(0,"GPU 0 (not detected)")]

def main():
    p=argparse.ArgumentParser(description="ORU native CUDA vs external miner hashrate (manual baseline)")
    p.add_argument("--binary",default=None,help="Path to compiled oru-cuda binary")
    p.add_argument("--devices",default=None,help="comma-separated GPU index list, default all from nvidia-smi")
    p.add_argument("--nonces",type=int,default=8388608,help="iterations per sample and per GPU")
    p.add_argument("--samples",type=int,default=3)
    p.add_argument("--baseline-name",default="Other miner",help="label for reference hashrate")
    p.add_argument("--baseline-hs",type=float,default=None,help="OTHER miner measured H/s, same GPUs")
    p.add_argument("--csv",default=None,help="write rows with measured data to CSV")
    args=p.parse_args()
    if args.samples<1 or args.samples>50 or not 1<=args.nonces<=0xffffffff:
        p.error("samples must be 1..50; nonces 1..2^32-1")
    binary=str(pathlib.Path(args.binary or pathlib.Path(__file__).with_name("oru-cuda")).resolve())
    if not pathlib.Path(binary).is_file():
        p.error(f"ORU native CUDA binary not found: {binary}")
    installed=devices_from_smi()
    names=dict(installed)
    ids=([int(x) for x in args.devices.split(",")]
         if args.devices is not None else [i for i,_ in installed])
    if not ids or any(x<0 for x in ids):p.error("invalid GPU device indices")
    hdr=(bytes(76)+bytes(4)).hex()
    rows=[]
    for gpu in ids:
        results=[]
        for run in range(args.samples):
            start=time.perf_counter()
            r=subprocess.run([binary,"--header",hdr,"--target","00"*32,"--start",str(run*args.nonces % (2**32)),
                              "--count",str(args.nonces),"--device",str(gpu)],
                             capture_output=True,text=True,timeout=300)
            dt=time.perf_counter()-start
            if r.returncode or r.stdout.strip()!=f"NONE {args.nonces}":
                raise RuntimeError(f"Device {gpu} run {run+1}: failure={r.returncode}, output={r.stdout!r}, stderr={r.stderr!r}")
            rate=args.nonces/dt
            results.append(rate)
            print(f"GPU {gpu} {names.get(gpu,'NVIDIA')}: sample {run+1} = {rate/1e6:.3f} MH/s ({dt:.2f}s)")
        median=statistics.median(results)
        rows.append({"device":gpu,"model":names.get(gpu,"NVIDIA"),"nonces":args.nonces,
                     "samples":args.samples,"median_hs":round(median)})
        print(f"GPU {gpu} median end-to-end = {median/1e6:.3f} MH/s\n")
    total=sum(x["median_hs"] for x in rows)
    print(f"ORU TOTAL estimated across GPUs = {total/1e6:.3f} MH/s")
    if args.baseline_hs is not None:
        if args.baseline_hs<=0:p.error("--baseline-hs must be >0")
        print(f"{args.baseline_name} (provided, not independently measured): {args.baseline_hs/1e6:.3f} MH/s")
        print(f"ORU/other ratio = {total/args.baseline_hs:.3f}x")
    if args.csv:
        with open(args.csv,"w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]))
            w.writeheader();w.writerows(rows)
        print("Saved:",args.csv)
    print("These rates include CUDA initialization, launch and transfers. "
          "Not equivalent to accepted network shares. Compare using the SAME GPU/driver/OC.")

if __name__=="__main__":
    main()
