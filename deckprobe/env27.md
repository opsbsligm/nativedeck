# env27 · 2026-10-26 14:15 — Deck x86-64 真机 MME/JIT/NVN 全量测试

## 目标
在 Steam Deck x86-64 真机上运行 ScarletNX 全部 MME 单测 + NVN 两测，升级验证等级。

## 方法
- 构建环境：`distrobox enter nativedeck-build`（Ubuntu 24.04，gcc 13.3，LLVM 18）
- 编译目标：`mme_hle.c` / `mme_native.c` / `mme_jit.c` / `nvn_control.c` / `nvn_command_gap.c` + 配套 support 源码 + 生成的 `snx_settings.h` + `settings.c`
- 链接：`libsnx_llvm.a` + `libscarletnx-common.a` + `-lstdc++` + `-lm` + `-ldl`
- 运行：Deck 原生 x86-64，`LD_LIBRARY_PATH=/usr/lib/llvm-18/lib`

## 结果

| 测试 | 结果 | 含义 |
|---|---|---|
| mme_hle | **585055 checks passed** | native 快路径（29 项 HLE 宏）与解释器逐 send 对拍一致 |
| mme_native | **57 checks passed** | MME hash 选择、native vs interp 分支覆盖 |
| mme_jit | **2053 checks passed** | JIT 编译器为未知 HLE 宏生成 x86-64 代码，与解释器对拍一致 |
| nvn_control | pass (rc=0) | TOTK 抓包命令流解码（indexed draw + program bind） |
| nvn_command_gap | pass (rc=0) | cursor gap 分类器验证 |

全部 pass，无 crash。

## 关键修正

此前误读：edenprobe 真机日志中 `mme: macro ... : interpreted` 被解读为"全部走解释器"。
实际：该日志出自 `mme_choose()`，表示 native HLE 表未命中 → 后续仍可能走 JIT 或解释器。
JIT 引擎正常启动：生产态日志零 `macros are interpreted: no LLVM`。
JIT 缓存 `edenprobe.jitcache` 470549 字节已生成（来自 `verify-hle1-jit1/run.log` 时段）。

## 标记更新
- `hardware_validated=false`（测试通过 ≠ 游戏画面）
- `input_validated=true`（限定：软件注入面，mme_native 已验证）
- 三态全部在 x86-64 真机通过 → `mme_hle_validated=true`、`mme_jit_validated=true`、`mme_native_validated=true`

## 产物路径
- Deck 上编译产物：`~/native-recomp/jitbuild/t-hle t-native snx-test-mme-jit t-nvnc t-nvng`
- 无新文件写入白名单外
