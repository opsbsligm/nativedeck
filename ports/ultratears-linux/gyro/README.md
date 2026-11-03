# Steam Deck 原生六轴后备输入

Steam 的虚拟 Deck 手柄可能只提供按钮与摇杆，没有 SDL 传感器。此补丁只在该手柄被选中且 SDL 六轴不可用时，只读内置 Deck IMU，并向既有 `motion_fusion.c` 供数。Steam 继续负责按钮；有六轴的外接手柄沿用 SDL。事件回调只接受当前选中手柄的传感器，防止两个来源同时更新融合。

C读取器不发送 HID feature report、不抓取输入。Steam 在应用切换后可能将 IMU_MODE 清零，因此正常启动增加会话父进程：先查询并保存0x30寄存器，仅启用0x18原始加速度/角速度位，退出时在寄存器仍等于本会话所设值的前提下恢复旧值并读回。启动后最多检查10秒、最多重新启用3次，只处理全关闭状态，避免与其它配置持续争用。不修改按键、触控板、lizard模式、udev或Steam持久设置；沿用现有hidraw权限。当前回读不匹配时拒绝改写。SIGKILL会话父进程或断电时无法保证finally恢复，属于未验证边界。`TOTK_GYRO=1` 启用游戏六轴，`TOTK_STEAMDECK_GYRO=0` 可禁用后备读取。实际游戏选项仍由玩家控制。

## 可复现私有构建

仅适用于已交付 TOTK 1.4.3 V8、18处实时计时补丁及其原始对象基线。脚本固定私有目录布局，拒绝不同源码与部署 SHA；不包含游戏数据或生成C。

1. 将本目录所有 `.c/.h/.py` 文件复制到 Deck 的 `~/native-recomp/work/totk-1.4.3-20261031/gyro-20261103/`，并复制 `tools/native_review/launchers/totk-steam.sh` 与 `totk-motion-session.py` 到同目录。
2. 宿主执行 `python3 .../prepare_gyro_candidate.py`，只生成候选 SDL 文件与最小 Ninja 计划；校验原始 SDL 源 SHA、记录全部不可变链接对象 SHA。
3. 宿主执行 `python3 .../build_gyro_candidate.py`。沿用现存 `nativedeck-build` 容器与依赖，只编译三份对象并链接；低优先级单并发、4 GiB 地址空间限制，额外磁盘峰值小于0.9 GiB。结束将候选输入和 ELF 绑定到 `build-receipt.json`，编译日志归任务 evidence。
4. 游戏空闲时执行 `python3 .../install_gyro_candidate.py`。它持有正常 profile 的 session lock，核验父 ELF、候选回执、剩余空间，备份77文件存档及旧 ELF/manifest/build record/launcher，再同步更新并执行 bundle 验证。游戏在运行时拒绝安装。
5. 从原有 Steam 掌机入口启动，日志应出现 `Steam Deck native six-axis fallback active`。等实际游戏启动六轴后检查 `[gyro]` 的真实游戏读取计数，再手测方向与瞄准。

## 验证边界与恢复

单元测试核验报文尺寸、版本/类型、大小端符号、轴向和量纲，不以按键字节作为六轴数据。真实设备静止采样可验证传感器到现有融合状态输出；它不等同于游戏瞄准、实体方向或神庙操作通过。

全零加速度报文被拒绝，不伪造样本新鲜度。报告停止、断开或200ms没有样本时，不提供陈旧运动状态。物理设备断开后不会在同一读取线程自动重新枚举，需手柄重新连接或重新启动游戏；休眠恢复与长时稳定性尚未验证。

本次安装的精确回滚副本在 `~/native-recomp/evidence/gyro-20261103/backup/`。退出原生游戏并持有同一 session lock 后，一并恢复其中 `ultratears`、`bundle.json`、`build-inputs/build-record.json` 和 `totk-steam.sh` 到原位置，若安装前无 `totk-motion-session.py` 则移除本次会话辅助入口（存在旧版则恢复备份）；验证 bundle 后再启动。不要覆盖玩家后来生成的存档。此回滚返回已交付的60Hz实时计时版本，原30fps回滚链仍独立保留。

协议及坐标来源见 [SOURCES.md](SOURCES.md)。
