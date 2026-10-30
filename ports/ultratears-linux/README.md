# UltraTears 1.4.3 的 Linux / Steam Deck 源码移植

本目录是对公开项目 [kuraeow/ultratears](https://github.com/kuraeow/ultratears) 的可重放移植补丁，固定提交 `0c9ce8afd4c3ab81c33200917af51fb9807aeef0`。复用其 ARM64→C 重编译器、NVN/Vulkan 后端、主机服务及已有 Linux 平台实现。保留上游 GPL-3.0-or-later 与各第三方组件署名；完整许可证见 LICENSE 和上游 third_party/licenses。

**当前产物是生产运行时代码静态库，不是可玩的《王国之泪》。** 库已在 Deck 的 Ubuntu 24.04 容器编译，链接审计只剩三个真实游戏模块的九个函数表符号。未用空表补成游戏，也未启动第二个 GPU 游戏。`hardware_validated=false` 仍指游戏实跑未通过。

## 本次实现与证据

- 60 个生产运行时单元（含 C++ 编码器）在原生 Linux x86-64 编译通过。
- 文件映射、受保护地址范围、安全读、读写锁、文件截断、缓存原子替换、SHA-256、音频绝对时钟等待、时区与 CPU 数量查询接入 POSIX / libc / pthread / OpenSSL。
- Linux Vulkan loader 直接载入 `libvulkan.so.1`。已用只读物理设备查询确认 VANGOGH 的 Vulkan 1.4.350、外部主机内存导入、Shader Object 扩展及特性；没有创建逻辑设备或渲染帧，不能据此推断游戏性能。
- 沿用上游集显默认关闭额外内存池副本的逻辑，不改系统 VRAM / BIOS。
- `bc7build` 已编译成 Linux 原生 ELF。着色器工具加入 Linux RID、受限 CPU 启动与失败传递；合成协议测试通过，**真实 .NET shader translator 的发布和游戏着色器转换尚未验收**。
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

## 真实游戏构建入口（待输入及验收）

`tools/setup.py` 仍是上游 Windows 流程。Linux 使用新增入口，不调用 Windows 安装器或下载器。需要用户本地解密、应用 1.4.3 更新的 `exefs/` 与 `romfs/`；本轮定向核查未找到完整有效输入。构建时先关闭占用资源的游戏，预留至少数十 GiB 于项目数据目录，禁止在 Mac `/tmp` 存放大产物。

```sh
python3 tools/prepare_linux_game.py --dump /absolute/local-dump --data /absolute/project-data --stage check
python3 tools/prepare_linux_game.py --dump /absolute/local-dump --data /absolute/project-data --stage romfs
python3 tools/prepare_linux_game.py --dump /absolute/local-dump --data /absolute/project-data --stage lift
python3 tools/build_linux.py --target game --exefs /absolute/local-dump/exefs --generated /absolute/project-data/generated --out /absolute/game-build --jobs 1
```

Lifter 的 Python 依赖为上游 capstone/lz4/unicorn，仅在构建分析阶段使用。运行时游戏不依赖这些 Python 包。

着色器与纹理沿用上游工具，新增 Linux 路径；以下完整流水线尚未用真实输入验收：

```sh
python3 tools/build_xlate.py --rid linux-x64 --dotnet /absolute/project-dotnet/dotnet --out /absolute/project-translator --cache /absolute/project-cache --jobs 1
export ULTRS_SHADER_TRANSLATOR=/absolute/project-translator/ultrs-shaders
python3 tools/export_shaders.py /absolute/project-data/romfs /absolute/project-data/shader-work /absolute/local-dump/exefs
python3 tools/run_ryujinx_xlate.py /absolute/project-data/shader-work --workers 1
python3 tools/pack_shaders.py /absolute/project-data/shader-work/translated /absolute/project-data/shaders/translated.pack
python3 tools/bc7_build.py --romfs /absolute/project-data/romfs --cache /absolute/project-data/textures --threads 1
```

## 剩余交付边界

真实 1.4.3 CPU 代码与资源构建、.NET translator、完整 Linux 链接/宿主依赖打包、Vulkan 真正创建设备与游戏渲染、存档和稳定性都尚未验收。简中可用语言代码为 `TOTK_LANG=zh-Hans`，但中文字库与全部画面未验证。Xbox 提示需要实际资源和输入行为一起对齐，目前尚未实现，不能仅改按钮映射就宣布图标完成。

最终安装仍采用自包含目录和 `run.sh`，直接启动原生 x86-64 ELF；本轮未改 Steam 库、Steam/Decky 插件、系统设置或当前 BOTW 会话。串流按用户要求从验收中跳过。后续须各项通过后才能宣布移植完成并加入掌机模式。
