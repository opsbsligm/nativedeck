# 目标模式提示词 · nativedeck · 第 31 轮版（待你批准）

> 用法：批准后用 `create_goal` 启动，objective 取下方"目标"段全文；
> 其余段落为执行约束与验收口径，随 goal 持续生效。
> 与第 7 轮八要件版的区别：路线已收敛（MNG 直跑 vs 静态重编译二选一），
> 不再是"验证模式"而是"交付模式"——直接开发完成 BOTW + TOTK 原生移植。

## 目标

将《塞尔达传说 王国之泪》(TOTK) 与《塞尔达传说 旷野之息》(BOTW) 以
**原生 x86-64 二进制**形态安装到 Steam Deck（deck@192.168.1.105, SteamOS 3.9.5,
AMD VANGOGH Vulkan 1.4.350）并实机运行，安装形态为 SteamOS 原生可运行模式：
不依赖 .deb 系统包、不经过任何兼容层（wine/proton/dxvk/box64/qemu/fex/binfmt），
安装入口为 Steam non-steam game 自包含目录 + run.sh。

## 路线（已收敛，不重开调研）

- **BOTW**：SavageWindRecomp v0.3.0-alpha.3（LAS 静态重编译族，x86-64 原生）。
  三判据已全过（AppImage 路径，2026-10-26 PID 338360/339997 实测）；
  自包含目录 `~/native-recomp/swr/` run.sh 已修 bug 并实机启动验证。
  **唯一缺口 = BOTW 1.9.0 exefs+romfs 游戏资产**（用户投放到
  `~/.local/share/savagewind/extracted/` 或 `~/native-recomp/roms/`）。
- **TOTK**：totk-recomp（a32f709e，AArch64→C++ 静态重编译 + NVN-on-Vulkan，
  即"arm to x86"层本体）。构建链已就绪：容器 `nativedeck-build`（Ubuntu 24.04,
  clang 18.1.3）deps 已 prewarm 163M；`build-totk.sh <xci> <prod.keys> -O1` 一键。
  **唯一缺口 = TOTK 1.0.0 xci + prod.keys**。
  版本墙：1.0.0 走 totk-recomp（一键）；1.4.3 走 ultratears Linux 化（半成品 stash，
  工作量中等，仅在用户 ROM 是 1.4.3 时启用）。

## 验收三判据（每个游戏各验一次，hardware_validated 门槛）

1. `readelf -h <exe>` = ELF64 / X86-64
2. `env -i ldd` 或运行期依赖解析中无 wine/proton/dxvk/box64/qemu/fex/binfmt
3. 运行期 `/proc/<pid>/maps` grep 兼容层 = 0，且 guest heap/swapchain 特征在场
   （GPU 阶段，非 TUI 阶段采样）

外加体验验收：Moonlight 串流自证首帧 + 进游戏 + 记录帧率/温度/是否冻结
（Deck 4CU iGPU，TOTK 预期 30-40fps@720p 区间，BOTW 参照上游 Deck 实测 40fps@60cap）。

## 安全基线（Deck 红线，与上轮一致）

- 只写：`~/native-recomp/`、`~/.local/share/containers/`、
  `~/.local/share/{savagewind,totk-recomp}/`（运行时自建）、`~/.local/share/lasrecomp/`
- 不碰：rootfs（/usr /opt /etc）、`~/.local/share/Steam/`、`~/.steam/`、
  Decky（`~/homebrew/`）、compattools.d、flatpak、`shortcuts.vdf`
  （M5 进 Steam 库需单独批准）、`/tmp/_MEI000004e7i2ncrS`（Decky 常驻解包）
- 不重启、不 systemctl、不改 ostree；不用 root（sudo 需密码）
- ROM/keys 不入库、不进 GitLab
- SSH 长任务 `nohup` + 落盘（TOTK 构建 1-1.5h）；前台命令 ≤45s；
  `-o ServerAliveInterval=5`
- 构建全部在容器 `nativedeck-build` 内；产物只落 /home
- 磁盘护栏：`df -h /` 可用 <400M 暂停非紧急写入；/home <50G 暂停构建
- 回滚：TOTK `uninstall-totk.sh`；BOTW `rm -rf ~/native-recomp/swr`
  （AppImage 备份 swr-alpha3.AppImage 保留）；rootfs 清理
  `~/native-recomp/tmp-cleanup-20261026/` 可整体删

## 执行顺序

1. 【等 ROM】用户投放 BOTW 1.9.0 exefs+romfs + TOTK 1.0.0 xci + prod.keys
2. BOTW：资产入位 → SWR 首启（游戏代码编译 ~16min + shader 预编译 ~7min on Deck）
   → Moonlight 串流验收 → 三判据③ GPU 阶段 maps 采样
3. TOTK：`nohup bash ~/native-recomp/build-totk.sh <xci> <prod.keys> -O1`
   → 构建日志监控（hactool→重编译→三判据→打包）→ install-totk.sh
   → 首启（TOTK_HANDHELD=1 默认）→ 三判据③ → 串流验收
4. M5（需单批）：`shortcuts.vdf` 写两条 non-steam game（SWR + TOTK）
5. 收尾：evidence 归档 → `codex/roundNN-*` 分支 → MR → 审查 PAT 批准合并
   → WeKnora finish（task_id=nativedeck-20261024, scene=homelab）

## 完成定义（goal complete 条件）

- 三判据对两个游戏各完成一次 GPU 阶段实测（hardware_validated=true）
- 两游戏均实机进游戏、串流可见、帧率记录在案
- 安装形态 = 自包含目录 + run.sh（非 AppImage 亦可启动），Steam 库可见（M5 批准后）
- GitLab main 合入全部 evidence；WeKnora finish 记录写回
- 未闭合项（如帧率低于 30fps 的调参、陀螺仪/Amiibo 增强）显式列为后续，不算阻塞

## 明确不算完成（防漂移）

- 只到 TUI/配置界面 = 未完成（须 GPU 阶段）
- ROM 版本不匹配（BOTW 非 1.9.0 / TOTK 非 1.0.0）硬跑 = 未完成
- 用模拟器（Ryujinx/Sudachi/EmuDeck Flatpak）顶替 = 未完成
- 上游"Deck 实测 xx fps"转述 = 第三方证据，不等于本机已验证
