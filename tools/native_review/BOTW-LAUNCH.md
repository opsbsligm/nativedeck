# BOTW 1.6.0 SDK7 启动完善

适用当前已安装的原生 x86-64 版本。`botw-run.sh` 直接启动私有原生运行时和游戏库，不增加 CPU 转译或 Windows 兼容工具。

启动流程先取得不删除 inode 的独占锁，再检查本用户 `/proc/*/exe`：已有 `savagewind`（包括旧启动器启动和已被替换的可执行文件）时直接返回，保留会话，不改配置或备份正在写入的存档。多个入口经过新启动器时只允许一局。绕过启动器直接运行程序仍不受此锁约束。

空闲启动固定 `SAVAGEWIND_DATA_ROOT` 和工作目录，避免当前目录的 `extracted/` 触发开发模式、使用另一套存档。沿用绝对 XDG 数据目录或显式数据目录，默认 `~/.local/share/savagewind`。保留现有简中/Xbox默认值和玩家自定义绑定。

启动前将 `save/` 备份到数据目录下 `native-launch/save-backups/<内容摘要>/save/`，校验副本和源文件，原子发布并保留清单。相同内容复用；变动、符号链接、异常体积或空间不足时拒绝启动。备份不自动清理、不自动恢复，避免误删或回滚玩家新进度。恢复必须等游戏退出后另行操作。

预检只确认 ELF 类型、版本标识和中文资源存在，不等于完整游戏库重建或资源完整性验收。失败记录在 `native-launch/last-launch.json`；子进程控制台日志为 `console.log` 与 `console.log.1`，每份最多约1MiB。运行时自己写的 `savagewind.log` 不由此工具管理。监督进程转发 Steam 发出的停止信号，锁由子进程同时继承，避免监督进程意外退出时立即允许双开。

部署把本目录的 `botw_launch.py`、`settings_defaults.py`、`botw-run.sh`、`install_botw_launcher.py` 放在 Deck 的项目取证目录，再执行 `python3 install_botw_launcher.py`。安装器核对现有启动器与默认配置工具的精确摘要、备份读回、原子替换，只更换启动脚本，不替换游戏或运行时，不修改 Steam 入口。`python3 install_botw_launcher.py --rollback` 仅在当前文件仍匹配本版时恢复旧启动器。

Xbox对应按物理位置生成：南=A、东=B、西=X、北=Y；提示通过实际 `g_bind_pad` 绑定反查。当前默认交互是东侧B、取消是南侧A，跳跃为北侧Y、攻击为西侧X，沿用游戏的动作位置，不擅自交换玩家操作。肩键/扳机分别为LB/RB/LT/RT。全物理按键、静态教程图和特殊动作仍须实机逐项验收，不能由源码检查宣称全部完成。

本轮保留已知遗留：`Demo104_1.webm` 有一个16KiB完整性坏块；当前各副本相同，既有NAS输入对应区间全零，无可信修复字节。完整fresh游戏库重建也尚未验收；游戏运行时不启动重型编译。王国之泪维持挂账。
