"""Send a bounded event through Steam's existing virtual Xbox device and read guest input trace.

This validates the software input path. It does not mechanically press handheld
buttons or test Steam/Home/Capture keys, and it changes no controller settings.
"""
import argparse
import fcntl
import json
import os
import re
import struct
import subprocess
import time
from pathlib import Path

CASES={
    'A':(1,304,1,'south'),'B':(1,305,1,'east'),'X':(1,307,1,'west'),'Y':(1,308,1,'north'),
    'LB':(1,310,1,'lshoulder'),'RB':(1,311,1,'rshoulder'),
    'LS':(1,317,1,'lstick'),'RS':(1,318,1,'rstick'),
    'View':(1,314,1,'back'),'Menu':(1,315,1,'start'),
    'DLeft':(3,16,-1,'dpad_left'),'DRight':(3,16,1,'dpad_right'),
    'DUp':(3,17,-1,'dpad_up'),'DDown':(3,17,1,'dpad_down'),
    'LT':(3,2,'max','ltrigger'),'RT':(3,5,'max','rtrigger'),
    'LX-':(3,0,'min',16),'LX+':(3,0,'max',18),
    'LY-':(3,1,'min',17),'LY+':(3,1,'max',19),
    'RX-':(3,3,'min',20),'RX+':(3,3,'max',22),
    'RY-':(3,4,'min',21),'RY+':(3,4,'max',23),
}
SLOTS=['a','b','x','y','lstick','rstick','l','r','zl','zr','plus','minus','left','up','right','down']
DEFAULTS=['east','south','north','west','lstick','rstick','lshoulder','rshoulder','ltrigger','rtrigger',
          'start','back','dpad_left','dpad_up','dpad_right','dpad_down']


def device():
    for block in Path('/proc/bus/input/devices').read_text().split('\n\n'):
        if 'Vendor=28de Product=11ff' not in block or 'Microsoft X-Box 360 pad' not in block:
            continue
        match=re.search(r'^H: Handlers=.*\b(event\d+)\b',block,re.M)
        if match:return Path('/dev/input')/match.group(1)
    raise ValueError('Expected Steam virtual Xbox controller is missing')


def probe(name,hold=0.2):
    pids=subprocess.check_output(['pgrep','-x','savagewind'],text=True).split()
    if len(pids)!=1:raise ValueError('Expected one running BOTW')
    environ={}
    for row in (Path('/proc')/pids[0]/'environ').read_bytes().split(b'\0'):
        if b'=' in row:
            key,value=row.split(b'=',1)
            if key in (b'SAVAGEWIND_DATA_ROOT',b'SAVAGEWIND_INPUT',b'SAVAGEWIND_NO_USER_INPUT'):
                environ[key.decode()]=value.decode()
    if environ.get('SAVAGEWIND_INPUT')!='' or environ.get('SAVAGEWIND_NO_USER_INPUT')!='0':
        raise ValueError('Explicit input audit must be enabled with real input retained')
    data=Path(environ['SAVAGEWIND_DATA_ROOT'])
    settings=(data/'savagewind.ini').read_text()
    bindings=dict(zip(SLOTS,DEFAULTS))
    for slot,host in re.findall(r'(?m)^bind_pad_(\w+)\s*=\s*(\w+)\s*$',settings):
        if slot in bindings:bindings[slot]=host
    typ,code,value,host=CASES[name]
    expected=(1<<host) if isinstance(host,int) else sum(1<<SLOTS.index(slot) for slot,target in bindings.items() if target==host)
    log=data/'savagewind.log'
    start=log.stat().st_size
    path=device()
    fd=os.open(path,os.O_RDWR|os.O_NONBLOCK)
    pressed=False
    def event(typ,code,value):
        os.write(fd,struct.pack('llHHi',0,0,typ,code,value)+struct.pack('llHHi',0,0,0,0,0))
    restore=0
    try:
        identity=bytearray(8);fcntl.ioctl(fd,0x80084502,identity,True)
        if struct.unpack('4H',identity)[1:3]!=(0x28de,0x11ff):raise ValueError('Controller identity changed')
        if typ==3:
            info=bytearray(24);fcntl.ioctl(fd,0x80184540+code,info,True)
            current,minimum,maximum,_,_,_=struct.unpack('6i',info)
            restore=current
            value=maximum if value=='max' else minimum if value=='min' else value
        else:
            state=bytearray(128);fcntl.ioctl(fd,0x80804518,state,True)
            restore=(state[code//8]>>(code%8))&1
            if restore:raise ValueError('Physical/user input is already holding this button; preserve it')
        event(typ,code,value)
        pressed=True
        time.sleep(hold)
    finally:
        try:
            if pressed:event(typ,code,restore)
        finally:os.close(fd)
    deadline=time.monotonic()+1.5
    while True:
        time.sleep(0.05)
        with log.open('rb') as stream:stream.seek(start);tail=stream.read().decode(errors='replace')
        masks=[int(v,0) for v in re.findall(r'\[input\] id 0 buttons (0x[0-9a-f]+|0)\b',tail)]
        matched=any((mask&0xffff)==expected for mask in masks) if expected<=0xffff else expected in masks
        if (matched and 0 in masks) or time.monotonic()>=deadline:break
    return {'case':name,'device':str(path),'pid':int(pids[0]),'expected_guest_mask':hex(expected),
            'observed_guest_masks':[hex(mask) for mask in masks],
            'software_input_path_passed':matched and 0 in masks,
            'physical_button_actuation_tested':False,'restored_host_value':restore}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case',choices=CASES)
    args=parser.parse_args()
    result=probe(args.case)
    print(json.dumps(result))
    raise SystemExit(0 if result['software_input_path_passed'] else 1)
