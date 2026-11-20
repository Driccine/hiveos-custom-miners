# NULL Native — original CUDA solver, 0.1.0-alpha

**Development / benchmark release, NOT a proven replacement for Aria or another production miner.**

This is actual new CUDA BLAKE2b and Wagner collision-search code for NULL Equihash (144,5),
not a launch script around lolMiner, miniZ, SRBMiner or Aria. Source is MIT-licensed.
No developer fee, hidden payout address, remote binary download or CPU mainnet fallback.

## What exists

- Original CUDA hash generation with NULL personalization `nullPoW_ || LE32(144) || LE32(5)`.
- First BLAKE2b compression precomputed once per nonce; one digest reused for three initial indices.
- Structure-of-arrays GPU storage, shared-memory collision keys, four parallel collision rounds
  followed by a 48-bit final match and GPU index-tree reconstruction.
- Persistent allocation reused across nonces; no repeated multi-gigabyte allocation each round.
- Multiple GPUs run concurrently in independent CUDA contexts, coordinated by one Python supervisor.
- Independent hashlib-based CPU verification of every returned solution before it counts as valid.
- Mandatory runtime GPU hash-vector and exhaustive (48,5) comparison before benchmarks/solo mining.
- Offline benchmarks report verified Equihash solutions/s, NOT hashes/s or accepted pool shares.
- Experimental direct-node mainnet mining using the officially documented RPC.
- Read-only RPlant subscription/authorization/job probe. **RPlant share submission is DISABLED**:
  its difficulty normalization and submit tuple have not been confirmed. An authorization success
  is not proof that a pool will accept our generated shares.

## Status / important limits

Build and CPU tests can run without a GPU. They do not prove kernel correctness on physical GPUs,
accepted RPlant shares, payouts, hashrate or superiority to an established miner.
Do not move a 12-GPU rig to this alpha in production.

144,5 uses roughly **5.51 GiB VRAM with 64 slots**, plus a 256 MiB reserve and driver overhead.
The default targets 8 GiB or larger cards. 128 slots uses about twice the memory.
This bucket solver is bounded: rare bucket overflows can drop rows. `dropped_rows` and candidate
truncation are explicitly reported. Every returned solution is still validated; overflow means the
search is not exhaustive and effective yield can decrease. No performance claim is made.

The alpha does NOT change GPU clocks, voltage, power limits, drivers, libc, or HiveOS settings.
Stop the existing miner on the one test GPU before benchmarking; do not run two solvers on that GPU.
CUDA is compiled with toolkit 12.4 on Ubuntu 20.04, native sm_75/sm_86 plus compute_86 PTX.
Actual driver/hardware compatibility is checked by the runtime self-test, not assumed.
Python >=3.8, glibc >=2.31, Linux x86-64.

## One-GPU test

Extract the release archive, enter `null-native/`, then:

```bash
python3 miner.py --mode selftest --devices 0
python3 miner.py --mode benchmark --devices 0 --seconds 120
```

**Benchmark mode earns no coins.** It runs against a fixed local header and does not connect to a pool.
A benchmark runs the mandatory GPU self-test first. The `RESULT` JSON is the useful comparison record.
To test additional GPUs explicitly: `--devices 0,1` (never start with all 12).

## RPlant — diagnostic only

```bash
python3 miner.py --mode probe \
  --pool stratum+ssl://stratum-eu.rplant.xyz:17073 \
  --wallet YOUR_PUBLIC_NULL_ADDRESS.worker
```

This sends subscribe/authorize, reads messages, then closes. It submits **no shares** and uses no keys.
`--mode rplant` intentionally refuses to start. There is no working revenue-producing RPlant Flight
Sheet in this release; do not point production rigs at it.

A bounded diagnostic on 2026-11-15 observed:
- TCP 7073 and TLS 17073 accept `mining.subscribe`.
- Reply: `[null, <4-byte nonce prefix>, 28]`.
- Authorization succeeded for a synthetic diagnostic-only public address (not a user's wallet).
- `mining.set_difficulty: [8]` followed by
  `mining.notify: [job_id, <113-byte pow_input>, <32-byte network target>, height, clean]`.
- The received target exactly matches the header's compact network target.

These facts do not establish the share-difficulty divisor, submit fields/endianness, or payment
behavior. The synthetic diagnostic address is NEVER a default payout address in this software.

## Optional experimental mining against YOUR own node

The network protocol is verified against NULL's official pool integration guide. The following is
for an operator who already runs a synced `nulld`; it does not install a node or access a wallet file.

```bash
python3 miner.py --mode solo --allow-experimental --devices 0 \
  --node http://127.0.0.1:18446/ --token-file /path/to/node/rpc.token \
  --wallet YOUR_PUBLIC_NULL_ADDRESS
```

Only the node's RPC authorization token is needed, not the wallet spending key. Keep it local.
The shared coordinator fetches templates, rebuilds and checks all header fields, cancels old-height
work, validates Equihash and block target locally, and only then calls `submitblock`.
Only a node response `status: accepted` counts as an accepted block. Never confuse local solutions
with credits. Direct-node mining is solo mining with irregular rewards, not RPlant pool mining.

## Sources and reproducibility

Chain specification inspected at NullNetProtocol/null-chain commit
`20fe0478881a4250d973d58833788695987325da`:
- `docs/guide-pool.md`: 113-byte pow_input, NULL personalization, 100-byte solution, BLAKE2b block hash.
- `crates/chain/src/equihash.rs`: reference verification, encoding and tiny solver.

CI generates fixtures with that exact Rust reference and cross-checks this project's CPU oracle.
The GPU self-test compares the CUDA implementation against independent Python/hashlib calculations.
Production eligibility requires real 144,5 GPU benchmarks, accepted RPlant shares and a payout test.

## File map

`native/blake.hpp`, `native/solver.cu`: original compute engine.
`native/pow.py`: independent validator and tiny test oracle.
`native/gpu.py`: CUDA ABI, memory lifecycle and GPU self-test.
`native/miner.py`: benchmark/solo coordinator.
`native/rplant.py`: strict read-only pool diagnostic.
`tests/`: CPU, encoding, wire-format and official Rust reference tests.

This branch is experimental; it does not replace existing GNR/QTC/NULL production installations.
