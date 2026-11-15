#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""NULL Native 0.1.0-alpha. CUDA solver, not a wrapper around another miner.
RPlant: read-only probe available; share submission intentionally blocked.
Solo RPC: experimental, explicit opt-in required. No keys or developer fees.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import secrets
import signal
import sys
import threading
import time
import urllib.request
from urllib.parse import urlsplit
import gpu
import pow as proof
import rplant

VERSION='0.1.0-alpha'


def atomic_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with open(tmp,'w') as f:
        os.chmod(tmp,0o600);json.dump(obj,f,allow_nan=False);f.write('\n')
    os.replace(tmp,path)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise ValueError('RPC redirect refused')


class RPC:
    def __init__(self,url,token):
        u=urlsplit(url)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.fragment or u.query:
            raise ValueError('Invalid node URL')
        self.url=url;self.token=token;self.lock=threading.Lock();self.seq=0
        self.opener=urllib.request.build_opener(NoRedirect)
    def call(self,method,params):
        with self.lock:
            self.seq+=1
            payload=json.dumps({'jsonrpc':'2.0','id':self.seq,'method':method,'params':params}).encode()
            req=urllib.request.Request(self.url,data=payload,headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
            with self.opener.open(req,timeout=20) as response:
                raw=response.read(2097153)
            if len(raw)>2097152: raise RuntimeError('Oversized RPC response')
            msg=json.loads(raw)
            if msg.get('error'): raise RuntimeError('Node RPC error: '+str(msg['error']))
            if msg.get('id')!=self.seq or 'result' not in msg: raise RuntimeError('Wrong RPC response ID')
            return msg['result']


def parse_template(t):
    eq=t['equihash']
    if (eq['n'],eq['k'],eq['solution_length'])!=(144,5,100) or bytes.fromhex(eq['personalization'])!=proof.PREFIX:
        raise ValueError('Not NULL mainnet Equihash 144,5')
    data=bytes.fromhex(t['pow_input']);bits=int(t['target'],16)
    rebuilt=proof.header(t['version'],bytes.fromhex(t['prev_hash']),t['height'],t['timestamp'],
                         bytes.fromhex(t['commitment_root']),bytes.fromhex(t['tx_root']),bits)
    if data!=rebuilt: raise ValueError('Node pow_input/header mismatch')
    target=int(t['target_hex'],16)
    if target!=proof.compact_target(bits): raise ValueError('Node target mismatch')
    if not isinstance(t['template_id'],str) or not t['template_id']: raise ValueError('No template ID')
    return {'input':data,'target':target,'id':t['template_id'],'timestamp':t['timestamp'],
            'height':t['height'],'prev':t['prev_hash'],'expires':int(t['expires_at'])}


def devices(text,lib):
    err=ctypes.create_string_buffer(1024);count=lib.nn_device_count(err,1024)
    if count<0: raise RuntimeError(err.value.decode(errors='replace'))
    if text=='all': values=list(range(count))
    else:
        if not re.fullmatch(r'\d+(,\d+)*',text): raise ValueError('Devices: 0,1,... or all')
        values=list(map(int,text.split(',')))
    if not values or len(set(values))!=len(values) or any(i>=count for i in values):
        raise ValueError('GPU selection invalid')
    return values


def run(args):
    lib=gpu.load();selected=devices(args.devices,lib)
    print('NULL Native %s | %s | GPUs %s | 0%% developer fee'%(VERSION,args.mode,selected),flush=True)
    if args.mode=='benchmark': print('BENCHMARK ONLY: no pool, no rewards, no submissions.',flush=True)
    stop=threading.Event();lock=threading.Lock();state={};solvers={};current=[None];fatal=[]
    started=time.monotonic();rpc=None;poller=None
    if args.mode=='solo':
        if not args.allow_experimental: raise ValueError('Solo mining requires --allow-experimental')
        if not re.fullmatch(r'null1[0-9a-z]{60,100}',args.wallet or ''): raise ValueError('NULL mainnet public address required')
        if not args.node or not args.token_file: raise ValueError('--node and --token-file required for your own node')
        token=Path(args.token_file).read_text().strip()
        if not token or '\n' in token or '\r' in token: raise ValueError('Invalid RPC token')
        rpc=RPC(args.node,token)
    def shutdown(*_):
        stop.set()
        with lock:
            for solver in solvers.values(): solver.cancel()
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    def poll():
        while not stop.is_set():
            try:
                work=parse_template(rpc.call('getblocktemplate',[args.wallet]))
                with lock:
                    old=current[0];current[0]=work
                    if old and (old['height'],old['prev'])!=(work['height'],work['prev']):
                        for solver in solvers.values(): solver.cancel()
            except Exception as e:
                print('NODE WAIT:',e,flush=True)
                with lock: current[0]=None
            stop.wait(5)
    if rpc:
        poller=threading.Thread(target=poll,daemon=True);poller.start()
    def worker(device):
        solver=None
        try:
            result=gpu.selftest(device,lib);print('SELFTEST '+json.dumps(result),flush=True)
            solver=gpu.Solver(device,slots=args.slots,lib=lib)
            with lock: solvers[device]=solver
            count=valid=filtered=overflow=truncated=accepted=rejected=0
            window_start=time.monotonic();window_valid=0;rate=0.0
            while not stop.is_set():
                now=time.monotonic()
                if args.mode=='benchmark' and now-started>=args.seconds: break
                with lock: work=current[0]
                if rpc and (work is None or time.time()+25>=work['expires']):
                    stop.wait(1);continue
                data=work['input'] if work else bytes(113)
                nonce=secrets.token_bytes(32)
                solutions,meta=solver.solve(data,nonce)
                if meta['cancelled']: continue
                count+=1;valid+=len(solutions);window_valid+=len(solutions)
                filtered+=meta['filtered_candidates'];overflow+=meta['dropped'];truncated+=meta['truncated']
                if meta['dropped'] or meta['truncated']:
                    print('GPU %d bounded-table drops=%d truncated=%d; not an exhaustive solve'%(device,meta['dropped'],meta['truncated']),flush=True)
                if rpc:
                    for solution in solutions:
                        with lock: latest=current[0]
                        if stop.is_set() or not latest or (latest['height'],latest['prev'])!=(work['height'],work['prev']): break
                        if int.from_bytes(proof.block_hash(data,nonce,solution),'big')>work['target']: continue
                        try:
                            answer=rpc.call('submitblock',[work['id'],work['timestamp'],nonce.hex(),solution.hex()])
                            if answer.get('status')=='accepted': accepted+=1
                            else: rejected+=1
                            print('BLOCK RESPONSE '+json.dumps(answer),flush=True)
                        except Exception as e:
                            print('SUBMISSION UNCERTAIN (not retried):',e,flush=True)
                now=time.monotonic()
                if now-window_start>=10:
                    rate=window_valid/(now-window_start);window_valid=0;window_start=now
                record={'rate_solutions':rate,'solutions_total':valid,'nonces':count,'filtered_candidates':filtered,
                        'dropped_rows':overflow,'truncated_attempts':truncated,'accepted_blocks':accepted,'rejected_blocks':rejected,
                        'memory_bytes':meta['memory_bytes'],'stages_ms':meta['stages_ms'],'updated':time.time()}
                with lock: state[device]=record
                print('GPU %d | %.3f verified Sol/s | solutions %d | blocks accepted %d | %.2fs/nonce'%(device,rate,valid,accepted,meta['seconds']),flush=True)
        except Exception as e:
            with lock: fatal.append('GPU %d: %s'%(device,e))
            shutdown()
        finally:
            with lock: solvers.pop(device,None)
            if solver: solver.close()
    threads=[]
    try:
        for device in selected:
            t=threading.Thread(target=worker,args=(device,),daemon=True);t.start();threads.append(t)
            if stop.wait(0.5): break
        while any(t.is_alive() for t in threads):
            with lock: snap={k:dict(v) for k,v in state.items()}
            rates=[snap.get(i,{}).get('rate_solutions',0) if time.time()-snap.get(i,{}).get('updated',0)<60 else 0 for i in selected]
            atomic_json(args.stats,{'updated':time.time(),'mode':args.mode,'version':VERSION,'devices':snap,
                'khs':sum(rates)/1000,'stats':{'hs':rates,'hs_units':'hs','algo':'nullpow','ver':VERSION,
                'uptime':int(time.monotonic()-started)},'pool_accepted_shares':None})
            stop.wait(2)
        if fatal: raise RuntimeError('; '.join(fatal))
        with lock: final={k:dict(v) for k,v in state.items()}
        elapsed=time.monotonic()-started
        print('RESULT '+json.dumps({'elapsed_seconds':elapsed,'devices':final,'revenue_generated':False if args.mode=='benchmark' else 'check_node'}),flush=True)
    finally:
        shutdown()
        for t in threads: t.join(timeout=30)
        atomic_json(args.stats,{'updated':time.time(),'khs':0,'stats':None,'version':VERSION,'stopped':True})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['selftest','benchmark','probe','solo','rplant'],default='selftest')
    p.add_argument('--devices',default='0');p.add_argument('--slots',type=int,choices=[64,128],default=64)
    p.add_argument('--seconds',type=int,default=120);p.add_argument('--stats',default='null-native-stats.json')
    p.add_argument('--pool',default='stratum+ssl://stratum-eu.rplant.xyz:17073')
    p.add_argument('--wallet');p.add_argument('--password',default='x');p.add_argument('--node');p.add_argument('--token-file')
    p.add_argument('--allow-experimental',action='store_true');p.add_argument('--version',action='version',version=VERSION)
    a=p.parse_args()
    if not 10<=a.seconds<=86400: p.error('--seconds must be 10..86400')
    if a.mode=='rplant': p.error('RPlant submission/normalization not yet verified: use --mode probe. No guessed shares will be sent.')
    if a.mode=='probe': rplant.probe(a.pool,a.wallet or '',a.password,min(a.seconds,30));return
    if a.mode=='selftest':
        lib=gpu.load()
        for i in devices(a.devices,lib): print(json.dumps(gpu.selftest(i,lib)),flush=True)
        return
    run(a)


if __name__=='__main__':
    try: main()
    except Exception as e: print('NULL NATIVE ERROR: '+str(e),file=sys.stderr,flush=True);sys.exit(1)
