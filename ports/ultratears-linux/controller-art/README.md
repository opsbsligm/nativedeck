# Steam Deck controller-art v2

独立C渲染器，生成自主front/inclined两视角580×340、top-down RGBA8 straight alpha；每张788800字节、每行2320字节。C API头与上一版逐字节相同。原生渲染时使用仓内Fira Sans及静态stb，运行时RLE上传不需要字体、图片库或渲染器。

## 最小几何修正与来源

仅将原576×288画布D-pad中心(38,65)下移至(38,79)。front成图D-pad=(40,105)，LS=(90,114)、RS=(472,114)与ABXY不变；inclined沿用原投影，新D-pad=(52.25694444444446,131.25)。独立renderer仍输出front/inclined两视角，anchors的resources保留原资源角色；实际controller-runtime hook对六项精确来源身份统一上传inclined（view=2），不按原资源角色切回front，纯top不参与。

Valve官方Deck正视图显示D-pad中心略高于LS，不能将关系反转；v2将原夸大的23px差值收敛为9px。按任务约束冻结ABXY/摇杆，右侧仍是示意比例，不宣称Valve CAD精确复刻。来源URL与参考文件摘要见references.json；官方图片未编入自主图或公开更新包。原始自主几何、第三方源码/字体及各许可仍在vendor/，来源声明见sources.json和NOTICE.md。

## 复现与测试

在本目录执行：

```sh
make check check-rle
```

check会从vendor原始自主绘图重新生成未修正的参考渲染器，产物只写build/reference/，不依赖报告私有路径、游戏文件、外部PNG或预置二进制基线。

保留原图逐像素验证：front仅允许半开矩形[20,71,60,125)内变化；inclined仅允许原源区域[18,45,58,99)经固定投影、双线性采样支撑覆盖的位置变化。区域外每个RGBA字节必须一致；top全图一致。允许区由设计预先固定，不依据实际差分扩张。原始参考SHA也被核对。

同时验证：真实字母、锚点、ABXY方位、透明度、缓冲区边界、padding、确定性、C/RLE解码逐字节往返和C++头兼容。RLE长游程65535拆分、非灰度输入拒绝、无效/溢出游程、无效身份元数据和已有输出拒绝覆盖均有测试。所有测试只使用自主图及合成测试数据。

## 通用RLE头生成器

Python标准库脚本scripts/make_rgba_rle_header.py只读取自主RGBA，以及可选SHA/view元数据；不读取原始游戏纹理、不含游戏解码器或GPU布局逻辑。

与同级controller-runtime现有接口兼容：nd_deck_run={uint16_t n,uint8_t grey,uint8_t alpha}，view1=front、view2=inclined；保留nd_deck_front、nd_deck_inclined、nd_deck_source_view和nd_deck_unpack。解码函数与现有实现一致。

```sh
python3 -B scripts/make_rgba_rle_header.py \
  --graphics build \
  --source-views-from-header ../controller-runtime/totk_deck_bitmaps.h \
  --out build/rle-v2
```

输出目录必须不存在，以保留旧产物。该命令保持现有SHA白名单及顺序，只替换自主图RLE数组。也可用--source-views views.json传入纯元数据数组，例如[{"linear_sha256":"64个小写十六进制字符","view":1}]。省略两种身份参数时，生成可独立解码但不匹配任何来源的通用头；正式runtime更新应保留已有白名单。

输出totk_deck_bitmaps.h和steamdeck-bitmap-build.json。头不含时间戳、绝对路径或平台字符串；相同RGBA和同序白名单生成相同字节。运行时直接使用nd_deck_unpack，避免字体路径依赖。C入口拒绝无效view、NULL和短缓冲且不写目标。

## 本次已实际验证的输出SHA-256

- front.rgba: ce04c2a5a30053698fd73e864fc3b8a0655f5503d4ce8d95241405d833c225ef
- inclined.rgba: 5f49626b1c0c6a7f0ec4df406b173e1fbb7022a8cd22cd1a8e95d90ed0746729
- 使用当前六项白名单生成的totk_deck_bitmaps.h: 3c843d31847ea01e9cddc58e407f9665ab64c030a30def184885601b2135088f

front1068像素、inclined872像素变化，区域外差异0；top完全不变。当前验证为macOS arm64，Linux编译和游戏实测由主线程完成。不同平台复编如出现SHA差异，应核查浮点/字体栅格化，不能跳过区域外exact测试。

sources/NOTICE和vendor许可证必须随公开源码保留；自主RGBA也应保留来源说明。本包没有生成或改动运行时真实编译验收记录。
