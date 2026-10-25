# Switch ARM → x86_64 原生移植 Steam Deck 可行性评估（终版 v3）

**task_id**: `nativedeck-20261024` | **phase**: finish | **scene**: homelab
**status**: partial（情报 + GitHub/论坛检索 + 本地反汇编实证 + Deck 真机只读取证全部完成；**真机实跑未做**）
**hardware_validated**: **false**（Deck 上未实跑任何上游发布物或重编译产物）
**只读约束**: 全程未在 Deck 上写入/装包/改配置；本机仅新增本目录与 `/private/tmp/nativedeck-20261024/`
**证据标记**：`[靶机]`=Deck 真机只读命令实测｜`[官方]`=项目官方发布说明/文档原文｜`[实证]`=本地反汇编静态核验｜`[推断]`=由已验证事实推出｜`[未验证]`=无证据

---

## 1. 结论（先给结果）

**能实现。你设想的形态不是设想，它已经在售，而且 Deck 就是你的机型。**

1. **路线本身天然满足"不是模拟器、不过兼容层"**。静态重编译（AOT）产出的就是普通 Linux **x86-64 原生 ELF**，加载期和运行期都没有翻译器介入，不存在 Wine/Proton/DXVK。这条路上有四个活跃实现：
   - **LAS Recomp**（`peiikai/LASRecomp`，MIT，★1720）：单游戏（织岛冒险）**官方发布 x86_64 AppImage**，beta_5 发布说明 Performance 段逐字写着 **"Steam Deck runs at 60 FPS"**、"Big improvements on integrated graphics and handhelds" `[官方]`
   - **totk-recomp**（`Muhammad1259-sigma/totk-recomp`，★3，2026-10-20）：README 第一句就是 "static recompilation of TOTK (Switch 1.0.0) to **native Linux x86-64, aimed at the Steam Deck**"，并写 **"Runs on a Steam Deck in the author's tests: about 60 fps outdoors (62-64 fps measured on one walk)"** `[官方]` → **TOTK 在 Deck 上原生直跑已被第三方实测**
   - **ScarletNX**（`scarletnx/ScarletNX`，GPL-3.0，★220）：**通用** ARM64→x86-64 静态重编译器 + Horizon HLE + NVN-on-Vulkan；nightly 发 **`ScarletNX-linux-x86_64.AppImage`（47.3 MB）**，同一批资产里还有你说的那条 iOS 线（`ScarletNX-ios-arm64.ipa` 28.9 MB）`[官方]`。**全库无一条 Deck/SteamOS 记录**（issue 检索 `deck`/`steamos` 仅 1 条无关命中）`[官方]`
   - **kirikae**（`Cor3Duo/kirikae`，Apache-2.0）：Rust+Cranelift 通用重编译，官方只出 Windows x64
2. **Deck 的四项硬门槛现场全部达标**（§2 靶机实测）：AVX2 ✓ / Vulkan 1.4.350（RADV VANGOGH，要求 1.3）✓ / glibc 2.43（要求 ≥2.35）✓ / **系统自带 SDL3 3.4.12**（LAS 要求 ≥3.4）✓
3. **`.deb` 路线不成立**。SteamOS 是 Arch 系（`pacman`，DBPath=`/usr/lib/holo/pacmandb/`）+ 只读 rootfs，**没有 apt/dpkg** `[靶机]`
4. **原生安装形态 = AppImage（首选）／纯目录 + run.sh（次选）／Flatpak（暂无包）**，全部通过 Steam **"添加非 Steam 游戏"** 进 Gaming Mode。详见 §3
5. **"唯一要攻克的是 arm to x86"这句话必须改写**：墙 A 是 CPU ISA（iOS 的省力全来自 host ISA == guest ISA，跨 ISA 后每个字节都要翻译）；**墙 B 是 Switch 发行包里的 Maxwell 二进制着色器**必须离线翻译成 SPIR-V 并建缓存（iOS 同样有此墙）。Deck 侧墙 B 的实测体积：**一款游戏 2700 个着色器 = 245 MB，另一款 18500 个 = 2 GB**（ScarletNX `docs/USAGE.md`）`[官方]`
6. **两条独立外部证据链强度不同，不可混为一谈**：LAS 的 Deck 60fps 是**维护者发布说明口径**（无机型代号、无帧率曲线），同期玩家实测是 #181（Deck 上 30→25fps 回归）、#213（森林 30→20fps）、#348（过场视频偶发整机冻结）`[官方]`；ScarletNX 的 TOTK 44fps 基线测的是**桌面独显**，Deck 形态零记录 → **TOTK-on-Deck-ScarletNX 在给出实测前一律 `hardware_validated=false`**

