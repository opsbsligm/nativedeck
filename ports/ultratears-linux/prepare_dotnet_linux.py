"""Install a hash-checked Microsoft SDK under this port only; no system packages."""
from pathlib import Path
import hashlib,json,os,tarfile,time,urllib.request
root=Path.home()/'native-recomp/ports/ultratears-linux-20261030'
deps=root/'deps'; deps.mkdir(exist_ok=True)
url='https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json'
with urllib.request.urlopen(url,timeout=45) as r: metadata=json.load(r)
version='10.0.403'  # Tested SDK; keep in sync with build-native-shaders.sh
file=None
for release in metadata['releases']:
    for sdk in [release.get('sdk',{}),*release.get('sdks',[])]:
        if sdk.get('version')==version:
            file=next((f for f in sdk['files'] if f['rid']=='linux-x64' and f['url'].endswith('.tar.gz')),None)
            if file:break
    if file:break
assert file and file['url'].startswith('https://builds.dotnet.microsoft.com/')
pin=dict(version=version,url=file['url'],sha512=file['hash'],metadata=url)
(root/'evidence/dotnet-sdk-pin.json').write_text(json.dumps(pin,indent=2)+'\n')
print('Official Linux SDK',version,'project-local; peak disk estimate 1.3GiB',flush=True)
archive=deps/f'dotnet-sdk-{version}-linux-x64.tar.gz'
h=hashlib.sha512(); n=0; last=0; t0=time.monotonic()
with urllib.request.urlopen(file['url'],timeout=45) as response,archive.open('wb') as out:
    while chunk:=response.read(4*1024*1024):
        n+=len(chunk)
        if n>450*1024*1024:raise RuntimeError('SDK archive exceeds bound')
        out.write(chunk);h.update(chunk)
        if n-last>=16*1024*1024:
            print(f'downloaded {n/2**20:.0f}MiB elapsed {time.monotonic()-t0:.0f}s',flush=True);last=n
assert h.hexdigest().lower()==file['hash'].lower(),'SDK SHA512 differs'
target=deps/f'dotnet-{version}'
assert not target.exists(),'Refusing to overwrite SDK directory'
with tarfile.open(archive,'r:gz') as tar:
    assert sum(m.size for m in tar.getmembers() if m.isfile())<1200*1024*1024
    target.mkdir()
    tar.extractall(target,filter='data')
print('SDK verified and extracted:',target,flush=True)
