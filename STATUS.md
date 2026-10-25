# nativedeck-20261024 挂账状态

## 挂账原因
用户"正在执行游戏安装的任务"，Deck（deck@192.168.1.105）禁止一切 SSH/scp/写入操作。

## 挂账时间
2026-10-25

## 当前进度
- ✅ 主报告 report.md（可行性+取证+安装形态+风险+验证计划）
- ✅ 作战计划.md（Phase 1-6）
- ✅ 技术栈与实现路径.md（17 节，~34KB）
- ✅ Deck 只读取证 16 份（env.txt ~ env16.txt）
- ✅ GitHub 归档（totk-recomp/las-beta5/snxjson/lasjson）
- ✅ 工作副本 snxdocs/ 17 篇全部精读 + 仓库克隆
- ✅ 第 6 轮（2026-10-25 挂账期内的 Mac 本地只读补强）：LAS issue #348/#234/#181/#213/#71/#255/#92/#258/#278/#290/#291/#310 + ScarletNX #661 + nightly 资产清单全部读完
  → 新增 技术栈与实现路径.md §18（Deck 实测性能演进表 + AMD 特化坑表 + 生态信号 + V3 SOP 修订）
  → WeKnora HOMELAB knowledge_id c35f5915-0c93-4d43-8dbb-b0bc66910312（checkpoint-deckevidence，已回读正文）
- ⏳ V1-V4 全部待挂账解除（hardware_validated 仍为 false）

## 恢复条件
用户说"继续"或"恢复 nativedeck 任务"，继续第 5 轮未完成部分（issue 穷尽读取 + WeKnora finish）。

## 已确认结论（不依赖未完成工作）
1. 能实现：三实现全产出原生 x86-64 ELF
2. .deb 不成立，AppImage 首选
3. 墙 A=CPU ISA，墙 B=GPU（NVN→Vulkan shader）
4. Deck 硬件达标，特化风险已列
5. iOS 省力=host ISA==guest ISA；Deck 必须重编译

## 下一轮行动（需用户解除挂账）
1. Phase 1/V1：Deck 上拉上游 AppImage 做存在性验证（`APPIMAGE_EXTRACT_AND_RUN=1 --version`）
2. V3 部署按 §18.4 修订清单执行（非 Steam 游戏 + 关桌面键盘映射 + 过场视频压测 #348）
3. V4 TOTK 需用户自有 .xci + prod.keys
4. 每周复查项：ScarletNX issue/PR、LAS Deck 标签 issue、totk-recomp 仓库

## 五要件审计（2026-10-25）
①可行性 report.md §1 ✅ ②作战计划 作战计划.md ✅ ③实现路径 技术栈与实现路径.md §1/§3/§9 ✅
④转换方式 同上 §3 ✅ ⑤原生编译技术栈 同上 §2/§4/§5/§11-§16 ✅
只读调研侧证据链已闭合；再推进必须接触 Deck → 已按用户"挂账"指令暂停目标。

---

## 第 7 轮追加（2026-10-25，挂账期内，全程未触碰 Deck）

- ✅ 手柄映射取证成文 → 技术栈与实现路径.md §19（SDL3 面孔风格链、Deck=ABXY=Switch 布局、`snx_pad_symmetric`=0、背键专用枚举、三家可配置面、LAS 按键提示贴图重绘 texpatch）
- ✅ 陀螺仪取证成文 → §20（ScarletNX/totk-recomp 六轴完整、**LAS 无体感**；Deck 内置 IMU 四条路径判定：SDL 驱动已存在但被 `28de:11ff` 退化阻断 / GyroDSU DSU-UDP 可用 / Steam 鼠标映射不可用 / 自定义内核驱动不可用；SDL PR #14353 加 DSU 客户端）
- ✅ 虚拟 Amiibo 取证成文 → §21（三家全空白 + ScarletNX `nfp:user`/`nfc:user` 桩接口面；Ryujinx 数据模型：NTAG215/540B/UUID BCC/`0xD8` 应用区/DeviceState 时序/ActivateEvent/`VirtualAmiiboFile`；三条路线对比 + `key_retail.bin` 红线；V6 四步实现顺序）
- ✅ 作战计划.md 追加 §7：V5（6 步，含 5.1 根因级判据）/ V6（6.1 只读探针 + 6.2-6.4 需批准）/ V7 + 标记升级路径（input_validated / motion_validated / amiibo_gap_mapped）
- ✅ report.md 追加 §7 判定结论四条（含"对可行性总结论无影响，只影响体验上限"）
- ⚠️ 记账纠正：早前 STATUS 写的"V1 已完成（两个 AppImage 在 Deck 上初始化验证通过）"**无证据支持**（deckprobe 无 AppImage 运行记录），已按 V1=未执行处理；Mac 本机 `/private/tmp/nativedeck-20261024/` 的两个 AppImage 从未推送到 Deck
- ⏳ 五要件之外的三项新增（手柄/陀螺仪/Amiibo）本轮成文完成；hardware_validated 仍 false

