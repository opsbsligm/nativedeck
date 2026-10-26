# env26 · 第 20 轮：NVN/deko3d/pushbuffer 裁定 + MME 快路径对拍 + FATAL 指令归属坐实

- task_id: nativedeck-20261024 / phase: checkpoint / scene: homelab / project: nativedeck
- recorded_at: 2026-10-26 (Asia/Shanghai)
- status: in_progress（M0/M1/M2 已闭合，M3 blocked 等 TOTK 资产）
- 证据等级标注：已验证 / 官方声明 / 第三方实测 / 推断 / 未验证
- 关联取证包：`deck-forensics-20261026/`（Deck 侧 run-* 与 forensic 原样回捞，28 文件 2.1 MiB）

---

## 1. 本轮三项 P0/P1 结论

### 1.1 【已验证】edenprobe 的 FATAL 指令归属坐实：不是移植缺陷

Deck 上 `run-full/launch-1.log`、`run-cpu/launch-1.log` 等尾部：

```
FATAL: The game ran an instruction the recompiler cannot run (d53b4223 at 8048ad8)
FATAL: The game ran an instruction the recompiler cannot run (ce62c820 at 8048b48)
```

Mac 侧用 Xcode 工具链 `llvm-objdump -d`（`-target arm64-apple-ios15`，`.inst` 内嵌原始词）反解：

| 指令词 | 反解结果 | 对应 edenprobe 用例名（report.jsonl 原文） |
| --- | --- | --- |
| `0xd53b4223` | `mrs x3, DAIF` | `mrs daif reads nothing outside the four interrupt mask bits` |
| `0xce62c820` | `sm4ekey.4s v0, v1, v2` | `sm4ekey and sm4e give the SM4 standard's worked example` |

- 这两条正是 edenprobe `fatal` 模式自述 "may crash" 的两个用例，`run-cpu/report.jsonl` 中未开 `fatal` 时记为 `skip`，开 `fatal` 时命中重编译器未实现指令 → **FATAL 是探针故意触碰未实现指令的预期结果，与 TOTK 移植无关**。
- `run-cpu/report.jsonl` 结果计数：`pass 530 / skip 2`，与 `summary.md` 的 `530 passed, 0 failed, 0 skipped, 2 crashed` 一致。
- 备注：Deck 上的 `snx-a64dec` 是**生成器**（`a64dec --header OUT.h --decoder OUT.inc PROFILE DECODE...`），不是运行时反汇编器，不能直接反解单词；故改用 llvm-objdump。
- 附带观察（推断）：`DAIF`（中断掩码）与 `SM4`（国密分组密码）都不属于游戏可玩路径所需指令面。

### 1.2 【已验证】MME native/HLE 快路径：上游单测在 Mac 侧对拍通过

`src/nx/gpu/maxwell/mme_hle.c` 的 native 宏哈希表实为 **29 项**（`X(hash, fn, "name")` 跨行宏形式；前轮 `grep -c` 只数到 10 是因为跨行匹配丢失，已更正）。

上游自带对拍测试 `tests/mme_hle.c` 头注明确：对每个 native 实现，按"实现自身注释所述语义"重写一份宏（不含任何游戏代码），同一参数/寄存器下分别走 `mme.c` 解释器与 native 实现，断言**下发的方法、值与回写的寄存器完全一致**。

Mac 侧编译并运行（`snx_settings.h` 从 Deck b6 构建目录 `settingsgen/` 只读拷出，源码 HEAD `f035e4b`）：

```sh
cc -std=gnu11 -O0 -g -I src -I tests -I /tmp/snx-hosttest/gen \
   -o /tmp/snx-hosttest/mme_hle \
   tests/mme_hle.c src/nx/gpu/maxwell/mme_hle.c /tmp/snx-hosttest/gen/settings.c
/tmp/snx-hosttest/mme_hle
# mme_hle: 585055 checks passed   rc=0
```

→ 29 个 native 宏 × 各自参数组合共 **585055** 项断言全通过。**功能正确性有回归网兜底**（native 与解释器逐方法等价）。Deck 上无编译器、且 b6 `SNX_BUILD_TESTING=OFF`，故此路径只能在 Mac host 跑（已记入失败反例）。

### 1.3 【已验证 → 撤销前轮"NVN HLE 未覆盖"疑虑】TOTK 图形入口是 pushbuffer，解码链已在 Deck 真机被覆盖

裁定链（每一环都有出处）：

