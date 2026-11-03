# Steam Deck 六轴输入来源

当前故障证据：最终Steam入口日志识别“Steam Deck 控制器”，但`SDL_GamepadHasSensor`返回不可用，明确输出`no gyro aiming`。这是当前虚拟手柄的能力边界，不能据SDL虚拟设备缺失推断物理IMU不存在。

现场只读核验：Steam保持运行，`/dev/hidraw3`两秒内501个有效64字节状态报告，序号连续；没有发送HID feature report，没有读取或注入按键映射。设备从sysfs核验为USB Valve 28de:1205，已有deck用户ACL允许读取，无新增权限。

协议和单位的主要来源是本机现存SDL3 3.2.30源码，亦与对应公开版本核对：

- [SDL 3.2.30 Steam Deck backend](https://github.com/libsdl-org/SDL/blob/release-3.2.30/src/joystick/hidapi/SDL_hidapi_steamdeck.c)
- [SDL Steam IMU mode implementation](https://github.com/libsdl-org/SDL/blob/release-3.2.30/src/joystick/hidapi/SDL_hidapi_steam.c)
- [Valve controller report structures](https://github.com/libsdl-org/SDL/blob/release-3.2.30/src/joystick/hidapi/steam/controller_structs.h)

SDL驱动原始来源为Max Maisel，版权与zlib许可仍在上游原文件中；本目录独立实现仅使用公开报文格式与量纲，没有复制其会改变控制器配置的初始化/看门狗代码。

输入必须恰好64字节，header为小端版本1、类型9、长度64。packet序号位于偏移4，加速度三轴从偏移24起、角速度三轴从偏移30起，均为小端有符号16位。先按SDL约定转换，再合成现有UltraTears的SDL→Switch旋转，结果为：加速度`-raw * 2 / 32768` G，角速度`raw * 2000 / 32768 * π / 180` rad/s。坐标最终与既有motion_fusion接口一致，未替换融合或游戏HID ABI。

只在选中Steam Deck手柄、SDL未提供传感器时启动后备传感器读取。外部有传感器的手柄继续走SDL；按键/摇杆仍完全来自Steam虚拟手柄，避免双重按钮输入。C读取器只使用O_RDONLY，不发feature report，不抓取输入、不清除lizard模式、不修改udev或Steam全局设置。后续正常入口回归发现Steam将IMU_MODE(0x30)置零，报告仍250Hz但六轴字段全零；因此独立会话父进程按SDL的SETTING_IMU_MODE协议查询旧值，仅租用0x18原始数据位，退出恢复仍由自己持有的值。模式查询/写入与恢复均有读回，传感器解码器拒绝零重力报告。早先游戏外有效采样不代表运行期可用。源断开即停止更新，既有融合在200ms后不再提供旧状态。

本机物理样本和离线解码单测只能证明设备链路与量纲；实体方向、游戏瞄准、神庙操作和长时恢复仍需实机手测。不得把合成样本或静止采样当成机械操作验收。
