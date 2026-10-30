"""Private resource-patch tests with synthetic bytes, never real game assets."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

import ultratears_bundle as bundle
import ultratears_xbox as ui
from verify_ultratears_bundle import digest, verify


def fixture(root):
    rom=root/'romfs';rom.mkdir()
    mod=root/'xbox';mod.mkdir()
    names=sorted([*ui.FONTS,ui.LAYOUT,'System/Resource/ResourceSizeTable.Product.140.Nin_NX_NVN.rsizetable.zs','untouched'])
    image=bytearray();native=bytearray();strings=bytearray();files=[];records={};lines=[];content=hashlib.sha256()
    for name in names:
        image+=b'\0'*(-len(image)%16);at=len(image)
        original=b'original fixture '+name.encode();image+=original
        content.update(hashlib.sha256(original).digest())
        files.append({'path':name,'offset':at,'size':len(original)})
        raw=name.encode()+b'\0';native+=struct.pack('<QQII',at,len(original),len(strings),len(raw));strings+=raw
        if name=='untouched':continue
        changed=b'Xbox synthetic fixture '+name.encode();path=mod/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(changed)
        item={'bytes':len(changed),'sha256':digest(path),'original_sha256':hashlib.sha256(original).hexdigest()}
        records[name]=item;lines.append('\t'.join((name,str(item['bytes']),item['sha256'],item['original_sha256'])))
    (rom/'romfs.bin').write_bytes(image)
    (rom/'runtime-index.bin').write_bytes(b'TOTKRFS1'+struct.pack('<QQ',len(names),24+len(native))+native+strings)
    (rom/'index.json').write_text(json.dumps({'status':'pass','content_sha256':content.hexdigest(),'files':files}))
    (mod/'manifest.tsv').write_text('\n'.join(lines)+'\n')
    (mod/'xbox-ui.json').write_text(json.dumps({'schema':1,'kind':'ultratears-xbox-ui','version':'1.4.3',
        'tool_commit':ui.COMMIT,'input_mapping':'position','resources':records,
        'tutorial_images_complete':False,'hardware_validated':False}))
    return rom,mod,dict(romfs_files=len(names),romfs_bytes=len(image),romfs_content=content.hexdigest())


class XboxResources(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nativedeck-xbox-test-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_patch_changes_indexed_reads_and_preserves_original_image_prefix(self):
        rom,mod,_=fixture(self.root);base=(rom/'romfs.bin').read_bytes()
        record=ui.apply_to_stage(rom,mod)
        result=(rom/'romfs.bin').read_bytes();self.assertEqual(result[:len(base)],base)
        doc=json.loads((rom/'index.json').read_text());native=(rom/'runtime-index.bin').read_bytes()
        self.assertEqual(doc['status'],'ui-patched');self.assertNotIn('content_sha256',doc)
        for i,row in enumerate(doc['files']):
            at,size=struct.unpack_from('<QQ',native,24+i*24)
            self.assertEqual((at,size),(row['offset'],row['size']))
            expected=(mod/row['path']).read_bytes() if row['path']!='untouched' else b'original fixture untouched'
            self.assertEqual(result[at:at+size],expected)
        self.assertFalse(record['tutorial_images_complete']);self.assertFalse(record['hardware_validated'])

    def test_wrong_base_digest_is_rejected_before_image_writes(self):
        rom,mod,_=fixture(self.root);before=(rom/'romfs.bin').read_bytes()
        path=mod/'manifest.tsv';text=path.read_text();old=text.splitlines()[0].split('\t')[3]
        path.write_text(text.replace(old,'0'*64))
        record=json.loads((mod/'xbox-ui.json').read_text());record['resources']=ui.manifest(mod)
        (mod/'xbox-ui.json').write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'another base'):ui.apply_to_stage(rom,mod)
        self.assertEqual((rom/'romfs.bin').read_bytes(),before)

    def test_regional_font_coverage_and_replacement_digest_are_required(self):
        _,mod,_=fixture(self.root);path=mod/'manifest.tsv';lines=path.read_text().splitlines()
        path.write_text('\n'.join(lines[1:])+'\n')
        with self.assertRaisesRegex(ValueError,'coverage'):ui.manifest(mod)
        path.write_text('\n'.join(lines)+'\n')
        font=mod/sorted(ui.FONTS)[0];font.write_bytes(b'x'*font.stat().st_size)
        with self.assertRaisesRegex(ValueError,'Changed Xbox'):ui.manifest(mod)

    def test_symlinked_resource_parent_is_not_followed(self):
        _,mod,_=fixture(self.root);(mod/'Font').rename(self.root/'other-fonts')
        (mod/'Font').symlink_to(self.root/'other-fonts',target_is_directory=True)
        with self.assertRaises(ValueError):ui.manifest(mod)

    def test_public_tool_bytes_are_pinned_before_execution(self):
        source=self.root/'tools';source.mkdir();path=source/'make_button_icons.py';path.write_text('pass\n')
        pin={'files':{'games/totk/scripts/make_button_icons.py':{'bytes':5,'sha256':digest(path)}}}
        with mock.patch.object(ui,'pins',return_value=pin):
            ui.check_tools(source);path.write_text('evil\n')
            with self.assertRaisesRegex(ValueError,'pinned public'):ui.check_tools(source)

    @unittest.skipUnless(sys.platform=='linux','Private ELF packaging requires Linux')
    def test_bundle_bakes_ui_into_own_image_without_modifying_original(self):
        import test_ultratears_bundle as tests
        builder=tests.NativeBundle();builder.root=self.root
        binary,exefs,data,jobs,pin=builder.make_inputs()
        shutil.rmtree(data/'romfs')
        rom,mod,rom_pin=fixture(self.root);rom.rename(data/'romfs');pin.update(rom_pin)
        original=digest(data/'romfs/romfs.bin');target=self.root/'published'
        with mock.patch.dict(bundle.GAME,pin):
            bundle.prepare(binary,exefs,data,jobs,target,workspace=self.root,xbox_ui=mod)
        self.assertEqual(digest(data/'romfs/romfs.bin'),original)
        self.assertTrue(verify(target,full=True)['structural_integrity_verified'])
        doc=json.loads((target/'bundle.json').read_text())
        self.assertIn('xbox_ui',doc);self.assertFalse(doc['xbox_prompts_validated'])
        self.assertNotEqual(digest(target/'data/romfs/romfs.bin'),original)


if __name__=='__main__':unittest.main(verbosity=2)
