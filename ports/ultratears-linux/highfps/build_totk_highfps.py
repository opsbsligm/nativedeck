"""Reuse existing native objects; compile five changed chunks plus the clock."""
import json
from pathlib import Path
import re
root=Path.home()/'native-recomp'
task=root/'work/totk-1.4.3-20261031'
out=task/'highfps-20261103'
record=json.loads((out/'prepare.json').read_text())
text=(task/'build/build.ninja').read_text()
replacements={}
for item in record['chunks']:
    pattern=r'(?m)^build ([^\n:]+): (cc(?:_recovery)?) '+re.escape(item['original'])+r'$'
    match=re.search(pattern,text);assert match,item['original']
    old=match.group(1);new=str(out/Path(old).name)
    replacements[old]=new
    text=text.replace(match.group(0),f'build {new}: {match.group(2)} {item["candidate"]}')
    # Recovery compile settings belong to the generated chunk and stay in place.
for old,new in replacements.items():
    text=text.replace(' '+old,' '+new)
text=text.replace(str(task/'build/ultratears')+': link',str(out/'ultratears')+': link')
text=text.replace('default '+str(task/'build/ultratears'),'default '+str(out/'ultratears'))
clock=str(out/'nd_totk_timing.o')
lines=text.splitlines()
for i,line in enumerate(lines):
    if line.startswith('build '+str(out/'ultratears')+': link '):
        lines[i]=line+' '+clock
lines.append(f'build {clock}: cc {out}/nd_totk_timing.c')
# The graphics path's old guard excluded 120Hz displays; the paired 60fps
# candidate is safe to use the independent clock on those displays as well.
gfx=root/'ports/ultratears-linux-20261030/source/src/gfx/nvn/hle_nvn.c'
gfxtext=gfx.read_text(); needle=' && g_hz < UNCAPPED_HZ; }'
assert gfxtext.count(needle)==1
gfxcandidate=out/'hle_nvn.c'
# Relative headers stay relative to the original directory via -iquote below.
gfxcandidate.write_text(gfxtext.replace(needle,'; }'))
for i,line in enumerate(lines):
    if line.startswith('build ') and line.endswith(': cc '+str(gfx)):
        old=line.split(':')[0][6:];new=str(out/Path(old).name)
        lines[i]=f'build {new}: cc {gfxcandidate}'
        lines=[s.replace(' '+old,' '+new) for s in lines]
        break
else:raise AssertionError('No graphics compile rule')
text='\n'.join(lines)+'\n'
text=text.replace(' -std=gnu17 ',f' -iquote {gfx.parent} -std=gnu17 ')
# Original objects are immutable link inputs here. Do not emit their rules:
# changing candidate flags must never cause an unrelated baseline recompile.
lines=text.splitlines(); kept=[]; keep=True
for line in lines:
    if line.startswith('build '):
        keep=line.split(':',1)[0].startswith('build '+str(out)+'/')
    elif line and not line.startswith(' '):
        keep=True
    if keep:kept.append(line)
text='\n'.join(kept)+'\n'
# Recovery builds retain an equivalent object in the complete V8 object set.
# Treat it as an external input; never rebuild the full game as a fallback.
for token in re.findall(r'\S+\.o',text):
    if token.startswith(str(task/'build/obj')) and not Path(token).exists():
        fallback=task/'build-cgp-all-v8/obj'/Path(token).name
        assert fallback.is_file(),token
        text=text.replace(token,str(fallback))
(out/'build.ninja').write_text(text)
print('Candidate peak additional files <1.2GiB; one compile job, current deployment preserved.',flush=True)
