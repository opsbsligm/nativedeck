# TF 卡 ROM 存在性终审裁定（round35 · 2026-10-27）

## 结论（先给结果）

**TOTK 与 BOTW 都不在这张 TF 卡上。round34 的"BOTW 强信号在卡上"结论已被推翻。**

| 游戏 | round34 判断 | round35 终审（挂载 exFAT 目录树） | 结论 |
|---|---|---|---|
| TOTK `0100F2C0115B6000` | 倾向不在卡上 | `switch/`、`Nintendo/Contents/*`、`SXOS/titles/` 全 0 命中 | **确定不在卡上** |
| BOTW `01007EF00011E000` | 强信号在卡上（27 次字节命中） | 同上全 0 命中 | **确定不在卡上**（27 次命中是字节流误报） |

## 终审口径与证据

镜像来源：`/Volumes/Share/游戏/Switch/TF-backup/tf-20261010-pre-cp100.img.zst`（107,661,265,803 B）
解压产物：`/private/tmp/nd-tf-image.raw`（113,913,102,336 B，`DECODE_DONE`，2026-10-27 14:17）

分区结构（直接解析 MBR）：单分区，type=0x07 (IFS/HPFS，此处实为 exFAT)，`start_lba=65536` → 分区起始偏移 **32 MiB**；其余 3 个 MBR 表项为空；无 GPT 头、无 GPT 备份签名字符串 → **卡上只有这一个 exFAT 分区，不存在 emuMMC/emuNAND 原始分区**。

挂载方式：`hdiutil attach` Share 上的等价 exFAT 分区镜像 → `mount -t exfat`（只读）→ 遍历完整目录树。

卡上实际内容（一级）：`switch/`(34 项，全是 homebrew：Goldleaf/NX-Shell/DBI/haze/daybreak/moonlight-nx/nxdumptool 等，**无任何游戏 title 目录**)、`Nintendo/{Album,Contents,save}`、`SXOS/{titles,exefs_patches,sxdp_cach}`、`atmosphere/`、`firmware/`、`bootloader/`、`themes/`、`SaltySD/`、`sx-fusion-recovery/`。

游戏可能存放的 3 个位置逐一否定：

1. `switch/` — 无 `0100F2C0115B6000`、无 `01007EF00011E000`，`grep -iE "zelda|botw|totk|tears|wild"` 0 命中，无 NSP/XCI/NSZ 大包（只有 Moonlight NX / Tinfoil / SwitchThemesNX 三个自制工具 nsp）。
2. `Nintendo/Contents/{registered,placehld,private,private1}` — `registered` 与 `placehld` 为**空**；`private/private`、`private1/private1` 是**空文件**（`find -maxdepth 3` 只返回自身）→ 卡上**从未正式安装过任何游戏**。
3. `SXOS/titles/` — 共 64 个 title 目录，逐一核对，`0100F2C0*` 与 `01007EF0*` 前缀**各 0 命中**。其中最大仅 48 MiB，绝大多数为 1 MiB 级补丁/DLC，**没有游戏本体体量**（BOTW 全量约 30 GiB 级）。`Nintendo/save/` 仅 5 个系统 title（`0000000000000005/6/7`、`8000000000000000`、`8000000000000124`），无任何游戏存档。

旁证：`SXOS/sxdp_cach` 为空 → SX Dumper 未在这张卡上留下 dump 缓存。`Nintendo/Album` 只有 2020/2021/2022 三年截图目录。

## round34 误判根因

字节流正则在 106 GiB 高密度压缩/二进制数据上，16 位 hex 命中期望值本身就高，且 `01007EF0` 前缀也属任天堂公共 title 号段。round34 已把该结论标为"强信号但未定论"，本轮挂载目录树即为其列明的唯一终审口径，结论为否定。**后续不要再基于字节扫描判定 title 存在性，直接挂载列目录。**

## 对路线的影响

- SWR 资产**无法从这张 TF 卡自给**，BOTW 与 TOTK 都需外部来源（用户提供 xci/nsx，或改用其他备份介质）。
- 卡上确实存在 `prod.keys` 相关引用与 hekate/bootloader 环境，key 类资产仍可继续挖掘；但**游戏镜像本体不在此卡**。

## 本机磁盘影响（重要）

本次为完成终审在 `/private/tmp/nd-tf-image.raw` 落了 **106.08 GiB** 临时解压产物，是本轮 Data 卷从 216 GiB 涨到 300 GiB 的唯一主因。已验证该文件与 Share 上既有 `Mac-offload/tf-part-exfat.img`（113,879,547,904 B）逐点内容一致：`raw 大小 - 32 MiB == 分区镜像大小`，30 个抽样点（分区起点 / 1 GiB / 30 GiB / 60 GiB / 90 GiB / 尾部 / 24 点等距全扫）SHA-256 **全部一致**，本机 raw **零独有内容**。终审完成后本机 raw 已删除，源 zst 与分区镜像继续保留在 Share。

**防复发**：此类"整盘镜像解压/大文件临时产物"必须直接写 Share 的 scratch 区，禁止写 `/private/tmp`；且动手前应先确认 Share 是否已有等价产物（本例 Share 上早有 exFAT 分区镜像，整轮解压本可避免）。
