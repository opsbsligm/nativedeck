# nativedeck

> Switch AArch64 游戏 → Steam Deck x86-64 **原生**运行（静态重编译，无模拟器、无 Wine/Proton/DXVK 兼容层）

- **task_id**：`nativedeck-20261024` · **scene**：homelab
- **当前阶段**：TOTK 1.4.3原生ELF已进入开场地下场景；移动、系统菜单、稳定画面的中文、读档和手动保存已实测，正在继续手柄/图标与完整游玩验收。
- **hardware_validated**：`false`（整体交付尚未验收；3D首次启动通过不代表中文、全部手柄功能、动画和稳定性已通过）
- **仓库**：<https://gitlab.example.com:8445/codex/nativedeck>（private · 默认分支 `main` 受保护）
  克隆：`git clone https://gitlab.example.com:8445/codex/nativedeck.git`

## 当前目标（2026-11-03）

当前第一优先级为《王国之泪》1.4.3 V8 的原生编译、缺陷修复与实机回归，按[完整交付目标提示词](目标模式提示词-TOTK交付纠偏-20261103.md)推进。正常游玩、输入、音画、存档、主线、性能与稳定性均须有真实验证；工具、报告或 MR 合并不等于游戏验收完成。

旧版目标提示词保留为历史，不再执行其中的旧版本资产等待、BOTW 并行或串流验收。应用内目标正文须另外回读核验，本文档提交不代表应用状态已更新。

## 历史调研结论（2026-10-24）

本节保留历史调研，不能替代当前工程状态或性能验收。当前公开实现入口见`ports/ultratears-linux/`与`tools/native_review/`。

2026-10-31本机实测使用UltraTears固定提交的Linux源码移植，自包含目录和`run.sh`直接启动x86-64 ELF。早期第三方项目与60FPS宣称不作为本机验收依据；当前开场短时观察约30FPS，尚未完成持续性能测试。

**能实现。** 三条活跃实现全部产出普通 Linux x86-64 原生 ELF，加载期与运行期均无翻译器介入。TOTK 在 Steam Deck 上已被第三方实测约 60fps；Deck 的四项硬门槛（AVX2 / Vulkan 1.3 / glibc ≥2.35 / SDL3 ≥3.4）现场全部达标。安装形态为 **AppImage**，SteamOS 无 `.deb`。

## 仓库结构

| 路径 | 内容 |
|---|---|
| `report.md` | 主报告：可行性结论、Deck 真机取证、安装形态、风险清单、验证计划 |
| `作战计划.md` | Phase 1-7 路线图、执行策略、阻塞项、时间估算、验证标记升级路径 |
| `技术栈与实现路径.md` | 21 节技术细节：三条实现对比、编译链、GPU 着色器层、手柄/陀螺仪/Amiibo、AMD 特化坑 |
| `STATUS.md` | 挂账状态与轮次进度日志（只追加，不覆盖） |
| `deckprobe/` | Deck 真机**只读**命令原始输出（`env.txt`~`env16.txt`、`vk.txt`、`bar.txt`） |
| `gh/` | GitHub 上游证据归档（LAS beta_5 发布说明、totk-recomp README、release 资产清单 JSON） |
| `evidence/input/` | 三家输入侧源码、SDL3 SteamDeck 驱动、GyroDSU、Ryujinx NFC 数据模型、DSU 协议头 |

## 三条上游实现

| 项目 | 许可 | 覆盖范围 | Deck 状态 |
|---|---|---|---|
| [LAS Recomp](https://github.com/peiikai/LASRecomp) | MIT | 织梦岛 1.0.0-1.1.0 | 官方发布说明称 60fps；玩家实测有回归 issue |
| [totk-recomp](https://github.com/Muhammad1259-sigma/totk-recomp) | MIT | TOTK 1.0.0（仅此版） | 作者自测 Deck 户外约 60fps |
| [ScarletNX](https://github.com/scarletnx/ScarletNX) | GPL-3.0 | 通用（任意 Switch 游戏） | 全库零 Deck 记录，`hardware_validated=false` |

## 验证标记体系

`hardware_validated` / `input_validated` / `motion_validated` / `amiibo_gap_mapped` —— 未实测一律 `false`，不得写成已验证。

## 红线

- 任何构建过程**不嵌入游戏数据**；游戏包由用户自有 `.xci`/`.nsp` + `prod.keys` 提供
- 本仓不存放 `prod.keys`、master key、游戏镜像或任何 Nintendo 版权内容
- 对 Deck 的一切写操作需先解除挂账并逐项批准；部署遵循「纯新增、可回滚」

## 当前推进边界

原作战计划和挂账记录保留为历史材料；当前已获授权开展原生移植、项目目录内构建部署与实机验证。未修改Steam/Decky/系统插件，串流按用户要求跳过。

本仓包含公开源码移植补丁、原生工具与研究/取证材料，不含私有游戏输入或生成游戏产物；Git 历史与 `STATUS.md` 轮次日志为追加式，构成可核对的进度事实源。
