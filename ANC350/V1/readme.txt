=========================================================
 ANC350 直流电压扫描控制器 - README.txt
=========================================================

项目概览
------------------
本项目旨在通过 Python 控制 ANC350 位移台控制器，实现对**特定轴的直流电压扫描**功能。

为了实现安全的“离线开发”（在没有连接硬件的情况下开发GUI）和“在线部署”的无缝切换，本项目采用了基于“接口”的抽象架构。

主要文件结构
------------------
您会看到三个核心的 Python 文件：

1.  **`scanner_interface.py`**
    * **用途：** 这是“接口”或“合同”文件。
    * **内容：** 定义了 `IAxisVoltageScanner` 抽象基类。
    * **关键：** 它规定了控制器**必须**提供哪些功能（例如 `connect`, `disconnect`, `set_voltage`），但不关心这些功能是如何实现的。GUI开发者应将此文件视为“功能说明书”。

2.  **`mock_scanner.py`**
    * **用途：** 这是“模拟器”，用于**离线开发**。
    * **内容：** 实现了 `IAxisVoltageScanner` 接口。
    * **行为：** 它不调用任何硬件DLL。当GUI调用 `set_voltage(50.0)` 时，它只会在控制台打印 `[MOCK] 电压设为 50.0 V`。
    * **优势：** 您可以在没有连接ANC350的任何电脑上安全地开发和测试您的GUI全部逻辑。

3.  **`real_scanner.py`**
    * **用途：** 这是“真实控制器”，用于**现场部署**。
    * **内容：** 同样实现了 `IAxisVoltageScanner` 接口。
    * **行为：** 它使用 `ctypes` 库来加载和调用 `anc350res.dll` 文件的C函数。它会真正地向硬件发送命令。
    * **依赖：** 运行此文件**必须** `anc350res.dll` 文件（及其驱动）。


GUI 开发者的核心指南
----------------------------------
您（GUI开发者）的任务是创建一个人机交互界面，您不需要关心 `real_scanner.py` 的复杂性。您的开发流程如下：

### 1. 您的开发环境
在您开发GUI的整个过程中，您**只需要** `scanner_interface.py` 和 `mock_scanner.py` 这两个文件。

### 2. 如何在GUI中使用控制器
您的GUI代码（例如 `main_app.py`）应该这样设计：

