# NEB GPU HiveOS bootstrap (NVIDIA)

**Status:** HiveOS integration/wrapper; **not** a new CUDA mining engine. Downloads and launches Aria Energy NEB 3.2.0, with its own Kepler/TESS kernels. The binary is supplied by AriaPool, not by this repository. No claim of higher hashrate, no extra developer fee from this wrapper. Aria reports 1% miner dev time plus 1% pool fee when mining on AriaPool.

## Sources / rationale (19 Nov 2026)

- [AriaPool NEB instructions](https://pool.ariabrain.com/neb.html): Energy 3.2 engine for RTX 50; 3.1 for RTX 30/40, CPU cross-check of engines, NVIDIA driver >=580.
- [Official NEB source and releases](https://github.com/SilasEigen/neb): deterministic proof-of-training and mainnet protocol.
- Official Aria HiveOS archive: https://dl.ariabrain.com/neb-dl/aria-energy-neb-3.2.0.tar.gz

## Build a HiveOS package

```bash
bash build_package.sh
```

Upload the resulting `neb-gpu-hiveos-1.0.0.tar.gz` as a GitHub Release asset or serve it over HTTPS, then in HiveOS configure a **Custom miner**:

| Field | Value |
| --- | --- |
| Miner name | `neb-gpu-hiveos` |
| Installation URL | Direct HTTPS URL to the built `.tar.gz`, **not** the GitHub file page |
| Wallet and worker | `%WAL%` (full `neb1...` address) |
| Pool URL (Aria) | `neb.ariabrain.com:3370` |
| Hash algorithm | leave blank unless HiveOS requires an entry |
| Password | `x` |
| Extra arguments | blank |

On first start the wrapper fetches the **official** Aria HiveOS package over HTTPS and runs its own `h-run.sh` with HiveOS environment intact. You need outgoing network access to `dl.ariabrain.com`; it is cached afterward. The wrapper does **not** change Aria's default pool and **does not** automatically make the Aria binary compatible with Suprnova. Consult Aria's own miner/pool docs for supported server protocols.

**Easier option:** HiveOS already supports the official Aria package directly: install URL `https://dl.ariabrain.com/neb-dl/aria-energy-neb-3.2.0.tar.gz`, miner name `aria-energy-neb`. This is the recommended, fully documented route, with no wrapper required.

## Validation and limitations

`bash -n h-run.sh && bash -n build_package.sh` checks script syntax. There is no GPU in the build environment, and the Aria binary/package has not been executed or benchmarked here. Verify publisher SHA256 manifests and trust the downloaded binary before deploying to rigs. The wrapper cannot independently audit or optimize the unpublished proprietary CUDA kernels; for independently developed NEB kernels, work from the official NEB reference implementation and verify bit-for-bit identity against CPU test vectors before submitting shares.

No wallet keys are handled. Never paste `wallet.txt` or secrets into the flight sheet.