**一句话**：路径存在、Deck 环境完全达标、已有第三方在 Deck 上原生跑到 60fps 量级；缺的只是一次属于你自己的真机测量。但"只卡在 arm→x86"不成立，着色器离线化 + iGPU 内存预算是同等量级的第二关。

---

## 2. Deck 真机取证（`deck@192.168.1.105`，只读，2026-10-24；`deckprobe/env*.txt` 为原始输出）

### 2.1 硬门槛
| 项 | 实测 | 判定 |
|---|---|---|
| OS / BUILD_ID | SteamOS 3.9.5 holo / 20261023.100；DMI `Valve Jupiter` | — |
| 内核 | `7.2.7-valve2-2-neptune-72` | ≥6.7 → PAGEMAP_SCAN 写追踪可用 ✓ |
| CPU | AMD Custom APU 0405，**4C8T Zen2**，411MHz–3501MHz，governor `powersave` | SMT 8 线程与翻译代码共享 |
| 指令面 | `avx avx2 fma bmi1 bmi2 sse4_2 pclmulqdq aes sha_ni f16c fsgsbase rdseed` | AVX2 ✓；AES/PMULL→`aes`/`pclmulqdq` ✓；线程指针→`fs` ✓；**无 avx512 / gfni / vaes / vpclmulqdq** |
| GPU/Vulkan | `AMD Custom GPU 0405 (RADV VANGOGH)`，INTEGRATED，`apiVersion 1.4.350`，Mesa 26.2.0-devel；`radeon_icd.x86_64.json` → `/usr/lib/libvulkan_radeon.so` | Vulkan 1.3 门槛 ✓ |
| Vulkan 扩展 | `VK_EXT_memory_budget` / `external_memory_host` / `descriptor_indexing` / `KHR_pipeline_library` / `EXT_shader_module_identifier` / `KHR_dynamic_rendering` 全部可枚举 | 不因缺扩展阻塞上游任一图形优化路径 ✓ |
| glibc | 2.43 | ≥2.35 ✓ |
| SDL3 | `/usr/lib/libSDL3.so.0.4.12`，`pacman -Q sdl3` → `sdl3 3.4.12-1`；另有 `sdl3_ttf 3.2.2-3`；Steam 自带 `~/.local/share/Steam/steamrt64/libSDL3.so.0` | LAS 要求的 ≥3.4 原生就有 ✓ |
| 内存 | 14 GiB（可用 ~11 GiB）+ zram 7.2G + `/home/swapfile` 16G = **swap 23 GiB** | totk 要求 16GB RAM：达标但无余量 |
| 显存 | `mem_info_vram_total` = 1 GiB，GTT = 8 GiB（APRT 统一内存） | 见 §4 风险 1 |

