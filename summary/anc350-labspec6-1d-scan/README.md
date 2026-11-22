# ANC350 与 LabSpec6 一维光谱扫描

这是一个 Windows 桌面 GUI，用 Attocube ANC350 改变压电驱动电压，并通过 TCP 控制 Horiba LabSpec6。每个电压点等待设定的稳定时间后采集一条一维光谱（例如 PL），记录波长和强度，并逐点保存。

**当前版本只支持开环电压扫描（V）。** 界面里的 `CLOSED / Servo` 可以开启反馈，但扫描程序尚未实现设定目标位置、确认到位和读回实际位置。因此，数据文件和热图的扫描坐标都是电压。

## 安装

本项目在 Windows 64 位、Python 3.12 和 Tk 8.6 下做过模拟验证。从项目目录安装依赖。

```powershell
python -m pip install -r requirements.txt
```

GUI 依赖 Python 自带的 `tkinter`。`ttkthemes` 是可选主题依赖，未安装时会使用标准 Tk 界面。

## 用模拟设备试跑

1. 在 `main_app.py` 顶部将 `USE_MOCK` 改为 `True`，从项目目录运行 `python main_app.py`。
2. 点击 **连接 (Connect)** 和 **连接光谱仪**，选择 **开环 (OPEN / Scan)**。
3. 输入起止电压、点数和稳定时间，再设置积分时间、平均次数及保存路径。可以用 `0` 到 `2 V`、`3` 个点做模拟试跑。
4. 点击 **开始扫描**。也可以用 **采集单帧 (Acquire)** 查看单条模拟光谱。

## 连接真机

1. 安装 Attocube ANC350 驱动，确保 DLL 与 Python 位数一致。把 `anc350v4.dll` 及驱动所需的 `libusb0.dll` 放在 `main_app.py` 同目录，并从该目录启动程序。
2. 打开 LabSpec6，确认其 AFM Server 在本机监听 TCP `1234`。当前代码连接 `localhost:1234`。
3. 确认 `main_app.py` 中的 `USE_MOCK = False`，运行 `python main_app.py`。选择对应的 ANC350 轴，连接位移台和光谱仪，然后选择 **开环 (OPEN / Scan)**。
4. 按实验条件设置电压和采集参数。可以先在空闲状态采一帧确认光谱读回，再开始逐点扫描。

## 输出文件

- **单点光谱**保存在每次扫描的子目录中，文件名形如 `Step001_V0.0000_HH-MM-SS.txt`。文件头记录扫描电压、积分时间和实验备注，数据列为 `Wavelength` 和 `Intensity`。
- **汇总矩阵**保存在所选输出目录中，文件名形如 `<前缀>_2DMapMatrix_<时间戳>.txt`。首行保存波长轴，后续每行保存一个电压点和该点的光谱强度。GUI 的二维热图由这些一维光谱拼成。

## 源码结构

| 模块 | 文件 |
| --- | --- |
| 主界面与控制面板 | `main_app.py`、`gui_plugins/anc350_widget.py`、`gui_plugins/spectrometer_widget.py` |
| 逐点扫描和保存 | `scan_engine.py` |
| ANC350 驱动 | `scanner_interface.py`、`real_scanner.py`、`mock_scanner.py` |
| LabSpec6 采谱 | `i_spectrometer.py`、`labspec6_debug_FULL.py`、`real_spectrometer.py`、`mock_spectrometer.py` |

## 第三方代码

`labspec6_debug_FULL.py` 基于 PyMoDAQ Horiba 插件的 LabSpec6 TCP 客户端。原版权及许可随目录附上。 [PyMoDAQ Horiba 上游](https://github.com/PyMoDAQ/pymodaq_plugins_horiba) · [上游 MIT 许可](LICENSES/PyMoDAQ-Horiba-MIT.txt)
