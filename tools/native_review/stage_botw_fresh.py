"""Stage a complete private SDK7 build plus both verified DLC; switch no Steam files."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from botw_launch import atomic_json, native_header, preflight, running_games
from native_binary_check import inspect
from legacy_sdk7 import verify_exefs
from botw_deck_layout import build as build_deck_layout


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def stage(root,work,evidence,helper):
    root,work,evidence=map(lambda p:Path(p).resolve(),(root,work,evidence))
    if running_games():raise ValueError('保留正在运行的游戏，暂不切换安装')
    log=(evidence/'fresh-build.log').read_text(errors='replace')
    for marker in ['FRESH_GENERATION_DONE','FRESH_COMPILE_DONE','FRESH_BUILD_SUCCESS']:
        if marker not in log:raise ValueError('完整原生构建尚未成功')
    source_info=json.loads((evidence/'fresh-source.json').read_text())
    if source_info.get('upstream')!='4249c880bc6b09ad0207fc3f6e7595346f08d232' or source_info.get('generated_code_reused') is not False:
        raise ValueError('缺少固定源码与完整新生成记录')
    dlc=json.loads((evidence/'dlc-content-verified.json').read_text())
    if [item['dlc'] for item in dlc]!=[1,2] or any(item['aoc_version']!='3.0' for item in dlc):
        raise ValueError('两个3.0版DLC尚未完成校验')
    if any(not all(any(f'Level {level} (GOOD)' in line for line in item['verification_good_lines']) for level in range(6)) for item in dlc):
        raise ValueError('DLC的完整IVFC校验记录不足')
    build=work/'source/build'
    subprocess.run([sys.executable,str(Path(__file__).with_name('botw_seal_generation.py')),
                    '--work',str(work),'--check'],check=True)
    verify_exefs(work/'source/extracted/exefs',['main','subsdk0','sdk'])
    for path in [build/'savagewind',build/'swgame.so']:native_header(path)
    tables=inspect(build/'swgame.so')['function_counters']
    if any(tables.get(name+'_fn_count',0)<=0 for name in ['main','subsdk0','sdk']):
        raise ValueError('完整游戏函数表缺失，拒绝运行时探针或空库')
    repair=json.loads((evidence/'movie-repair-applied.json').read_text())
    if repair.get('source_nca_content_id_matches') is not True or digest(root/'games/botw-1.6.0/romfs/Movie/Demo104_1.webm')!=repair['installed_movie_sha256']:
        raise ValueError('影片尚未完成原始数据修复校验')
    library_id=(build/'swgame.so.id').read_text().strip()
    release=root/'releases'/('sdk7-fresh-'+library_id)
    game=root/'games'/('botw-1.6.0-fresh-'+library_id)
    if release.exists() or game.exists():raise ValueError('保留已有同版本安装，不覆盖')
    old_release=root/'releases/sdk7-20261029'
    old_game=root/'games/botw-1.6.0'
    scratch=Path(tempfile.mkdtemp(prefix='.fresh-stage-',dir=root))
    try:
        new_release=scratch/'release'
        shutil.copytree(old_release,new_release,copy_function=os.link,symlinks=True)
        (new_release/'bin/savagewind').unlink()
        os.link(build/'savagewind',new_release/'bin/savagewind')
        new_game=scratch/'game'
        new_game.mkdir()
        for name in ['romfs','exefs']:
            shutil.copytree(old_game/name,new_game/name,copy_function=os.link,symlinks=True)
        for name in ['swgame.so','swgame.so.id']:os.link(build/name,new_game/name)
        original_bootup=new_game/'romfs/Pack/Bootup.pack'
        deck_bootup=new_game/'romfs/Pack/Bootup.deck.pack'
        deck_ui=build_deck_layout(original_bootup,deck_bootup)
        original_bootup.unlink()
        deck_bootup.rename(original_bootup)
        for index in (1,2):
            incoming=work/f'private/aoc{index}'
            shutil.copytree(incoming,new_game/f'aoc{index}',copy_function=os.link)
            original={p.relative_to(incoming).as_posix():p.stat().st_ino for p in incoming.rglob('*') if p.is_file()}
            copied={p.relative_to(new_game/f'aoc{index}').as_posix():p.stat().st_ino for p in (new_game/f'aoc{index}').rglob('*') if p.is_file()}
            if original!=copied:raise ValueError('同卷DLC发布读回不匹配')
        profile={'schema':1,'version':'1.6.0','release':release.relative_to(root).as_posix(),
                 'game':game.relative_to(root).as_posix(),'gamelib_id':library_id,
                 'runtime_sha256':digest(build/'savagewind'),'gamelib_sha256':digest(build/'swgame.so'),
                 'dlc':{'1':'3.0','2':'3.0'},
                 'ui':{'controller':'steamdeck','bootup_sha256':deck_ui['output_sha256']}}
        if digest(new_release/'bin/savagewind')!=profile['runtime_sha256'] or digest(new_game/'swgame.so')!=profile['gamelib_sha256']:
            raise ValueError('新程序或库的发布读回失败')
        new_release.rename(release)
        new_game.rename(game)
        active=root/'native-active.json'
        old_profile=active.read_bytes() if active.exists() else None
        saved_helper=(root/'botw_launch.py').read_bytes()
        new_helper=Path(helper).read_bytes()
        compile(new_helper,'botw_launch.py','exec')
        private=evidence/'private';private.mkdir(exist_ok=True,mode=0o700)
        rollback={'active_profile_hex':old_profile.hex() if old_profile is not None else None,
                  'old_helper_sha256':hashlib.sha256(saved_helper).hexdigest(),
                  'new_helper_sha256':hashlib.sha256(new_helper).hexdigest()}
        with (private/'launcher-before-fresh.py').open('xb') as stream:stream.write(saved_helper)
        with (private/'fresh-rollback.json').open('x') as stream:json.dump(rollback,stream,indent=2)
        if running_games():raise ValueError('游戏已启动，保留会话，暂不激活新版本')
        fd,path=tempfile.mkstemp(prefix='.launcher-fresh-',dir=root)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(new_helper);stream.flush();os.fsync(stream.fileno())
            os.chmod(path,0o644);os.replace(path,root/'botw_launch.py')
        finally:Path(path).unlink(missing_ok=True)
        try:
            atomic_json(active,profile)
            preflight(root)
        except BaseException:
            if old_profile is None:active.unlink(missing_ok=True)
            else:
                fd,path=tempfile.mkstemp(prefix='.profile-rollback-',dir=root)
                with os.fdopen(fd,'wb') as stream:stream.write(old_profile)
                os.replace(path,active)
            fd,path=tempfile.mkstemp(prefix='.helper-rollback-',dir=root)
            try:
                with os.fdopen(fd,'wb') as stream:
                    stream.write(saved_helper);stream.flush();os.fsync(stream.fileno())
                os.chmod(path,0o644)
                os.replace(path,root/'botw_launch.py')
            finally:Path(path).unlink(missing_ok=True)
            raise
        result={'staged_and_selected':True,'profile':profile,'old_install_retained':True,'game_function_counters':tables,
                'steam_files_changed':False,'game_started':False,'gameplay_validated':False}
        with (evidence/'fresh-install.json').open('x') as stream:json.dump(result,stream,indent=2)
        return result
    finally:
        shutil.rmtree(scratch)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.home()/'native-recomp/swr')
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(stage(args.root,args.work,args.evidence,Path(__file__).with_name('botw_launch.py')),ensure_ascii=False))
