"""Prepare only a sensor fallback candidate; leave current native game untouched."""
import hashlib
import json
from pathlib import Path
import shutil

r=Path.home()/'native-recomp';t=r/'work/totk-1.4.3-20261031';out=t/'gyro-20261103'
out.mkdir(parents=True,exist_ok=True)
for name in ['deck_motion.h','deck_motion_decode.c','deck_motion_linux.c']:
    src=Path(__file__).resolve().parent/name
    if src.resolve() != (out/name).resolve():
        shutil.copy2(src,out/name)
source=r/'ports/ultratears-linux-20261030/source/src/host/window_sdl.c'
data=source.read_text()
expected='fd5faab11b3a6fadd20d8d3d57e87238ef0dfb0e2e41c5ee1d9cdf2ec52cf044'
if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:raise ValueError('Window source no longer matches the delivered V8 baseline')
start=data.index('static void pad_attached(void) {')
end=data.index('// SDL\'s controller frame:',start)
replacement='''static int pad_uses_sdl_motion;
static void pad_attached(void) {
    nd_deck_motion_stop();
    pad_uses_sdl_motion = 0;
    if (!pad) { runtime_motion_live(0); return; }
    const char *name = SDL_GetGamepadName(pad);
    fprintf(stderr, "[totk] game controller: %s\\n", name ? name : "unknown");
    const char *axes = getenv("TOTK_GYRO_AXES");
    if (runtime_motion_axes(axes) < 0)
        fprintf(stderr, "[totk] invalid TOTK_GYRO_AXES ignored\\n");
    if (SDL_GamepadHasSensor(pad, SDL_SENSOR_GYRO) && SDL_GamepadHasSensor(pad, SDL_SENSOR_ACCEL) &&
        SDL_SetGamepadSensorEnabled(pad, SDL_SENSOR_GYRO, true) && SDL_SetGamepadSensorEnabled(pad, SDL_SENSOR_ACCEL, true)) {
        pad_uses_sdl_motion = 1;
        runtime_motion_live(1);
        fprintf(stderr, "[totk] controller motion sensors on (%.0f Hz gyro)\\n", SDL_GetGamepadSensorDataRate(pad, SDL_SENSOR_GYRO));
    } else {
        int is_deck = (SDL_GetGamepadVendor(pad) == 0x28de && SDL_GetGamepadProduct(pad) == 0x1205) ||
                      (name && strstr(name, "Steam Deck"));
        if (is_deck && runtime_gyro_enabled() && nd_deck_motion_start()) {
            fprintf(stderr, "[totk] Steam Deck native six-axis fallback active; buttons remain on Steam\\n");
        } else {
            runtime_motion_live(0);
            fprintf(stderr, "[totk] controller has no usable motion source: no gyro aiming\\n");
        }
    }
}
'''
data=data[:start]+replacement+data[end:]
sensor='static void pad_sensor(const SDL_GamepadSensorEvent *e) {'
if data.count(sensor)!=1:raise ValueError('Unexpected sensor event handler')
data=data.replace(sensor,sensor+'\n    if (!pad_uses_sdl_motion || !pad || e->which != SDL_GetGamepadID(pad)) return;')
data='#include "deck_motion.h"\n#include <string.h>\nextern int runtime_gyro_enabled(void);\n'+data
(out/'window_sdl.c').write_text(data)
base=(t/'highfps-20261103/build.ninja').read_text()
# Retain only rules; all already-built objects become immutable link inputs.
lines=base.splitlines();keep=True;rules=[];link=None
for line in lines:
    if line.startswith('build '):
        if ': link ' in line:link=line
        keep=False
    elif line and not line.startswith(' '):keep=True
    if keep and not line.startswith('default '):rules.append(line)
if link is None:raise ValueError('No native linker target')
newtarget=str(out/'ultratears')
objects=link.split(': link ',1)[1].split()
oldwindow=next(p for p in objects if p.endswith('_window_sdl.o'))
objects=[str(out/'window_sdl.o') if p==oldwindow else p for p in objects]
objects += [str(out/'deck_motion_decode.o'),str(out/'deck_motion_linux.o')]
for p in objects:
    if Path(p).parent!=out and not Path(p).is_file():raise ValueError('Missing delivered object: '+p)
rules += [f'build {out}/window_sdl.o: cc {out}/window_sdl.c',
          f'build {out}/deck_motion_decode.o: cc {out}/deck_motion_decode.c',
          f'build {out}/deck_motion_linux.o: cc {out}/deck_motion_linux.c',
          'build '+newtarget+': link '+' '.join(objects),'default '+newtarget]
plan='\n'.join(rules)+'\n'
plan=plan.replace(' -std=gnu17 ',f' -iquote {source.parent} -std=gnu17 ')
(out/'build.ninja').write_text(plan)
receipt={'parent_elf_sha256':'f10b228eac91a34cfaf4b54cdc589c96be62c8aa71432c93672d0b4ee218feca',
         'window_baseline_sha256':expected,'candidate_window_sha256':hashlib.sha256(data.encode()).hexdigest(),
         'immutable_object_hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in objects if Path(p).parent!=out},
         'source_hashes':{name:hashlib.sha256((out/name).read_bytes()).hexdigest()
                          for name in ['deck_motion.h','deck_motion_decode.c','deck_motion_linux.c']}}
(out/'prepare.json').write_text(json.dumps(receipt,indent=2))
print('Prepared read-only gyro candidate; 3 objects + native link, extra peak <0.9GiB; current game unchanged.')
