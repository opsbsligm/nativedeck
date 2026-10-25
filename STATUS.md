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