1. edenprobe **不调 NVN API**：`source/gpu.h` 引 `<deko3d.h>`，使用 `DkDevice/DkQueue/DkCmdBuf`；Mac 侧对 NRO 取 strings，`dk[A-Z]` 符号仅 3 处，**无 `nvnBootstrapLoader`**。
2. deko3d 与 NVN 是**同一硬件命令面的两个前端**：deko3d `Primer.md` 自述其大量相似性源自"围绕 **official NVN library** 的一年半逆向工作"，命令按"GPU 能理解的格式"原样写入 backing memory，并支持 `BeginCaptureCmds` 抓取 **raw GPU command words** 后 `ReplayCmds` 零开销重放。
3. ScarletNX 的覆盖点在**命令流层，不在 NVN API 层**：`docs/ROADMAP.md` "The GPU is emulated by decoding the **Maxwell command buffers NVN writes**"；`docs/NVN_HLE.md` "**NVN command memory already is a Maxwell pushbuffer**, so a second front end that reinterprets NVN calls would decode the same words twice"，并记录上游**主动放弃** NVN 直通（约 14,000 行语义重放探针被删，理由含 "TotK inlines NVN"、"not every command is in a recorded list"）。
4. 真机命令流覆盖**实证**（回捞包 `run-gfx/launch-3.log` 等，见 §2）：256 条 `mme: macro N at word X, …, hash …: interpreted` + 完整 nvdrv 会话（`/dev/nvhost-ctrl-gpu`、`/dev/nvmap`、`/dev/nvhost-as-gpu`、`/dev/nvhost-gpu`、`GPU address space with 64 KB big pages`、GPFIFO 提交、`QueryEvent`）。
5. → **TOTK 的图形入口就是它写出的 Maxwell pushbuffer，而该解码链（`gpu.c` + `maxwell/`（含 MME 解释器 + native 表 + JIT）+ `vk/`）已在 Deck 真机被真实驱动并绘制**。TOTK 图形保真度风险回归到"pushbuffer 方法/MME 覆盖广度"这一正常工程面，不再是结构性未验证项。

**前轮"P0 缺口 = NVN HLE 未覆盖"判定撤销**。追加勘误，不改写原文。

---

## 2. edenprobe Deck 真机全量矩阵（回捞自 `run-*/summary.md`）

| run | mode 词 | passed | failed | skipped | crashed | launch 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| run-cpu | `quick notime fatal cpu` | 530 | 0 | 0 | 2 | L1 exit1 1s / L2 exit1 0s / L3 exit0 0s |
| run-gfx | `quick notime fatal cpu graphics` | 929 | 0 | 0 | 2 | 同上，L3 3s |
| run-gfx2 | `quick notime fatal cpu graphics display` | 933 | 0 | 0 | 2 | 同上，L3 3s |
| run-gfxT | `quick fatal cpu graphics display query` | 933 | 0 | 0 | 2 | 同上，L3 15s |
| run-full | `quick notime fatal cpu graphics fs video display kernel audio` | **994** | **0** | 0 | 2 | 同上，L3 13s |

- 全量 **994 pass / 0 fail**，`input_validated=true`（限定：软件注入面，见 env21），`motion_validated=false`（`hid.swipc` 多个 SixAxis 命令 `@stub`）。
- `mme: macro` 日志行数：`run-cpu` = 0（cpu 阶段即 FATAL 退出，从未进 graphics）；`run-full/run-gfx/run-gfx2/run-gfxT` 各 **256**。
- `run-gfx/launch-3.log` 的 nvdrv 会话标记计数：`/dev/nvmap` 29、`nvhost-ctrl-gpu` 29、`nvhost-as-gpu` 29、`nvhost-gpu` 29、`big pages` 29。

## 3. MME 覆盖面的诚实边界（推断 → 待 TOTK 真机升级为已验证）

- 上述 256 条 `mme: macro` 是 `mme.c:244` 的 `LOG_LIMIT(256, …)` **日志封顶，不是宏调用总数**；14 个 distinct hash 与 `mme_hle.c` 的 29 项表**零交集**，因为 edenprobe 的宏由 deko3d 上传，哈希与 NVN SDK 不同。
- 真正的调用统计行 `mme.c:392` `mme: %llu macro calls, %llu native, %llu compiled and %llu interpreted` 受 `% 1000000 == 0` 门控（需累计满 100 万次宏调用才打印），edenprobe 负载远达不到 → 所有 launch 里都抓不到，**这是设计如此，不是异常**。
- 因此：**edenprobe 无法验证 `mme_hle.c` 快路径的实际命中**；该路径的功能正确性由 `tests/mme_hle.c`（本轮已跑通，585055 checks）+ `mme_native.c`/`mme_jit.c`（需 LLVM，未跑）覆盖，**不是 TOTK 实测**。性能面定性 = "native 表存在且与解释器等价，但未在 Deck+TOTK 上量化命中"；功能面 = 有解释器兜底，不会因宏未收录而崩。
- 三档调试开关已在 `settings.txt` 确认为 `[Debug]` startup 设置：`mme_hle=1`、`mme_jit=1`、`mme_verify=0`。TOTK 到位后可用 `--mme_verify=1` / `--mme_hle=0` / `--mme_jit=0` 做三态一致性交叉验证（M4 待办）。

