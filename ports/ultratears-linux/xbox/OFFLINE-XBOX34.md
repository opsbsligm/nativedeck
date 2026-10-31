# 离线 Xbox34 生成路径

四份原始 MIT MNG 文件来自用户本地既存 f1d00772df1ac3230268f3124bdeb6b7cc81a61c 快照，位于 vendor/macnativegames-f1d00772，包含原 LICENSE。UPSTREAM.json 及原 check_tools() 完整保留；这些文件的字节数、SHA 不变。vendor 目录不包含游戏内容。

公共 prepare 默认使用上述原始 vendor，也接受 --tools 指定同一固定 SHA 的原始工具目录。流程：原始 check_tools → 核验 XBOX_STICKS.json 中的补丁 SHA → 创建临时副本 → 严格应用统一差异（无模糊匹配、路径越界、偏移修复或系统 patch 依赖）→ 核验派生脚本及合成测试的精确字节数/SHA → 用派生 make_button_icons.py --style xbox 生成 34 glyph → 沿用六资源 manifest 校验和新目录发布。派生副本用完删除；不修改原 vendor，不降低原 check_tools 门禁。xbox-ui.json 新增 tool_derivation，记录上游 commit、补丁 SHA、派生 SHA、依赖 pin SHA 和 34 glyph。

依赖：Python >=3.14（必须带标准库 compression.zstd）。fontTools 4.68.0 纯 Python .py 源码来自既有本地安装，位于 vendor/fonttools-4.68.0；MIT LICENSE 与 LICENSE.external 均保留。FONTTOOLS.json 逐文件绑定 354 个文件，包括许可证；不含任何字体样本、游戏字体、C 扩展、动态库或二进制构建产物。本轮只验证本工具用到的 API，不承诺这份纯源码包含 fontTools 的所有可选功能。原 requirements.txt 为可选独立安装参考；本生成路径和专用 CI 不运行 pip，也不访问网络。

公共 CI：xbox34-offline 使用 Python 3.14 镜像，执行 python3 -S -B tools/native_review/run_xbox34_ci.py；6 项生成路径/篡改测试 + 子进程 4 项合成轮廓测试，任何失败、缺依赖或 skip 均失败。该 job 不依赖 zstd CLI、编译器、patch、RomFS、key 或字体数据。CI 容器镜像本身需预置/由现有 registry 提供，离线承诺指 job 内的依赖与测试执行，不包含首次取得 CI 镜像。既有 review-tools/SAST/secret_detection 保持原有门禁；新增测试放 ports/.../tests，由专用 runner 显式执行，避免旧 Python job 将新依赖变为 skip。

本地/CI 验证：

```sh
python3.14 -S -B tools/native_review/run_xbox34_ci.py
```

由主线程在合并审查后、对自己的已授权 RomFS 执行生成（目标必须全新、位于 ~/native-recomp）：

```sh
python3.14 -B tools/native_review/ultratears_xbox.py prepare \
  --romfs "$HOME/native-recomp/work/totk-1.4.3-20261031/data/romfs" \
  --destination "$HOME/native-recomp/work/totk-1.4.3-20261031/xbox34-generated-new" \
  --python "$(command -v python3.14)"
```

这是公共字体/HUD 基础生成器，不会凭空生成主线程的额外 v4 控制器机身图/布局。需要该布局的最终 ui-v5 已在报告私有目录独立合成；不要用本命令的基础输出覆盖 v4/v5。字体及 HUD 的生成能力确实为 34 glyph，不依赖手工私有资源才能生效。

离线测试的 prepare 路径用小型合成输入，资源生成子进程由夹具模拟；派生脚本本身另由真实 CFF 合成轮廓测试执行。Mac 对 Linux 专用 renameat2 发布使用测试限定的 rename shim，Linux CI 使用真实发布函数。未在本 candidate 上重跑真实游戏生成或实机验证；hardware_validated=false。
