# ANC350 直流电压扫描控制器 (V1.9)

## 1. 项目概览

本项目是一个使用 Python 和 Tkinter 开发的图形用户界面 (GUI) 应用程序，用于控制 attocube ANC350 位移台控制器。

其核心功能是**在特定轴上执行直流电压扫描**。

此 V1.9 版本包含以下关键功能：
* **连接管理：** 手动连接和断开硬件。
* **轴选择：** 支持在连接时选择要控制的目标轴 (0, 1, 或 2)。
* **三态模式控制：** 精确控制轴的三种逻辑状态："轴关闭 (OFF/GND)"、"开环 (OPEN)" 和 "闭环 (CLOSED)"。
* **电压扫描：** 仅在安全的 "开环" 模式下执行多点电压扫描。
* **高级扫描控制：**
    * **暂停/继续：** 随时中断和恢复扫描。
    * **终止：** 安全停止扫描。
    * **单步调试：** 在暂停状态下，可以逐点执行 "上一个点" 或 "下一个点"，并实时显示当前点和电压。

## 2. 核心架构：面向接口编程

为了实现安全、可测试的开发，本项目采用了基于“接口”的抽象架构。

* **`scanner_interface.py` (合同)**
    这是一个抽象基类 (ABC)，它定义了一个控制器**必须**提供哪些功能（如 `connect`, `disconnect`, `set_axis_mode` 等），但不关心这些功能是如何实现的。

* **`real_scanner.py` (真实控制器)**
    实现 `IAxisVoltageScanner` 接口，用于**现场部署**。它使用 `ctypes` 库加载 `anc350v4.dll` 并调用 C 函数来控制真实硬件。

* **`mock_scanner.py` (模拟控制器)**
    同样实现 `IAxisVoltageScanner` 接口，用于**离线开发和测试**。它不调用任何 DLL，而是通过 `print` 和 `time.sleep` 来模拟硬件行为，甚至包括模拟错误（例如，在“闭环”模式下尝试设置电压）。

* **`main_app.py` (GUI 应用)**
    GUI 程序。它**只依赖 `scanner_interface.py`**。它不知道也不关心幕后是 `real_scanner` 还是 `mock_scanner` 在工作。

    通过修改 `main_app.py` 顶部的 `USE_MOCK` 标志，可以在“模拟器”和“真实硬件”之间无缝切换。

## 3. 文件详解

### `main_app.py` (V1.9)

这是项目的主入口点和图形界面。

* **`ScanningApp` 类：**
    * **`_create_widgets()`**：初始化所有 GUI 元素，包括连接按钮、轴选择下拉菜单、三态模式单选按钮、参数输入框和扫描控制按钮。
    * **`on_connect_toggle()`**：连接/断开按钮的回调。它会启动一个**子线程** (`connect_thread` 或 `disconnect_thread`) 来执行耗时的硬件操作，防止 GUI 冻结。
    * **`on_set_mode()`**：模式单选按钮的回调。启动 `toggle_mode_thread` 子线程来切换硬件的 "OFF", "OPEN", "CLOSED" 状态。
    * **`on_start_scan()`**：开始扫描按钮的回调。
        * **安全检查：** 验证当前模式是否为 "OPEN"。如果不是，则弹窗报错，拒绝扫描。
        * **启动扫描：** 初始化扫描参数并启动 `start_scan_thread` 子线程。
    * **`on_pause_toggle()`**：暂停/继续按钮。它通过设置 `self.is_paused` 标志来控制扫描线程的执行。
    * **`on_prev_point()` / `on_next_point()`**：
        * **原子化设计：** 仅在 `is_paused` 状态下可用。
        * **防双击：** 使用 `self.single_step_running` 锁来防止用户在单步执行完成前连续点击。
        * **通信：** 通过 `self.step_direction` 变量告诉扫描线程要移动的方向（-1 或 1），然后使用 `self.run_one_step.set()` 唤醒它。
    * **`periodic_queue_check()`**：GUI 主线程的轮询函数。它周期性地检查 `self.gui_queue`，并安全地将子线程发来的信息（状态更新、绘图数据、错误）应用到 GUI 控件上。
    * **`start_scan_thread()` (子线程)：**
        * **V1.9 核心逻辑：** 使用 `while self.current_scan_index < num_points` 循环。
        * **忙等待：** 当 `self.is_paused` 为 `True` 时，线程会进入一个内部循环 (`while not self.run_one_step.is_set(): ...`)，并向 GUI 发送 `single_step_ready` 消息（包含当前点和电压）。它在此处“清醒地”等待，直到被 `on_pause_toggle` (继续)、`on_prev_point` 或 `on_next_point` 唤醒。
        * **状态机：** 线程被唤醒后，会检查 `self.step_direction` 来决定是自动前进（0）、下一步（1）还是上一步（-1），从而安全地更新 `self.current_scan_index`，避免了 V1.7 的竞态条件。
    * **`connect_thread()` / `disconnect_thread()` / `toggle_mode_thread()` (子线程)：**
        * 封装了对 `self.scanner` 的耗时调用，并通过 `gui_queue` 将结果（成功或失败）返回给主线程。