## 七要件审计（2026-10-25 第 7 轮）
①可行性 report.md §1+§7 ✅ ②作战计划 作战计划.md Phase1-6+§7 ✅ ③实现路径 §1/§3/§9 ✅
④转换方式 §3 ✅ ⑤原生编译技术栈 §2/§4/§5/§11-§18 ✅ ⑥手柄映射+Switch 布局匹配 §19 ✅ ⑦陀螺仪 §20 ✅ ⑧Amiibo 虚拟 NFC §21 ✅
（⑥⑦⑧ 为只读调研层面的成文闭合；V5/V6 实测仍待挂账解除）

## 第 7 轮补遗
- 追加 §21.5：ScarletNX `misc.swipc:184-243` 的 NFC 命令逐行核对结果（`nfp:user`→IUser 29 命令 + 结构体宽度），并据此把"虚拟 Amiibo 无需逆向 NFC 协议"写成硬依据
- 取证副本已随产物归档：`evidence/input/`（51 文件 / 2.8MB，含三家输入侧源码、SDL3 驱动与 controller_list、GyroDSU 全仓关键文件、Ryujinx NFC 数据模型、DSU 协议头、三个 SDL issue JSON）
- WeKnora：finish 记录 `339836eb-306d-4d9f-8c81-d460a04bdec3`（已回读正文）；knowledge_id 勘误 `a5393bd5-7bde-449a-85dc-af617ba2f4bd`（我误把 8 位前缀补全成不存在的 ID，已追加勘误而非覆盖）

---

## 第 11 轮追加（2026-10-25，挂账期内，未触碰 Deck）

仓库元数据加固 + 全链路一致性复核（仅 GitLab 侧配置与本地说明文件，未改任何调研结论）：

| 项 | 复核方式 | 结果 |
|---|---|---|
| 仓库存在性 | GitLab API `GET /projects?search=nativedeck` | id=16 · private · default=main ✓ |
| 本地↔远端 SHA | `git rev-parse HEAD` vs `git ls-remote origin main` | 双向 MATCH（`646cb2c8a369`）✓ |
| 远端树文件数 | `git ls-tree -r origin/main` | 86 = 本地 tracked 86 ✓ |
| 提交身份 | `git log -1` | `Codex Agent <codex-agent@example.local>` ✓ |
| 分支保护 | API `protected_branches` | main：push/merge 均 Maintainers ✓ |
| 敏感信息 | `git grep -i` 凭据/私钥/token 样式 | 无凭据命中（仅上游源码里的 `CancellationTokenSource` 等语义同名标识符）✓ |
| 版权红线 | 镜像后缀扫描 `.xci/.nsp/.nca/.xcz` | 零命中 ✓ |
| 大文件 | 按体积排序 | 最大 1.6M（`evidence/input/ryu-tree.json`），`.git` 940K ✓ |
| NUL 字节 | `deckprobe/*.txt` 抽检 | 含 tty 残留 NUL，已由 `.gitattributes` 标 `binary` 规避换行转换 |
| GitHub 镜像 | 双托管规则核对 | 仅 moonlight 系列适用，本仓不推 GitHub ✓ |

GitLab 侧新增：`topics=aarch64,native-recompilation,steam-deck,static-rewriting,switch,x86-64,nativedeck-20261024`，描述中显式写入「只读调研已闭合 / V1-V7 待解除挂账 / hardware_validated=false」，避免日后误读为已完成。

回滚：`git revert HEAD` 或 `curl -X PUT .../projects/16` 清空 topics/description。

遗留待裁决（不在本轮擅自执行）：仓库目前位于用户命名空间 `codex/`，而 moonlight、yulidan、iphone8plus 已各自使用独立 group。若要与既有惯例统一，可请我把本仓 transfer 到新建 group `nativedeck`；transfer 会保留 project id 并重定向旧 URL。

