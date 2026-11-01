#!/usr/bin/env python3
"""Independent reopened-byte validator: separate transforms/evaluator; no builder imports."""
import argparse
import ast
import collections
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('resource_reader',HERE/'resource_layout.py');R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
CONTROL={'ZL':('left_trigger',),'ZR':('right_trigger',),'L':('left_bumper',),'R':('right_bumper',),'Minus_00':('view',),'Plus':('menu',),'LStick':('left_stick',),'RStick':('right_stick',),'CrossKey':('dpad_center',),'ABXY':('face_south','face_east','face_west','face_north')}
LAYOUT='blyt/PaSystemController_00.bflyt';PATTERN='anim/PaSystemController_00_Pattern.bflan';HORSE='anim/PaSystemController_00_IsHorse.bflan'

def sha(b):return hashlib.sha256(b).hexdigest()
def channel_raw(b,c):
    end=max(k['offset']+(12 if c['data_type']==2 else 8) for k in c['keys']);return b[c['offset']:end]

def value(c,f,side):
    keys=c['keys'];eq=[k for k in keys if k['frame']==f]
    if eq:return eq[-1 if side=='right' else 0]['value']
    if f<keys[0]['frame']:return keys[0]['value']
    if f>keys[-1]['frame']:return keys[-1]['value']
    lo=max((k for k in keys if k['frame']<f),key=lambda k:k['frame']);hi=min((k for k in keys if k['frame']>f),key=lambda k:k['frame'])
    if c['data_type']==1:return lo['value']
    length=hi['frame']-lo['frame'];t=(f-lo['frame'])/length
    return (1-3*t*t+2*t*t*t)*lo['value']+(t-2*t*t+t*t*t)*length*lo['slope']+(3*t*t-2*t*t*t)*hi['value']+(t*t*t-t*t)*length*hi['slope']

def affine_mul(a,b):
    A,B,C,D,X,Y=a;e,f,g,h,x,y=b
    return (A*e+B*g,A*f+B*h,C*e+D*g,C*f+D*h,A*x+B*y+X,C*x+D*y+Y)
def point(a,p):A,B,C,D,X,Y=a;return [A*p[0]+B*p[1]+X,C*p[0]+D*p[1]+Y]
def inverse(a,p):
    A,B,C,D,X,Y=a;det=A*D-B*C;x,y=p[0]-X,p[1]-Y;assert abs(det)>1e-9;return [(D*x-B*y)/det,(-C*x+A*y)/det]
def rectangle(p,v):
    f=p['origin_flags'];w,h=v['width'],v['height'];left=(-w/2,0,-w)[f&3];top=(h/2,0,h)[(f>>2)&3]
    return left,top,w,h

def scene(l,pattern,horse,frame,riding,side):
    changes=collections.defaultdict(dict)
    for anim,f in [(pattern,frame),(horse,riding)]:
        if not anim:continue
        for e in anim['entries']:
            if e['target_type']!=0:continue
            for c in e['channels']:
                if c['tag']=='FLPA':changes[e['name']][c['property']]=value(c,f,side)
    result={};ordered=[]
    for p in l['panes']:
        v=dict(p['values']);v.update(changes[p['name']]);assert v['rotation_x']==v['rotation_y']==0 and p['origin_flags']<16
        angle=v['rotation_z']*math.pi/180;co,si=math.cos(angle),math.sin(angle);local=(co*v['scale_x'],-si*v['scale_y'],si*v['scale_x'],co*v['scale_y'],v['translation_x'],v['translation_y'])
        a=affine_mul(ordered[p['parent']]['affine'],local) if p['parent'] is not None else local
        left,top,w,h=rectangle(p,v);g=dict(affine=a,values=v,origin=point(a,[0,0]),center=point(a,[left+w/2,top-h/2]),quad=[point(a,q) for q in [[left,top],[left+w,top],[left,top-h],[left+w,top-h]]]);ordered.append(g);result[p['name']]=g
    return result

def groups(l,animations,c):
    pmap={p['name']:p for p in l['panes']};names=[e['name'] for e in animations['PaSystemController_00_OnOff_'+c]['entries']];roots=[pmap[n] for n in names];ps=[p for p in l['panes'] if any(p['path']==r['path'] or p['path'].startswith(r['path']+'/') for r in roots)]
    def only(prefix):
        x=[p for p in ps if p['name'].startswith(prefix)];assert len(x)==1;return x[0]['name']
    return dict(horizontal=only('P_Horizon'),vertical=only('P_Verti'),marker=only(('P_Circle','W_Circle')))

