# real_scanner.py (V1.6)
import ctypes
from scanner_interface import IAxisVoltageScanner

# (省略了顶部的常量定义, 与 V1.5 相同)
# --- 从 anc350res.h 和 ancdecl.h 导入关键定义 ---
ANC_Handle = ctypes.c_void_p
Uit32 = ctypes.c_uint32
Int32 = ctypes.c_int32
Bln32 = ctypes.c_int32 
c_double = ctypes.c_double
ANC_Ok = 0
ANC_Error = -1
ANC_Timeout = 1
ANC_NotConnected = 2
ANC_DriverError = 3
ANC_DeviceLocked = 7
ANC_Unknown = 8
ANC_NoDevice = 9
ANC_NoAxis = 10
ANC_OutOfRange = 11
ANC_NotAvailable = 12
ANC_FileError = 13
ON = 1
OFF = 0
# --------------------------------------------------


class RealVoltageScanner(IAxisVoltageScanner):
    """
    [V1.6 修改]
    - 实现了 set_axis_mode() 来正确控制三个逻辑状态
      (OFF, OPEN, CLOSED)。
    - get_axis_status() 返回 'output_on' 状态。
    """
    def __init__(self, dev_no: int, axis_to_scan: int):
        self.dev_no = Uit32(dev_no)
        self.axis_to_scan = Uit32(axis_to_scan)
        self.dll = None
        self.handle = ANC_Handle() 
        print(f"[REAL] 真实扫描器已为设备 {dev_no} / 轴 {axis_to_scan} 初始化。")

    def _define_prototypes(self):
        """定义所有 C 函数的原型 (参数类型和返回类型)"""
        
        # (V1.5 中已定义: ANC_discover, ANC_connect, ANC_disconnect)
        self.dll.ANC_discover.argtypes = [Uit32, ctypes.POINTER(Uit32)]
        self.dll.ANC_discover.restype = Int32
        self.dll.ANC_connect.argtypes = [Uit32, ctypes.POINTER(ANC_Handle)]
        self.dll.ANC_connect.restype = Int32
        self.dll.ANC_disconnect.argtypes = [ANC_Handle]
        self.dll.ANC_disconnect.restype = Int32

        # (V1.5 中已定义: ANC_startAutoMove - 反馈/闭环)
        self.dll.ANC_startAutoMove.argtypes = [ANC_Handle, Uit32, Bln32, Bln32]
        self.dll.ANC_startAutoMove.restype = Int32
        
        # --- [V1.6 关键] 轴输出 (GND/ON) ---
        self.dll.ANC_setAxisOutput.argtypes = [ANC_Handle, Uit32, Bln32, Bln32]
        self.dll.ANC_setAxisOutput.restype = Int32
        # ------------------------------------

        # (V1.5 中已定义: ANC_setDcVoltage, ANC_getDcVoltage)
        self.dll.ANC_setDcVoltage.argtypes = [ANC_Handle, Uit32, c_double]
        self.dll.ANC_setDcVoltage.restype = Int32
        self.dll.ANC_getDcVoltage.argtypes = [ANC_Handle, Uit32, ctypes.POINTER(c_double)]
        self.dll.ANC_getDcVoltage.restype = Int32
        
        # (V1.5 中已定义: ANC_getAxisStatus)
        self.dll.ANC_getAxisStatus.argtypes = [
            ANC_Handle, Uit32, 
            ctypes.POINTER(Bln32), # connected
            ctypes.POINTER(Bln32), # enabled (This is Output ON/OFF)
            ctypes.POINTER(Bln32), # moving
            ctypes.POINTER(Bln32), # target
            ctypes.POINTER(Bln32), # eotFwd
            ctypes.POINTER(Bln32), # eotBwd
            ctypes.POINTER(Bln32)  # error
        ]
        self.dll.ANC_getAxisStatus.restype = Int32

    def _check_error(self, error_code: int, operation: str):
        """(V1.5 代码, 无变化) 内部辅助函数"""
        if error_code == ANC_Ok:
            return # 成功
        
        error_map = {
            ANC_Error: "Unspecified error",
            ANC_Timeout: "Timeout",
            ANC_NotConnected: "Not connected",
            ANC_DriverError: "Driver error (anc350v4.dll/libusb0.dll problem?)",
            ANC_DeviceLocked: "Device is locked (被 DAISY 或其他软件占用?)",
            ANC_NoDevice: "No device found (未找到设备)",
            ANC_NoAxis: "Invalid axis number (轴号错误)",
            ANC_OutOfRange: "Parameter out of range (电压超出范围?)",
            ANC_NotAvailable: "Function not available (功能对该设备不可用)",
            ANC_FileError: "File error (e.g., LUT file)",
            ANC_Unknown: "Unknown error"
        }
        message = error_map.get(error_code, f"Unknown error code {error_code}")
        raise Exception(f"[REAL] {operation} 失败: {message} (Code: {error_code})")

    def connect(self):
        """(V1.5 代码, 无变化) 只连接到硬件"盒子"。"""
        print("[REAL] 正在加载 anc350v4.dll...")
        try:
            self.dll = ctypes.windll.LoadLibrary("anc350v4.dll") 
        except Exception as e:
            print(f"[REAL] 致命错误: 无法加载 anc350v4.dll。请检查驱动和文件路径。")
            raise e
        
        self._define_prototypes()
        
        dev_count = Uit32(0)
        if_all = 0x03 # 搜索 USB 和 TCP
        err = self.dll.ANC_discover(if_all, ctypes.byref(dev_count))
        self._check_error(err, "ANC_discover")
        
        if dev_count.value == 0:
            raise Exception(f"[REAL] ANC_discover 成功，但未找到设备 (USB或以太网均未找到)。")
        if self.dev_no.value >= dev_count.value:
            raise Exception(f"[REAL] 错误: 目标设备号 {self.dev_no.value} 超出范围 (总共只找到 {dev_count.value} 个设备)。")
            
        print(f"[REAL] 找到 {dev_count.value} 个设备。正在连接到设备 {self.dev_no.value}...")
        err = self.dll.ANC_connect(self.dev_no, ctypes.byref(self.handle))
        self._check_error(err, "ANC_connect (连接硬件盒子)")
        
        print(f"[REAL] 硬件连接成功。设备 {self.dev_no.value} 句柄已获取。")

    def disconnect(self):
        """
        [V1.6 修改]
        在断开前，尝试将轴安全地设为 OFF (GND) 状态。
        """
        if self.dll and self.handle.value: 
            print(f"[REAL] 正在将轴 {self.axis_to_scan.value} 设为 OFF (GND) 状态...")
            try:
                # 尝试在断开前设置安全状态
                self.set_axis_mode("OFF")
            except Exception as e:
                print(f"[REAL] 断开时设置轴模式失败: {e}。将继续尝试断开连接...")
            
            print(f"[REAL] 正在断开与设备 {self.dev_no.value} 的连接...")
            err = self.dll.ANC_disconnect(self.handle)
            if err != ANC_Ok:
                 print(f"[REAL] ANC_disconnect 报告了一个错误 (Code: {err})。")
            
            self.handle.value = None 
            print("[REAL] 已断开。")
        else:
            print("[REAL] disconnect 被调用，但无需操作 (未连接或句柄为空)。")

    # --- [V1.6 关键] ---
    def set_axis_mode(self, mode: str):
        """
        控制目标轴的逻辑模式。
        """
        if not self.handle.value:
            raise Exception("[REAL] 错误: 尚未连接 (handle 为空)。")
            
        print(f"[REAL] 正在将轴 {self.axis_to_scan.value} 设置为 {mode} 模式...")
        
        if mode == "OFF":
            # 状态 1: 逻辑 OFF (GND)
            # 1. 关闭反馈 (以防万一)
            err = self.dll.ANC_startAutoMove(self.handle, self.axis_to_scan, OFF, OFF)
            self._check_error(err, "set_axis_mode(OFF): ANC_startAutoMove(OFF)")
            # 2. 关闭输出 (设置GND)
            err = self.dll.ANC_setAxisOutput(self.handle, self.axis_to_scan, OFF, OFF)
            self._check_error(err, "set_axis_mode(OFF): ANC_setAxisOutput(OFF)")
            
        elif mode == "OPEN":
            # 状态 2: 开环 (用于扫描)
            # 1. 关闭反馈
            err = self.dll.ANC_startAutoMove(self.handle, self.axis_to_scan, OFF, OFF)
            self._check_error(err, "set_axis_mode(OPEN): ANC_startAutoMove(OFF)")
            # 2. 开启输出
            err = self.dll.ANC_setAxisOutput(self.handle, self.axis_to_scan, ON, OFF)
            self._check_error(err, "set_axis_mode(OPEN): ANC_setAxisOutput(ON)")
            
        elif mode == "CLOSED":
            # 状态 3: 闭环 (用于定位)
            # 1. 开启输出
            err = self.dll.ANC_setAxisOutput(self.handle, self.axis_to_scan, ON, OFF)
            self._check_error(err, "set_axis_mode(CLOSED): ANC_setAxisOutput(ON)")
            # 2. 开启反馈
            err = self.dll.ANC_startAutoMove(self.handle, self.axis_to_scan, ON, OFF)
            self._check_error(err, "set_axis_mode(CLOSED): ANC_startAutoMove(ON)")
            
        else:
            raise ValueError(f"未知的轴模式: {mode}")
        
        print(f"[REAL] 轴 {self.axis_to_scan.value} 模式设置成功。")

    # --- [V1.6 关键] ---
    def get_axis_status(self) -> dict:
        """
        检查所选轴的物理连接和 "Output Enable" 状态。
        """
        if not self.handle.value:
            raise Exception("[REAL] 错误: 尚未连接 (handle 为空)。")

        axis_connected = Bln32(0)
        axis_error = Bln32(0)
        axis_output_on = Bln32(0) # 'enabled' 标志对应 "Voltage Output is Enabled"
        
        err = self.dll.ANC_getAxisStatus(
            self.handle, self.axis_to_scan, 
            ctypes.byref(axis_connected),  # (Bln32 *connected)
            ctypes.byref(axis_output_on),  # (Bln32 *enabled)
            None, None, None, None,        # (忽略 moving, target, eotFwd, eotBwd)
            ctypes.byref(axis_error)       # (Bln32 *error)
        )
        self._check_error(err, "ANC_getAxisStatus (物理连接检查)")
        
        # 返回一个字典，精确反映硬件状态
        return {
            "physically_connected": (axis_connected.value != 0),
            "output_on": (axis_output_on.value != 0), # 这是 "enabled" 标志
            "error_detected": (axis_error.value != 0)
        }

    def set_voltage(self, voltage: float):
        """
        (V1.5 代码, 无变化)
        设置直流电压。
        (警告: 只有在 set_axis_mode("OPEN") 之后才能安全调用)
        """
        if not self.handle.value:
            raise Exception("[REAL] 错误: 尚未连接 (handle 为空)。")
            
        err = self.dll.ANC_setDcVoltage(self.handle, self.axis_to_scan, c_double(voltage))
        # 此时如果模式不是 "OPEN", 硬件将返回 ANC_Error (-1)
        self._check_error(err, f"ANC_setDcVoltage({voltage})")

    def get_voltage(self) -> float:
        """(V1.5 代码, 无变化)"""
        if not self.handle.value:
            raise Exception("[REAL] 错误: 尚未连接 (handle 为空)。")
        
        voltage_ptr = c_double(0.0)
        err = self.dll.ANC_getDcVoltage(self.handle, self.axis_to_scan, ctypes.byref(voltage_ptr))
        self._check_error(err, "ANC_getDcVoltage")
        
        return voltage_ptr.value