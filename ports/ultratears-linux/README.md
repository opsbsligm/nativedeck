# UltraTears 1.4.3 的 Linux / Steam Deck 源码移植

2026-11-01 更新：以下早期里程碑保留为历史记录；当前实机与剩余验收范围见本文末尾的增量说明，不能把早期“未渲染/未转换”等描述当作当前状态。

本目录是对公开项目 [kuraeow/ultratears](https://github.com/kuraeow/ultratears) 的可重放移植补丁，固定提交 `0c9ce8afd4c3ab81c33200917af51fb9807aeef0`。复用其 ARM64→C 重编译器、NVN/Vulkan 后端、主机服务及已有 Linux 平台实现。保留上游 GPL-3.0-or-later 与各第三方组件署名；完整许可证见 LICENSE 和上游 third_party/licenses。

**当前交付是公开源码、可重放移植补丁、图示renderer/RLE、运行时图示hook及私有布局构造工具。** 不分发游戏输入或生成游戏代码。实际游戏加载问题由主线程修复；本目录的历史静态库/协议检查不代表当前游戏已可玩。`hardware_validated=false`。

## 本次实现与证据

- 60 个生产运行时单元（含 C++ 编码器）在原生 Linux x86-64 编译通过。
- 文件映射、受保护地址范围、安全读、读写锁、文件截断、缓存原子替换、SHA-256、音频绝对时钟等待、时区与 CPU 数量查询接入 POSIX / libc / pthread / OpenSSL。
- Linux Vulkan loader 直接载入 `libvulkan.so.1`。已用只读物理设备查询确认 VANGOGH 的 Vulkan 1.4.350、外部主机内存导入、Shader Object 扩展及特性；没有创建逻辑设备或渲染帧，不能据此推断游戏性能。
- 沿用上游集显默认关闭额外内存池副本的逻辑，不改系统 VRAM / BIOS。
- `bc7build` 已编译成 Linux 原生 ELF。着色器工具加入 Linux RID、受限 CPU 启动与失败传递；合成协议测试通过；实际 .NET Linux 翻译器已生成 78 MB x86-64 ELF，并在 SteamOS 宿主通过负面请求/EOF 协议测试，**真实游戏着色器转换尚未验收**。
- 游戏构建必须核对上游 1.4.3 三个 ExeFS SHA-256，并验证生成表非空、地址/指针/计数一致、生成清单及 lifter/所有 C 文件内容指纹。该清单用于完整性与续跑检查，不是外部来源的真实性证明。
- POSIX 5 组行为检查、着色器 worker 3 项集成测试、版本/函数表/链接边界的 10 项 Python 测试已通过，证据见 evidence。

## 应用公开源码补丁

在独立干净的上游 checkout 中应用；脚本拒绝错误 SHA、脏目录及覆盖已有 overlay 文件。

```sh
git clone https://github.com/kuraeow/ultratears.git /home/deck/native-recomp/src/ultratears-linux
git -C /home/deck/native-recomp/src/ultratears-linux checkout 0c9ce8afd4c3ab81c33200917af51fb9807aeef0
python3 tools/native_review/apply_ultratears_linux.py --source /home/deck/native-recomp/src/ultratears-linux
```

补丁只含公开源码。ROM、密钥、共享字体、生成的游戏 C/库/资源缓存均不能提交或发布。本项目不下载或解密游戏包。

## 构建公开运行时

全部编译在现有 `nativedeck-build` 容器执行，依赖 clang/clang++、ar、ninja、pkg-config，以及 SDL3、Vulkan headers、opus、vpx、OpenSSL、zstd 开发文件。已有 SDL3 和新 Vulkan headers 放在 `~/native-recomp/totkbuild/deps/`，不写 SteamOS rootfs。

```sh
export PKG_CONFIG_PATH=/home/deck/native-recomp/totkbuild/deps/sdl3-install/lib/pkgconfig
export ULTRS_VULKAN_INCLUDE=/home/deck/native-recomp/totkbuild/deps/vulkan-headers/include
nice -n 19 python3 tools/build_linux.py --target runtime --out /home/deck/native-recomp/ports/ultratears-linux-20261030/build --jobs 1
python3 tools/audit_linux_runtime.py --build /home/deck/native-recomp/ports/ultratears-linux-20261030/build --evidence /home/deck/native-recomp/ports/ultratears-linux-20261030/evidence
```

`libultratears-runtime-audit.so` 仅作链接审计，禁止执行或冒充游戏安装。容器内依赖解析已验证；SteamOS 宿主的最终完整游戏依赖打包尚待完成。

## 真实游戏构建入口（私有输入；实机验收待完成）

`tools/setup.py` 仍是上游 Windows 流程。Linux 使用新增入口，不调用 Windows 安装器或下载器。需要用户本地解密、应用 1.4.3 更新的 `exefs/` 与 `romfs/`；输入只在调用方私有环境核验，本公开树不声明它们当前存在或缺失。构建时先关闭占用资源的游戏，预留至少数十 GiB 于项目数据目录，禁止在 Mac `/tmp` 存放大产物。

```sh
python3 tools/prepare_linux_game.py --dump /absolute/local-dump --data /absolute/project-data --stage check
python3 tools/prepare_linux_game.py --dump /absolute/local-dump --data /absolute/project-data --stage romfs
python3 tools/prepare_linux_game.py --dump /absolute/local-dump --data /absolute/project-data --stage lift
python3 tools/build_linux.py --target game --exefs /absolute/local-dump/exefs --generated /absolute/project-data/generated --out /absolute/game-build --jobs 1
```

Lifter 的 Python 依赖为上游 capstone/lz4/unicorn，仅在构建分析阶段使用。运行时游戏不依赖这些 Python 包。

着色器与纹理沿用上游工具，新增Linux路径；真实1.4.3输入已完成28667个着色器转换打包和纹理预编码：

```sh
python3 tools/build_xlate.py --rid linux-x64 --dotnet /absolute/project-dotnet/dotnet --out /absolute/project-translator --cache /absolute/project-cache --jobs 1
export ULTRS_SHADER_TRANSLATOR=/absolute/project-translator/ultrs-shaders
python3 tools/export_shaders.py /absolute/project-data/romfs /absolute/project-data/shader-work /absolute/local-dump/exefs
python3 tools/run_ryujinx_xlate.py /absolute/project-data/shader-work --workers 1
python3 tools/pack_shaders.py /absolute/project-data/shader-work/translated /absolute/project-data/shaders/translated.pack
python3 tools/bc7_build.py --romfs /absolute/project-data/romfs --cache /absolute/project-data/textures --threads 1
```

## 剩余交付边界

真实1.4.3已完成282702函数、1432生成单元加三表的完整编译，并在SteamOS宿主使用RADV VANGOGH进入开场地下场景。键盘映射的移动和系统菜单、中文标题/读档/系统画面、读取自动存档、手动保存“已保存”均已实测；自主SteamDeck图和引线已实际显示。过渡动画早期截图存在空白，稳定画面中文字完整，不能把过渡帧当成已确定的字体故障；当前正进行关闭临时R8强刷的对照。Xbox图标仍需补齐RS等提示；全部物理按键、动画音画、能力与稳定性验收未完成。

Clang18对两个复杂生成单元的CodeGenPrepare产物未通过LLVM自身IR校验；`--compile-overrides`允许精确源SHA绑定的`["-mllvm","-disable-cgp"]`，保留O1及其他编译单元。早期调度/分配恢复和O0对照也保留为明确白名单；O0标记为实验对照。生成游戏代码始终留在私有数据目录。

最终安装采用自包含目录和`run.sh`，直接启动原生x86-64 ELF；未改Steam库、Steam/Decky插件或系统设置。用户已授权保存、校验备份并退出BOTW，该操作已完成。TOTK首轮试玩的17文件也已备份读回，退出后内容一致。串流按用户要求跳过；整体实机门禁通过后才能宣布完成并加入掌机模式。

## Linux 着色器工具的补充验证

`prepare_dotnet_linux.py` 从微软官方 .NET 10 release metadata 选择 Linux x64 SDK，逐字节核对 SHA-512，在当前项目 deps 目录解包，拒绝覆盖已有 SDK，不装系统包。此次固定证据为 SDK 10.0.403。`build-native-shaders.sh` 使用已有容器、单 CPU / nice19 / 每进程512 MiB托管堆限制构建公开翻译器；CLR 的虚拟地址空间上限为8 GiB，不能将它误认为实际内存占用。运行时 C/C++ 构建的2 GiB地址限制保持不变。

早期合成请求验证保留在`evidence/dotnet-sdk-pin.json`与`evidence/shader-translator-build.json`。2026-10-31已进一步完成28667个真实游戏着色器转换，并实际进入Vulkan游戏场景；这些结果尚不等于完整渲染正确性。SDK、工具二进制与生成GPU资源留在Deck项目目录，未提交仓库。

## 控制器公共源码入口

- `controller-art/`：自主renderer v2、锚点、RLE生成器及公开图形测试。
- `controller-runtime/`：六个精确纹理身份统一inclined上传的patch、RLE头和对应proof；通过`tools/native_review/apply_ultratears_controller.py`在Linux移植后应用。
- `controller-layout/`：通用renderer锚点API与私有UI patch构造器；公共7项单测不读取游戏文件，私有输入/输出必须留在仓外。

源码/自绘像素/格式核验与真实Vulkan上传和游戏操作验收分开记录；本次没有将后者标为完成。

## 不可变资源与可写纹理缓存

`TOTK_BC7_DIR`指向安装包内只读预烘焙资源，Linux启动器同时将`TOTK_BC7_CACHE_DIR`设为本游戏用户缓存子目录。新增纹理只写增量pack/idx，不复制8GB基准包，也不让运行时修改安装清单保护的文件。无效/截断索引、目录或文件别名、并发写锁冲突均关闭这组缓存；不会猜测修复原数据。

`cache-tests/`将原始公开fixture应用真实生产Linux补丁，与独立缓存补丁重建结果按SHA绑定，再运行34组原生C回归与4项篡改/完整性检查；不需要网络或游戏资源。它们验证缓存I/O，不替代真实游戏验收。

## 2026-11-01 增量：字形更新、完整摇杆提示与影片数据

28 段既有安装 WebM（1,609,787,432 字节，约 71 分 38 秒）已在 Deck 逐段完整严格解码，无解码错误。此结果证明影片数据可解码；实际游戏中的解码调用、声音和同步另行验收。

1.4.3 已实际进入开场地下 3D、移动、读档和手动保存。关闭临时 R8 强刷后，稳定读档列表和系统菜单仍出现缺字，不能把它归为过渡动画。Linux 缺少 write watch，显式 NVN MemoryPool/Buffer/Texture flush 现在会发布修改通知；但无通知的 CPU 字形写入仍可能发生，因此增加 CPU 可见 R8/R8_SNORM 单层字形纹理的精确快照比较。只在内容变化时重传，最多每图 16 MiB、总计 64 MiB；分配失败或预算耗尽时保守重传。GPU 写入、虚拟池、ASTC 与原写入追踪路径保持各自语义。未增加系统写入追踪、故障处理器或外部兼容层。相关原生 C 测试验证内容变化、未变化复用、分配失败、预算、释放和并发，实机字形结果仍须单独核对。

三份额外大型单元 main108/802/804 也已实证 CodeGenPrepare 后非法 SSA；定向禁用该 pass 后，三者 O1 原生对象、链接均成功。当前五份源 SHA 绑定覆盖 main108/150/151/802/804，未全局禁用优化，也未修改生成的游戏 C。不能把五份审计扩大成全部路径正确性证明。

Xbox 字形生成器现默认离线派生原始 MNG 固定工具，保持原门禁，增加完整 17 个 LS/RS 普通、方向与按下字形，合计 34 个按键 glyph；四区域字体、八项 HUD 与容量表均有内容绑定。公开工具和纯 Python fontTools 附许可证及逐文件 pin，专用 CI 无 pip、无游戏输入；详见 `xbox/OFFLINE-XBOX34.md`。最终私有 UI 同时保留十组 Steam Deck 机身引线，但物理按压、全部教程画面与全部功能仍待实机验收。

## 2026-11-01 增量：实际对话、背景键位与构建记录

连续录像和后续刷新捕获已确认开场行走、转向、镜头、蹲下/取消、攀爬/放手以及两段中文剧情对话。此前 XGetImage 单帧方法多次返回完全相同的旧帧，导致“移动无响应”误判；现在使用连续抓取并丢弃起始帧。早期字体关闭对照也受此因素影响，不能用旧截图证明全部缺字的唯一根因；CPU 无写入追踪时的源码更新遗漏、精确快照的原生测试及当前中文字形显示分别成立。静态 28 影片解码、引擎内对话与预渲染影片实际播放仍是不同验收范围。

实机“调查”提示暴露独立遗漏：亮起的图标已是 Xbox B，淡色四键位置仍显示 Switch 字母。这些字母是 `DoCommand_00.bflyt` 的普通 UTF-16 文本，不在原字体/八纹理替换范围。`tools/native_review/xbox_context_labels.py` 仅替换普通及同伴变体的 15 个位置字母，并将该布局的 `+` 换为 Menu 字形；每项核对原文、范围、唯一性和完整集合，档案长度、几何、纹理与其他成员保持逐字节一致。它已接入新 UI 构造流程；公开测试使用人工布局，不包含游戏文件。实际新版画面验收另记，不能仅凭构造成功声明全部提示通过。

恢复编译参数曾遗漏构建成功后的 `.build.json` 输出。现在成功链接后再次验证完整生成输入及恢复配置指纹，记录 ELF 摘要、三模块函数数量和恢复参数；失败构建先使旧记录失效，避免陈旧凭据配上新程序。新增失败与篡改用例覆盖输入/配置变化、缺失二进制和空函数表。真实 Deck 生产版本移除临时输入观测后已重新编译链接，自动生成记录；ELF 摘要回到原生产 `c8e38be5e685671d182079e83bfe2f9205853d0ead67aabe2a9474302855aa86`，不是复用诊断库。

本轮退出前在游戏内手动保存，读取列表确认该新手动档，30 文件稳定备份，退出后摘要未变。完整可玩性、实际预渲染过场音画、战斗/能力/地图/死亡恢复及长期稳定性门禁仍未全部完成，`hardware_validated=false`、`playability_validated=false`。

后续实机复验更正：仅修改布局初值不足，语言消息会覆盖同名普通字母。已定位 `LayoutMsg/DoCommand_00.msbt` 的准确 16 个标签，在原有 15 个语言包中同步按标签 ID 修正；不会全局替换字母，也不改变对白、条目顺序或档案长度。新 UI 集合为原六项加完整十五项 Mals 资源，共 21 项；只接受精确 1.4.3 名称和完整语言集合，仍能读取六项历史安装以回滚。现有数据已逐语言验证修改边界、全部无关档案成员和解压回读，新增总压缩数据 29,383,188 字节。实际修改后的提示需继续实机确认；前一版布局修复的截图复验失败已保留，不能把单测通过写成游戏已通过。