### 2.2 运行环境（决定"能不能直接跑")
| 项 | 实测 | 对安装形态的意义 |
|---|---|---|
| FUSE | `libfuse3.so.3.18.2` + **setuid `/usr/bin/fusermount3`** + `/dev/fuse`；**旧版 `libfuse.so.2` + setuid `/usr/bin/fusermount` 也在** | AppImage 可 FUSE 直挂直跑 ✓ |
| squashfs | `/lib/modules/.../fs/squashfs/squashfs.ko.zst` **存在但未加载**，`/dev` 只有 `loop-control` 无 loop 节点 | 传统 loop-mount 路径不可靠 → 兜底 `--appimage-extract-and-run`（`unsquashfs`/`7z` 均在位，可手工解包） |
| 包管理 | `pacman` 在，`DBPath=/usr/lib/holo/pacmandb/`，5 个 sync db 在场（holo/jupiter 2026-10-24 更新）；`mirrorlist` → `steamdeck-packages.steamos.cloud`；**无 apt/dpkg/nix/brew** | **deb 不适用**；pacman 理论可用（见下条限制） |
| rootfs | `steamos-readonly status = enabled`；`/` 与 `/usr` 实际 btrfs `rw`；`/var` ext4 rw；`/etc` 是 overlay；**A/B partsets + `steamos-update`** | 官方升级会覆盖 `/usr`，装进系统的包不持久 |
| **根分区余量** | **`/` 共 5.0G，仅余 837M**；`/var` 余 176M；`/home` 余 **544G** | 任何产物/镜像/缓存**必须落 /home**；pacman 装 clang(41MB)+lld+cmake+ninja+依赖会吃掉大半根分区 |
| pacman 实证 | 本机 2026-10-24 15:17 有两条 `pacman -S --noconfirm xorg-x11-apps python-xlib` 记录，日志**无 `installing` 行**，`pacman -Q` 查不到该二包（非本次操作） | `pacman -S` 在非交互 root 下未成功；不把 pacman 当可靠分发通道 |
| 容器 | `podman` + `distrobox` + `fuse-overlayfs` 可用；**无任何本地镜像**；storage 在 `~/.local/share/containers`（/home，544G ✓） | Deck 上重编译的唯一现实路径 |
| 编译链 | `clang / gcc / cc / make / cmake / ninja / cargo / rustc / llvm-config` **全部缺失** | 重编译/AOT 构建必须容器内做 |
| Flatpak | 1.18.4，flathub + flathub-beta；已装 Protontricks/Edge/Moonlight/Parsec/ProtonUp-Qt；`flatpak search scarletnx`/`recomp` **无匹配**，`switch` 只返回 Ryujinx/Eden 等模拟器 | Flatpak 通道技术可用但**上游未出包**，短期不可依赖 |
| 会话/性能层 | 当前 `gamescope --generate-drm-mode fixed ... -O *,eDP-1`（**gamescope 3.16.30.1+**）；`gamemoded` active；`mangohud` 在位；`implicit_layer.d` 有 `MangoHud` + `VkLayer_FROG_gamescope_wsi` + `VkLayer_MESA_device_select` | 原生 AppImage 直接吃到 Steam 的帧率限制/性能覆盖层，无需额外配置 |
| 手柄 | `/dev/hidraw*` ACL 已含 `user:deck:rw-`；`60-steam-input.rules`、`70-steam-jupiter-input.rules` 在位 | SDL3 原生手柄（含 rumble/gyro）+ Steam Input 两条路都通 |
| ulimit | `Max locked memory = 8 MiB`（会话内同值）；`vm.max_map_count = 2147483642` | 若上游用 `VK_EXT_external_memory_host`/userptr 大量锁页需关注（LAS 在 Deck 上确实走 userptr） |
| 网络 | `api.github.com` 从 Deck 直连 HTTP/2 200 | Deck 可自行拉 AppImage，无需中转 |
| 现状痕迹 | **无** AppImage / `totk-recomp` / `scarletnx` / `lasrecomp` 目录；`shortcuts.vdf` **不存在**（从未加过非 Steam 游戏）；decky/hhd **未装**；`/tmp` 是 tmpfs 7.2G | 从零起步，纯新增即可回滚（删目录 + 删 shortcut） |

---

## 3. 你问的核心：成功后游戏怎么"安装"？（可落地）

**不是 deb。** SteamOS 无 apt/dpkg；且 rootfs `steamos-readonly enabled`、`/` 只剩 837M，官方 A/B 升级会覆盖 `/usr`，"装进系统"这条路既不可用也不该用。正确形态是**自包含分发 + 用户目录数据 + Steam 非 Steam 游戏入库**三件套。

