# UltraTears 原生目录安装器

本工具只在本机准备私有游戏目录。不得上传该目录、游戏程序、游戏数据、共享字体或生成的游戏代码。打包成功仅代表版本、格式、依赖和复制完整性检查通过；游戏进入、中文画面、Xbox提示和存档/性能仍须实机验收。

## 输入与拒绝规则

- 游戏程序必须是带原生 glibc loader 和有效入口的 x86-64 ELF；三个模块的函数计数、访客地址表和本机函数指针表必须一致、非空，指针须落在程序的可执行段内。运行时审计库不满足此条件。
- `build_linux.py --target game` 编译成功后生成同名 `ultratears.build.json`，绑定程序SHA-256、已核对的1.4.3 ExeFS指纹、生成清单和三个函数计数。没有记录、记录与程序不匹配均拒绝。
- 重新核对1.4.3三个代码模块SHA-256。RomFS实际文件内容按上游顺序逐项哈希，与1.4.3内容指纹匹配；同时核对JSON索引与原生索引的路径、尺寸、偏移及完整边界，不仅相信一个完成标记。
- 着色器包必须逐项匹配所给导出清单，并满足SPIR-V头、记录范围和内容stamp检查。这只能证明与该清单一致，不能代替真实游戏的着色器覆盖/渲染验收。BC7缓存检查记录边界，六份BFTTF检查容器头和尺寸；完整字形覆盖仍待实机与游戏文字核对。
- 目标必须是 `~/native-recomp/` 内的新目录。复制逐文件读回SHA，任一失败清理本次暂存目录；使用Linux `renameat2(RENAME_NOREPLACE)`发布，连既有空目录也不覆盖。

## 命令

在现有构建容器中运行；输入均为玩家已有的本地文件。更新后的Linux编译入口与MR !8固定上游配套，不能用历史空探针代替游戏程序。

```sh
python3 tools/native_review/ultratears_bundle.py \
  --binary /home/deck/native-recomp/game-build/ultratears \
  --exefs /home/deck/native-recomp/local-dump/exefs \
  --data /home/deck/native-recomp/project-data \
  --shader-jobs /home/deck/native-recomp/project-data/shader-work/jobs.jsonl \
  --library-dir /home/deck/native-recomp/totkbuild/deps/sdl3-install/lib \
  --destination /home/deck/native-recomp/installed/ultratears-1.4.3
```

`--data` 内需有 `romfs/{romfs.bin,index.json,runtime-index.bin}`、`shaders/translated.pack`、`textures/{bc7.idx,bc7.pack}`和 `fonts/` 六份上游命名字体。缺少真实输入时本工具拒绝生成安装目录。构建清单默认取程序旁的 `ultratears.build.json`，可用 `--build-record`显式指定。

安装形态为目录内 `ultratears`、`lib/`、`data/`、`run.sh` 和校验脚本。普通应用依赖复制为实际文件，避免外部软链接；glibc、C++运行时与GPU驱动使用SteamOS本身，防止用构建容器的旧C++库覆盖Mesa所需符号。Vulkan loader与驱动不随包替换。复制后和启动前都会使用 `ldd -r`核对依赖；拒绝Wine/Proton等路径和逃逸到安装目录之外的应用依赖。

先在SteamOS宿主运行 `run.sh --verify` 完整读回，再进行真实游戏验收；本工具不自动写Steam库，不中断现有游戏。

## 启动行为

`run.sh` 默认 `TOTK_LANG=zh-Hans`、handheld模式、集显不另建内存池副本，保留玩家显式语言/模式设置。存档与可变shader缓存写入 `${XDG_DATA_HOME:-$HOME/.local/share}/ultratears`，不写其他游戏。启动器只直接exec本目录的原生程序，不调用兼容工具；正常启动做关键文件哈希、全部文件尺寸和原生链接检查，`--verify`才遍历全部大文件哈希。

Xbox图标及完整中文显示没有因这些默认项而被标记为完成，清单相应验收字段始终为false。测试使用可识别的微型合成格式/ELF夹具，未被当作游戏或安装到Steam。