```python
# --- 导入接口和模拟器 ---
from scanner_interface import IAxisVoltageScanner
from mock_scanner import MockVoltageScanner
from real_scanner import RealVoltageScanner # 仅在“工厂”中导入

# -----------------------------------------------------------------
# 这是您在开发和部署之间切换的“唯一”开关
USE_MOCK = True  # 开发时设为 True, 部署时设为 False
# -----------------------------------------------------------------

def create_controller(dev_no=0, axis_no=0) -> IAxisVoltageScanner:
    """
    这个“工厂”函数会根据开关，返回一个“符合标准”的控制器。
    GUI代码应该调用这个函数，而不是直接实例化 Mock 或 Real。
    """
    if USE_MOCK:
        print("--- 正在使用 MOCK 模拟控制器 ---")
        return MockVoltageScanner(dev_no, axis_no)
    else:
        print("--- 正在使用 REAL 真实硬件控制器 ---")
        return RealVoltageScanner(dev_no, axis_no)

# --- 您的GUI主窗口（例如 PyQt/Tkinter） ---
class MyMainWindow:
    def __init__(self):
        # 1. 创建控制器实例
        # 注意：self.scanner 的类型是“接口”，而不是某个具体实现
        self.scanner: IAxisVoltageScanner = create_controller(dev_no=0, axis_no=1)
        
        # 2. 连接到硬件（或模拟器）
        try:
            self.scanner.connect()
        except Exception as e:
            print(f"连接失败: {e}")
            # (在这里弹出错误对话框)

    def on_user_clicks_set_voltage_button(self):
        # 3. GUI 调用标准接口
        # 您的GUI代码不需要知道 self.scanner 到底是 MOCK 还是 REAL
        # 它只管调用“合同”上规定的函数。
        try:
            voltage_to_set = 50.5
            self.scanner.set_voltage(voltage_to_set)
            print("设置电压成功")
        except Exception as e:
            print(f"设置电压失败: {e}")
            # (在这里弹出错误对话框)

    def on_window_close(self):
        # 4. 在退出时安全断开
        if self.scanner:
            self.scanner.disconnect()


=========================================================
 GUI (main_app.py) 使用与扩展指南
=========================================================

[cite_start]本文档是 `readme.txt` [cite: 80] 的补充，专注于解释 `main_app.py` 文件的功能、设计思想，
以及如何扩展它以集成新仪器。


项目概览 (GUI)
------------------
`main_app.py` 是这个项目的可执行主程序。它提供了图形用户界面 (GUI)，
用于设置扫描参数（电压范围、点数、稳定时间）并实时监控扫描过程。

核心设计思想：
1.  [cite_start]**界面与逻辑分离 [cite: 58]：** GUI (`main_app.py`) 只负责显示和接收用户输入。它不包含任何硬件驱动（如 `ctypes`）的复杂代码。

2.  [cite_start]**多线程 [cite: 60][cite_start]：** 所有的硬件控制和扫描循环都在一个独立的“子线程”中 (在 `start_scan_thread` 函数中) 运行。这确保了即使用户在扫描期间（例如在 `time.sleep(settle_time)` 等待时），GUI 界面也**绝不会卡死** [cite: 60]，用户可以随时拖动窗口、点击“暂停”或“终止”。

3.  [cite_start]**面向接口编程 [cite: 80][cite_start]：** GUI 不直接与 `real_scanner.py` 对话，而是通过 `scanner_interface.py` 定义的“合同” [cite: 80, 83, 84] [cite_start]来调用功能。`create_controller` 工厂函数 [cite: 81] 负责决定在幕后提供“模拟”控制器还是“真实”控制器。


如何运行
------------------
1.  **安装依赖：**
    pip install numpy matplotlib
    (可选，为了更好的UI) pip install ttkthemes

2.  **选择模式 (最关键的开关)：**
    打开 `main_app.py` 文件，找到顶部的 `USE_MOCK` 变量：
    * [cite_start]`USE_MOCK = True`：  使用 `mock_scanner.py`。无需连接硬件，用于安全地测试GUI布局和逻辑 [cite: 80]。
    * [cite_start]`USE_MOCK = False`： 使用 `real_scanner.py`。这将尝试连接并控制真实的ANC350硬件 [cite: 81, 82]。

3.  **运行主程序：**
    python main_app.py


GUI 功能介绍
------------------
* [cite_start]**参数输入区：** 设置起始/终止电压、点数和稳定时间 [cite: 53]。
* [cite_start]**开始扫描：** 禁用输入框；启动一个**新的子线程**来执行 `start_scan_thread` 函数 [cite: 60]。
* **暂停/继续：**
    * [cite_start]点击“暂停”：GUI主线程会设置一个 `threading.Event` 标志（`self.pause_event.clear()`），这相当于亮起“红灯” [cite: 54, 59]。
    * 子线程在下一次循环开始前会检查此事件，并调用 `self.pause_event.wait()` 自我挂起（暂停），不消耗CPU。
    * 点击“继续”：GUI主线程设置事件（`self.pause_event.set()`），子线程恢复运行。
* **终止扫描：**
    * [cite_start]GUI主线程设置 `self.stop_requested = True` 标志 [cite: 54]。
    * [cite_start]子线程在循环的多个检查点（包括 `time.sleep` 期间）会检查此标志，并安全退出循环 [cite: 64]。
* [cite_start]**状态栏 [cite: 56]：** 实时显示子线程通过“线程安全队列” (Queue) 发回的状态信息（例如 "正在连接...", "点 5/100..."）。
* [cite_start]**绘图区 [cite: 55]：** 实时绘制子线程发回的数据。


=========================================================
 如何扩展：添加新仪器（例如 光谱仪）
=========================================================

[cite_start]本程序的核心价值在于其可扩展性。按照《控制宏观规划指南》[cite: 3][cite_start]和 `readme.txt` [cite: 80] 的架构，
添加一个新仪器（如光谱仪或磁场）的步骤是标准化的，并且不会破坏现有逻辑。

### 步骤 1：定义新仪器的“接口”和“模拟器”
[cite_start](完全复制您为ANC350所做的操作 [cite: 80])

1.  **创建 `spectrometer_interface.py`**
    * 定义一个 `ISpectrometer` 抽象类（继承 `abc.ABC`）。
    * 规定它必须有哪些方法，例如：
        `connect()`, `disconnect()`, `set_integration_time(sec)`, `acquire_data()`

2.  **创建 `mock_spectrometer.py`**
    * 创建一个 `MockSpectrometer` 类，继承 `ISpectrometer`。
    * 实现 `acquire_data()`：让它 `time.sleep(integration_time)` 并返回一个假的 `numpy` 数组（例如一个高斯峰）。

3.  **(可选) 创建 `real_spectrometer.py`**
    * 创建一个 `RealSpectrometer` 类，继承 `ISpectrometer`。
    * [cite_start]在 `acquire_data()` 内部实现PyVISA或ctypes逻辑，包括发送采集命令和**循环等待**仪器完成信号 [cite: 65]。

### 步骤 2：将新仪器集成到 `main_app.py`
您只需要在 `main_app.py` 的几个固定位置添加代码：

**1. 在 GUI 中添加参数 (在 `_create_widgets` 方法中):**
    * 在 `param_list` 中为光谱仪添加入参，例如：
        `("integ_time", "积分时间 (s):", "1.0")`

**2. 在 `create_controller` 附近添加新的工厂函数:**
    * (推荐) 添加一个 `create_spectrometer_controller()` 工厂函数，它同样接受 `USE_MOCK` 标志。

**3. 在 `start_scan_thread` (子线程) 中集成控制逻辑:**
    * **读取参数：** 从 `self.entries` 中读取积分时间。
    * **初始化：** 在 `self.scanner = ...` 下方，添加 `self.spectrometer = create_spectrometer_controller(...)`。
    * **连接：** 在 `self.scanner.connect()` 下方，添加 `self.spectrometer.connect()`。
    * **设置参数：** 在主循环开始前，添加 `self.spectrometer.set_integration_time(integ_time)`。
    * **主循环中 (核心)：** 在 `time.sleep(settle_time)` (稳定等待) 之后，添加：
        
        # --- 光谱仪控制 (未来扩展点) ---
        self.gui_queue.put(("status", f"点 {i+1}/{num_points}: 正在采集光谱..."))
        data = self.spectrometer.acquire_data() # (此方法会自行等待积分完成)
        
        # --- 数据保存 (未来扩展点) ---
        # save_data_to_file(voltage, data) # (您需要实现这个保存函数)

    * [cite_start]**数据绘图：** 修改 `self.gui_queue.put(("plot_data", ...))`，使其传递真实的光谱数据（或其积分）而非电压值。您还需要修改 `_init_plot` 和 `_update_plot` 来绘制光谱 [cite: 55]。
    * **断开连接：** 在 `finally` 块中，`self.scanner.disconnect()` 下方，添加 `self.spectrometer.disconnect()`。

通过遵循此模式，您的 GUI 逻辑 (`main_app.py`) 始终保持清晰，
而仪器的复杂性（例如“等待光谱采集完成”）被完美地封装在
[cite_start]各自的 `Real...Scanner` 或 `Real...Spectrometer` 类中 [cite: 41, 43]。