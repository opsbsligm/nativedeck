# Controller layout patch tool v4

可直接入仓的 Python 3.9+ 公共工具，只有标准库依赖。不包含游戏资源、原件字节、私有输入、凭据、个人路径或机器默认目录。
所有路径显式传参；私有输入、补丁和私有集成测试产物应放到仓外。公共7项锚点单元测试不需要CONTROLLER_PRIVATE_DIR。

本版本使用任意renderer提供的像素锚点，支持不同位置、画布尺寸及可选覆盖轮廓，不再固定投影公式或D-pad位置。
产品约定仍是 `display_art="unified-steamdeck-inclined"`：已知控制器帮助页的六个精确机身纹理名，由外部runtime白名单上传同一份自绘图。
本工具不上传图像，也不宣称未知的其他pane消费者或实机画面已经验收。

## 构造与复核

从仓库根执行。先将CONTROLLER_PRIVATE_DIR设为仓外私有目录（示例不把23个游戏小文件输出到公开树）：

```sh
: "${CONTROLLER_PRIVATE_DIR:?Set CONTROLLER_PRIVATE_DIR to a private directory outside this checkout}"
python3 -B ports/ultratears-linux/controller-layout/build_controller_patch.py \
  --metadata "$CONTROLLER_PRIVATE_DIR/ui-inputs.json" \
  --input-root "$CONTROLLER_PRIVATE_DIR/extracted-ui" \
  --anchors ports/ultratears-linux/controller-art/anchors-inclined.json \
  --output "$CONTROLLER_PRIVATE_DIR/controller-layout-v4"

python3 -B ports/ultratears-linux/controller-layout/verify_controller_patch.py \
  "$CONTROLLER_PRIVATE_DIR/controller-layout-v4" --output-name verification-reread.json
```

同目录保留 `resource_layout.py`、`anchor_contract.py` 和两个构造/验证脚本。
`--input-root` 可省略，使用metadata.root；`--check-only`只读取和求解，不写输出。
输出必须是新目录且在原始资源根之外。输入23个小文件必须与元数据长度/SHA一致；目前仅支持已确认的FLYT/FLAN 9.0结构。
不得使用Python `-O`，以免关闭结构核验断言。

输出包含23个对应小文件、manifest及独立verification。按manifest仅合入changed=true的两项：

- `blyt/PaSystemController_00.bflyt`
- `anim/PaSystemController_00_Pattern.bflan`

动画长度增加，集成方必须按新长度打包并维护所需资源大小表。其他21项是比对副本，BNTX/ASTC/BC4不由本工具生成。
运行时精确白名单仍为 `Controller_{Console,Grip,Pro}{无后缀,1}^w` 六名，在manifest中完整列出。
运行时图像应与anchor画布保持相同归一化坐标；工具按width/height映射到游戏图片pane的完整矩形。

## Renderer anchor API

输入最少包括：

```json
{
  "width": 800,
  "height": 400,
  "view": "renderer-defined",
  "anchors": [
    {"id": "dpad_center", "pixel": [40, 80], "coverage_bounds": [20, 60, 60, 100]}
  ]
}
```

示例仅说明字段，实际构造须提供全部10组所需的13个ID：
`left_trigger/right_trigger/left_bumper/right_bumper/view/menu/left_stick/right_stick/dpad_center/face_south/face_east/face_west/face_north`。
ABXY目标是四个face中心的质心；其他组用对应ID的像素坐标。像素必须有限且位于画布内，ID不可重复。
`view`仅为描述信息，布局位置不依赖固定视角名；`pixel`始终是权威坐标，不要求其等于旧source的某个固定投影结果。

ABXY与十字键窗口覆盖支持以下优先级：

1. 文档级 `group_coverage`：如 `{"CrossKey": [[x,y], ...]}`，绝对像素支持点。
2. 单anchor的 `coverage_points`、`coverage_bounds=[x0,y0,x1,y1]` 或 `coverage_radius`，均为当前renderer的像素单位。
3. 兼容已有schema2：anchor带source且文档带transform.x/y表达式，按源覆盖几何投影；投影后以权威pixel重新对中心。ABXY源半径10外接矩形，十字键源半长19/半厚6的交叉多边形。
4. 无上述轮廓时，使用以pixel为中心的默认外接框，ABXY半径10、十字键半径19。不同尺寸或形状的renderer应提供显式轮廓以保证窗口覆盖其真实图形。

