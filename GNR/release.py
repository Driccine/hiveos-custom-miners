#!/usr/bin/env python3
"""Publish only after successful tests, build and package validation."""
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

TAG = 'gnr-hiveos-v1.2.0'
BASE = 'https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY']
TOKEN = os.environ['GITHUB_TOKEN']


def request(url, method='GET', data=None, binary=False):
    body = data if binary else (json.dumps(data).encode() if data is not None else None)
    headers = {'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json',
               'User-Agent': 'gnr-hiveos-release', 'X-GitHub-Api-Version': '2022-11-28'}
    if data is not None:
        headers['Content-Type'] = 'application/octet-stream' if binary else 'application/json'
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=90) as response:
        return json.load(response)


def main():
    folder = Path(sys.argv[1])
    archive = folder / 'gnr-hiveos-1.2.0.tar.gz'
    expected = (folder / 'SHA256SUMS').read_text().split()[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise SystemExit('Artifact checksum mismatch')
    try:
        request(BASE + '/releases/tags/' + TAG)
    except urllib.error.HTTPError as exc:
        if exc.code != 404: raise
    else:
        raise SystemExit('Release already exists; refusing to overwrite it')
    release = request(BASE + '/releases', 'POST', {
        'tag_name': TAG, 'target_commitish': os.environ['GITHUB_SHA'],
        'name': 'GNR HiveOS 1.2.0 - shared node coordinator for parallel GPUs',
        'draft': True, 'prerelease': True,
        'body': 'Fix for too many requests on multi-GPU rigs. Parallel GPU workers share one loopback-only coordinator: cached templates (3s default), HTTP 429 Retry-After/backoff, real per-GPU statistics, staggered startup, safe process cleanup. No fee or wallet change. Same unmodified krypton-miner 1.0.37 rebuilt from pinned source on Ubuntu 20.04. Python >=3.8 and glibc >=2.31. Tests include simulated 12-client HTTP load and 12 fake miner processes; **real 12-GPU performance and payments are not yet validated**. See GNR/README.md for the Flight Sheet and limits across multiple rigs on one public IP.'})
    upload = release['upload_url'].split('{')[0]
    for name in (archive.name, 'SHA256SUMS', 'BUILD.json'):
        request(upload + '?name=' + urllib.parse.quote(name), 'POST', (folder / name).read_bytes(), binary=True)
    result = request(BASE + '/releases/' + str(release['id']), 'PATCH', {'draft': False})
    print(result['html_url'])


if __name__ == '__main__': main()