def support_points(control,records,doc):
    # Independent implementation of pixel coverage and restricted projection.
    def expr(text,x,y):
        nodes=ast.parse(text,mode='eval')
        assert len(list(ast.walk(nodes)))<=128
        def calc(n):
            if type(n) is ast.Expression:return calc(n.body)
            if type(n) is ast.Constant and type(n.value) in (int,float):return float(n.value)
            if type(n) is ast.Name and n.id in ('x','y'):return {'x':x,'y':y}[n.id]
            if type(n) is ast.UnaryOp and type(n.op) in (ast.USub,ast.UAdd):return -calc(n.operand) if type(n.op) is ast.USub else calc(n.operand)
            assert type(n) is ast.BinOp
            a,b=calc(n.left),calc(n.right)
            if type(n.op) is ast.Add:return a+b
            if type(n.op) is ast.Sub:return a-b
            if type(n.op) is ast.Mult:return a*b
            assert type(n.op) is ast.Div
            return a/b
        v=calc(nodes);assert math.isfinite(v);return v
    if control in doc.get('group_coverage',{}):return doc['group_coverage'][control]
    ids=CONTROL[control] if control in ('ABXY','CrossKey') else ()
    result=[]
    for key in ids:
        a=records[key];px,py=a['pixel']
        if 'coverage_points' in a:result.extend(a['coverage_points']);continue
        if 'coverage_bounds' in a:
            x0,y0,x1,y1=a['coverage_bounds'];result.extend([[x,y] for x in (x0,x1) for y in (y0,y1)]);continue
        if 'coverage_radius' in a:
            r=a['coverage_radius'];result.extend([[px+i*r,py+j*r] for i in (-1,1) for j in (-1,1)]);continue
        t=doc.get('transform',{})
        if a.get('source') is not None and all(k in t for k in ('x','y')):
            x,y=a['source'];base=[expr(t[k],x,y) for k in ('x','y')]
            shapes=[(10.,10.)] if control=='ABXY' else [(6.,19.),(19.,6.)]
            for hx,hy in shapes:
                for i in (-1,1):
                    for j in (-1,1):result.append([px+expr(t['x'],x+i*hx,y+j*hy)-base[0],py+expr(t['y'],x+i*hx,y+j*hy)-base[1]])
        else:
            r=10. if control=='ABXY' else 19.;result.extend([[px+i*r,py+j*r] for i in (-1,1) for j in (-1,1)])
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('patch',type=Path);ap.add_argument('--output-name',default='verification.json');args=ap.parse_args();patch=args.patch.resolve()
    if not __debug__:raise SystemExit('Do not run this validator with Python -O')
    mf=json.loads((patch/'manifest.json').read_text());metadata=json.loads(Path(mf['metadata']).read_text());root=Path(mf['source_root']);anchors={a['id']:a['pixel'] for a in mf['anchor_document']['anchors']};anchor_records={a['id']:a for a in mf['anchor_document']['anchors']}
    assert mf['display_art']=='unified-steamdeck-inclined' and mf['complete_10_groups'] is True
    anchor_bytes=Path(mf['anchor_path']).read_bytes();assert sha(anchor_bytes)==mf['anchor_sha256'] and json.loads(anchor_bytes)==mf['anchor_document'], 'Anchor source drift'
    expected_controls=set(CONTROL)
    assert set(mf['controls_patched'])==expected_controls and all(i in anchors for ids in CONTROL.values() for i in ids)
    assert mf['missing_anchor_ids']==[]
    assert mf['runtime_texture_whitelist']==sorted('Controller_'+kind+suffix+'^w' for kind in ['Console','Grip','Pro'] for suffix in ['', '1'])
    original={};output={};oldlayouts={};newlayouts={};oldanims={};newanims={};checks=collections.Counter()
    for entry in metadata['members']:
        n=entry['name']
        if not n.endswith(('.bflyt','.bflan')):continue
        b=(root/n).read_bytes();o=(patch/n).read_bytes();assert len(b)==entry['bytes'] and sha(b)==entry['sha256'];original[n]=b;output[n]=o
        if n.endswith('.bflyt'):oldlayouts[Path(n).stem]=R.parse_layout(b);newlayouts[Path(n).stem]=R.parse_layout(o)
        else:oldanims[Path(n).stem]=R.parse_animation(b);newanims[Path(n).stem]=R.parse_animation(o)
        checks['original_sha256_unchanged']+=1
    assert len(original)==23
    file_manifest={f['name']:f for f in mf['files']};assert set(file_manifest)==set(original)
    for n,b in original.items():
        f=file_manifest[n];assert f['original_sha256']==sha(b) and f['patch_sha256']==sha(output[n]) and f['original_bytes']==len(b) and f['patch_bytes']==len(output[n]) and f['changed']==(b!=output[n]);checks['manifest_hashes_and_sizes_readback']+=1
    for n in original:
        if n not in [LAYOUT,PATTERN]:assert original[n]==output[n];checks['unrelated_files_byte_exact']+=1
    l=oldlayouts['PaSystemController_00'];nl=newlayouts['PaSystemController_00'];group={c:groups(l,oldanims,c) for c in mf['controls_patched']};pmap={p['name']:p for p in l['panes']};allow={}
    for c,g in group.items():
        allow[g['horizontal']]={'width','rotation_z'};allow[g['vertical']]={'translation_x','translation_y','height'};allow[g['marker']]={'translation_x','translation_y','rotation_z'}|({'width','height'} if c in ['ABXY','CrossKey'] else set())
    offsets={byte for n,props in allow.items() for prop in props for byte in range(pmap[n]['field_offsets'][prop],pmap[n]['field_offsets'][prop]+4)}
    assert len(original[LAYOUT])==len(output[LAYOUT])
    diffs=[i for i,(x,y) in enumerate(zip(original[LAYOUT],output[LAYOUT])) if x!=y];assert set(diffs)<=offsets;checks['layout_changed_bytes_allowlisted']=len(diffs)
    # All source sections other than targeted pane floats remain byte-identical.
    for p in l['panes']:
        if p['name'] not in allow:
            s=next(s for s in l['sections'] if s['offset']==p['offset']);assert original[LAYOUT][p['offset']:p['offset']+s['size']]==output[LAYOUT][p['offset']:p['offset']+s['size']];checks['unrelated_panes_byte_exact']+=1
    oa=oldanims['PaSystemController_00_Pattern'];na=newanims['PaSystemController_00_Pattern'];ob=original[PATTERN];nb=output[PATTERN]
    assert ob[:12]==nb[:12] and ob[16:20]==nb[16:20]
    for s in oa['sections']:
        t=next(s2 for s2 in na['sections'] if s2['tag']==s['tag'])
        if s['tag']!='pai1':assert ob[s['offset']:s['offset']+s['size']]==nb[t['offset']:t['offset']+t['size']];checks['animation_other_sections_byte_exact']+=1
        else:
            assert s['offset']==t['offset'];o=s['offset'];a=ob[o:o+s['size']];b=nb[o:o+s['size']];assert all(x==y for i,(x,y) in enumerate(zip(a,b)) if i not in set(range(4,8))|set(range(16,20)));checks['original_pai1_bytes_preserved_except_two_header_fields']=len(a)-8
    assert len(oa['entries'])==len(na['entries'])
    em={e['name']:e for e in na['entries']}
    for old in oa['entries']:
        new=em[old['name']];assert old['target_type']==new['target_type']
        assert ob[old['offset']:old['offset']+32]==nb[new['offset']:new['offset']+32];checks['active_entry_headers_byte_exact']+=1
        oldcs={(c['tag'],c['index'],c['target']):c for c in old['channels']};newcs={(c['tag'],c['index'],c['target']):c for c in new['channels']}
        assert len(oldcs)==len(old['channels']) and len(newcs)==len(new['channels'])
        for key,c in oldcs.items():
            cc=newcs[key]
            if c['tag']=='FLPA' and c['property'] in allow.get(old['name'],set()):continue
            assert channel_raw(ob,c)==channel_raw(nb,cc),(old['name'],key);checks['unrelated_animation_channels_byte_exact']+=1
        for key,c in newcs.items():
            if key not in oldcs:assert c['tag']=='FLPA' and c['property'] in allow.get(old['name'],set());checks['new_flpa_channels_allowlisted']+=1
        if old['name'] not in allow:assert oldcs.keys()==newcs.keys()
    # Independently recompute scenes from reopened float bytes with independent affine math.
    child=newlayouts['PaController_00'];cg=scene(child,None,None,0,0,'right');imagepane=next(p for p in child['panes'] if p['name']=='P_Controller_00');left,top,w,h=rectangle(imagepane,imagepane['values']);records=[];max_error=0.;max_label=0.;coverage_count=0
    for side,mode in [('right',0),('right',1),('right',2),('left',1),('left',2)]:
        for riding in range(2):
            oldg=scene(l,oa,oldanims['PaSystemController_00_IsHorse'],mode,riding,side);newg=scene(nl,na,newanims['PaSystemController_00_IsHorse'],mode,riding,side);part=newg['Pa_Controller_00']['affine'];part_pane=pmap['Pa_Controller_00'];sx,sy=part_pane['parts_scale'];part=affine_mul(part,(sx,0,0,sy,0,0));image=affine_mul(part,cg['P_Controller_00']['affine'])
            def toworld(p):return point(image,[left+p[0]/mf['anchor_document']['width']*w,top-p[1]/mf['anchor_document']['height']*h])
            def topixel(p):
                q=inverse(image,p);return [(q[0]-left)/w*mf['anchor_document']['width'],(top-q[1])/h*mf['anchor_document']['height']]
            # Label roots, text alignment panes and all unrelated pane origins stay fixed.
            for p in l['panes']:
                if p['name'] not in allow:
                    assert math.dist(oldg[p['name']]['origin'],newg[p['name']]['origin'])<1e-6
            for control,g in group.items():
                ps=[anchors[i] for i in CONTROL[control]];target=[sum(p[i] for p in ps)/len(ps) for i in range(2)];hg=newg[g['horizontal']];mk=newg[g['marker']];endpoint=point(hg['affine'],[hg['values']['width'],0]);lp=math.dist(hg['origin'],oldg[g['horizontal']]['origin']);enderr=math.dist(topixel(endpoint),target);markerr=math.dist(topixel(mk['center']),target);max_error=max(max_error,enderr,markerr);max_label=max(max_label,lp)
                assert enderr<0.001 and markerr<0.001 and lp<1e-6,(control,side,mode,riding,enderr,markerr,lp)
                assert abs(newg[g['vertical']]['values']['height'])<1e-7
                # Original marker world orientation retained; new dimensions may enclose cluster.
                oldmat=oldg[g['marker']]['affine'];assert max(abs(mk['affine'][i]-oldmat[i]) for i in range(4))<1e-6
                tests=[(p,0.) for p in support_points(control,anchor_records,mf['anchor_document'])]
                if tests:
                    window=pmap[g['marker']];custom=window['custom'];assert mk['values']['width']>=custom[0]+custom[1] and mk['values']['height']>=custom[2]+custom[3]
                for q,radius in tests:
                    local=inverse(mk['affine'],toworld(q));lf,tp,ww,hh=rectangle(pmap[g['marker']],mk['values']);a,b,c,dd,_,_=mk['affine'];det=a*dd-b*c;rx=radius*math.hypot(dd,b)/abs(det);ry=radius*math.hypot(c,a)/abs(det)
                    assert lf-1e-4<=local[0]-rx and local[0]+rx<=lf+ww+1e-4 and tp-hh-1e-4<=local[1]-ry and local[1]+ry<=tp+1e-4;coverage_count+=1
                records.append(dict(control=control,mode=['Console','Grip','Pro'][mode],is_horse=riding,boundary=side,target_pixel=target,line_endpoint_pixel=topixel(endpoint),marker_center_pixel=topixel(mk['center']),line_error_px=enderr,marker_error_px=markerr,label_endpoint_drift_layout=lp,marker_bounds_layout=mk['quad']))
    result=dict(passed=True,tool_version=4,display_art='unified-steamdeck-inclined',complete_10_groups=True,hardware_validated=False,unknown_alternate_pane_consumers_validated=False,controls_patched=mf['controls_patched'],missing_anchor_ids=[],independent_math=True,reopened_all_23_files=True,max_endpoint_or_marker_error_px=max_error,max_label_endpoint_drift_layout=max_label,state_group_checks=len(records),cluster_coverage_checks=coverage_count,checks=dict(checks),records=records)
    out=patch/args.output_name;assert out.resolve().parent==patch and not out.exists()
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