### 形态 A：AppImage（LAS Recomp / ScarletNX 官方发布形态，首选）
零依赖落盘，产物就是一个可执行文件，天然可回滚（删文件即卸载）。
```bash
mkdir -p ~/native-recomp && cd ~/native-recomp
curl -LO https://github.com/peiikai/LASRecomp/releases/download/beta_5.1/LAS.Recomp-beta_5.1-linux-x86_64.AppImage   # 112.2 MB
chmod +x LAS.Recomp-beta_5.1-linux-x86_64.AppImage
./LAS.Recomp-beta_5.1-linux-x86_64.AppImage            # Deck 有 setuid fusermount3，FUSE 可直挂
# FUSE 失败时的官方兜底（LAS 文档明写；LAS issue #346 即 Deck 上的 Steam 启动参数写法）
APPIMAGE_EXTRACT_AND_RUN=1 ./LAS.Recomp-beta_5.1-linux-x86_64.AppImage
```
- 数据目录：LAS → `~/.local/share/lasrecomp`（游戏解包/存档/种子/`larecomp.ini`/着色器缓存/日志）；ScarletNX → `~/.local/share/scarletnx`，或用**便携目录** `.scarletnx/`（放在 AppImage 旁边即生效，适合放 SD 卡）
- 自更新：ScarletNX 官方说明用 **AppImageUpdate** 直接升到最新 nightly（资产带 `.zsync`）；Deck 上无 `appimagetool`/`runtime-zsync`，需另取单文件
- 首次启动有代价：LAS beta_5 起"首次启动多花几分钟准备"；totk-recomp 的 `tools/linux/warmup.sh` 着色器预热在 Deck 全新安装约 **4.5 分钟**
- 注意：AppImage **不能放 `/tmp`**（Deck 的 `/tmp` 是 tmpfs 且 `nosuid`，setuid `fusermount3` 在 `/usr/bin` 所以 FUSE 仍可用，但重启即丢；`--appimage-extract-and-run` 会往 `$TMPDIR` 解 100+MB）

### 形态 B：纯二进制目录 + `run.sh`（totk-recomp 形态，无包管理器概念）
它**不发可执行文件**，发的是 recompiler + runtime + 构建脚本；**游戏由你自有 dump 现场编译产出**。
```bash
# Deck 上 rootfs 只读且无工具链 → 官方指定用 distrobox(Ubuntu 24.04) 或换台 Linux PC 构建，再把 dist/ 拷回
distrobox create --image ubuntu:24.04 --name totk-build -H   # -H 共享 $HOME，产物直接落 /home
distrobox enter totk-build -- ./tools/build_from_xci.sh ~/Games/TOTK.xci ~/.switch/prod.keys --out ~/totk-build
~/totk-build/dist/totk-recomp/run.sh                          # 交付物就是这个目录
```
- 磁盘：峰值 **45 GB**、成品 **20 GB**（Deck `/home` 余 544G ✓）；RAM 要求 16GB（14Gi+23GiB swap，够但紧）
- **`dist/` 不可跨机搬运 JIT/AOT 缓存**：cache key 含 ABI/LLVM 版本/runtime 库/host CPU+features/SVC-hook 模式/`-O` 级别，不匹配即拒绝（ScarletNX `AOT_PACKS.md`）
- 构建时间是最开放的问题：作者 PC clang `-O2` 约 17 分钟墙钟（~2.1h CPU）；**Deck 上未实测，README 预计 1–1.5h**

### 形态 C：Flatpak（技术上 Deck 完全支持，但上游无包）
`flatpak search` 实测 scarletnx/recomp 零命中。要把它做成 Flatpak 需自己写 manifest（AppImage 转 Flatpak 可行但会丢掉上游的 zsync 自更新）。**短期不作为交付形态。**

