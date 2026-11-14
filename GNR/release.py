#!/usr/bin/env python3
"""Create a draft release, upload validated artifacts, then publish. No trading."""
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

TAG = "gnr-hiveos-v1.0.0"
REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
BASE = "https://api.github.com/repos/" + REPO


def request(url, method="GET", data=None, binary=False):
    body = data if binary else (json.dumps(data).encode() if data is not None else None)
    headers = {"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json",
               "User-Agent": "gnr-hiveos-release", "X-GitHub-Api-Version": "2022-11-28"}
    if data is not None:
        headers["Content-Type"] = "application/octet-stream" if binary else "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=90) as response:
        return json.load(response)


def main():
    folder = Path(sys.argv[1])
    archive = folder / "gnr-hiveos-1.0.0.tar.gz"
    expected = (folder / "SHA256SUMS").read_text().split()[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise SystemExit("Artifact checksum mismatch")
    try:
        request(BASE + "/releases/tags/" + TAG)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    else:
        raise SystemExit("This release already exists; refusing to overwrite it")
    release = request(BASE + "/releases", "POST", {
        "tag_name": TAG, "target_commitish": os.environ["GITHUB_SHA"],
        "name": "GNR HiveOS 1.0.0 - krypton-miner 1.0.37",
        "draft": True, "prerelease": True,
        "body": "Custom HiveOS NVIDIA package. Upstream pinned to genoryn/genoryn@5532d04ba7bdf3362f97a560437694fddb0bddc5; rebuilt on Ubuntu 20.04, CUDA only. Requires glibc >= 2.31 and Python >= 3.8. No Docker, compilation, system-library upgrades or private keys on the rig. Wrapper tests and binary CLI smoke tests run in CI. **GPU mining and live payouts have not been validated on hardware: test one GPU first.** Use the FULL public gnr1 address, not gnrs1. See GNR/README.md for the Flight Sheet."})
    upload = release["upload_url"].split("{")[0]
    for name in (archive.name, "SHA256SUMS", "BUILD.json"):
        request(upload + "?name=" + urllib.parse.quote(name), "POST", (folder / name).read_bytes(), binary=True)
    result = request(BASE + "/releases/" + str(release["id"]), "PATCH", {"draft": False})
    print(result["html_url"])


if __name__ == "__main__":
    main()
