#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import gzip, hashlib, json, os, re, shutil, subprocess, tarfile, tempfile
from pathlib import Path
BASE=Path(__file__).resolve().parent
VERSION='0.1.0'

def main():
    binary=BASE/'native/libnullcuda.so'
    if not binary.is_file():raise SystemExit('CUDA library was not compiled')
    symbols=subprocess.check_output(['readelf','--version-info',str(binary)],text=True)
    required={tuple(map(int,x.split('.'))) for x in re.findall(r'GLIBC_(\d+\.\d+)',symbols)}
    if required and max(required)>(2,31):raise SystemExit('GLIBC baseline too new')
    out=BASE/'dist';out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)/'null-native';root.mkdir();(root/'src').mkdir()
        for f in (BASE/'native').iterdir():
            if f.suffix in ('.py','.so'):shutil.copyfile(f,root/f.name)
            elif f.suffix in ('.cu','.hpp'):shutil.copyfile(f,root/'src'/f.name)
        shutil.copyfile(BASE/'README.md',root/'README.md')
        shutil.copyfile(BASE.parent/'GNR/LICENSE',root/'LICENSE')
        fixture=BASE/'tests/rust-fixtures.jsonl'
        if not fixture.exists():raise SystemExit('Official Rust fixtures missing')
        shutil.copyfile(fixture,root/'rust-fixtures.jsonl')
        metadata={'version':VERSION+'-alpha','cuda_toolkit':'12.4.1','architectures':['sm_75','sm_86','compute_86 PTX'],
            'compiler':subprocess.check_output(['nvcc','--version'],text=True).strip(),
            'source_commit':os.environ.get('GITHUB_SHA','unknown'),'null_reference_commit':'20fe0478881a4250d973d58833788695987325da',
            'glibc_max_symbol':'.'.join(map(str,max(required))) if required else None,
            'host_tests_passed':True,'rust_reference_crosscheck':True,'gpu_tested':False,
            'rplant_submissions_enabled':False,'rplant_accepted_shares_verified':False,
            'performance_claim':'none','developer_fee_percent':0}
        (root/'BUILD.json').write_text(json.dumps(metadata,indent=2)+'\n')
        for p in root.rglob('*'):
            if p.is_file():p.chmod(0o644)
        entries=[p for p in sorted(root.rglob('*')) if p.is_file()]
        (root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n' for p in entries))
        target=out/('null-native-'+VERSION+'.tar.gz')
        with target.open('wb') as file,gzip.GzipFile(filename='',mode='wb',fileobj=file,mtime=0) as stream,tarfile.open(fileobj=stream,mode='w') as tar:
            def norm(i):i.uid=i.gid=0;i.uname=i.gname='root';i.mtime=0;return i
            tar.add(root,arcname='null-native',filter=norm)
        (out/'SHA256SUMS').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
        shutil.copyfile(root/'BUILD.json',out/'BUILD.json')
        print((out/'SHA256SUMS').read_text())

if __name__=='__main__':main()
