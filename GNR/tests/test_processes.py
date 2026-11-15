"""Twelve fake CUDA processes through a real local relay; tests shutdown, not GPUs."""
import http.server
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

BASE = Path(__file__).resolve().parents[1]
ADDRESS = 'gnr1' + 'q' * 2600
FAKE = r'''
import argparse, json, os, signal, sys, time, urllib.request
from pathlib import Path
if '--version' in sys.argv:
    print('krypton-miner 1.0.37'); raise SystemExit(0)
if '--list-devices' in sys.argv:
    print(json.dumps({'gpus':[{'backend':'cuda','index':i,'usable':True} for i in range(12)]})); raise SystemExit(0)
p = argparse.ArgumentParser()
for name in ('node','address-file','devices','backend','batch'): p.add_argument('--' + name)
p.add_argument('--json', action='store_true')
a=p.parse_args()
i=int(a.devices)
Path(__file__).with_name('pid-'+str(i)).write_text(str(os.getpid()))
assert a.backend == 'cuda'
assert os.environ['RAYON_NUM_THREADS'] == '1'
address=Path(a.address_file).read_text().strip()
def request(path, value):
    r=urllib.request.Request(a.node+path,data=json.dumps(value).encode())
    with urllib.request.urlopen(r,timeout=10) as response: return json.load(response)
shares=0
for step in range(1000):
    w=request('/v1/mining/template', {'address':address})
    if not shares:
        answer=request('/v1/mining/submit', {'job_id':w['job_id'],'nonce':i+1000})
        shares=int(answer['accepted'])
    print(json.dumps({'event':'status','hashrate_hs':10000000+i,'accepted_shares':shares,
                      'accepted_blocks':0,'rejected':0,'height':w['height']}),flush=True)
    if i == 2 and os.environ.get('GNR_TEST_CRASH') == '1': raise SystemExit(7)
    time.sleep(.1)
'''


class ProcessTests(unittest.TestCase):
    def run_case(self, crash=False):
        counts = {'templates': 0, 'submits': 0}
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def reply(self, value):
                data=json.dumps(value).encode(); self.send_response(200)
                self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
            def do_GET(self): self.reply({'network':'mainnet','height':15926,'hashrate':123456789,'unpaid':0})
            def do_POST(self):
                value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path.endswith('/template'):
                    counts['templates'] += 1
                    self.reply({'job_id':100,'height':15926,'pow_hash':'ab'*32,
                                'chain_seed':'cd'*32,'share_difficulty':'20','epoch':0,'network':'mainnet'})
                else:
                    counts['submits'] += 1
                    self.reply({'accepted':True,'kind':'share','height':15926})
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.daemon_threads=True
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                for name in ('gnr.py','relay.py','runtime.py'): shutil.copyfile(BASE/'hiveos'/name,root/name)
                (root/'krypton-miner').write_text('#!'+sys.executable+'\n'+FAKE)
                (root/'krypton-miner').chmod(0o755)
                cfg={'node':'http://127.0.0.1:%s'%server.server_address[1], 'address':ADDRESS,
                     'devices':None,'batch':None,'node_poll':3,'start_delay':0,'cpu_threads':1}
                (root/'config.json').write_text(json.dumps(cfg))
                env=dict(os.environ)
                if crash: env['GNR_TEST_CRASH']='1'
                with (root/'run.log').open('w') as output:
                    proc=subprocess.Popen([sys.executable,str(root/'runtime.py'),'run',str(root/'config.json')],
                                          stdout=output,stderr=subprocess.STDOUT,env=env)
                    try:
                        deadline=time.monotonic()+16
                        while time.monotonic()<deadline:
                            if proc.poll() is not None: break
                            if not crash and (root/'stats.json').exists():
                                stats=json.loads((root/'stats.json').read_text())
                                if stats.get('stats',{}).get('ar',[0])[0] == 12: break
                            time.sleep(.1)
                        if crash:
                            proc.wait(timeout=10)
                            self.assertNotEqual(proc.returncode,0)
                        else:
                            self.assertIsNone(proc.poll(),(root/'run.log').read_text())
                            stats=json.loads((root/'stats.json').read_text())
                            self.assertEqual(len(stats['stats']['hs']),12)
                            self.assertEqual(stats['stats']['ar'],[12,0])
                            self.assertGreater(stats['khs'],119999)
                            self.assertLessEqual(counts['templates'],6)
                            proc.send_signal(signal.SIGTERM)
                            self.assertEqual(proc.wait(timeout=15),0)
                    finally:
                        if proc.poll() is None: proc.kill(); proc.wait()
                self.assertEqual(json.loads((root/'stats.json').read_text())['khs'],0)
                for pidfile in root.glob('pid-*'):
                    pid=int(pidfile.read_text())
                    with self.assertRaises(ProcessLookupError): os.kill(pid,0)
        finally:
            server.shutdown(); server.server_close()

    def test_12_processes_stats_and_clean_shutdown(self): self.run_case(False)
    def test_child_failure_stops_remaining_workers(self): self.run_case(True)


if __name__ == '__main__': unittest.main()