### 进 Gaming Mode（三种形态共用）
Deck 上 `shortcuts.vdf` 目前不存在 → 这是全新写入，删除即完全回滚。
- 桌面模式：Steam → 游戏 → **"添加非 Steam 游戏"** → 选 AppImage 或 `run.sh` → 写入 `~/.steam/steam/config/shortcuts.vdf`（注意：真实库根是 `~/.local/share/Steam`，`~/.steam/steam` 是其符号链接）
- 启动选项（在 Steam 里给该 shortcut 设置）：
```
APPIMAGE_EXTRACT_AND_RUN=1 MANGOHUD=1 %command%          # FUSE 兜底 + 帧率
GAMEMODE_AUTO=1 VK_DEVICE_EXCLUSIVE_LIST=... %command%   # 按需
TOTK_FPS=60 %command%                                     # totk-recomp：90/60/30/0；TOTK_UNLOCK_FPS=1 解锁
```
- Steam Input：`steam-devices` udev 规则在场、`hidraw` 已授权 → 手柄走 Steam Input 或 SDL3 原生两条路都通（LAS 文档：Steam Input 开启时游戏看到的是虚拟 Xbox 手柄、提示变 Xbox 图标）
- 想要 GryppingMode 里更完整的体验可装 **Decky Loader + gamescope 相关插件**，但 decky 现场未装，属额外写入，非必需

### "游戏本体"不是安装包（关键认知）
两个项目仓库都**不含游戏码/数据/keys**。你需要：自有 `.xci`/`.nsp` dump + 自有 `prod.keys`（TOTK 1.0.0 需 master key rev `0x0E`，title `0100F2C0115B6000`）→ 本机重编译 → 产出 x86_64 专属目录。ScarletNX 的形态是：AppImage 直接吃 dump（`./ScarletNX-linux-x86_64.AppImage Game.nsp`），**每个游戏得到一份 AppImage 副本**放在 `recompiled/<titleID>/`，`--game=recompiled/<titleID>` 启动。所以"安装"这件事在你的机器上实际等于"解包 + 重编译 + 着色器预热"，不是一条 `apt install`。

---

## 4. 风险清单（Deck 特化，按优先级）

1. **iGPU 内存预算 / BAR 窗口（高，已量化）**：Deck GPU PCI Region 0 = **256 MB**（64-bit prefetchable，实测）。ScarletNX 自述无 resizable BAR 时 staging 窗口 246 MB、驱动只留 47~111 MB，超出即内核级缺页 → 曾出现 3 秒内 10fps 爬行，23 次镜头运行命中 12 次 `[官方]`。LAS 在 Deck 上因 3.25 GiB guest 堆落成 **userptr import**、每帧写追踪作废 3.2GB 导入，森林 **30→20fps**（PR #213 修，但 PR 自述 "Not tested on a Deck yet"）。**Deck 同时命中两个坑，且 `mem_info_vram_total` 只报 1 GiB、GTT 8 GiB。ScarletNX 在该形态下行为完全未测。**
2. **RADV 设备丢失（高）**：ScarletNX issue **#662**（NAVI22，Paper Mario TYD 约 6.5 分钟后 GPU device lost，Splatoon 3 同现）。VANGOGH 是更老 RDNA2 IP，需专门长跑；内核 cmdline 已带 `amdgpu.lockup_timeout=5000,10000,10000,5000` `[靶机]`。LAS #348 也有 Deck 侧过场视频**整机冻结**须长按电源。
3. **性能余量（中高）**：TOTK 的 44fps 基线来自桌面独显；Deck 是 4CU RDNA2 级 iGPU + 4C8T Zen2 与翻译代码共享 CPU，**不可线性外推**。LAS 的 Deck 实测集中在 20–30fps 区间（60fps 为官方口径）。governor `powersave` + SMT 会让重编译产物的短指令序列更敏感。
   - **出处更正（v3.1）**：LASRecomp **Issue #40 存在**（"Low FPS"，closed，2026-10-15，53 comments），正文是 **"Running Bazzite on an Rog Ally X with the Beta 4 appimage … stuck at a constant 20fps"** `[官方]`——即它是 **ROG Ally X + Bazzite** 的低帧反例，**不是** Deck 稳定 60fps 的证据。Deck 60fps 的唯一出处仍是 beta_5 / beta_5.1 官方 changelog；#40 只能作为"host 驱动栈/机型差异大"的补充证据。（早前 v2 稿曾误判"该仓无 #40"，此为对该误判的纠正。）
