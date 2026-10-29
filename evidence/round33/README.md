# round33 产物（2026-10-27）

- `MacNativeGames深度调研与路线决策.md` — 第 33 轮：MNG 深度调研 + 路线收敛 + 现场取证
- `tfscan.log` — TF-backup 全盘镜像 zst 流式特征扫描（进行中，pid 记录见下）
  - 数据源：`/Volumes/Share/游戏/Switch/TF-backup/tf-20261010-pre-cp100.img.zst`
  - 压缩态 100.7 GB（NAND 全盘备份，TF 2026-10-10）
  - 扫描标记：NNOA/prod.keys/keychain/.nca/TearsOfTheKingdom/BreathOfTheWild/romfs/exefs/Title
  - 启动：`nohup python3 /tmp/tfscan.py > .../tfscan.log 2>&1 &`（Mac 本机只读 NAS 文件）
