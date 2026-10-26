# MacNativeGames 深度调研与路线决策（round33，2026-10-27）

> 用户指令：深度调研 https://github.com/ly05010419/MacNativeGames ，不再做可行性调研，
> 参照它把 TOTK + BOTW 直接搬到 Steam Deck。
> 结论先行：**路线已收敛为"totk-recomp（TOTK 1.0.0）+ SavageWindRecomp（BOTW 1.9.0）"双管线**，
> 第 31 轮目标模式提示词即本路线的交付版；MNG 的价值是**验证了天花板 + 提供了资产/补丁可搬件**，
> 不是我们要整体移植的运行时。

## 1. MNG 项目本质（已验证：clone 到 /tmp/macng-a，2431 文件，183M）

| 项 | 事实 |
|---|---|
| stars/license | 5718★，MIT，C 为主 |
| 创建/更新 | 2026-10-17 创建，10-26 仍在更新（10 天 5718★，现象级） |
| 原理 | Switch(ARM64) 与 Apple Silicon(ARM64) 同 ISA → **游戏代码直接原生运行**，仅 patch x18/TP/SVC/counter；NVN 图形在 Metal 重建 |
| 支持版本 | TOTK 1.0.0/1.1.2/1.2.1/1.4.3，BOTW 1.6.0/1.9.0，另有 SSBU/奥德赛/猎天使魔女3/惊奇/奥日/Jamboree/MVdK 社区移植 |
| 上游 | 架构来自 d2r-mobile（4688★）：NSO 改写器 + Horizon HLE host + NVN-on-Metal |
| 着色器 | NVN Maxwell → Ryujinx translator(.NET NativeAOT) → SPIR-V → SPIRV-Cross → MSL；共享 shader list 已 13,422 变体 |
| 性能 | M4 约 90fps（shader 暖后）；首启 shader 预热 60-80s |

**关键点：MNG 不需要 arm→x86，因为 host 也是 ARM64。Steam Deck 是 x86-64，
代码执行层必须重编译——这正是 totk-recomp/SWR 在做的。MNG 自己也没有 Linux 分支
（issue 搜索 linux/steam deck 仅 1 条无关已关闭）。**

## 2. 为什么"整体移植 MNG 到 Deck"不成立（排除 B 路线）

1. **代码执行层是纯 ARM64 原生**（NSO 改写 + 直接执行），搬到 x86-64 就等于重写该层 = 从头做 totk-recomp，不如直接用。
2. **系统服务层（services.c/threads.c/ipc.c/audio_*/romfs.c）是 macOS API 写的**：
   Mach 线程/VM、CoreAudio、IOKit、BSD 语义。移植到 SteamOS = 改写成 POSIX/ALSA/evdev，
   而 totk-recomp 的 runtime/（hle_*.cpp，已为 Linux x86-64 写好）干的就是这件事。
3. **图形层 Metal**：nvn_mtl.m 1.57MB。D2R 的 Vulkan 后端（dm/gfx/vulkan/）虽存在，
   但 totk-recomp 已有自己的 NVN-on-Vulkan（runtime/nvn/），且作者实测 Deck 户外 60fps。
4. MNG 仓库明确自述为 "a technical exploration… feasibility experiments"，社区移植各自维护独立运行时。

**MNG 对我们真正可搬的资产（已验证存在于其仓库）：**
- `games/totk/runtime/game_patches*.c` — 游戏逻辑补丁（帧率解锁、>30fps 修复），可对照 totk-recomp 的 romfs overlay 检查覆盖度
- `docs/shader-list.md` — 13,422 条 shader/bind-state 变体清单 → **Deck 首启 shader 卡顿的共享预热线索**
- `games/botw/` 的版本清单与 1.9.0 资产布局 → 对照 SWR 的 extracted/ 需求
- `build_app.py` 的 exefs/romfs 抽取 + 补丁流程 → 交叉验证我们的 hactool 管线

## 3. 双管线现场状态（本轮 SSH 只读取证，Deck 2026-10-27 00:30）

### BOTW（SavageWindRecomp v0.3.0-alpha.3）
- `~/native-recomp/swr/` 自包含目录：run.sh → usr/bin/savagewind（ELF64 x86-64 PIE，已验证）
- 23:21 实机运行日志（savagewind.log）：**swapchain 1280x720 建立成功，RADV VANGOGH api 1.4.350，
  pipeline libraries on** —— 比 23:10 的 "dumped core" 前进（core 时 extracted/ 尚无游戏资产）
- 唯一缺口 = **BOTW 1.9.0 exefs+romfs** 放入 `~/.local/share/savagewind/extracted/`
  （首次启动自动编译游戏代码 ~16min + shader ~7min，在 Deck 上）

### TOTK（totk-recomp @ a32f709e，目标版本 1.0.0）
- `~/native-recomp/src/totk-recomp/` 已克隆；构建链全就绪：
  hactool_bin 已编译（18:26）、venv-capstone 5.0.9、容器 nativedeck-build（Ubuntu 24.04）deps prewarm 163M
- **runtime 已编译出 15.8MB 原生 ELF**：`~/native-recomp/dist/totk-recomp/totk`
  `readelf` 三判据①② 已过（ELF64/X86-64，dist 带 lib/ 自包含）
