# GNR HiveOS 1.2.0 — coordinated network access, parallel NVIDIA mining

Experimental adapter around `krypton-miner 1.0.37`, pinned upstream commit
`5532d04ba7bdf3362f97a560437694fddb0bddc5`. No new fee or payout address.

## Why this supersedes 1.0.0 and the unreleased 1.1.0

1.0.0 launched one process per GPU directly against the public node. Twelve workers
polling every two seconds can exceed the upstream template budget (120/minute/IP).
1.1.0 grouped GPUs into one unmodified miner, but its CUDA loop calls synchronous
searches successively. That alone is not a satisfactory parallel GPU optimization.

1.2.0 keeps independent CUDA workers for parallelism and measured per-GPU rates,
but ALL their API calls go through ONE local work coordinator. It:

- refreshes a shared mining template at most once per 3 seconds by default,
  approximately 20 upstream template requests/minute/rig, not 30 per GPU;
- caches info and account statistics for 30 seconds;
- respects HTTP 429 Retry-After, with shared exponential backoff; it does NOT
  rotate IPs, wallets, or spoof headers to circumvent server limits;
- forwards each share to the real node; only its real `accepted:true` response
  counts as accepted. It retries a submit once after an explicit HTTP 429, not
  after an ambiguous network failure;
- does not return expired cached work when an upstream refresh fails;
- limits the relay to random-token-protected loopback and mining endpoints;
- staggers worker startup by 1.5 seconds and sets RAYON_NUM_THREADS=1 per worker;
- preserves actual per-GPU H/s, shares, rejects and PCI mapping in HiveOS;
- stops all worker processes on termination or worker failure and prevents two
  copies of this wrapper using the same runtime configuration simultaneously.

The upstream CUDA kernel and proof validation are UNMODIFIED. No performance
multiplier is claimed. Host cache memory is still allocated once per GPU worker.
This fixes request duplication, not every possible CPU, RAM, driver or node issue.

## Flight Sheet (same wallet, same node)

| Field | Value |
|---|---|
| Coin | GNR |
| Pool | Configure in miner |
| Miner | Custom |
| Miner name | `gnr-hiveos` |
| Installation URL | `https://github.com/Driccine/hiveos-custom-miners/releases/download/gnr-hiveos-v1.2.0/gnr-hiveos-1.2.0.tar.gz` |
| Hash algorithm | `kryptohash` |
| Wallet and worker template | `%WAL%` |
| Pool URL | `https://genoryn.io` |
| Password | `x` (unused) |
| Extra config | empty for all NVIDIA GPUs, or `--devices 0,1,2,3,4,5,6,7,8,9,10,11` |

Use the FULL public `gnr1...` address, never `gnrs1...`, a recovery phrase or a
private key. No `.worker` suffix. The wrapper does not store a wallet secret.
The installation URL becomes usable when the release is actually published.

First validate a subset with `--devices 0,1,2,3`, then all 12. This does not stop
another independently launched miner: stop the old Flight Sheet before switching.
Requirements: x86-64 HiveOS, glibc >=2.31, Python >=3.8, usable NVIDIA driver.
No drivers, system libraries, clock settings or power limits are changed.

## Options

`--devices 0,2` selects devices. `--batch 1048576` overrides the official miner's
batch tuning; leave unset initially. `--start-delay 3` increases startup spacing.
`--cpu-threads 2` changes the per-worker Rayon thread budget; default is 1.
`--node-poll 5` lowers template traffic further for multiple rigs on one public IP.

**The quota is shared across your whole public IP, not per rig.** Default is about
20 templates/minute/rig; 12 rigs would still exceed the inspected node's quota.
Actual server policy may differ. A full node on your private network remains the
preferred scaling option. This relay is NOT a validating blockchain node.
Do not expose its loopback HTTP service to the Internet.

## Check after installation

```bash
miner
cat /run/hive/miners/gnr-hiveos/stats.json
```

The log starts with `GNR HiveOS 1.2.0` and reports `GNR RELAY | templates ... |
cache ... | HTTP429 ... | pause ...`. These counters are cumulative since startup.
`wrapper_version` in stats must be `1.2.0`. There is no local API rate/balance
promise: accepted shares are not proof of final on-chain payment.

Look for all selected GPUs, progressing accepted-share counters, and no sustained
rate-limit loop. Check CPU/RAM with `free -h` and `top` if performance remains poor.

## Test boundaries and provenance

The suite includes cached-work concurrency, 12 simulated HTTP clients, a simulated
minute under the request budget, real Retry-After parsing, correct acceptance/
rejection forwarding, prohibited endpoints, and a 12-process fake-miner lifecycle
with cleanup on SIGTERM and child failure. These are SOFTWARE tests, not a real
12-GPU benchmark. Live NVIDIA throughput and rewards must be validated on the rig.

CI rebuilds the pinned official CUDA miner on Ubuntu 20.04, verifies its CLI and
GLIBC symbol requirement, packages the adapter and publishes SHA256SUMS/BUILD.json.
The build job is read-only; only the publication job has release write permission.

Sources: upstream `apps/kryptond/src/guard.rs` (API budgets),
`apps/kryptond/src/rpc.rs` (template/submit protocol),
`apps/krypton-miner/src/main.rs` (polling and CUDA loop), at the commit above.
Adapter MIT; upstream retains its MIT/Apache-2.0 licenses.

Active entrypoint: `hiveos/runtime.py`; `gnr.py` is retained only for tested helpers.
Neither its old one-process-per-GPU-direct runner nor its old single-process runner is called.
