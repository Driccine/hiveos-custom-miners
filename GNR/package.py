#!/usr/bin/env python3
"""Package an already built, pinned upstream miner; no network or wallet access."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

VERSION = "1.0.0"
UPSTREAM_SHA = "5532d04ba7bdf3362f97a560437694fddb0bddc5"
BASE = Path(__file__).resolve().parent


def main():
    upstream = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    binary = upstream / "target/release/krypton-miner"
    if not binary.is_file():
        raise SystemExit("Compiled binary missing")
    version = subprocess.check_output([str(binary), "--version"], text=True).strip()
    if version != "krypton-miner 1.0.37":
        raise SystemExit("Unexpected binary version: " + version)
    symbols = subprocess.check_output(["readelf", "--version-info", str(binary)], text=True)
    import re
    required = sorted({tuple(map(int, v.split("."))) for v in re.findall(r"GLIBC_(\d+\.\d+)", symbols)})
    if required and max(required) > (2, 31):
        raise SystemExit("Binary requires GLIBC > 2.31")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gnr-hiveos"
        root.mkdir()
        for file in (BASE / "hiveos").iterdir():
            if file.is_file() and file.suffix in (".py", ".sh", ".conf"):
                shutil.copyfile(file, root / file.name)
        shutil.copyfile(binary, root / "krypton-miner")
        shutil.copyfile(BASE / "README.md", root / "README.md")
        for file in upstream.glob("LICENSE*"):
            if file.is_file():
                shutil.copyfile(file, root / ("UPSTREAM-" + file.name))
        shutil.copyfile(BASE / "LICENSE", root / "LICENSE")
        provenance = {"wrapper_version": VERSION, "upstream_version": "1.0.37",
                      "upstream_repository": "https://github.com/genoryn/genoryn",
                      "upstream_commit": UPSTREAM_SHA, "build_os": "Ubuntu 20.04",
                      "glibc_max_symbol": ".".join(map(str, max(required))) if required else None,
                      "features": ["cuda"], "gpu_tested": False}
        (root / "BUILD.json").write_text(json.dumps(provenance, indent=2) + "\n")
        for file in root.iterdir():
            file.chmod(0o755 if file.suffix in (".py", ".sh") or file.name == "krypton-miner" else 0o644)
        sums = "".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                       for p in sorted(root.iterdir()) if p.is_file())
        (root / "SHA256SUMS").write_text(sums)
        archive = out / ("gnr-hiveos-" + VERSION + ".tar.gz")
        with archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as tar:
                def normalize(info):
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    info.mtime = 0
                    return info
                tar.add(root, arcname="gnr-hiveos", filter=normalize)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (out / "SHA256SUMS").write_text(digest + "  " + archive.name + "\n")
        shutil.copyfile(root / "BUILD.json", out / "BUILD.json")
        print(str(archive), digest)


if __name__ == "__main__":
    main()
