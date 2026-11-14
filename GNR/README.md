# GNR / Genoryn Krypton — Custom Miner HiveOS NVIDIA

**Adapter 1.0.0 · upstream krypton-miner 1.0.37. Experimental: no live GPU payout test yet.**

This is a HiveOS adapter around the real official miner, not a new mining algorithm or a pool.
The official upstream is pinned to `genoryn/genoryn@5532d04ba7bdf3362f97a560437694fddb0bddc5`.
It is rebuilt in CI on Ubuntu 20.04 to avoid the official binary's glibc 2.39 requirement.
The build checks that the resulting binary requires no GLIBC symbol newer than 2.31.
**No Docker, Rust compilation, root package installation, NVIDIA update or libc replacement on your rig.**

## Flight Sheet — champs a copier

Add a GNR wallet in HiveOS using the **FULL public address `gnr1...`**, not the short `gnrs1...` address.
The full address can be thousands of characters: this is normal. Never paste a recovery phrase,
password, private key or wallet file. No address is stored in this repository.

| Champ | Valeur |
|---|---|
| Coin | GNR (custom coin if absent) |
| Wallet | Your GNR wallet selected in HiveOS |
| Pool | Configure in miner |
| Miner | Custom |
| Miner name | `gnr-hiveos` |
| Installation URL | `https://github.com/Driccine/hiveos-custom-miners/releases/download/gnr-hiveos-v1.0.0/gnr-hiveos-1.0.0.tar.gz` |
| Hash algorithm | `kryptohash` |
| Wallet and worker template | `%WAL%` |
| Pool URL | `https://genoryn.io` |
| Password | `x` (ignored) |
| Extra config | empty (all detected NVIDIA GPUs) |

**The Installation URL is usable only after the build succeeds and publishes this release.**
Do not use GitHub's source-code ZIP as a custom-miner package.
First test: put `--devices 0` in Extra config. To select GPUs 0 and 2: `--devices 0,2`.
Optional: `--batch 1048576`. No other arguments are accepted, and nothing is evaluated as shell code.
Do not append `.worker` to the wallet. This protocol does not use Stratum workers.

## Requirements and operation

- Linux x86-64, glibc >= 2.31 (Ubuntu 20.04+ based HiveOS), Python >= 3.8, Bash, sha256sum.
- Working NVIDIA driver able to load the upstream PTX kernel. Probe `--list-devices` is run before mining.
- Dataset memory and GPU architecture requirements come from upstream; compatibility is checked on the rig, not assumed.
- Full public `gnr1...` payout address. Short address resolution is deliberately not added without local verification.
- Internet access to the configured node's HTTP(S) API; node availability and accepted shares are not guaranteed.

The adapter launches one official miner process per selected NVIDIA GPU to obtain **measured per-GPU**
hashrates. Each process uses `--backend cuda --devices N --json`. CPU is only used by the official
miner for verification and coordination, not as a silent mining fallback. HiveOS owns the foreground
supervisor and processes; SIGINT/SIGTERM stop the children. No detached screen/systemd service.

`h-config.sh` writes public-only configuration under `/run/hive/miners/gnr-hiveos`.
`h-stats.sh` reports total kH/s, per-GPU H/s, accepted shares, rejects, uptime and PCI bus IDs when
available. Accepted full blocks are already included in `accepted_shares`; they are not counted twice.
Stats older than 45 seconds become zero. Failed GPU processes stop the supervisor with an error.
The first launch verifies package SHA256 checksums. Checksums detect corruption; they are not an independent security audit.

## Logs / diagnostic

```bash
miner
cat /run/hive/miners/gnr-hiveos/stats.json
/hive/miners/custom/gnr-hiveos/krypton-miner --list-devices --json
```

If the log says `COMPLETE`, replace the short wallet address with its full public form.
If a GPU is not usable, keep the error message: the adapter does not change drivers or mine on CPU.
If the node is unavailable, do not infer that rewards are being credited from local hashrate alone.
Do not run two Flight Sheets on the same GPUs at the same time.

## Build / provenance

The workflow `.github/workflows/gnr-hiveos.yml` builds the pinned upstream on Ubuntu 20.04,
runs wrapper unit tests, verifies CLI help/version and GLIBC requirements, packages the four HiveOS
hooks and miner, then publishes a prerelease with SHA256SUMS and BUILD.json.
The compilation job has read-only repository permissions; only the separate publication job has write permissions.

Tests do not prove real GPU performance or payments. Validate one GPU and actual shares before using an entire rig.
No developer fee is added by this wrapper. Upstream consensus and reward rules remain unchanged.

Sources inspected:
- https://genoryn.io/docs
- https://github.com/genoryn/genoryn/tree/v1.0.37
- https://github.com/minershive/hiveos-linux/blob/master/hive/miners/custom/README.md

The adapter is MIT-licensed. Upstream code keeps its own MIT/Apache-2.0 license and attribution.
