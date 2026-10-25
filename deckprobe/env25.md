# env25 — b5 构建产物 + GUI 版显示面复验（2026-10-26 06:08，Deck 真机只读取证）

## 一、运行时基线（只读）

- `date -Iseconds` = `2026-10-26T06:08:46+08:00`，`up 12:46`，load 1.00
- `/dev/nvme0n1p8` 939G / used 679G / **余 260G**
- `Mem` total 14Gi / available **10Gi**
- 结论：资源护栏全绿，与第 13~18 轮 baseline 一致。

## 二、b5 构建产物清单（Deck 侧，白名单 `~/native-recomp/src/ScarletNX/build/b5/`）

构建方式：podman `nativedeck-build`（Ubuntu 24.04，clang 18.1.3 / gcc 13.3 / cmake 3.28 / ninja 1.11 / LLVM 18），
CMake 开关 `-DSNX_BUILD_NX=OFF -DSNX_BUILD_GNUABI=ON -DSNX_BUILD_TESTING=OFF`，SDL3 经 CPM 从 `release-3.4.18.tar.gz` 源码构建。

| 产物 | 大小 | SHA-256 |
|---|---|---|
| `scarletnx-gui` | 22,398,112 | `46747b9188f5b54c176d19f062d227db110af1d4df341be45c60d4294b06675b` |
| `scarletnx-gnuabi` | 8,712,896 | `1afcc6375ab292ab4bdae4f91ebe724ccf4c6ddee368ff96fabf300274de764f` |
| `snx-a64dec` | 105,376 | `1454462b1f03519719be0ed5bc5b647be7e8cd26a2e458f95845801e77997448` |
| `snx-logscan` | 287,792 | `dece10c5be6e092f4e714840930dcfdce6cdfaee4b1465fb854a5a643f3f7644` |
| `snx-settingsgen` | 114,840 | `46a2851a6312dbef9bc37bbb5db4717ec86e5de0209f88b398970fcfc0d3a66a` |
| `snx-uigen` | 162,056 | `6d8121f6f19e697f2ae7eb29abcebb33336ba6de2ecb8d73fe81bc28497db3ed` |
| `libsnx_build_info.a` | 3,876 | `08c5930d9f012435a15336ec1476d880bb9bdaf961ef0358862c18cd0fc6d58d` |
| `libsnx_settings.a` | 91,890 | `b6bbde7f554d2a847601aabc124fe5f72d4a3bd65aca5993edc1964cc9fc8a9a` |
| `libsnx_settings_runtime.a` | 161,198 | `f837d63ece72ed132f82319fe1d8d22d1ab742300a1a070af19a5dc5567ac39b` |

（文件属主显示 `100000:100000` = 容器内 root 的宿主 uid 映射，deck 用户可读写执行，不影响使用。）

## 三、原生性三判据复现（GUI 版，本轮新增）

`ldd ~/native-recomp/src/ScarletNX/build/b5/scarletnx-gui` 完整依赖树：

```
linux-vdso.so.1
libm.so.6      => /usr/lib/libm.so.6
libstdc++.so.6 => /usr/lib/libstdc++.so.6
libgcc_s.so.1  => /usr/lib/libgcc_s.so.1
libc.so.6      => /usr/lib/libc.so.6
```

- 判据②：依赖树中 **wine/proton/dxvk/box64/qemu/fex 零命中**，且**零 LLVM 动态依赖**
  （对比 `scarletnx-gnuabi` 仍 NEEDED `libLLVM.so.18.1`，需 `runtmp/llvm18/` 快照补齐）。
- 这是当前项目内**依赖最干净**的产物：只依赖 SteamOS 自带的 glibc / libstdc++ / libgcc_s。
  分级：**已验证**（静态依赖面，`ldd` 直读）。
- 判据①（EM_X86_64）与判据③（运行期 maps）沿用 `deckprobe/env19.txt`、`env20.txt` §二的结论；
  本轮未重复展开。

## 四、GUI 版显示面复验（关键负面结果）

命令（从 steam 进程 environ 提取显示环境，无 root）：

```
export DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1000   # XAUTHORITY 在 steam environ 中不存在
timeout 20 env SDL_VIDEODRIVER=x11 ./build/b5/scarletnx-gui --help   → rc=0，stdout 空
```

对比：`scarletnx-gnuabi --help` 正常输出用法文本。

**结论：`scarletnx-gui` 的 `--help` 不打印任何内容。**
最合理解释：GUI 二进制把 stdout/stderr 重定向进了自身日志面，且 `--help` 在
SDL 初始化阶段仍走 `SDL_CreateWindow`（SSH 会话无 `XAUTHORITY`/X cookie → 创建失败即静默退出）。
分级：**推断**（未定位到具体源码行；不影响 M0）。

M0（像素级 GUI 自证）**不受此结果影响**，其成立依据是 `recompiled2/hbmenu/hbmenu`
（AOT 客户机代码 + RADV 光栅化，帧 SHA `445be562…`，见 `deckprobe/env20.txt`），
该路径不经 X11、直接在进程内回读 swapchain。

## 五、主机 LLVM 依赖快照（`~/native-recomp/runtmp/llvm18/`）

`scarletnx-gnuabi` 经 `LD_LIBRARY_PATH` 指向该目录后 `--help` 正常，`ldd` 全解析：
`libLLVM.so.18.1` + `libedit` / `libxml2` / `libicuuc` / `libicudata` / `libncurses` / `libtinfo`。
用途：使 gnuabi 产物能在**无 root、不装包**的 SteamOS 宿主上直接运行。

## 六、本轮红线合规

- 全部为只读命令（`ls`/`sha256sum`/`ldd`/`df`/`free`/`pgrep`/`tr`）+ 一次 GUI 二进制的 20s 超时运行。
- 未写任何文件到 Deck（本文件写在 Mac 侧），未改权限，未碰 Steam 区，未 sudo。
