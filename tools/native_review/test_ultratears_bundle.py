"""Synthetic format/transaction checks. Fixtures never represent a Nintendo game."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from native_binary_check import inspect
import ultratears_bundle as bundle
from verify_ultratears_bundle import digest, verify

# Frozen BFTTF vector: BE decoded magic 0x7f9a0218, size 4, sfnt 0x00010000,
# each XORed with synthetic 0x12345678. No system font bytes are distributed.
FONT_EXAMPLE = bytes.fromhex('6dae5460 1234567c 12355678')


class Formats(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nativedeck-bundle-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def make_romfs(self):
        root=self.root/'romfs';root.mkdir()
        blobs=[b'one',b'two']
        packed=blobs[0]+b'\0'*13+blobs[1]
        rows=[{'path':'A','offset':0,'size':3},{'path':'B','offset':16,'size':3}]
        content=hashlib.sha256(b''.join(hashlib.sha256(b).digest() for b in blobs)).hexdigest()
        (root/'romfs.bin').write_bytes(packed)
        (root/'index.json').write_text(json.dumps({'status':'pass','content_sha256':content,'files':rows}))
        native=b'TOTKRFS1'+struct.pack('<QQ',2,72)+struct.pack('<QQII',0,3,0,2)+struct.pack('<QQII',16,3,2,2)+b'A\0B\0'
        (root/'runtime-index.bin').write_bytes(native)
        return root,dict(romfs_files=2,romfs_bytes=19,romfs_content=content)

    def test_romfs_checks_actual_bytes_and_matching_runtime_index(self):
        root,pin=self.make_romfs()
        with mock.patch.dict(bundle.GAME,pin):
            self.assertEqual(bundle.romfs_check(root),digest(root/'romfs.bin'))
            (root/'romfs.bin').write_bytes(b'bad'+b'\0'*13+b'two')
            with self.assertRaises(ValueError):bundle.romfs_check(root)

    def test_romfs_rejects_traversal_and_mismatched_index(self):
        root,pin=self.make_romfs()
        with mock.patch.dict(bundle.GAME,pin):
            p=root/'runtime-index.bin';p.write_bytes(p.read_bytes()[:-2]+b'Z\0')
            with self.assertRaises(ValueError):bundle.romfs_check(root)
            doc=json.loads((root/'index.json').read_text());doc['files'][0]['path']='../A'
            (root/'index.json').write_text(json.dumps(doc))
            with self.assertRaises(ValueError):bundle.romfs_check(root)

    def test_shader_pack_is_bound_to_inventory_and_blob_hash(self):
        key='ab'*32;j=b'{}';spv=struct.pack('<5I',0x07230203,0x10000,0,1,0)
        stamp=struct.unpack('<I',hashlib.sha256(j+spv).digest()[:4])[0]|1
        at=32+len(j)+len(spv)
        body=b'UTSPACK1'+struct.pack('<IIQQ',1,1,at,0)+j+spv
        body+=struct.pack('<32sQQIIII',bytes.fromhex(key),32,34,2,20,stamp,0)
        pack=self.root/'translated.pack';pack.write_bytes(body)
        jobs=self.root/'jobs.jsonl';jobs.write_text(json.dumps({'job':{'key':key}})+'\n')
        bundle.shader_check(pack,jobs)
        pack.write_bytes(body[:34]+b'BAD!'+body[38:])
        with self.assertRaises(ValueError):bundle.shader_check(pack,jobs)
        pack.write_bytes(body);jobs.write_text(json.dumps({'job':{'key':'cd'*32}})+'\n')
        with self.assertRaises(ValueError):bundle.shader_check(pack,jobs)

    def test_fonts_and_texture_extents_are_checked(self):
        font=self.root/'font.bfttf';font.write_bytes(FONT_EXAMPLE)
        bundle.font_check(font)
        for bad in (FONT_EXAMPLE[:7]+b'\x7d'+FONT_EXAMPLE[8:],
                    FONT_EXAMPLE[:-1]+b'\x79', FONT_EXAMPLE[:11],
                    struct.pack('>III',0x18029a7f,4,0x00010000)):
            font.write_bytes(bad)
            with self.assertRaises(ValueError):bundle.font_check(font)
        idx=self.root/'bc7.idx';pack=self.root/'bc7.pack';pack.write_bytes(b'\0'*16)
        idx.write_bytes(struct.pack('<QQQII',1,2,0,16,0));bundle.texture_check(idx,pack)
        idx.write_bytes(struct.pack('<QQQII',1,2,16,16,0))
        with self.assertRaises(ValueError):bundle.texture_check(idx,pack)

    def test_compatibility_library_paths_are_rejected(self):
        self.assertTrue(bundle.forbidden('/home/deck/.wine/lib/wine64'))
        self.assertTrue(bundle.forbidden('/Steam/steamapps/common/Proton/lib/libc.so'))
        self.assertFalse(bundle.forbidden('/usr/lib/libvpx.so.9'))


@unittest.skipUnless(sys.platform=='linux','Native ELF transaction tests require Linux')
class NativeBundle(unittest.TestCase):
    setUp=Formats.setUp
    def make_elf(self,kind='executable',zero=False):
        src=self.root/('fixture-'+kind+'.c');out=self.root/('fixture-'+kind)
        text='#include <stdint.h>\nstatic void f(void){}\n'
        for m,(lo,_) in {'main':(0x800000000,0),'subsdk0':(0x804000000,0),'sdk':(0x805000000,0)}.items():
            text+=f'const uint64_t {m}_fn_count={0 if zero else 2 if kind=="mismatch" else 1};\n'
            text+=f'const uint64_t {m}_fn_addrs[]={{0x{lo:x}ULL}};\n'
            text+=f'void (*const {m}_fn_ptrs[])(void)={{{0 if kind=="bad-target" else "f"}}};\n'
        text+='int main(void){return 0;}\n';src.write_text(text)
        cmd=['cc','-rdynamic','-o',str(out),str(src)]
        if kind=='audit':cmd[1:1]=['-shared','-fPIC']
        subprocess.run(cmd,check=True,capture_output=True)
        return out

    def test_audit_library_and_empty_tables_cannot_be_packaged_as_game(self):
        self.assertFalse(inspect(self.make_elf('audit'),require_ultratears=True)['inspection_passed'])
        self.assertFalse(inspect(self.make_elf('zero',True),require_ultratears=True)['inspection_passed'])
        self.assertFalse(inspect(self.make_elf('mismatch'),require_ultratears=True)['inspection_passed'])
        self.assertFalse(inspect(self.make_elf('bad-target'),require_ultratears=True)['inspection_passed'])
        result=inspect(self.make_elf(),require_ultratears=True)
        self.assertTrue(result['inspection_passed'])
        self.assertFalse(result['release_accepted'])

    def test_no_replace_cannot_overwrite_even_an_empty_existing_directory(self):
        source=self.root/'stage';target=self.root/'published';source.mkdir();target.mkdir()
        (source/'data').write_text('fixture')
        with self.assertRaises(OSError):bundle.publish_no_replace(source,target)
        self.assertTrue((source/'data').exists());self.assertEqual(list(target.iterdir()),[])

    def test_existing_destination_is_rejected_before_resource_reads(self):
        target=self.root/'exists';target.mkdir()
        with self.assertRaises(ValueError):
            bundle.prepare(self.root/'absent',self.root/'absent',self.root/'absent',self.root/'absent',target,workspace=self.root)
        self.assertEqual(list(target.iterdir()),[])

    def make_inputs(self):
        binary=self.make_elf()
        data=self.root/'data';data.mkdir();exefs=self.root/'exefs';exefs.mkdir()
        pins={}
        for name in ('main','subsdk0','sdk'):
            file=exefs/name;file.write_bytes(b'test fixture '+name.encode());pins[name]=digest(file)
        rom,pin=Formats.make_romfs(self);rom.rename(data/'romfs');pin['exefs']=pins
        for d in ('fonts','textures','shaders'):(data/d).mkdir()
        for name in bundle.FONTS:
            (data/'fonts'/(name+'.bfttf')).write_bytes(FONT_EXAMPLE)
        (data/'textures/bc7.pack').write_bytes(b'0'*16)
        (data/'textures/bc7.idx').write_bytes(struct.pack('<QQQII',1,2,0,16,0))
        key='ab'*32;j=b'{}';spv=struct.pack('<5I',0x07230203,0x10000,0,1,0)
        stamp=struct.unpack('<I',hashlib.sha256(j+spv).digest()[:4])[0]|1
        at=32+len(j)+len(spv)
        packed=b'UTSPACK1'+struct.pack('<IIQQ',1,1,at,0)+j+spv
        packed+=struct.pack('<32sQQIIII',bytes.fromhex(key),32,34,2,20,stamp,0)
        (data/'shaders/translated.pack').write_bytes(packed)
        jobs=self.root/'jobs.jsonl';jobs.write_text(json.dumps({'job':{'key':key}})+'\n')
        record={'schema':1,'kind':'ultratears-linux-build','version':'1.4.3',
                'upstream':'0c9ce8afd4c3ab81c33200917af51fb9807aeef0','exefs':pins,
                'binary_sha256':digest(binary),'generated_manifest_sha256':hashlib.sha256(b'fixture only').hexdigest(),
                'function_counts':dict(main=1,subsdk0=1,sdk=1)}
        binary.with_suffix('.build.json').write_text(json.dumps(record))
        return binary,exefs,data,jobs,pin

    def test_real_copy_transaction_stays_prepared_and_full_hash_detects_tampering(self):
        binary,exefs,data,jobs,pin=self.make_inputs();target=self.root/'published'
        with mock.patch.dict(bundle.GAME,pin):
            result=bundle.prepare(binary,exefs,data,jobs,target,workspace=self.root)
        self.assertTrue(result['prepared']);self.assertFalse(result['hardware_validated'])
        self.assertTrue(verify(target,full=True)['structural_integrity_verified'])
        manifest=json.loads((target/'bundle.json').read_text())
        self.assertFalse(manifest['xbox_prompts_validated'])
        image=target/'data/romfs/romfs.bin';image.write_bytes(b'bad'+image.read_bytes()[3:])
        with self.assertRaises(ValueError):verify(target,full=True)

    def test_copy_failure_never_publishes_partial_directory(self):
        binary,exefs,data,jobs,pin=self.make_inputs();target=self.root/'published'
        with mock.patch.dict(bundle.GAME,pin),mock.patch.object(bundle.shutil,'copyfile',side_effect=OSError('injected copy failure')):
            with self.assertRaises(OSError):bundle.prepare(binary,exefs,data,jobs,target,workspace=self.root)
        self.assertFalse(target.exists());self.assertEqual(list(self.root.glob('.published.partial-*')),[])
        self.assertTrue(binary.exists());self.assertTrue((data/'romfs/romfs.bin').exists())

    def test_build_record_binds_executable_and_translated_function_counts(self):
        binary=self.make_elf();record=binary.with_suffix('.build.json')
        record.write_text(json.dumps({'schema':1,'kind':'ultratears-linux-build','version':'1.4.3',
                'upstream':'0c9ce8afd4c3ab81c33200917af51fb9807aeef0','exefs':bundle.GAME['exefs'],
                'binary_sha256':'0'*64,'generated_manifest_sha256':'ab'*32,
                'function_counts':dict(main=1,subsdk0=1,sdk=1)}))
        with self.assertRaisesRegex(ValueError,'build record'):
            bundle.prepare(binary,self.root/'absent',self.root/'absent',self.root/'absent',self.root/'out',workspace=self.root)

    def test_launcher_quotes_paths_and_preserves_user_language(self):
        root=self.root/'bundle $(touch INJECTED)';root.mkdir()
        (root/'run.sh').write_text(bundle.RUN);(root/'run.sh').chmod(0o755)
        (root/'verify_ultratears_bundle.py').write_text('# fixture: verifier behavior tested separately\n')
        out=root/'ultratears'
        out.write_text('#!/bin/bash\nprintf "%s\\n%s\\n%s\\n" "$TOTK_LANG" "$TOTK_PROFILE_DIR" "$1" > invocation.txt\n')
        out.chmod(0o755)
        env=dict(os.environ,TOTK_LANG='en-US',XDG_DATA_HOME=str(self.root/'app data'))
        subprocess.run(['bash',str(root/'run.sh')],env=env,check=True,capture_output=True)
        lines=(root/'invocation.txt').read_text().splitlines()
        self.assertEqual(lines,[env['TOTK_LANG'],str(self.root/'app data/ultratears/userdata'),str(root/'data/exefs')])
        self.assertFalse((root/'INJECTED').exists());self.assertFalse((self.root/'INJECTED').exists())
        self.assertTrue((self.root/'app data/ultratears/cache').is_dir())

    def test_second_launcher_cannot_enter_the_same_save_profile(self):
        import fcntl
        root=self.root/'bundle';root.mkdir()
        (root/'run.sh').write_text(bundle.RUN)
        (root/'verify_ultratears_bundle.py').write_text('# fixture verifier\n')
        game=root/'ultratears'
        game.write_text('#!/bin/bash\ntouch GAME_ENTERED\n');game.chmod(0o755)
        app_data=self.root/'app data';profile=app_data/'ultratears';profile.mkdir(parents=True)
        with (profile/'session.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            result=subprocess.run(['bash',str(root/'run.sh')],
                env=dict(os.environ,XDG_DATA_HOME=str(app_data)),capture_output=True,text=True)
        self.assertEqual(result.returncode,75)
        self.assertIn('已经运行',result.stderr)
        self.assertFalse((root/'GAME_ENTERED').exists())
        subprocess.run(['bash',str(root/'run.sh')],env=dict(os.environ,XDG_DATA_HOME=str(app_data)),check=True)
        self.assertTrue((root/'GAME_ENTERED').exists())


if __name__=='__main__':unittest.main(verbosity=2)
