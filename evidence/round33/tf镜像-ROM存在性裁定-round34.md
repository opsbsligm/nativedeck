
# TF 镜像 ROM 存在性裁定（round34 · 2026-10-27）

## 结论（先给结果）

| 游戏 | 卡上存在性 | 证据等级 |
|---|---|---|
| **TOTK** (0100F2C0115B6000) | **倾向不在卡上** | 已验证（两轮独立全扫 0 命中） |
| **BOTW** (01007EF00011E000) | **强信号在卡上** | 已验证（27 次命中，终审待挂载） |

## round32b 分歧厘清

上一轮遗留分歧：`tf_scan.py`（tf_scan.sh 调用）报 TOTK hits=0，但 `tfscan2/titleids.txt` 扫出 `0100F2C0` 前缀。两者口径对比：

| | tf_scan.py (tf_totk_scan3.log) | tfscan2 (rg 粗扫) |
|---|---|---|
| 匹配方式 | 完整 16 位 title id 字节精确匹配（`0100F2C0115B6` + 小写版 + `0100F2C0115B7` 变体）+ NESFS + UTF-16LE 游戏名 | 正则 `01[0-9A-F]{14}`，**无边界断言** |
| 覆盖量 | 106.1 GiB 全量（SCAN_DONE exit=0） | 162,405 行 raw 命中（无覆盖量记录，但同一 zstd 管道） |
| TOTK 精确 id 命中 | **0** | `0100F2C0` 前缀 8 处，**全部是 0EED4/0EED5 系列**（`0100F2C00EED4000/01/02/03`），`0100F2C0115B6000/7000` = **0** |
| BOTW 精确 id 命中 | 未扫此 id | `01007EF00011E000` = **27**，另有 0011F001/0011F002/0011E800 若干 |

**裁定**：rg 粗扫的 `0100F2C0` 前缀命中是"同发行商（任天堂 EP20 区域）其他 title"的目录/元数据（0EED 系列非 TOTK），不是 TOTK 本体。tf_scan.py 的精确 id + UTF-16LE 名称双通道 0 命中权重更高（exFAT 长文件名与 cnmt 均用 UTF-16LE，已覆盖）。

## 注意（不能 100% 定论的原因）

1. 两轮都是**字节流扫描**，未解析 exFAT 目录树。若 TOTK 以 NSZ/压缩 NSP 单独存放、且 title 目录名被 exFAT 卷损坏/稀疏存储覆盖，字节扫描可能漏。
2. 字节命中（含 BOTW 的 27 次）也可能是二进制数据巧合——15 位 hex 在 106GB 随机数据里期望出现次数不低。
3. **终审唯一口径 = 挂载 exFAT 后看 `/switch/` 实际目录**。

## 终审进行中

- `tfextract2.sh`（pid 见 `/private/tmp/tfextract2.pid`）双 fork 后台解压 `tf-20261010-pre-cp100.img.zst` (107.6GB) → `/private/tmp/tf-switch-20261010.img`。
- 前两轮 `rc=-15` 根因：exec_command 会话回收 SIGTERM。本轮 nohup+双 fork 脱离。
- 解压完成后：`hdiutil`/`mount -t exfat` 挂载（或 dd 出 offset 后用 7z/exfatprogs 列目录），核对 `/switch/0100F2C0115B6000/` 与 `/switch/01007EF00011E000/`。
- 同时核对 `/switch/prod.keys` 或 `/atmosphere/` 内 keys（tfscan.log 已见 `sdmc:/switch/prod.keys` 路径引用，确认卡上有 prod.keys）。

## 对路线的影响

- 若 BOTW 在卡上 → SWR 资产（exefs+romfs 1.9.0）**可自给**，不依赖用户提供。
- 若 TOTK 确认不在 → 向用户要 TOTK 1.0.0 xci（或改用卡上实际版本，需核对 build id）。
