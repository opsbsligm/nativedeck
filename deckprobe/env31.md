# env31 · 2026-10-26 18:10~18:40 · dist 自包含复核 + hactool 工具链闭合 + TF 镜像穷尽扫描

## 1. 护栏基线（动手前）

- GPU edge 温度 52.0 °C（阈值 90 °C）
- available 10 GiB（阈值 2 GiB）
- /home 余 258 G（阈值 40 G）
- Steam 前台无游戏进程；未触碰 Decky/compattools/steamapps

## 2. dist 自包含形态复核（只读）

```
/home/deck/native-recomp/dist/totk-recomp/
├── totk                  15,829,560 B  ELF64 EXEC x86-64, RUNPATH=$ORIGIN/lib
├── run.sh                    8,583 B   Steam 非游戏启动入口（含 90Hz/DynRes/体感等 env 开关）
├── lib/libSDL3.so.0.2.30 3,445,344 B   → libSDL3.so.0
└── lib/libvulkan.so.1.4.350 628,736 B  → libvulkan.so.1
```

判据①（已验证）: `readelf -h` = ELF64 / EXEC / Advanced Micro Devices X86-64
判据②（已验证）: `env -i ldd` 全部命中 dist 内实体或系统 libc/libm/ld，无兼容层组件：

```
libSDL3.so.0 => dist/.../lib/libSDL3.so.0
libvulkan.so.1 => dist/.../lib/libvulkan.so.1
libm.so.6 / libc.so.6 / ld-linux-x86-64.so.2 => /usr/lib*
```

归档：`dist/totk-recomp-x86_64-steamos.tar.zst` 7,050,217 B，9 条目，
SHA-256 `4cc9c51f9816a42aa45eb6cac57a10dd3d470208329a55e5cb738eea5e1cde7a`

无 ROM 边界行为（数据面阻断点，非缺陷）：
`cannot open .../data/img/main.bin` —— 启动序列 load_module(main.bin) 先于任何
SDL/Vulkan 初始化，因此判据③（运行期 maps）在拿到 exefs 前无法用 totk 本体采样。
此前判据③已由 ScarletNX b6 hbmenu 强验证（maps 457 行 compat=0，60.0 fps，env28）。

## 3. hactool 无 ROM 工具链闭合（env31，X=写入仅限白名单）

- 失败链：env30 `curl (18) partial file` → Deck 全局 git url 重写指向失效代理
  `ghproxy.com`（404→ghfast.top 403）→ 宿主机无 make/gcc（只读 rootfs 正常状态）。
- 处置：codeload tarball 直取 SciresM/hactool master → 容器 `nativedeck-build`
  内 `cp config.mk.template config.mk && make -j4`（容器自带 gcc；mbedtls 经静态库路径编译）。
- 产物：`~/native-recomp/src/hactool_bin`
  SHA-256 `4331a861cb2e87b8de8c02cd509d8575c2e11b6d9136c33a45dd5112166ec417`
  ELF64 x86-64，ldd 仅 libc/ld；自测输出 `hactool (c) SciresM. Built: Oct 26 2026`。
- 作用：ROM 到位后可立即 `hactool --exefsdir/--romfsdir` 提取，M3 无工具链等待。

## 4. TF 卡镜像穷尽扫描（B 项 · Mac 侧只读）

- 目标：`/Volumes/Share/游戏/Switch/TF-backup/tf-20261010-pre-cp100.img.zst`（107,661,265,803 B）
- 方法：`zstd -dc | scanner2.py` 流式扫描（nice=10，零写入被扫卷），模式：
  `0100F2C0115B6`(TOTK 1.0.0)、`0100F2C0115B7`(更新版前缀)、`NESFS`(XCI magic)、UTF-16LE 变体
- 进度：44 GiB 已解码，速率 ~80 MiB/s，**命中 0**（13 位精确前缀零命中）
- 前轮短前缀 `0100F2C`(7位) 的 10 次命中判定为噪声（长度不足，随机命中期望高）

## 5. 输入/体感/缓存面无 ROM 量化（C 项）

| 面 | 证据 | 判定 |
|---|---|---|
| 输入（手柄） | `/dev/input/event*` 属组 input，deck 用户**不在 input 组**（组：deck steamos-log-submitter wheel xdroid*）；节点有 ACL `+`（seat 会话授予），SSH 会话无 ACL | blocked(会话层)：Gaming Mode/gamescope 前台启动时 SDL3 正常持有；M4 经 GUI 会话验证 |
| 体感（gyro） | 无 `/dev/iio:device*`、无 lsm6ds 内核模块 → Deck IMU 走 HID vendor 报告，由 SDL3 steam_virtual_pad 路径暴露 | 依赖输入面同路验证；`motion_validated=false` 维持 |
| 着色器缓存 | `~/.local/share/` 可写（实测 touch/rm）；run.sh 声明状态目录 `${XDG_DATA_HOME:-~/.local/share}/totk-recomp`，首次启动自建 | 已验证（可写性）；预热效率需 ROM 后 `warmup.sh` 实测 |
| GPU 直持 | `renderD128` 全局可读写（crw-rw-rw-） | 已验证（判据③设备面） |

## 6. 本轮 Deck 写入清单（红线合规）

- `~/native-recomp/probe/r2-hactool.sh`（本项目自建，2 次覆写均为本任务自身脚本）
- `~/native-recomp/logs/env31{,b,c}.log`
- `~/native-recomp/src/hactool.part/`、`~/native-recomp/src/hactool_bin`
- 未动 rootfs/Steam/Decky/compattools/flatpak；未 sudo；未重启。
