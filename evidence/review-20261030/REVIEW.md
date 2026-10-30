# NativeDeck 全局审查：2026-10-30

结论：存在阻止完整交付的问题。当前可确认《旷野之息》1.6.0经Steam掌机入口原生启动、读档和短程操作；不能宣布两款移植全部完成，也未满足“最新版本含DLC”的完整要求。本次变更合入只代表审查修复交付，不代表游戏验收通过。

## 发现、修复和剩余问题

| 严重度 | 发现及影响 | 本次处置 | 剩余验收 |
|---|---|---|---|
| P1 | 王国之泪现有ELF只有运行时，三张函数表计数均为0；误当游戏构建会产生假完成 | 在当前入口和真实构建打包前拒绝空表，真实构建改用独立目录 | 真实游戏代码生成、构建及实机进游戏均未完成 |
| P1 | BOTW共享字体曾回退DejaVu；先前Noto子集还缺实际文本125字 | 部署含TrueType轮廓的文泉驿微米黑并保留许可；实际1091个消息文件的3206个汉字覆盖通过；下一次启动默认简中/Xbox | 当前会话保留，中文画面未验证；不把文件覆盖率当作渲染验收 |
| P1 | 现有BOTW生成库使用过应急元数据修改，不能作为可复现构建流程 | 源码增加精确1.6.0/SDK7模式，校验三个原始NSO的SHA与模块布局；已验证layout；新helper加入缓存身份 | 需独立fresh生成及完整编译，并绑定新库哈希重新做游戏验收 |
| P1 | BOTW原始RomFS存在一个16KiB叶块不匹配，落在`Movie/Demo104_1.webm` | 保留游戏现状；检查NAS和旧错位副本均无正确替代块，未静默跳过或替换影片 | 需要完整、校验通过的同版本资源；当前不可称资源完整 |
| P1 | 构建脚本把路径展开进shell程序；归档失败可能继续输出完成，空格文件名的摘要可能错误 | 改用位置参数与数组；打包失败退出、NUL分隔文件清单、归档读回及唯一输出名；补齐rootfs空间护栏 | 真实TOTK构建尚未运行，不能把合成打包测试当游戏成功 |
| P2 | 项目内两份密钥权限为0644 | 调整为0600；未读取或记录内容 | ROM、密钥和生成游戏库继续禁止入仓 |
| P2 | 旧记录把版本/功能支持范围写得过满 | 明确现有BOTW为1.6.0，完整流程、物理手柄全键、中文、DLC及最新版本均未全部验收 | 逐项验收后才能提升相应状态 |

## 当前现场证据

`review-session-snapshot.json`绑定实际运行二进制、启动器、字体及构建入口的SHA。取样时PID24031由Steam AppID2245023905启动，已连续运行10小时27分；最近帧1128875、30fps。此为静止场景长跑和短程操作的证据，不能外推为通关或全地图稳定性。映射中未发现Wine/Proton/DXVK/Box64/QEMU/FEX运行库；ELF与映射检查只证明该项原生运行路径。

`steam-entry-review.json`只读检查了9个快捷方式，本项目只有一个正确的旷野之息入口。本次未改Steam快捷方式、插件、Steam Input全局设置、rootfs或系统服务，未重启Steam/设备/当前游戏。

字体包来源为Debian官方`fonts-wqy-microhei_0.2.0-beta-4_all.deb`，包SHA-256为`3fb0ff79033124b863bf9d28af56c62646d5b74774d26be0ce8a5beefe2fed55`；部署字体SHA见`full-chinese-font-coverage.json`。字体只进入本项目目录，不安装系统包。设置helper对缺失/auto语言给出简中默认值，保留明确选择的其他语言、图标、绑定及音量，改动前留逐字节备份。

影片问题依据上一轮独立校验：880128个叶块中1块不匹配，RomFS偏移`0xd6050000`，影片内范围`[0x2fcd90,0x300d90)`。本轮NAS归档虽然长度正确，但末尾下一头为零且CRC失败，目标密文区间也为零；不能作为修复源。该核验不重新下载或提取整份游戏。

## 代码与测试

两份SDK7源码补丁在固定上游提交`4249c880bc6b09ad0207fc3f6e7595346f08d232`上重放通过。没有在当前游戏运行时重新编译或替换游戏库。

构建容器运行12项测试：11项通过，归档正向测试因容器内缺zstd跳过；随后在Deck宿主的现有zstd环境补测两项打包测试全部通过。覆盖真实ELF空表、版本身份与布局拒绝、设置保留及备份、路径命令替换不执行、打包失败不发布、含空格资源归档读回。原始测试输出见`review-tests.log`及`package-host-tests.log`。CI安装所需zstd并要求相同测试全部执行。

CI启用单元测试、Python语法、MR内SAST及密钥检测，扫描作业不允许失败。实际精确SHA流水线与报告结果以MR交付回读为准；本文件不预写CI已通过。

## 王国之泪后续按同一标准实施

现有[totk-recomp](https://github.com/Muhammad1259-sigma/totk-recomp)只支持1.0.0；上游报告的Deck帧率不是本机验收。[UltraTears dev](https://github.com/kuraeow/ultratears/tree/dev)适配1.4.3，当前README明确Linux/Deck尚未支持，并列出集成显卡尚未支持的限制。不能把其Windows成果当成Deck原生成果，也不能把1.0.0地址表直接套在1.4.3上。本地仅查到标注1.4.3的更新归档，文件名不证明版本或本体完整。

两游戏共同顺序：精确版本/输入摘要 → 资源完整性 → 游戏代码生成 → ELF/依赖/打包 → Steam掌机入口 → 读写存档与操作 → 简中实际画面与Xbox提示/键位对齐 → 完整版本/DLC范围验收。只读ELF、窗口、帧数、非空函数表或CI成功均不能替代后面的项目。

本轮已为王国之泪落实共用构建检查及故障处理；因上述P1未全部闭环，暂不把旷野之息登记为已通过基准，不启动重型游戏构建抢占当前会话。

## 回滚与产物

Deck备份均在`~/native-recomp/evidence/review-20261030/`：`run.sh.before-chinese`、`build-totk.sh.before-review`、`build-totk.sh.before-packaging-fix`和`totk-run.sh.before-guard`。若需回滚，先确认本项目游戏退出，再对照本次哈希恢复对应文件；不要覆盖任何保存进度。配置逐字节备份在应用数据目录`native-settings-backups/`。

本轮脚本和证据归档在Mac `~/reports/nativedeck-review-20261030/`及此工作树，设备侧仅使用上述项目目录。没有本轮大于2GiB产物，没有往`/tmp`或`/private/tmp`生成文件。原工作区脏`STATUS.md`保留原状。

来源：[Debian字体包及摘要](https://packages.debian.org/trixie/all/fonts-wqy-microhei/download)、[GitLab MR安全扫描配置](https://docs.gitlab.com/user/application_security/detect/security_configuration/#use-security-scanning-tools-with-merge-request-pipelines)。