### `scanner_interface.py` (V1.6+)

定义了 `IAxisVoltageScanner` 抽象类，要求所有子类必须实现以下方法：

* `connect()`
* `disconnect()`
* `set_axis_mode(mode: str)`：V1.6 新增，用于设置 "OFF", "OPEN", "CLOSED"。
* `set_voltage(voltage: float)`
* `get_voltage() -> float`
* `get_axis_status() -> dict`：V1.6 新增，用于检查物理连接和逻辑状态。

### `real_scanner.py` (V1.6+)

`ctypes` 硬件控制器。

* **`_define_prototypes()`**：定义所有需要调用的 C 函数原型（来自 `anc350v4.dll`），包括 `ANC_connect`、`ANC_setAxisOutput`、`ANC_startAutoMove`、`ANC_setDcVoltage` 和 `ANC_getAxisStatus`。
* **`_check_error()`**：在每次 DLL 调用后检查返回码，如果不是 `ANC_Ok`，则抛出一个带详细错误信息的 Python 异常。
* **`connect()`**：只调用 `ANC_discover` 和 `ANC_connect`，**不再**自动设置轴模式。
* **`get_axis_status()`**：调用 `ANC_getAxisStatus`。根据 C 库文档，它返回的 `enabled` 标志对应“轴输出是否打开”，因此字典返回 `{ "physically_connected": ..., "output_on": ... }`。
* **`set_axis_mode(mode: str)`**：**V1.6 的核心逻辑**。
    * `mode == "OFF"`：调用 `ANC_startAutoMove(OFF)` + `ANC_setAxisOutput(OFF)` (接地)。
    * `mode == "OPEN"`：调用 `ANC_startAutoMove(OFF)` + `ANC_setAxisOutput(ON)` (开环，可扫描)。
    * `mode == "CLOSED"`：调用 `ANC_setAxisOutput(ON)` + `ANC_startAutoMove(ON)` (闭环)。
* **`set_voltage()`**：调用 `ANC_setDcVoltage`。如果硬件模式不是 "OPEN"，此调用将失败（被 `_check_error` 捕获）。

### `mock_scanner.py` (V1.6+)

离线模拟器。

* **`__init__()`**：初始化一个内部状态机，`self.mode = "OFF"`。
* **`set_axis_mode(mode: str)`**：修改内部的 `self.mode` 状态。
* **`set_voltage()`**：**关键的模拟逻辑**。它会检查 `self.mode`。如果 `self.mode != "OPEN"`，它会主动抛出一个异常，模仿真实硬件的行为，这对于测试 GUI 的错误处理至关重要。
* **`get_axis_status()`**：根据 `self.mode` 模拟 `output_on` 标志。

## 4. 环境与依赖

### Python 库
* `numpy` (用于 `linspace`)
* `matplotlib` (用于绘图)
* `ttkthemes` (可选，用于 "arc" GUI 风格)

### 硬件与二进制文件
* ANC350 控制器
* `anc350v4.dll` (主库)
* `libusb0.dll` (`anc350v4.dll` 的 USB 依赖库)

## 5. 如何运行

### A. 离线开发 (MOCK 模式)

1.  确保已安装 `numpy`, `matplotlib`, `ttkthemes`。
2.  打开 `main_app.py`。
3.  设置 `USE_MOCK = True`。
4.  运行 `python main_app.py`。
5.  程序将使用 `mock_scanner.py` 运行，您可以安全地测试所有 GUI 功能（包括错误处理）。

### B. 在线部署 (REAL 模式)

1.  在实验电脑上安装 ANC350 硬件驱动程序（如手册所示）。
2.  将 `main_app.py`, `scanner_interface.py`, `real_scanner.py`, `mock_scanner.py` 放在同一文件夹。
3.  **将 `anc350v4.dll` 和 `libusb0.dll` 复制到上述文件夹中。**
4.  打开 `main_app.py`。
5.  设置 `USE_MOCK = False`。
6.  运行 `python main_app.py`。

## 6. 打包为 .EXE

您可以使用 PyInstaller 将程序打包为单个可执行文件。

### 选项 1：手动复制 DLL (推荐)

1.  运行打包命令：
    ```bash
    pyinstaller --onefile --windowed main_app.py
    ```
2.  打包完成后，进入 `dist` 文件夹。
3.  将 `anc350v4.dll` 和 `libusb0.dll` **手动复制**到 `dist` 文件夹中，与生成的 `main_app.exe` 放在一起。
4.  将整个 `dist` 文件夹分发给实验电脑。

### 选项 2：捆绑 DLL

(此方法更整洁，但如果 DLL 依赖复杂，有时会失败)

```bash
pyinstaller --onefile --windowed --add-binary "anc350v4.dll;." --add-binary "libusb0.dll;." main_app.py