- parity 探针 553,170 次比对 0 mismatch（kern_a64 提升正确性证据，env37）
- 唯一缺口 = **TOTK 1.0.0 xci + prod.keys** → `build-totk.sh` 一键（预计 Deck 上 1-1.5h）
- 注意：`~/native-recomp/dist/totk-recomp/data` 当前为空 → 现有 ELF 是无 ROM 的 runtime 空壳，
  AppImage 5.7MB 也是边界行为测试包（T1 记录），**不构成可玩游戏**

### ROM 现场排查（本轮穷尽）
| 位置 | 结果 |
|---|---|
| Deck ~/Games/totk | 空目录（用户游戏安装任务的落点，21:05 创建） |
| Deck ~/Downloads、/home 全盘 >1G 文件 | 仅 swapfile |
| Mac ~/Documents ~/code /private/tmp | 无 .xci/.nsp/prod.keys |
| NAS `/Volumes/Share/游戏/Switch/` | **TF-backup/tf-20261010-pre-cp100.img.zst（100.7GB 压缩，NAND 全盘镜像）** |
| NAS 其他（LM/ISO/跨机续跑/code/运维资源） | 未见游戏目录 |

**TF-backup 是 ROM 的唯一现实来源**：10 天前对 Switch 的完整 NAND 备份，
TF 备份必然含 prod.keys（在 prod 分区 /prod.keys 或 keychain）与全部游戏 NSP 内容。
流式特征扫描已启动（见 §5）。

## 4. 路线结论（A 采纳，B/C 排除）

- **A（采纳）= 第 31 轮目标模式提示词原文**：SWR(BOTW 1.9.0) + totk-recomp(TOTK 1.0.0)，
  自包含目录 + run.sh，Steam non-steam game 入口。
- B（整体移植 MNG 运行时）排除理由见 §2。
- C（混合）实际退化为 A：totk-recomp 本身就是"MNG 式 HLE runtime + x86-64 重编译代码 + NVN-on-Vulkan"，
  三层全齐，只是代码执行层不同——而这正是 ISA 差异逼出来的。
- MNG 资产（shader list、game_patches）作为**加速/修复弹药**并入 A，不另立管线。

## 5. 下一轮行动（按阻塞排序）

1. **ROM 决策（唯一硬阻塞）**：
   - 用户 Switch 手边 → TF/SideLOad 导出 1.0.0 TOTK.xci + 1.9.0 BOTW.xci + prod.keys（最干净，TOTK 必须 1.0.0）
   - 或：我流式扫 TF-backup → 若命中 NCA/prod.keys 特征 → 解 zst 定位 → 直接抽（约 3-6h 带宽，Mac→Deck）
   - TF 镜像里若是 1.4.3 则 totk-recomp 不认（版本墙）→ 需用户 Switch 上把 TOTK 降回 1.0.0 再备，或走 ultratears 支线
2. BOTW 资产入位 → SWR 首启（~23min 编译+shader）→ Moonlight 串流验收 + 三判据③ GPU 阶段 maps
3. TOTK：`nohup build-totk.sh <xci> <prod.keys> -O1` → 安装 → 首启验收
4. M5 单批：shortcuts.vdf 两条 non-steam game
5. 收尾：evidence → codex/roundNN 分支 → MR → WeKnora finish

## 6. 证据索引

- MNG clone：/tmp/macng-a（README/构建表/games/totk 结构均已读）
- d2r-mobile clone：/tmp/d2rm-a（dm/gfx/vulkan/ 存在性已验）
- Deck 取证：本 SSH 会话（swr 日志、readelf dist/totk、roms 目录、TF-backup 路径）
- TF 扫描：evidence/round33/tfscan.log（增量追加）
- 第 31 轮提示词：仓库 main 10f341e（路线已写死，本轮未推翻）

## 7. TF-backup 扫描进展（02:35 更新）

- 已解压进度：~324MB+/100GB 流式，速度受 SMB 读取限速（NAS 带宽），全程预计 30-90min
- 关键命中（均为 **atmosphere 用户区字符串引用**，非文件本体）：
  - `/switch/prod.keys`、`sdmc:/switch/prod.keys` → 用户 SD 上有 prod.keys（atmosphere 读取路径）
  - atmosphere 内容数据库中的 NCA 哈希引用（`.nca`/`cnmt.nca`）→ 游戏 NSP 内容在 SD 镜像 ext4 里
  - 0 个 `NNOA` 原始 NCA 头命中（前 300MB 范围）→ NCA 数据块在 ext4 数据区，字节流扫描对碎片化/压缩区不敏感
- **结论修正**：TF 备份 = SD 卡全盘镜像（zstd 压缩）。最可靠抽取路径不是字节流扫描，而是
  ① `zstd -d` 展开（需 640G 空间 → 走 Share 或分块）② 识别镜像内 SD 分区表（MBR/GPT）
  ③ ext4 挂载/`debugfs` 直接取 `switch/prod.keys` + `switch/PATCH/0100F2C0115B6000/` (TOTK) + `.../010018E011596000/` (BOTW) 的 NSP 内容
- 字节流扫描继续跑，作为交叉验证（命中 TearsOfTheKingdom/BreathOfTheWild 字符串 = 版本证据）
