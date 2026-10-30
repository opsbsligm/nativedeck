# BOTW 1.6.0 / SDK7 适配补丁

基于 SavageWindRecomp 固定源码提交 `4249c880bc6b09ad0207fc3f6e7595346f08d232`。上游及其许可见 `LICENSE.upstream`；补丁保留上游权利说明。这里不包含NSO、游戏生成代码或游戏库。

1. 在固定的上游源码中应用 `sdk7-native-runtime.patch`。
2. 应用 `sdk7-codegen.patch`，将仓库 `tools/native_review/legacy_sdk7.py` 复制为上游的 `tools/legacy_sdk7.py`。
3. 使用 `--legacy-sdk7` 生成本地自有游戏代码；该模式拒绝未知模块SHA、错误build ID或非预期模块布局。不能和 `--no-sites` / `--any-version` 混用。

运行时补丁为精确1.6.0输入提供旧SDK的NVN版本、音频回退和Xbox字形布局，并关闭缺少对应地址的可选改写。它不把1.6.0升级成1.9.0，也不证明完整游戏或DLC兼容。

本次已把两份补丁在固定上游的干净源码片段上顺序重放，结果见 `evidence/review-20261030/source-patch-replay.json`。仅生成器的layout阶段已用真实输入验证；使用新生成模式的完整游戏库重编译尚未执行，当前已运行的旧库未替换。