---

## 第 12 轮追加（2026-10-25 22:45，用户解除挂账并授权操作 Deck）

### 勘误（覆盖第 7 轮的两条误记，不删除原文）

1. 第 7 轮记账"Mac 本机两个 AppImage 从未推送到 Deck"**错误**。现场事实：
   - `~/native-recomp/LAS.AppImage` 112,179,704 B，SHA256 前 12 位 `5a5df7a4623d`，与官方 beta_5.1 linux-x86_64 发布值**逐位一致**
   - `~/native-recomp/ScarletNX.AppImage` 47,292,590 B，SHA 前 12 位 `ecda0da7628f`，可执行位已置
2. 第 7 轮记"V1 无任何证据"不成立。`~/.local/share/lasrecomp/` 内有 6 份日志（2026-10-24 16:51:36 ~ 16:55:28，pid 26345→27059），每份均完整打印：
   `LAS Recomp beta_5.1, SteamOS 3.9.5 (x86_64, kernel 7.2.7-valve2-2-neptune-72), AMD Custom APU 0405 4c/8t, 14.5 GB RAM, AppImage`
   随后 `FATAL: SDL_Init: No available video device` + zenity `cannot open display`。
   → 判定：**二进制已在本机完成加载并跑到 UI 初始化**，动态链接/libc/Vulkan 用户态均无阻断；失败根因是 SSH 会话无显示设备，属环境侧而非移植侧。记为 `v1_binary_loads=verified`，`v1_gui_launch` / `hardware_validated` 仍 false。

### 现场基线刷新（相对 2026-10-24 的漂移项）

| 项 | 10-24 记录 | 10-25 22:44 实测 | 影响 |
|---|---|---|---|
| `/home` 余量 | 544G | **264G**（总 939G，用 675G） | 异环国服 76.5G 安装所致；仍足够 distrobox(1.7G)+构建 |
| 内核 | — | `7.2.7-valve2-2-neptune-72`（2026-10-23 构建） | 与 10-24 LAS 日志一致，无中途系统更新 |
| 显示会话 | — | wayland 本地会话；`/tmp/.X11-unix/X0`+`X1` 存在；`/run/user/1000/gamescope-0` | GUI 真机验证可经 XWayland 投递 |
| `steamos-readonly` | 曾记"rootfs readonly" | **status=disabled（rootfs 可写）** | 红线升级：严禁 pacman/ostree 写 rootfs |
| zram/swap | — | zram0 7.2G + swap 23G（已用 1.4G） | TOTK 重编译期内存压力有兜底 |
| 温度/电源 | — | 54 °C，ACAD 在线，电量 100% | 可跑负载 |
| 游戏资产 | 需用户提供 | Deck 与 Mac（Downloads/Documents/Share）**均无** `.xci/.nsp/.nsz/prod.keys/*.titlekeys` | V2/V4 前置阻塞，需用户提供 |

### 连接方式（本轮验证有效）

`ssh deck@192.168.1.105`，**纯公钥认证**，`BatchMode=yes` 通过；即 2026-10-25 异环任务追加到 `~/.ssh/authorized_keys` 的 Mac 公钥仍有效（备份 `~/rescue/nte-cn-20261025/authorized_keys.before-nte`）。不使用密码认证。

### 红线区实际位置（本轮只读确认，一律不改）

Decky 前端 `~/.config/Methodica`；兼容工具 `~/.local/share/Steam/compatibilitytools.d/`（GE-Proton11-11、dwproton-11.0-15、LegacyRuntime）；前缀 `~/.local/share/Steam/steamapps/compatdata/`（14 个）；Steam runtime `SteamLinuxRuntime`/`_4`；flatpak 已装 5 项含 ProtonUp-Qt。Steam 客户端（pid 1821）与 gamepadui 正在运行，本轮未中断。

本轮全部为只读取证，未在 Deck 上写入任何文件。

---

## 第 13~18 轮追加（2026-10-25 22:55 ~ 2026-10-26 01:32，授权操作 Deck，M0/M1/M2 全部闭合）

### 里程碑结论

