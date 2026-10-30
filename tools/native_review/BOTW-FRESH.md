# BOTW SDK7 全量复建与四项验收

本轮修复使用设备上已有资料，未新增游戏下载。安装仍为原生Linux x86-64目录和原`run.sh`入口，未改Steam、Decky或系统分区。公开仓只收工具、补丁和脱敏证据。

## 固定构建

上游源码固定`4249c880bc6b09ad0207fc3f6e7595346f08d232`；原始`main/subsdk0/sdk`必须匹配`legacy_sdk7.py`内固定摘要。`botw_prepare_fresh.py --upstream SOURCE --exefs PRIVATE_EXEFS --work WORK --evidence EVIDENCE`通过`git archive`创建空工程，再应用本仓SDK7和Xbox补丁；已有工程或生成目录不覆盖。

设置绝对路径`BOTW_FRESH_WORK=WORK BOTW_FRESH_EVIDENCE=EVIDENCE`后执行`bash tools/native_review/botw_build_fresh.sh`。已有私有依赖前缀为`~/native-recomp/swr-src/build/linux/x86_64/deps`，构建在`nativedeck-build`容器中完成。Python包仅装入工作目录venv，固定版本见`botw-build-requirements.txt`。运行游戏时拒绝重型编译，需至少35GiB余量。项目构建容器保留10GiB/4CPU限额，并读回实际cgroup值；容器以外不设置系统限额。产物/临时文件均写工作目录。

三模块完整生成后`botw_seal_generation.py`封存输入、生成器与全部生成C文件。链接失败后仅在封存完全一致时允许续编，不复用另一游戏或另一输入的代码。发布工具`stage_botw_fresh.py`还检查完整构建日志、原始模块、非空真实函数表、影片修复证据与双DLC完整校验记录；保留旧安装、启动器和配置回滚信息，以版本目录和原子配置切换，不覆盖运行中的游戏。

`stage_botw_fresh.py`是本项目已有安装的迁移入口，读取本轮设备证据约定；不是接收任意游戏资料的通用安装器。它不下载、不解密、不分发游戏或密钥。DLC验证记录由本地取证流程产生，不能用手写布尔值代替真实签名和IVFC校验。

## 实测证据

全量新生成1901个C文件，真实函数计数main83259/subsdk013640/sdk34472。库ID`c7e6b36ee560a510`，SHA-256`76a1f4e4564782368c1c6f2ac7697354da9993db067167b7bf9e2212f24fed84`。Xbox图示补丁仅重编原生运行时，不改变此完整游戏库；最终运行时SHA-256为`948f0449d3379fb43c4a44c64e195851826844618cd0e11a29b7272589bfd89c`。

影片恢复16KiB leaf内唯一错误字节（偏移15664，0x4a→0x41）；恢复后的leaf SHA-256精确匹配原始IVFC表，完整NCA摘要也匹配原内容ID。不是重编码或跳过校验。正确影片SHA-256`a87e9c75d39998557a1832eae85f8334e8e28bff0a62b675416a6af624bc1f06`，严格FFmpeg全解码退出0。旧未使用的1.0.0 RomFS缓存另有155574个leaf不匹配，保留旧缓存后从已验证NCA重新提取；新缓存880128个leaf全部通过。故意保留的取证备份不改写。

两个DLC的归档CRC、签名、Superblock与IVFC六层均通过，版本均3.0。第一包7094文件/1389929109字节；第二包仅3字节版本标记，符合此代数据布局，不能凭小体积判为损坏。已实测中文介绍、DLC3.0标题、两包挂载、大师模式3D开场、保存和重新读档；普通模式原存档保持完整。未声称已通关DLC后期挑战。

控制器检测通过既有虚拟Xbox设备，不创建新设备、不改Steam绑定，也不发送Home/Steam/Capture保留键。`botw_pad_probe.py`拒绝未显式启用诊断的会话，按键/轴释放放在finally中；实际GetNpadState匹配才判通过。初轮RX-释放日志超时，独立复测按下/释放均通过，原失败证据保留。

Xbox静态图示补丁仅识别两个完整FNV-1a哈希相符的576x288/576x100 RG8纹理，保留alpha、位置和掌机外形，仅重绘物理键名字。选择其他图标风格时保留原数据，并由原运行时generation机制刷新。不把原游戏图片或其纹理数据纳入公开补丁。

2026-10-30 Steam Deck示意图增量：用户要求将Switch机身轮廓也替换为Steam Deck。最新`botw_xbox_diagram.inc`改为代码绘制Steam Deck正面（双摇杆、双触摸板、ABXY、View/Menu）和顶部肩键图，顶部同时标注L1/LB、L2/LT、R1/RB、R2/RT。`botw_deck_layout.py`用固定原始布局摘要核对输入，在基本/骑乘/滑盾三组说明中移动15个控制分组，使指示线对应新硬件位置；只有一个BFLYT成员的15组XY平移改变，所有其他SARC成员逐条一致，Yaz0解压回读一致。SARC/Yaz0工具固定`oead==1.3.0`，公开依赖清单已记录；需要从构建venv执行发布工具。`stage_botw_fresh.py`同时发布新图形与新布局，启动器将配套Bootup.pack摘要纳入预检。

最新运行时SHA-256为`ce43b07ba3d47a50ffd9439a29ddb66c556c880d926801e88af76a2dee3030aa`；完整游戏库未改变。原始图示与旧目录保留，配套布局包SHA-256为`00c88ee3e8d6fbab703135c451c3fa7841c7b443c8983d37dbf57680358e1c1f`。图形替换是游戏运行时行为，不修改截图，也不改Steam控制器配置。触摸板、Steam键和快捷键画出真实位置；没有为其新增游戏动作。

2026-10-30 最终连线修正：左摇杆移位后额外延长三套布局的水平连接线，保持功能文字旁的括号位置不变，消除悬空线段。修改范围为15个控制组的平移及12个线段坐标/宽度属性；最新配套包SHA-256为`942a751142aee6b563a67f8ec700e3c9a26925dcee538825db367a14989a691b`。原动画对应组只使用可见性轨道，不覆盖这些坐标。早期配套包和首版截图作为过程证据保留。
