# 来源、作者与许可

- 原始自主机身绘图：用户提供的 BOTW 已成功绘图源码 `botw_xbox_diagram.inc`，仓内保留位置、来源标识与完整 SHA-256 见 `sources.json`。原件保留在 `vendor/botw_xbox_diagram.original.inc`。原注释声明为自主绘制的 Steam Deck 图；文件未写独立作者姓名或许可证，因此本目录不补造作者、不擅自将该原件重授权为 MIT。
- SDF 几何与 Fira Sans 文字布局：Revivedx/SavageWindRecomp，固定提交 `4249c880bc6b09ad0207fc3f6e7595346f08d232`，`runtime/nvn/glyphs.c`。版权人为 2026 Revivedx and the Savage Wind Recomp contributors，以及 2026 Peiikai（LAS Recomp）。MIT 全文保留在 `vendor/LICENSE.SavageWind.txt`；完整源文件保留作溯源，不参与构建。衍生源码只抽取绘制所需部分，不使用原文件的游戏图标、纹理识别或运行时加载逻辑。
- 字体：Fira Sans SemiBold，沿用上述提交已有字体，SIL Open Font License 1.1，完整作者及权利声明见 `vendor/OFL.FiraSans.txt`。没有修改字体，没有读取游戏字体或系统字体。
- 字体光栅化：同一提交已使用的 `third_party/imgui/imstb_truetype.h`，stb_truetype 的 Dear ImGui 版本；原文件内保留作者及 MIT/public-domain 双许可声明，另保留 `vendor/LICENSE.imgui.txt`。没有新增替代字体库。
- 本次新增的独立 API、画布适配、示例与验证脚本由 Codex Agent 为当前任务编写。这些新增部分按 `LICENSE.adaptation.txt` 的 MIT 条款提供；这不替代上面各来源自身的许可。
- 斜视增量：`inclined_view.inc`的投影、采样、顶缘及四个肩键为本任务自主代码；正面图元仍来自上述BOTW自主绘图。游戏预览只读用于确认“无1=正视、有1=斜视”的资源角色，没有复制预览像素、材质或图形进本目录。

全部公开下载均固定提交；URL、字节数、SHA-256 记录在 `sources.json`。本目录不包含游戏资源、密钥、游戏代码、纹理上传挂钩或布局补丁。第三方项目完整源快照仅用于来源和确定性衍生，示例程序不连接游戏运行时。

## v2官方位置核验增量

原图和原作者声明未改。v2仅将自主十字键四个图元下移14px；双摇杆及ABXY不动，依据Valve官方Deck正视图的相对位置。两张外部核验图片版权属于Valve；本公开树仅在references.json保留来源URL与摘要，不包含图片文件，也没有复制其像素进渲染产物。它们不属于本项目MIT授权材料。官方近似中心读数不是工程尺寸。

## 公开RLE工具增量

scripts/make_rgba_rle_header.py、scripts/test_rgba_rle.py、tests/test_rle_unpack.c由本任务新增，沿用LICENSE.adaptation.txt。编码格式、符号和解码逻辑保持报告原build_totk_deck_bitmaps.py及现有公共totk_deck_bitmaps.h的接口；公开工具没有包含原生成器的游戏纹理读取、Tegra GOB处理或原资源依赖。可选SHA/view列表只含身份元数据，不含原图像素。

公开exact测试从vendor原始自主图重建参考输出，不分发或依赖报告私有二进制基线。sources.json及既有vendor许可均保留；references.json记录官方参考链接与摘要，官方图片不随公开最小包分发。
