# SPDX-License-Identifier: MIT
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import unittest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'native'))
import pow as proof
import gpu
import rplant
import miner

WIRE=['6ab1','01000013f96bf39de7307349c8f644e8bb8d88b098b18e61c395eaac2da04dcce05b4f0000b00df96a0000000002f2dcd94b3a974bcd0c5276940fff482928b01cbb8bcb731612db31c6fc4d38f6f35fea4f0f49b2c6a5d089346cfcbc18b9e04ea372cc8eb39c00e50d148fb3c3911e1e','00001e91c3000000000000000000000000000000000000000000000000000000',20315,True]

class CoreTests(unittest.TestCase):
    def test_mainnet_encoding_length(self):
        values=[(i*991817)%((1<<25)-1) for i in range(32)]
        b=proof.pack(values);self.assertEqual(len(b),100);self.assertEqual(proof.unpack(b),values)
    def test_pack_bounds(self):
        for values in ([0]*31,[0]*33,[1<<25]*32,[-1]*32,[True]*32):
            with self.assertRaises(ValueError):proof.pack(values)
    def test_solution_length(self):
        self.assertEqual(len(proof.pack(list(range(32)),48)),36)
        for length in (0,99,101):
            self.assertFalse(proof.verify(bytes(113),bytes(32),bytes(length)))
    def test_duplicate_indices(self):
        self.assertFalse(proof.verify(bytes(113),bytes(32),proof.pack([0]*32)))
    def test_tiny_solver_positive_and_tampered(self):
        total=0
        for i in range(1,5):
            nonce=bytes([i])*32
            for solution in proof.tiny_solve(bytes(113),nonce):
                total+=1;self.assertTrue(proof.verify(bytes(113),nonce,solution,48))
                bad=bytearray(solution);bad[0]^=1
                self.assertFalse(proof.verify(bytes(113),nonce,bytes(bad),48))
                self.assertFalse(proof.verify(bytes([1])*113,nonce,solution,48))
        self.assertGreater(total,0)
    def test_domain_separation(self):
        h=bytes(113);nonce=bytes(32)
        z=hashlib.blake2b(h+nonce+bytes(4),digest_size=54,person=b'ZcashPoW'+struct.pack('<II',144,5)).digest()
        self.assertNotEqual(proof.leaf(h,nonce,0)[0],int.from_bytes(z[:3],'big'))
    def test_header_roundtrip(self):
        b=bytes.fromhex(WIRE[1]);bits=int.from_bytes(b[-4:],'little')
        rebuilt=proof.header(b[0],b[1:33],int.from_bytes(b[33:37],'little'),int.from_bytes(b[37:45],'little'),b[45:77],b[77:109],bits)
        self.assertEqual(b,rebuilt)
    def test_compact_matches_recorded_network_target(self):
        b=bytes.fromhex(WIRE[1])
        self.assertEqual(proof.compact_target(int.from_bytes(b[-4:],'little')),int(WIRE[2],16))
    def test_bad_targets(self):
        for bits in (0,0x1e800001,0x2300ffff,-1,1<<32):
            with self.assertRaises(ValueError): proof.compact_target(bits)
    def test_block_hash_personalization(self):
        h=bytes(113);nonce=bytes(32);solution=bytes(100)
        expected=hashlib.blake2b(h+nonce+solution,digest_size=32,person=b'null_BlockHash__').digest()
        self.assertEqual(proof.block_hash(h,nonce,solution),expected)
    def test_wire_notify(self):
        j=rplant.decode_notify(WIRE);self.assertEqual(j['height'],20315);self.assertFalse(j['share_target_verified'])
    def test_wire_malformed(self):
        for i,v in ((0,''),(1,'ff'),(2,'ff'*32),(3,1),(4,'true')):
            msg=list(WIRE);msg[i]=v
            with self.assertRaises(ValueError): rplant.decode_notify(msg)
        with self.assertRaises(ValueError):rplant.decode_notify(WIRE+[0])
    def test_pool_url(self):
        self.assertEqual(rplant.endpoint('stratum+ssl://stratum-eu.rplant.xyz:17073'),('stratum-eu.rplant.xyz',17073,True))
        for s in ('https://host:3','stratum+tcp://a:b@host:3','stratum+ssl://host','stratum+tcp://host:3/path'):
            with self.assertRaises(ValueError):rplant.endpoint(s)
    def test_rpc_template(self):
        b=bytes.fromhex(WIRE[1]);t={'equihash':{'n':144,'k':5,'solution_length':100,'personalization':proof.PREFIX.hex()},
        'pow_input':b.hex(),'version':b[0],'prev_hash':b[1:33].hex(),'height':20315,'timestamp':int.from_bytes(b[37:45],'little'),
        'commitment_root':b[45:77].hex(),'tx_root':b[77:109].hex(),'target':format(int.from_bytes(b[-4:],'little'),'08x'),
        'target_hex':WIRE[2],'template_id':'test-id','expires_at':2000000000}
        self.assertEqual(miner.parse_template(t)['input'],b)
        t['height']+=1
        with self.assertRaises(ValueError):miner.parse_template(t)

class HostCudaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib=gpu.load()
    def test_all_hash_groups_against_hashlib(self):
        for n in (48,144):
            for seed in (0,1,255):
                h=bytes((i+seed)%256 for i in range(113));nonce=bytes([seed])*32
                output=(C.c_uint8*(64*128))()
                self.assertEqual(self.lib.nn_hash_host(gpu.buffer(h),gpu.buffer(nonce),n,128,output),0)
                size=(512//n)*n//8
                for group in range(128):
                    expected=hashlib.blake2b(h+nonce+struct.pack('<I',group),digest_size=size,person=proof.PREFIX+struct.pack('<II',n,5)).digest()
                    self.assertEqual(bytes(output[group*64:group*64+size]),expected)

class RustOracleTests(unittest.TestCase):
    def test_official_rust_fixtures(self):
        fixture=BASE/'tests'/'rust-fixtures.jsonl'
        if not fixture.exists():self.skipTest('Rust fixture generated by CI reference job')
        records=[json.loads(line) for line in fixture.read_text().splitlines() if line.strip()]
        self.assertEqual(len(records),4)
        for record in records:
            h=bytes.fromhex(record['input']);nonce=bytes.fromhex(record['nonce'])
            expected={bytes.fromhex(s) for s in record['solutions']}
            self.assertEqual(proof.tiny_solve(h,nonce),expected)
            for solution in expected:self.assertTrue(proof.verify(h,nonce,solution,48))

if __name__=='__main__':unittest.main()
