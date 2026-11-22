# 任天堂官方素材声明

本仓库为个人工程（fan project）。*The Legend of Zelda* 等游戏名与商标、以及下述编译产物与实机截图中出现的画面、角色与字标，版权均归任天堂株式会社所有；本仓以个人研究/取证用途使用，非商业、不重新分发游戏镜像。

## 编译产物归档

| 文件 | 内容 | 来源与许可口径 |
|------|------|------|
| `deckprobe/totk-recomp-x86_64-steamos.tar.zst` | TOTK 1.0.0 totk-recomp 的 x86-64/SteamOS 编译产物归档（deckprobe 遥操现场证据） | 构建自用户从自有卡带 ExeFS 提取的输入，非重新分发的游戏镜像；`prod.keys` 不入库 |

## 个人实机取证截图

| 文件 | 内容 | 来源与许可口径 |
|------|------|------|
| `evidence/m0/env20-hbmenu-frame_0002.ppm` | Steam Deck 实机手柄菜单帧取证 | 用户自有主机运行时的帧抓取，个人取证材料 |
| `evidence/review-20261030/chinese-title.png` | 汉化版标题画面截图 | 用户实机运行取证，非官方宣传图 |
| `evidence/review-20261030/chinese-gameplay.png` | 汉化版实机游玩截图 | 用户实机运行取证，非官方宣传图 |

## 上游调用树取证 JSON

`evidence/input/ryu-tree.json` 与 `evidence/input/las-tree.json` 为 Ryujinx / LAS 调用树取证 JSON，可能含上游符号名，属个人取证材料，不重新分发上游代码。

**用户自带**：运行需用户自行提取 ExeFS 与 `prod.keys`；除上述对象外，本仓不含游戏代码、密钥或固件。

*This project is not affiliated with, endorsed by, or sponsored by Nintendo.*
