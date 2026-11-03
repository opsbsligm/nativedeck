# TOTK 1.4.3：Steam Deck 60fps 原生计时适配

此工具只使用玩家本机已有的 1.4.3 NSO、静态代码生成结果和原生对象文件；不包含游戏资产，也不下载游戏。基于现有 V8 Linux/Vulkan 构建，补齐原移植缺失的帧控制器与测量时钟，解除原来的 30fps 上限。默认最高 60fps，与掌机显示相配；不保证所有场景达到 60fps。

实现依据为本机既有 MacNativeGames `games/totk/runtime/game_patches_v143.c` 的七处帧控制器指令、七处计时指令和四处布料/头发更新点。每处必须精确匹配原指令；受影响函数在修改前重新生成，结果必须与现有代码逐字节一致。只重新生成五个 C 编译单元，不改原代码生成目录，不引入运行时 ARM 翻译。

`nd_totk_timing.c` 用已完成画面的单调时间计算五样本平均帧长。原来的游戏时间倍率、半步选择及普通动画路径保持；布料/头发使用各自的测量秒数/30Hz 比率。暂停超过 250ms、重复时间戳和短于 1ms 的异常间隔不发布异常步长；单次物理步长仍按上游限制为最多 1/15 秒。当前发布上限为 60fps，因此不启用依赖额外跳板修正的 >100fps 模式。

## 重建

工具针对已存在的私有工作区 `~/native-recomp/work/totk-1.4.3-20261031`。先保留现有 ELF、manifest、构建记录和存档备份，再把本目录文件放入工作区的 `highfps-20261103/`；准备和构建脚本放其父目录，`preserve_codegen.py`、`build_codegen_candidate.py`与构建/安装脚本放在同一目录。

1. 使用现有代码生成 Python 环境运行 `prepare_totk_highfps.py`，校验18处指令和原函数生成结果。
2. 运行 `build_totk_highfps.py` 生成独立 Ninja 文件。该文件只声明候选对象的构建规则，其他对象仅作为输入，禁止触发全量重建。所有1432个数值游戏单元必须使用完整 V8 对象集及其 SHA 绑定的 `-disable-cgp` 策略；不能因为旧对象存在就复用旧对象。五个候选单元继承 V8 编译规则和逐单元参数。V8对象、生成源、策略或编译记录缺失/不一致则失败。
3. 用 `python3 build_codegen_candidate.py --candidate ~/native-recomp/work/totk-1.4.3-20261031/highfps-20261103` 在已有原生 x86-64 容器内单任务构建，绑定计划、selection、源/头文件、不可变对象与输出ELF；候选ELF或构建回执已存在时拒绝，须使用新目录或先核对归档旧候选。新增文件峰值预计不超过1.2GiB，当前安装不随编译改变。
4. `test_totk_timing.py` 验证30/60/90/120fps的测量时钟不改变游戏速度，以及异常时间戳、暂停和物理步长限制。该测试不证明实际游戏能力或整体验收通过。
5. `install_totk_highfps.py` 仅关闭原诊断游戏单元；先按活进程的 XDG 路径备份隔离存档并校验稳定，保留旧 ELF、manifest和构建记录，原子替换后执行资源与原生依赖校验。出错恢复旧文件。

正常启动使用 `tools/native_review/launchers/totk-steam.sh`，由 Steam 直接运行宿主 ELF，继承掌机图形/手柄会话。诊断 FIFO、脚本输入、录音与性能日志开关均在正常入口移除。继续使用已有隔离存档，不覆盖另一套玩家正式存档。旷野之息入口使用已有动态帧时间支持，`SAVAGEWIND_FPS=0`、`SAVAGEWIND_FRAMEPACE=1`。

安装验证与玩家测试分开：需分别检查 Steam 入口、实际进程、环境、画面、手柄、读档和游戏速度。原生程序存在、日志或计时单测通过均不代表全游戏已可玩。不得将诊断截图黑屏解释成游戏本身黑屏。

## 回滚

停止对应游戏后，将 `~/native-recomp/evidence/library-unlock-20261103/backup/totk-bundle/` 中的 `ultratears`、`bundle.json`、`build-inputs/build-record.json` 一起恢复到原 bundle；运行 bundle 校验，再启动。不要只恢复 ELF。存档备份独立保留，回滚代码不应覆盖玩家后续进度。

本目录不包含私有生成代码、图片或存档。指令位置来自已有 MIT 许可上游；上游声明与许可保留在 Linux overlay 和既有来源树内。

## 后续增量构建必须保留 V8 编译规避

Clang 18 的 CodeGenPrepare 曾在数值游戏单元产生错误机器码，导致开场影片结束或攻击时崩溃。完整 V8 构建对1432个生成单元使用 SHA 绑定的 `-mllvm -disable-cgp`，其余优化保留。增量链接即使发现旧 `build/obj` 对象存在，也不能用它覆盖 V8；五个解帧候选同样必须继承这项规避。

已安装后续六轴等宿主功能时，使用最新交付的 Ninja 链接计划组合：

```sh
python3 preserve_codegen.py \
  --base-plan "$HOME/native-recomp/work/totk-1.4.3-20261031/gyro-20261103/build.ninja" \
  --out "$HOME/native-recomp/work/totk-1.4.3-20261031/cgp-preserved-candidate"
```

输出目录必须不存在。脚本验证 V8 ELF/构建记录、策略、完整源摘要和逐单元恢复参数；只把数值游戏对象切到 V8，保留所选计划的全部宿主、六轴、实时输入和计时对象。五个已有解帧源重新编译；其他对象只作为外部链接输入。`codegen-selection.json`绑定对象摘要、原始/候选源、策略与计划，编译前后均应复核，编译仍使用现有容器、单任务和4GiB进程地址上限。使用 `build_codegen_candidate.py --candidate <输出目录>`生成受约束的编译回执；安装前必须以 `verify_receipt`核对精确输入和输出，缺失/漂移即拒绝。再停止游戏、锁定入口、备份并原子部署 ELF/构建记录/manifest，执行 bundle 完整校验；安装记录的 `compile_overrides_files`应恢复为1432项，同时保留 `native_highfps`和 `native_gyro`。

`test_preserve_codegen.py`使用不含游戏内容的实际混合计划，覆盖旧对象仍存在、候选继承边级参数、最新宿主对象保留，以及策略丢失、源/候选/ELF变化和缺少对象/链接单元时拒绝。该测试不代替影片后切换和攻击的实机复验。
