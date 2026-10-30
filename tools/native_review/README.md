# NativeDeck 审查与构建检查

这些工具不包含游戏、密钥或游戏生成代码。它们用于检查现有本地输入和产物；CI不接收任何游戏资源。

- `native_binary_check.py BIN --totk`：只读解析ELF，不执行目标程序；拒绝零游戏函数表。函数表非零也不会把`release_accepted`或`playability_validated`置为true。
- `chinese_font_check.py FONT Bootup_CNzh.pack`：只读核对TrueType轮廓与实际消息文本的汉字覆盖率，不提取或保存游戏文本。支持TTF及TTC首个字体。
- `settings_defaults.py`：将缺失或自动文本语言设为简中；保留玩家明确设置的其他语言、按键、音量和画面选项。先按内容哈希备份，再原子写入并读回。
- `legacy_sdk7.py`、`prepare_codegen_profile.py`：给固定上游源码增加显式`--legacy-sdk7`模式，核对原始main、subsdk0、sdk的SHA-256，输出真实的1.6.0版本与build ID；不复用其他版本sites、不修改成品库。新模块也加入`GAMELIB_ID`的源文件集合。
- `install_chinese_defaults.py`与`install_totk_probe_guard.py`：本次已审查部署的迁移脚本。仅适用于代码中固定的旧状态，拒绝未知或已改变的启动器；不是通用安装程序。重跑会拒绝已存在的备份或目标，不清理原数据。
- `harden_totk_wrapper.py` → `finalize_totk_wrapper.py`：按顺序迁移旧构建入口，隔离空探针与真实构建目录，检查前台游戏、内存、磁盘和电源；路径按参数传递，失败不发布归档。
- `package_native_dir.sh`：支持含空格的资源名，校验逐文件摘要并读回压缩归档；失败时清理本次临时文件，保留既有归档。它不验证游戏是否可玩。

## 验收标准

每个游戏分别证明：原生x86-64程序与真实游戏代码、精确版本与输入哈希、资源完整性、Steam掌机入口、读档与操作、简中画面及Xbox按键提示。证据必须绑定所运行二进制的SHA-256。

检查顺序为：输入及版本 → 生成代码 → 原生构建 → 依赖与打包 → 实机启动/读档/操作 → 简中与Xbox提示 → 发布。缺少证据时保留未通过状态；ELF、窗口、帧数或CI绿色不能单独证明整个移植完成。

## 当前边界（2026-10-30）

《旷野之息》本地适配为1.6.0。已有Steam入口、读档、操作及Xbox提示的实机证据，整夜静止场景会话超过百万帧；这不代表完整通关验证。仍有一个影片区间的IVFC校验问题；已有NAS副本对应区间为零且7z尾部校验失败，不能拿它覆盖现有资源。完整中文字库已覆盖实际1091个消息文件的3206个汉字，尚需重启游戏确认画面。

现有《王国之泪》15MB ELF的`g_ftab_count`、`g_imp_count`和`g_s_ftab_count`均为0，生成目录只有ROM-free探针。它只能证明运行时能联编。已补充检查，不能登记为游戏构建或实机成功。

现有totk-recomp源码仅支持1.0.0；UltraTears的1.4.3上游仍把Linux/Deck列为未支持。两者不能通过替换版本字段互换。当前检查到的本地素材仅有标注为1.4.3的更新归档，尚无经过验证的TOTK本体。后续必须先核实真实版本与完整输入，再开发并验证相应Linux路径。

来源：[totk-recomp](https://github.com/Muhammad1259-sigma/totk-recomp)、[UltraTears](https://github.com/kuraeow/ultratears/tree/dev)、[文泉驿微米黑Debian包及SHA-256](https://packages.debian.org/trixie/all/fonts-wqy-microhei/download)。字体只部署到用户项目目录，保留许可，不安装系统包。

## 本地检查

在有C编译器的Linux构建环境中运行：

```sh
python3 -m unittest discover -s tools/native_review -p 'test_*.py' -v
```

测试覆盖真实ELF空表拒绝、非空表不能冒充可玩、架构/截断拒绝、原始模块身份与载入布局拒绝、设置备份及幂等性。真实游戏生成与实机检查在设备侧完成；CI不以合成输入替代游戏验收。

构建及打包测试需要Linux的C编译器、GNU coreutils、tar与zstd。CI启用MR内SAST和密钥检测；安全扫描作业成功还需检查其报告中的实际发现，不能把扫描进程退出0直接当作零风险。
