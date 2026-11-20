#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import hashlib,json,os,urllib.request,urllib.error,urllib.parse
from pathlib import Path
TAG='null-native-v0.1.0-alpha-'+os.environ['GITHUB_SHA'][:8]
REPO=os.environ['GITHUB_REPOSITORY']
BASE='https://api.github.com/repos/'+REPO

def request(url,method='GET',obj=None,raw=False):
    data=obj if raw else (json.dumps(obj).encode() if obj is not None else None)
    headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'NULL-Native-release',
             'Content-Type':'application/octet-stream' if raw else 'application/json','X-GitHub-Api-Version':'2022-11-28'}
    with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),timeout=90) as r:return json.load(r)

def main():
    folder=Path('dist');archive=folder/'null-native-0.1.0.tar.gz'
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=(folder/'SHA256SUMS').read_text().split()[0]:raise SystemExit('Checksum mismatch')
    try:request(BASE+'/releases/tags/'+TAG)
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
    else:raise SystemExit('Refusing to overwrite an existing release')
    release=request(BASE+'/releases','POST',{'tag_name':TAG,'target_commitish':os.environ['GITHUB_SHA'],
        'name':'NULL Native 0.1.0-alpha — CUDA development/benchmark, NOT production RPlant',
        'draft':True,'prerelease':True,
        'body':'Original CUDA Equihash (144,5) solver, not a third-party miner wrapper. Host hash vectors, encoding tests and official Rust (48,5) reference cross-check run in CI. GPU execution/performance not validated here. Mandatory GPU self-test before benchmarking. RPlant subscribe/authorize/jobs were observed, but share submission and difficulty normalization are NOT verified; RPlant mining mode is deliberately disabled. Benchmark mode earns no coins. Optional direct-node solo RPC mode is experimental. No developer fee. Test ONE GPU, keep production miners unchanged. Read NULL/README.md on the release tag.'})
    upload=release['upload_url'].split('{')[0]
    for name in (archive.name,'SHA256SUMS','BUILD.json'):
        request(upload+'?name='+urllib.parse.quote(name),'POST',(folder/name).read_bytes(),True)
    print(request(BASE+'/releases/'+str(release['id']),'PATCH',{'draft':False})['html_url'])
if __name__=='__main__':main()