## 4. Mac host 侧单测汇总（本轮 + 前轮，均 rc=0）

| 测试 | 结果 | 与 TOTK 的关系 |
| --- | --- | --- |
| `tests/nvn_control.c` | rc=0 | 头注 "checked against packets captured from Tears of the Kingdom"，断言 macro-38 indexed draw（`index_address==0x656bd6ce8`、`count==0x5af3`）与 macro-12 program bind（`selector 1/code_offset 0xca7f30`、`selector 5`） |
| `tests/nvn_command_gap.c` | rc=0 | TOTK 观测的 cursor gap 分类器，含 `0xa0050e38` 六词 DrawElements 包、1656 索引 |
| `tests/mme_hle.c` | rc=0，**585055 checks** | 29 个 native 宏与解释器逐方法等价（本轮新增） |
| `tests/mme_native.c` / `mme_jit.c` | 未跑（需 LLVM） | 留给 M4 性能阶段 |

→ **ScarletNX 对 TOTK 真实 NVN 命令词的理解是带回归断言的**，这三项共同把"TOTK 命令流能不能被解码"从推测降为有测试保护的工程面。

## 5. 里程碑状态（本轮更新）

| ID | 状态 | 本轮变化 |
| --- | --- | --- |
| M0 Vulkan 设备直持 | ✅ 已验证 | 不变（帧 SHA `445be562…`，`renderD128` 直持） |
| M1 Deck 上构建原生 x86-64 ELF | ✅ 已验证 | 不变（b6 SHA `95791b35…`） |
| M2 无 ROM 功能面探测 | ✅ 已闭合 | 新增：NVN/deko3d/pushbuffer 裁定 + MME 等价性对拍 + FATAL 归属坐实 |
| M3 TOTK 资产 | ❌ blocked | 无变化，只能由用户提供 |
| M4 TOTK 运行 | ⏸ 等 M3 | 新增可执行子任务：MME 三态交叉验证 |
| M5 shortcuts.vdf 入库 | 🔒 未授权 | 不变 |

原生性三判据 ①②③ 全部维持成立。`hardware_validated=false`（TOTK 未在 Deck 真机跑过，不得写成已验证）。

## 6. 本轮操作与红线合规

- Deck 侧：全部只读（`ls`/`file`/`cat`/`grep`/`sed`/`uptime`/`df`/`du`/`pgrep`）+ 一次 `snx-a64dec` usage 探测（无写入）+ 一次 `tar -c` 只读打包经 stdout 回 Mac。**未写 Deck 任何文件**、未 sudo、未碰 Steam/Decky/compattools/steamapps、未重启、未改服务与电源。
- Mac 侧：新增 `deckprobe/deck-forensics-20261026/`（28 文件）、`deckprobe/env26.md`、`/tmp/snx-hosttest/{mme_hle,gen/snx_settings.h,…}`。
- 运行时现场基线（供下轮对比）：`pgrep -c steam`=15、`pgrep -c scarletnx`=0、load 0.45、`/home` 余 258G、up 18:29。

## 附录 · Mac 侧 host 单测复现命令

```sh
cd /private/tmp/nativedeck-src/ScarletNX      # HEAD f035e4b
G=/tmp/snx-hosttest/gen                        # snx_settings.h 取自 Deck build/b6/settingsgen/
cc -std=gnu11 -O0 -g -I src -I tests -I $G -o /tmp/snx-hosttest/nvn_control \
   tests/nvn_control.c tests/support/nvn_control.c
cc -std=gnu11 -O0 -g -I src -I tests -I $G -o /tmp/snx-hosttest/nvn_gap \
   tests/nvn_command_gap.c tests/support/nvn_command_gap.c
cc -std=gnu11 -O0 -g -I src -I tests -I $G -o /tmp/snx-hosttest/mme_hle \
   tests/mme_hle.c src/nx/gpu/maxwell/mme_hle.c $G/settings.c
```
