"""Build a separate, guarded timing candidate from existing static codegen.

Only affected functions are re-emitted. Every input opcode is verified against
the public upstream v1.4.3 port; baseline re-emission must equal the installed
generator's original output. Original generated files and ELF remain unchanged.
"""
import bisect
import hashlib
import json
from pathlib import Path
import re
import sys

def require(condition, message='High-fps validation failed'):
    if not condition:
        raise ValueError(message)

root = Path.home() / 'native-recomp'
task = root / 'work/totk-1.4.3-20261031'
source = root / 'ports/ultratears-linux-20261030/source'
out = task / 'highfps-20261103'
out.mkdir(exist_ok=True)
sys.path.insert(0, str(source / 'tools/lifter'))
from gen import Module, PATCHES
base = 0x800000000
m = Module('main', task / 'input/exefs/main', base, 'c')
fps = {0x2db204:(0x6b08015f,0x7100055f),0x2db208:(0x1a89b10a,0x1a9fa52a),
       0x2db22c:(0xb940468a,0xd503201f),0x2db360:(0x6b0801bf,0x710005bf),
       0x2db36c:(0x1a88c1ac,0x1a9fc5ac),0x2db340:(0xb9400288,0x52800028),
       0x2db34c:(0x2a0a03f5,0x1a9fa555)}
guard = {0x3e5658:0x1e210808,0x2daa54:0xbd425260,0x2daa58:0x52a84e08,
         0x2daa6c:0x5e21d800,0x2daa70:0x1e201820,0x2daa74:0x1e2c1001,0x2daa78:0x1e210800,
         0x246eac:0x1e200940,0x345904:0x1e210801,0x24944c:0x94015e7d,0x28bc98:0x9400546a}
for off, (old, _) in fps.items(): guard[off] = old
for off, old in guard.items():
    require(m.word(base+off) == old, f'Unexpected v1.4.3 instruction at {off:#x}')

generated = task / 'data/generated/main'
table = (generated / 'main_table.c').read_text()
addresses = sorted(set(int(a,16) for a in re.findall(r'void f_([0-9a-f]+)\(Cpu \*c\);',table)))
functions = {}
for off in guard:
    i = bisect.bisect_right(addresses,base+off)-1
    start,end = addresses[i],addresses[i+1]
    functions[start] = (end, *m.scan(start,end)[::2])  # end, labels, tables

chunks = {}
for p in generated.glob('main_*.c'):
    if p.name=='main_table.c': continue
    text = p.read_text()
    for start,(end,labels,tables) in functions.items():
        marker=f'void f_{start:x}(Cpu *c) {{\n'
        at=text.find(marker)
        if at<0: continue
        stop=text.index('\n}\n',at)+3
        old=text[at:stop]
        regenerated='\n'.join(m.emit_function(start,end,labels,tables,{}))+'\n'
        require(regenerated==old, f'Baseline re-emission drift: {p.name} {start:x}')
        chunks.setdefault(p,[]).append((start,end,labels,tables,old))
require(sum(map(len,chunks.values()))==len(functions), 'High-fps validation failed')

for off,(_,new) in fps.items():
    ins=m.lifter.lift(new,base+off)
    require(ins.kind=='op', 'High-fps validation failed')
    PATCHES[base+off]=lambda gen,a,code=ins.code:code
for off in [0x2daa58,0x2daa6c,0x2daa70,0x2daa74,0x2daa78]:
    PATCHES[base+off]=lambda gen,a:'; /* replaced by measured frame ratio */'
PATCHES[base+0x2daa54]=lambda gen,a:'FP_SETS(0, nd_totk_step(30.0f));'
original=m.lifter.lift(guard[0x3e5658],base+0x3e5658).code
PATCHES[base+0x3e5658]=lambda gen,a:'FP_SETS(0, nd_totk_step(60.0f)); '+original
PATCHES[base+0x246eac]=lambda gen,a:('{ float factor=nd_totk_reg(c,10); '
    'FP_SETS(0,nd_totk_step(30.0f)*factor); ST32(c->sp+0x364,VS32(0)); '
    'FP_SETS(0,nd_totk_step(1.0f)*factor); }')
PATCHES[base+0x345904]=lambda gen,a:('{ float factor=nd_totk_reg(c,0); '
    'FP_SETS(1,nd_totk_step(30.0f)*factor); ST32(c->sp+0x114,VS32(1)); '
    'FP_SETS(1,nd_totk_step(1.0f)*factor); }')
for off in [0x24944c,0x28bc98]:
    PATCHES[base+off]=lambda gen,a:('FP_SETS(2,nd_totk_reg(c,2)*nd_totk_step(30.0f)); '
       'FP_SETS(3,nd_totk_reg(c,3)*nd_totk_step(30.0f)); '
       f'c->x[30]={a+4:#x}ull; f_8002a0e40(c);')

receipt=[]
for p, rows in chunks.items():
    text=p.read_text()
    declarations=set()
    for start,end,labels,tables,old in rows:
        new='\n'.join(m.emit_function(start,end,labels,tables,{}))+'\n'
        declarations.update(m._refs)
        require(text.count(old)==1, 'High-fps validation failed')
        text=text.replace(old,new)
    header=f'#include "{out}/nd_totk_timing.h"\n'
    header+=''.join(f'void f_{a:x}(Cpu *c);\n' for a in sorted(declarations))
    dest=out/p.name;dest.write_text(header+text)
    receipt.append({'original':str(p),'candidate':str(dest),'functions':[f'{x[0]:x}' for x in rows],
                    'original_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                    'candidate_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
(out/'prepare.json').write_text(json.dumps({'verified_sites':len(guard),'chunks':receipt},indent=2))
print(json.dumps({'verified_sites':len(guard),'changed_chunks':[p.name for p in chunks]},indent=2))
