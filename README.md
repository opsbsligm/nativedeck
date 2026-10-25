# nativedeck

> Switch AArch64 游戏 → Steam Deck x86-64 **原生**运行（静态重编译，无模拟器、无 Wine/Proton/DXVK 兼容层）

- **task_id**：`nativedeck-20261024` · **scene**：homelab
- **当前阶段**：只读调研已闭合，真机实测待挂账解除
- **hardware_validated**：`false`（Deck 上尚未实跑任何上游发布物或重编译产物）
- **仓库**：<https://gitlab.example.com:8445/codex/nativedeck>（private · 默认分支 `main` 受保护）
  克隆：`git clone https://gitlab.example.com:8445/codex/nativedeck.git`

## 一句话结论

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

## 恢复推进

挂账解除后按 `作战计划.md` 顺序执行 V1 → V1.5 → V2 → V3 → V4 → V5-V7，每次只推进一项。

本仓只承载调研与取证产物，不含游戏数据；Git 历史与 `STATUS.md` 轮次日志为追加式，构成可核对的进度事实源。