4. **着色器墙 B（中，已有容量与耗时数据）**：2700 着色器 = 245 MB / 18500 = 2 GB；首次进新区域的卡顿长度由 Deck 的 NVMe + 8 核决定。`async_pipelines=1` 换平滑度但上游自承会让 edenprobe 190 用例失败、默认关闭。totk-recomp 走 `warmup.sh` 4.5 分钟预热路线。
5. **AppImage/FUSE（低，必现）**：传统 loop 路径在本机不可靠（squashfs 未加载、无 loop 节点），**统一带 `APPIMAGE_EXTRACT_AND_RUN=1` 兜底**。
6. **构建路径（低但硬）**：Deck 无 clang/gcc/make/cmake/ninja/cargo，rootfs 只读且 `/` 仅余 837M → **一切构建走 distrobox/podman，镜像与产物必须在 /home**。pacman 装工具链不推荐（会挤爆根分区 + 官方升级覆盖 `/usr`）。
7. **memlock 8 MiB（中，条件性）**：会话内 `Max locked memory = 8 MiB`。LAS 在 Deck 走 userptr/import 路径，若上游有 `mlock`/锁页假设需实测；未在上游发现该假设。
8. **FP 语义（中）**：ARM default-NaN/定向舍入/FPSR 累计上游自认有缺口（`DIVERGENCES.md`）；`main.nso` 的 NEON 密度未测——本地样本 `libnx.a`（201,867 条指令）算术 NEON 实测为 0，但那是系统/框架代码，**不可外推到游戏主二进制**。
9. **版本锁定（中）**：totk-recomp **仅支持 1.0.0**（main build ID `082CE09B06E33A12`），其他版本不工作。

---

## 5. 持续验证计划（每次只推进一项，纯新增、可回滚）

- **V0（本轮完成）** 情报 + GitHub/论坛 + 本地反汇编 + Deck 只读取证 → 本报告。
- **V1（10 分钟，纯新增，需你核准写入）** 拉上游 AppImage 做**存在性**验证，不碰游戏内容：
  ```bash
  mkdir -p ~/native-recomp && cd ~/native-recomp
  curl -LO https://github.com/scarletnx/nightly/releases/latest/download/ScarletNX-linux-x86_64.AppImage
  curl -LO https://github.com/peiikai/LASRecomp/releases/download/beta_5.1/LAS.Recomp-beta_5.1-linux-x86_64.AppImage
  chmod +x *.AppImage && ./ScarletNX-linux-x86_64.AppImage --version
  ```
  判定：能否在 SteamOS 上启动并列出驱动。**仍是"环境侧"证据，不升级为 hardware_validated。** 回滚：`rm -rf ~/native-recomp`。
- **V2（hardware_validated 的最低门槛）** 用你自有织岛游戏文件在 Deck 上跑完 LAS beta_5.1 全流程（含首启准备 + 实跑），采帧率/温度/功率/是否冻结，落 `~/.local/share/lasrecomp`。通过则"Deck 能原生跑 Switch AOT 产物"升级为**已验证**。
- **V3** ScarletNX 重编译一个中等规模游戏，Deck 长跑 30 分钟，采帧率、GPU busy、device-lost、`vi:` 缺页计数 → 回答 VANGOGH 稳定性与风险 1/2。
- **V4（终极靶）** TOTK：你自有 1.0.0 XCI + `prod.keys` → distrobox 构建 totk-recomp → Deck 实测，对照上游 62-64fps（野外）与 4.5 分钟 warmup 声明，**并首次给出 Deck 上真实构建时长**（当前 README 只有 1–1.5h 预估）。
- **持续项** 每周复查 ScarletNX issue/PR（#629 volatile 代价、#662 后续、兼容矩阵是否出现 Deck 行）、LAS 的 Deck 标签 issue、totk-recomp 仓库（当前 ★3、仅 2 commit、无 release、launcher 内建构建未接线）。**以本报告时间戳为基线去重。**