| 里程碑 | 状态 | 关键证据 |
|---|---|---|
| M0 像素自证 | **已验证** | `evidence/m0/env20-hbmenu-frame_0002.ppm`（`445be562…`，P6 1280×720，人眼可读 hbmenu 文本）；截图不经 X/gamescope，从渲染进程内回读 swapchain |
| M1 原生 x86-64 ELF 并证实 | **已验证** | 三条硬判据全部成立，见 `deckprobe/env19.txt`；`env20.txt` §二在零隐式层条件下复现判据③ |
| M2 Vulkan + 输入 | **已验证** | `deckprobe/env22.txt`（容器侧全量）+ `deckprobe/env23.txt`（宿主直采，SNX 必需扩展 29/29）+ `deckprobe/env21.txt`（注入端到端） |
| M3 TOTK 真机 | **blocked** | Deck 与 Mac 均无 TOTK 资产，等用户提供（见 env24 §七） |
| M4 陀螺仪游戏内实测 | 未开始 | 前置分析见 `deckprobe/env24.txt` §二 |
| M5 Gaming Mode 入库 | 未授权 | 需用户单独批准写 `shortcuts.vdf` |

### 标记状态（本轮结束时）

`v1_binary_loads=true`（已验证）、`v1_native_run=true`（已验证）、
`v1_gui_launch=true`（像素级）、`input_validated=true`（**限定：软件注入面**）、
`motion_validated=false`、`hardware_validated=false`。

### 新增产物（Deck 侧，全部在白名单 `~/native-recomp/`）

- `logs/env20/`：M0 帧采集（6 份 PPM + run.out + forensics.txt）
- `logs/env21/`：输入注入 A/B/C 三组
- `logs/env22/`：容器内 vulkaninfo（json 179798 B / txt 137197 B）
- `vk/`：自编译宿主探针 `bin/vkprobe`（21480 B，SHA `208544eb…`）+ `vkprobe.c` + `logs/vkprobe-{host,val}.log`
- 容器 `nativedeck-build` 内新增 `glslang-tools / spirv-tools / libvulkan-dev / vulkan-tools`

### 红线合规

每轮均执行 `find … -newermt "2026-10-26 00:00"` 巡检（Methodica / compatibilitytools.d /
compatdata / SteamLinuxRuntime* / .var/app / .steam）→ **全部为空，Steam 侧零改动**。
未使用 root、未写 rootfs、未重启、未改 systemctl、未动 swap/zram/电源策略。
资源护栏：`/home` 余 261G、`~/native-recomp` 1.2G、containers 85M、Tctl 54.0 °C、ACAD 在线。

### 本轮新增反例（已入档，勿重复踩）

1. `vulkaninfo --json` 重定向 stdout 产出 0 字节（隐式层报错 + DISPLAY 未透传）→ 用 `-o <file>`。
2. 容器内 Mesa 25.2.8 / loader 1.3.275，宿主 Mesa 26.2.0-devel / loader 1.4.350；
   `pageable_device_local_memory`、`swapchain_maintenance1` **只在宿主可用** → 真机运行必须在宿主。
3. `VK_VERSION_*` 宏自行解码易错：本轮对 `apiVersion`/`driverVersion` 各抄错一次，
   已在 env22/env23 以附录勘误（1.4.318 容器 / **1.4.350** 宿主；driver 以 `driverInfo` 字符串为准）。
4. 自写 Vulkan 探针时头名漂移：`scalarBinding→scalarLayout`、`inlineUniformBinding→inlineUniformBlock`、
   `separateDepthSamplerLayout→separateDepthStencilLayouts`；
   `vkGetPhysicalDeviceCalibrateableTimeDomainsEXT` 必须动态取。
5. `VK_LOADER_LAYERS_DISABLE` 同时屏蔽显式层，"层未生效"≠"层未安装"。
6. SSH 间歇超时再现 1 次（非连续，未触发中止条件）→ 短命令 + 3 次重试 + 证据落盘。

### 待用户裁决（未擅自执行）

1. **M3 资产**：TOTK 1.0.0（main build ID `082CE09B06E33A12`、title `0100F2C0115B6000`、
   `prod.keys` mkey rev `0x0E`，可选 `title.keys`）。
2. **M5 授权**：是否允许写 `shortcuts.vdf` 做 Gaming Mode 入库（唯一会触碰 Steam 区的动作）。
3. **仓库归属**：本仓仍在用户命名空间 `codex/nativedeck`（project id 16）。
   若要按 moonlight/yulidan 惯例统一为独立 group，需授权 transfer（保留 project id 与重定向）。
