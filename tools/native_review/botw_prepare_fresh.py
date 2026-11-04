"""Create a pinned, empty SDK7 build from existing public source and private NSO files."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from apply_botw_controls import apply, apply_diagram
from legacy_sdk7 import verify_exefs

UPSTREAM='4249c880bc6b09ad0207fc3f6e7595346f08d232'

def prepare(upstream,exefs,work,evidence):
    upstream,exefs,work,evidence=map(lambda p:Path(p).resolve(),(upstream,exefs,work,evidence))
    verify_exefs(exefs,['main','subsdk0','sdk'])
    if subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip()!=UPSTREAM:
        raise ValueError('Pinned public upstream moved')
    if (work/'source').exists() or (evidence/'fresh-source.json').exists():
        raise ValueError('Preserve existing source and build evidence')
    source=work/'source'; source.mkdir(parents=True)
    evidence.mkdir(parents=True,exist_ok=True)
    proc=subprocess.Popen(['git','-C',str(upstream),'archive',UPSTREAM],stdout=subprocess.PIPE)
    try:
        subprocess.run(['tar','-x','-C',str(source)],stdin=proc.stdout,check=True)
    finally:
        proc.stdout.close()
        rc=proc.wait()
    if rc:raise ValueError('Pinned source archive failed')
    tools=Path(__file__).resolve().parent
    patches=tools.parents[1]/'patches/botw-sdk7-20261029'
    for name in ['sdk7-native-runtime.patch','sdk7-codegen.patch']:
        subprocess.run(['git','apply','--check',str(patches/name)],cwd=source,check=True)
        subprocess.run(['git','apply',str(patches/name)],cwd=source,check=True)
    shutil.copy2(tools/'legacy_sdk7.py',source/'tools/legacy_sdk7.py')
    destination=source/'extracted/exefs';destination.mkdir(parents=True)
    for name in ['main','subsdk0','sdk']:shutil.copy2(exefs/name,destination/name)
    verify_exefs(destination,['main','subsdk0','sdk'])
    apply(source);apply_diagram(source)
    result={'upstream':UPSTREAM,'source':str(source),'exact_original_inputs_verified':True,
            'game_library_reused':False,'generated_code_reused':False,'xbox_diagram_labels_applied':True}
    with (evidence/'fresh-source.json').open('x') as stream:json.dump(result,stream,indent=2)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['upstream','exefs','work','evidence']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.upstream,args.exefs,args.work,args.evidence)))