## 6. 证据文件
本目录内（已随报告归档）：`deckprobe/env.txt`~`env16.txt`（Deck 只读命令原始输出）、`deckprobe/bar.txt`（GPU BAR：Region 0 = 256M prefetchable）、`deckprobe/vk.txt`（所需 Vulkan 扩展逐项命中 + device limits）、`gh/totk-recomp-README.md`、`gh/las-beta5-notes.md`、`gh/snx.json`/`gh/las.json`（nightly/beta_5.1 release 资产清单与 SHA 表）。
工作副本（未归档，可重建）：`/private/tmp/nativedeck-20261024/snxdocs/`（ScarletNX 官方文档 17 篇）、`las-linux.md`、`lasreadme.md`、`probe/instruction_profile.json`（201,867 条指令画像）、`README-可行性评估.md`（v2 稿）。
WeKnora 收尾记录 knowledge_id：`8b8ed092-6bd3-4014-90db-a9ca24317892`（HOMELAB 库）。

---

## 7. 追加结论：手柄映射 / 陀螺仪 / 虚拟 Amiibo（第 7 轮，2026-10-25）

细节全部在 `技术栈与实现路径.md` §19–§21，这里只放判定结果。

1. **手柄映射几乎零成本**：Deck 内置手柄与 Switch 同为"A 右 / B 下"+ 非对称摇杆。SDL3 的面孔风格判定（`GetGamepadFaceStyleForGamepadType`）把 Deck 归入 ABXY，ScarletNX 的默认位置映射 `POSITION` 本身就是任天堂布局、`snx_pad_symmetric()` 对 Deck 返回 0（非对称）→ **不要开 A/B 交换**。真正需要动手的只有 ZL/ZR（Deck 是模拟扳机，LAS 专门造了 `PADB_LTRIGGER/PADB_RTRIGGER`）与背键落点（SDL 有 `SDL_GAMEPAD_BUTTON_STEAM_DECK_{LEFT,RIGHT}_PADDLE{1,2}` 专用枚举）。`hardware_validated=false`。
2. **陀螺仪是本项目在 Deck 上唯一的输入侧硬风险，但有成熟规避**：SDL3 **已内置** Deck 内置 IMU 驱动（`SDL_hidapi_steamdeck.c` 解析 `sGyro*/sAccel*`，±2000 dps / ±2 g），但 Steam Input 生效时设备退化为 `28de:11ff` 虚拟手柄 → 传感器丢失（SDL #9148 已被"unplanned"关闭、#12997/#15201 仍 open）。可用规避：Steam Input 陀螺仪设 None 透传，或跑 `SteamDeckGyroDSU`（cemuhook DSU / UDP 26760，纯 home 目录 user systemd 安装，无 root）；SDL PR **#14353** 正在给 SDL3 加 **DSU 客户端驱动**（里程碑 3.6.0），届时"recomp 侧零代码"即可拿到体感。三家实现里 ScarletNX 与 totk-recomp 的六轴 HLE **已完整**（四元数/Mahony 融合），**LAS Recomp 完全没有体感**。
3. **虚拟 Amiibo 可做，注入点已定位**：三家都没有 NFC 后端（ScarletNX 只有 `nfp:user`/`nfc:user` 的完整 IPC 声明 + 一律返回 `NFP_DEVICE_NOT_FOUND` 的桩），需自实现。可直接照搬 Ryujinx 的 `INfp`/`VirtualAmiibo` 数据模型：NTAG215 / 540 B dump / UUID 9 B+BCC 持久复用 / `ApplicationAreaSize=0xD8` / `NfpDeviceState` 时序 + ActivateEvent 事件驱动 / 每卡持久 JSON。**Deck 无 NFC 硬件 → 纯软件注入是唯一与"原生运行"契合的路线**，硬件仿真标签（Flipper/AmiiBee）对 IPC 路线无效。红线：从 dump 解应用区绕不开 `key_retail.bin`，故"仅备份自有实体卡"在技术上无法与批量解密分离；空应用区模式可完全不需密钥。
4. **对"可行性"总结论无影响**：这三项都落在 HLE/输入层，不改变墙 A（CPU ISA 已解）与墙 B（GPU shader 已解）。它们决定的是"体验能否优于原版 Switch"，而不是"能不能跑"。
