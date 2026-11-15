# SPDX-License-Identifier: MIT
"""RPlant NULL wire diagnostic. This module intentionally does NOT submit shares.
Observed 2026-11-15: subscription [null, nonce1, 28], difficulty, and
notify [job_id, pow_input_hex, NETWORK_target_hex, height, clean].
The share difficulty normalization and submit tuple are not documented in
NULL's node protocol and have NOT been verified. Do not guess them.
"""
import json
import re
import socket
import ssl
import time
from urllib.parse import urlsplit
import pow as proof


def endpoint(url):
    p=urlsplit(url)
    if p.scheme not in ('stratum+tcp','stratum+ssl','stratum+tcps') or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):
        raise ValueError('Use stratum+ssl://host:port or stratum+tcp://host:port')
    if p.port is None or not 1 <= p.port <= 65535: raise ValueError('Explicit pool port required')
    return p.hostname,p.port,p.scheme != 'stratum+tcp'


def hex_bytes(value,size):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-fA-F]{%d}'%(size*2),value):
        raise ValueError('Expected %d-byte hex value'%size)
    return bytes.fromhex(value)


def decode_notify(params):
    if not isinstance(params,list) or len(params)!=5:
        raise ValueError('Unknown NULL notification schema; refusing to guess')
    job,header,target,height,clean=params
    if not isinstance(job,str) or not 1<=len(job)<=128: raise ValueError('Invalid job ID')
    header=hex_bytes(header,113); target=hex_bytes(target,32)
    if isinstance(height,bool) or not isinstance(height,int) or height!=int.from_bytes(header[33:37],'little'):
        raise ValueError('Header height mismatch')
    if not isinstance(clean,bool): raise ValueError('Invalid clean flag')
    network_target=proof.compact_target(int.from_bytes(header[-4:],'little'))
    if int.from_bytes(target,'big')!=network_target:
        raise ValueError('Unexpected notify target; capture required before mining')
    return {'job_id':job,'pow_input':header.hex(),'network_target':target.hex(),
            'height':height,'clean':clean,'share_target_verified':False}


def probe(url,user='',password='x',seconds=25):
    host,port,tls=endpoint(url)
    if user and (not re.fullmatch(r'null1[0-9a-z]{60,100}(?:\.[A-Za-z0-9_-]{1,64})?',user)):
        raise ValueError('Expected mainnet NULL public address, optionally .worker')
    raw=socket.create_connection((host,port),timeout=10)
    conn=raw
    try:
        if tls: conn=ssl.create_default_context().wrap_socket(raw,server_hostname=host)
        conn.settimeout(2)
        def send(id_,method,params):
            conn.sendall((json.dumps({'id':id_,'method':method,'params':params})+'\n').encode())
        send(1,'mining.subscribe',['NULL-Native/0.1.0-alpha'])
        if user: send(2,'mining.authorize',[user,password])
        end=time.monotonic()+seconds; pending=b''; events=[]; total=0
        while time.monotonic()<end and len(events)<50:
            try: data=conn.recv(16384)
            except socket.timeout: continue
            if not data: break
            total+=len(data)
            if total>1048576: raise ValueError('Oversized pool response')
            pending+=data
            while b'\n' in pending:
                line,pending=pending.split(b'\n',1)
                obj=json.loads(line)
                if obj.get('method')=='mining.notify':
                    obj={'method':'mining.notify','decoded':decode_notify(obj.get('params'))}
                events.append(obj);print(json.dumps(obj),flush=True)
        return events
    finally:
        conn.close()
        if conn is not raw: raw.close()
