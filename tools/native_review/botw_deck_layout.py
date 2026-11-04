"""Reposition the private SDK7 help callouts to the authored Steam Deck artwork.

Requires oead==1.3.0. Rebuild only one SARC member, verify all other members and
the compression roundtrip, never overwrite an existing input or output file.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

SOURCE_SHA='8bf0fad6b6297a9357817b9628ad0989dad4f3989d9e08d6181bee50c888e443'
LAYOUT_SHA='2a9b54ff5e42f40e750f90becb3eb3ab820a3f94bed3e129c6de50b4e3991635'
LAYOUT='blyt/PaAllControllerTipsNN_00.bflyt'
# Source texture coordinates -> authored Deck coordinates; BFLYT has Y up.
MOVES={'left_stick':(58,88,88,88),'right_stick':(517,152,470,88),
       'dpad':(58,152,38,65),'view':(81,54,126,54),'menu':(494,54,450,54)}

def patch_layout(data):
    if hashlib.sha256(data).hexdigest()!=LAYOUT_SHA:
        raise ValueError('Unsupported private help layout; no changes')
    result=bytearray(data);at=20;stack=[];last='';changes=[];connectors=[]
    def delta(name):
        x,y,a,b=MOVES[name];return (a-x)*.67,(y-b)*.67
    while at<len(data):
        tag=data[at:at+4];size=struct.unpack_from('<I',data,at+4)[0]
        if size<8 or at+size>len(data):raise ValueError('Invalid BFLYT section')
        if tag in (b'pan1',b'pic1',b'txt1',b'bnd1',b'wnd1',b'prt1'):
            last=data[at+12:at+36].split(b'\0')[0].decode();move=None
            if last.startswith('N_OpenRStickPress_'):move=delta('right_stick')
            elif last.startswith('N_CrossKey_'):move=delta('dpad')
            elif last in ('N_Line_00','N_Line_08','N_Line_10') and len(stack)==3:move=delta('left_stick')
            elif last.startswith('N_OpenPlusMinus_'):move=delta('menu')
            elif last.startswith('N_Minus_'):
                a,b=delta('view');c,d=delta('menu');move=(a-c,b-d)
            if move:
                x,y=struct.unpack_from('<2f',data,at+44)
                struct.pack_into('<2f',result,at+44,x+move[0],y+move[1])
                changes.append({'pane':last,'before':[x,y],'after':[x+move[0],y+move[1]]})
            # Keep the left hint bracket attached to the unchanged text box,
            # while extending the line to the relocated left thumbstick.
            if tag==b'pic1' and stack and stack[-1] in ('N_Line_00','N_Line_08','N_Line_10'):
                x=struct.unpack_from('<f',data,at+44)[0]
                shift=delta('left_stick')[0]
                if x<=-50:
                    struct.pack_into('<f',result,at+44,x-shift)
                    connectors.append({'pane':last,'property':'x','before':x,'after':x-shift})
                elif x==-16 and struct.unpack_from('<f',data,at+64)[0]==0:
                    width=struct.unpack_from('<f',data,at+76)[0]
                    struct.pack_into('<f',result,at+76,width+shift)
                    connectors.append({'pane':last,'property':'width','before':width,'after':width+shift})
        elif tag==b'pas1':stack.append(last)
        elif tag==b'pae1':stack.pop()
        at+=size
    if len(changes)!=15 or len(connectors)!=12:raise ValueError('Expected 15 control groups and 12 left hint connector adjustments')
    return bytes(result),changes+connectors

def build(source,destination):
    import oead
    source,destination=Path(source),Path(destination)
    data=source.read_bytes()
    if destination.exists() or source.resolve()==destination.resolve():raise ValueError('Do not overwrite private inputs or prior output')
    if hashlib.sha256(data).hexdigest()!=SOURCE_SHA:raise ValueError('Unsupported original Bootup pack')
    pack=oead.Sarc(data)
    compressed=bytes(pack.get_file('Layout/Common.sblarc').data)
    common=oead.Sarc(oead.yaz0.decompress(compressed))
    layout,changes=patch_layout(bytes(common.get_file(LAYOUT).data))
    writer=oead.SarcWriter.from_sarc(common);writer.files[LAYOUT]=layout
    alignment,new_common=writer.write()
    encoded=bytes(oead.yaz0.compress(new_common,alignment))
    if bytes(oead.yaz0.decompress(encoded))!=bytes(new_common):raise ValueError('Yaz0 roundtrip failed')
    rebuilt=oead.Sarc(new_common)
    for member in common.get_files():
        expected=layout if member.name==LAYOUT else bytes(member.data)
        if bytes(rebuilt.get_file(member.name).data)!=expected:raise ValueError('Unrelated layout content changed')
    outer=oead.SarcWriter.from_sarc(pack);outer.files['Layout/Common.sblarc']=encoded
    _,result=outer.write();check=oead.Sarc(result)
    for member in pack.get_files():
        expected=encoded if member.name=='Layout/Common.sblarc' else bytes(member.data)
        if bytes(check.get_file(member.name).data)!=expected:raise ValueError('Unrelated Bootup content changed')
    with destination.open('xb') as stream:stream.write(bytes(result))
    if destination.read_bytes()!=bytes(result):raise ValueError('Pack readback failed')
    return {'source_sha256':SOURCE_SHA,'output_sha256':hashlib.sha256(result).hexdigest(),
            'output_bytes':len(result),'changed_members':[LAYOUT],'callouts':changes,
            'other_members_unchanged':True,'compression_roundtrip':True,'control_locations':MOVES}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    parser.add_argument('--manifest',type=Path,required=True)
    args=parser.parse_args()
    if args.manifest.exists():raise ValueError('Preserve existing layout manifest')
    result=build(args.source,args.destination)
    with args.manifest.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))
