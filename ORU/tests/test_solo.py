"""No external daemon needed: test canonical SOLO serialization and payout guard."""
import hashlib
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
from solo import (sha256d,compact_size,read_compact,bech32_polymod,
                  bech32_decode_v0,coinbase_txid_and_payout,merkle_from_leaves,
                  bits_target,prepare_work,digest_header)

ALPH="qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def wallet_for(program):
    acc=0;bits=0;data=[0]
    for b in program:
        acc=(acc<<8)|b;bits+=8
        while bits>=5:
            bits-=5;data.append((acc>>bits)&31)
    if bits:data.append((acc<<(5-bits))&31)
    hrp="rg"
    expanded=[ord(c)>>5 for c in hrp]+[0]+[ord(c)&31 for c in hrp]
    values=data+[0]*6
    check=bech32_polymod(expanded+values)^1
    values=data+[(check>>(5*(5-i)))&31 for i in range(6)]
    return hrp+"1"+"".join(ALPH[v] for v in values)

def template():
    program=bytes(range(20))
    addr=wallet_for(program)
    script=b"\x00\x14"+program
    ss=b"\x01\x01\x00\x00"
    vout1=(128*100000000).to_bytes(8,"little")+compact_size(len(script))+script
    witness_commit=b"\x6a\x24\xaa\x21\xa9\xed"+bytes(32)
    vout2=(0).to_bytes(8,"little")+compact_size(len(witness_commit))+witness_commit
    version=(2).to_bytes(4,"little")
    inputs=b"\x01"+bytes(32)+b"\xff"*4+compact_size(len(ss))+ss+b"\xff"*4
    outputs=b"\x02"+vout1+vout2
    tx=version+b"\x00\x01"+inputs+outputs+b"\x01\x20"+bytes(32)+bytes(4)
    txid=sha256d(version+inputs+outputs+bytes(4))
    bits="207fffff"
    target=f"{bits_target(bits):064x}"
    gbt={"rigor_coinbase_immutable":True,"height":1,"default_coinbase_tx":tx.hex(),
         "default_coinbase_scriptsig":ss.hex(),"default_coinbase_txid":txid[::-1].hex(),
         "coinbasevalue":128*100000000,"transactions":[],"merkleroot":txid[::-1].hex(),
         "version":0x20000000,"previousblockhash":"12"*32,"curtime":1710000000,
         "bits":bits,"target":target}
    return addr,gbt,tx

class SoloTests(unittest.TestCase):
    def test_bech32_wallet_guard(self):
        addr,_,_=template()
        self.assertEqual(bech32_decode_v0(addr),b"\x00\x14"+bytes(range(20)))
        with self.assertRaises(ValueError):
            bech32_decode_v0(addr[:-1]+"q")
    def test_template_and_header(self):
        addr,gbt,tx=template()
        header,target,transactions=prepare_work(gbt,addr)
        self.assertEqual(len(header),80)
        self.assertEqual(transactions,[tx])
        self.assertEqual(header[4:36],bytes.fromhex(gbt["previousblockhash"])[::-1])
        self.assertEqual(int(target,16),bits_target(gbt["bits"]))
        self.assertEqual(header[76:80],bytes(4))
    def test_refuse_wrong_payout(self):
        addr,gbt,_=template()
        wrong=wallet_for(bytes([2]*20))
        with self.assertRaisesRegex(ValueError,"YOUR address"):
            prepare_work(gbt,wrong)
    def test_refuse_merkle_mismatch(self):
        addr,gbt,_=template()
        gbt["merkleroot"]="00"*32
        with self.assertRaisesRegex(ValueError,"merkle"):
            prepare_work(gbt,addr)
    def test_refuse_target_mismatch(self):
        addr,gbt,_=template()
        gbt["target"]="ff"*32
        with self.assertRaisesRegex(ValueError,"bits/target"):
            prepare_work(gbt,addr)
    def test_compact_size(self):
        for val in (0,252,253,65535,65536,0xffffffff,0x100000000):
            data=compact_size(val)
            self.assertEqual(read_compact(data,0),(val,len(data)))
    def test_sha3_vector(self):
        self.assertEqual(digest_header(bytes(80)).hex(),
                         "dd057fc1df8f5b9466e834cc9d7b819e2d511c75b43675b577f6d9f5d6de04fc")

if __name__=="__main__":
    unittest.main()
