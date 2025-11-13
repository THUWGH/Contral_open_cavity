# real_scanner.py
import ctypes
from scanner_interface import IAxisVoltageScanner

# --- 从 anc350res.h 和 ancdecl.h 导入关键定义 ---
#
ANC_Handle = ctypes.c_void_p
Uit32 = ctypes.c_uint32
Int32 = ctypes.c_int32
Bln32 = ctypes.c_int32 # Bln32 是一个 32位布尔值
c_double = ctypes.c_double

# --- [已修正] 完整定义了所有用到的返回值 ---
ANC_Ok = 0
ANC_Error = -1
ANC_Timeout = 1
ANC_NotConnected = 2
ANC_DriverError = 3         # 新增
ANC_DeviceLocked = 7
ANC_Unknown = 8             # 新增
ANC_NoDevice = 9
ANC_NoAxis = 10
ANC_OutOfRange = 11
ANC_NotAvailable = 12       # 新增
ANC_FileError = 13          # 新增
# ---------------------------------------------

# 布尔常量
ON = 1
OFF = 0
# --------------------------------------------------

class RealVoltageScanner(IAxisVoltageScanner):
    """
    电压扫描器的“真实”版本。
    它使用 ctypes 加载 anc350res.dll 并与真实硬件通信。
    """
    def __init__(self, dev_no: int, axis_to_scan: int):
        self.dev_no = Uit32(dev_no)
        self.axis_to_scan = Uit32(axis_to_scan)
        self.dll = None
        self.handle = ANC_Handle() # 初始化为空句柄
        print(f"[REAL] 真实扫描器已为设备 {dev_no} / 轴 {axis_to_scan} 初始化。")

    def _define_prototypes(self):
        """定义所有 C 函数的原型 (参数类型和返回类型)"""
        
        self.dll.ANC_discover.argtypes = [Uit32, ctypes.POINTER(Uit32)]
        self.dll.ANC_discover.restype = Int32

        self.dll.ANC_connect.argtypes = [Uit32, ctypes.POINTER(ANC_Handle)]
        self.dll.ANC_connect.restype = Int32

        self.dll.ANC_disconnect.argtypes = [ANC_Handle]
        self.dll.ANC_disconnect.restype = Int32

        self.dll.ANC_startAutoMove.argtypes = [ANC_Handle, Uit32, Bln32, Bln32]
        self.dll.ANC_startAutoMove.restype = Int32

        self.dll.ANC_setDcVoltage.argtypes = [ANC_Handle, Uit32, c_double]
        self.dll.ANC_setDcVoltage.restype = Int32

        self.dll.ANC_getDcVoltage.argtypes = [ANC_Handle, Uit32, ctypes.POINTER(c_double)]
        self.dll.ANC_getDcVoltage.restype = Int32
        
        # --- [新增] 为物理连接检查添加原型 ---
        self.dll.ANC_getAxisStatus.argtypes = [
            ANC_Handle, Uit32, 
            ctypes.POINTER(Bln32), # connected
            ctypes.POINTER(Bln32), # enabled
            ctypes.POINTER(Bln32), # moving
            ctypes.POINTER(Bln32), # target
            ctypes.POINTER(Bln32), # eotFwd
            ctypes.POINTER(Bln32), # eotBwd
            ctypes.POINTER(Bln32)  # error
        ]
        self.dll.ANC_getAxisStatus.restype = Int32
        # ------------------------------------

    def _check_error(self, error_code: int, operation: str):
        """内部辅助函数，用于检查所有 DLL 调用的返回码"""
        if error_code == ANC_Ok:
            return # 成功
        
        # --- [已修正] 扩充了错误映射表 ---
        error_map = {
            ANC_Error: "Unspecified error",
            ANC_Timeout: "Timeout",
            ANC_NotConnected: "Not connected",
            ANC_DriverError: "Driver error (anc350res.dll problem?)",
            ANC_DeviceLocked: "Device is locked (被 DAISY 或其他软件占用?)",
            ANC_NoDevice: "No device found (未找到设备)",
            ANC_NoAxis: "Invalid axis number (轴号错误)",
            ANC_OutOfRange: "Parameter out of range (电压超出范围?)",
            ANC_NotAvailable: "Function not available (功能对该设备不可用)",
            ANC_FileError: "File error (e.g., LUT file)",
            ANC_Unknown: "Unknown error"
        }
        # ---------------------------------
        
        message = error_map.get(error_code, f"Unknown error code {error_code}")
        raise Exception(f"[REAL] {operation} 失败: {message} (Code: {error_code})")

    def connect(self):
        print("[REAL] 正在加载 anc350res.dll...")
        try:
            # 假设 dll 在系统路径或程序工作目录中
            self.dll = ctypes.windll.LoadLibrary("anc350v4.dll") 
        except Exception as e:
            print(f"[REAL] 致命错误: 无法加载 anc350v4.dll。请检查驱动和文件路径。")
            raise e
        
        # 定义所有函数原型
        self._define_prototypes()
        
        dev_count = Uit32(0)
        # 接口类型: 0x01 = USB, 0x02 = TCP, 0x03 = All
        # 我们使用 0x03 来同时搜索 USB 和 以太网
        if_all = 0x03 
        err = self.dll.ANC_discover(if_all, ctypes.byref(dev_count))
        self._check_error(err, "ANC_discover")
        
        if dev_count.value == 0:
            raise Exception(f"[REAL] ANC_discover 成功，但未找到设备 (USB或以太网均未找到)。")
        if self.dev_no.value >= dev_count.value:
            raise Exception(f"[REAL] 错误: 目标设备号 {self.dev_no.value} 超出范围 (总共只找到 {dev_count.value} 个设备)。")
            
        print(f"[REAL] 找到 {dev_count.value} 个设备。正在连接到设备 {self.dev_no.value}...")
        err = self.dll.ANC_connect(self.dev_no, ctypes.byref(self.handle))
        self._check_error(err, "ANC_connect")
        
        print(f"[REAL] 连接成功。正在将轴 {self.axis_to_scan.value} 设置为开环电压模式 (关闭反馈)...")
        #
        # 这是关键步骤：关闭反馈，以满足 setDcVoltage 的前提条件
        # (参考 ANC_setDcVoltage 文档)
        err = self.dll.ANC_startAutoMove(self.handle, self.axis_to_scan, OFF, OFF)
        self._check_error(err, "ANC_startAutoMove(OFF)")
        
        # --- [新增] 检查物理轴的连接状态 ---
        print(f"[REAL] 正在检查轴 {self.axis_to_scan.value} 的物理连接状态...")
        axis_connected = Bln32(0)
        axis_error = Bln32(0)
        
        err = self.dll.ANC_getAxisStatus(
            self.handle, self.axis_to_scan, 
            ctypes.byref(axis_connected),  # (Bln32 *connected)
            None,                          # (Bln32 *enabled)
            None,                          # (Bln32 *moving)
            None,                          # (Bln32 *target)
            None,                          # (Bln32 *eotFwd)
            None,                          # (Bln32 *eotBwd)
            ctypes.byref(axis_error)       # (Bln32 *error)
        )
        self._check_error(err, "ANC_getAxisStatus (物理连接检查)")

        if axis_error.value != 0:
             print(f"[REAL] 警告: 轴 {self.axis_to_scan.value} 报告了一个错误状态 (Error=1)。")
             # (可以考虑在此处 raise Exception)

        if axis_connected.value == 0:
            # 这不一定是致命错误（也许开环扫描不需要传感器？），但必须警告
            print(f"[REAL] 警告: 轴 {self.axis_to_scan.value} 未检测到传感器/物理连接 (Status 'connected' = 0)。")
            # (可以考虑在此处 raise Exception)
        else:
            print(f"[REAL] 轴 {self.axis_to_scan.value} 物理连接已确认 (Status 'connected' = 1)。准备就绪。")
        # ------------------------------------

    def disconnect(self):
        if self.dll and self.handle.value: # 检查句柄是否有效 (非空指针)
            print(f"[REAL] 正在将轴 {self.axis_to_scan.value} 电压清零...")
            try:
                # 在断开连接时，set_voltage 可能会失败（例如硬件已拔出）
                # 我们尝试清零，但即使失败，也应继续尝试 disconnect
                self.set_voltage(0.0) 
            except Exception as e:
                print(f"[REAL] 断开时清零电压失败: {e}。将继续尝试断开连接...")
            
            print(f"[REAL] 正在断开与设备 {self.dev_no.value} 的连接...")
            err = self.dll.ANC_disconnect(self.handle)
            # 在 disconnect 期间也检查错误，但不要抛出异常，以免掩盖原始错误
            if err != ANC_Ok:
                 print(f"[REAL] ANC_disconnect 报告了一个错误 (Code: {err})。")
            
            self.handle.value = None # 清除句柄
            print("[REAL] 已断开。")
        else:
            print("[REAL] disconnect 被调用，但无需操作 (未连接或句柄为空)。")

    def set_voltage(self, voltage: float):
        if not self.handle.value:
            raise Exception("[REAL] 错误: 尚未连接 (handle 为空)。")
            
        err = self.dll.ANC_setDcVoltage(self.handle, self.axis_to_scan, c_double(voltage))
        self._check_error(err, f"ANC_setDcVoltage({voltage})")
        # (可选：运行时打印太频繁，已注释掉)
        # print(f"[REAL] 轴 {self.axis_to_scan.value}: 电压设为 {voltage:.3f} V") 

    def get_voltage(self) -> float:
        if not self.handle.value:
            raise Exception("[REAL] 错误: 尚未连接 (handle 为空)。")
        
        voltage_ptr = c_double(0.0)
        err = self.dll.ANC_getDcVoltage(self.handle, self.axis_to_scan, ctypes.byref(voltage_ptr))
        self._check_error(err, "ANC_getDcVoltage")
        
        return voltage_ptr.value