算术投影只支持数字、x/y及 `+ - * /` 和括号，禁止函数调用、属性访问、索引、幂与非有限结果，不使用eval。
自定义复杂投影可直接传入已计算的像素轮廓，不必向本工具提供投影代码。

可导入的API：

```python
from anchor_contract import validate, coverage_points
anchors = validate(document)
outline = coverage_points("CrossKey", anchors, document)
```

构造器与独立验证器分别实现覆盖计算和仿射几何，没有共用求解结果冒充独立验证。

## 改动及验证边界

三套原Pattern×普通/骑马共六状态的10组均对齐同一份renderer锚点。
标签端原点及位置键固定；原水平段旋转/伸缩直连marker，竖段高度置零，保留全部可见性键。
marker补偿父变换以保持朝向，ABXY/十字键窗口覆盖给定轮廓，保留资源自身custom边框的最小空间。
字体文本、OnOff、IsHorse、图片/阴影pane以及其他21文件按字节保留。

静态布局只改30个目标pane的白名单浮点字段。Pattern保留原始pai1字节，追加替换entry和offset表，仅更新必要的大小和指针。
位置曲线保留0、1左、1右、2左、2右边界键。

独立进程重开全部原始/输出23文件，核对manifest哈希/长度、无关字节、白名单字段及实际几何。
检查六状态60组和额外左右重复边界40组，共100项端点/marker检查，阈值0.001 anchor画布像素；标签端阈值0.000001布局单位。
验证只是资源结构/静态几何，不等于实机首次启动或真实画面验收。

## 测试

无需私有资源的公共单元测试：

```sh
python3 -B ports/ultratears-linux/controller-layout/test_anchor_contract.py
```

私有资源集成测试（不会将资源打入工具包）：

```sh
python3 -B ports/ultratears-linux/controller-layout/test_controller_patch.py \
  --metadata "$CONTROLLER_PRIVATE_DIR/ui-inputs.json" \
  --anchors ports/ultratears-linux/controller-art/anchors-inclined.json \
  --reference-patch "$CONTROLLER_PRIVATE_DIR/controller-layout-v4" \
  --work "$CONTROLLER_PRIVATE_DIR/controller-layout-tests-v4"
```

覆盖可重复构造、已有输出拒绝、越界/缺ID/SHA异常拒绝、权威pixel移动、自定义画布且无source的完整构造和独立验证、可执行表达式拒绝、marker偏移及无关OnOff字节篡改。
所有变更发生在新增测试副本中；测试结果、私有metadata、游戏文件和生成补丁都不应进入公共提交。

## 独立教程中的单按钮引线

`PaActionGuide_00` 是另一套消费者；上文基本操作页的100项检查不覆盖它。
`build_action_guide_patch.py` 单独修正 PatternA/B/C 的状态0、3、4、11、14、19、23，
共21个状态：西侧攻击键X、Menu、View和左摇杆。输入需要以下五个私有文件：
`blyt/PaActionGuide_00.bflyt`、`blyt/PaController_00.bflyt`，
以及 `anim/PaActionGuide_00_Pattern{A,B,C}.bflan`。

```sh
python3 -B ports/ultratears-linux/controller-layout/build_action_guide_patch.py \
  --input-root "$CONTROLLER_PRIVATE_DIR/action-guide-originals" \
  --anchors ports/ultratears-linux/controller-art/anchors-inclined.json \
  --output "$CONTROLLER_PRIVATE_DIR/action-guide-patch"
```

输出只有三份新动画和清单。集成时重打包Common并增加资源大小表，不覆盖原输入。
求解器保留每个原引线靠近文字框的端点，移动圆圈并重新计算线段角度、长度与中心位置。
保持原可见性及所有非目标通道的字节，显式保留左右重复帧边界；插值源曲线拒绝处理。
它逐个复算21个目标位置，并在其余状态的整数与四分之一帧核对几何未变。
这是同一工具内的存储几何检查，不是独立运行时证明；`ali1`动态对齐仍需实机画面验收。
组合键、肩键、十字方向、陀螺仪和其他教程尚不在该补丁的验证范围。
