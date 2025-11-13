# mock_scanner.py (V1.6)
import time
from scanner_interface import IAxisVoltageScanner # 确保这是 V1.6 版本的接口

class MockVoltageScanner(IAxisVoltageScanner):
    """
    电压扫描器的“模拟”版本 (V1.6)。
    
    它实现了 V1.6 接口，用于离线 GUI 开发。
    - 模拟了 connect/disconnect 的延迟。
    - 维护一个 "OFF", "OPEN", "CLOSED" 的三态模式。
    - 如果在 "OFF" 或 "CLOSED" 模式下调用 set_voltage，
      它会像真实硬件一样抛出异常。
    """
    def __init__(self, dev_no: int, axis_to_scan: int):
        self.dev_no = dev_no
        self.axis_to_scan = axis_to_scan
        
        # 内部状态
        self.is_connected = False
        self.voltage = 0.0
        # [V1.6 关键] 模拟硬件的默认启动状态 (OFF / GND)
        self.mode = "OFF" 
        
        print(f"[MOCK] 模拟扫描器已为设备 {dev_no} / 轴 {axis_to_scan} 初始化。")

    def connect(self):
        """
        [V1.6 MOCK]
        模拟连接到盒子，不改变轴状态。
        """
        print(f"[MOCK] 正在连接到设备 {self.dev_no}...")
        time.sleep(0.5) # 模拟硬件连接延迟
        
        self.is_connected = True
        self.voltage = 0.0
        # 模拟连接后的默认状态 (OFF / GND)
        self.mode = "OFF"
        
        print(f"[MOCK] 设备 {self.dev_no} 连接成功。")

    def disconnect(self):
        """安全断开与模拟器的连接。"""
        if not self.is_connected:
            return
            
        print(f"[MOCK] 正在断开与设备 {self.dev_no} 的连接...")
        time.sleep(0.1) # 模拟断开延迟
        
        self.is_connected = False
        self.voltage = 0.0
        self.mode = "OFF"
        print("[MOCK] 已断开。")

    def set_axis_mode(self, mode: str):
        """
        [V1.6 MOCK]
        模拟设置目标轴的逻辑模式。
        """
        if not self.is_connected:
            raise Exception("[MOCK] 错误: 尚未连接 (handle 为空)。")
            
        if mode not in ["OFF", "OPEN", "CLOSED"]:
             raise ValueError(f"[MOCK] 未知的轴模式: {mode}")

        print(f"[MOCK] 正在将轴 {self.axis_to_scan} 模式设为: {mode}")
        self.mode = mode
        
        if self.mode == "CLOSED" or self.mode == "OFF":
             # 如果切换回闭环或关闭，模拟器将电压重置 (模仿真实硬件的行为)
             self.voltage = 0.0

    def set_voltage(self, voltage: float):
        """
        [V1.6 MOCK]
        在目标轴上设置直流电压。
        """
        if not self.is_connected:
            raise Exception("[MOCK] 错误: 尚未连接 (handle 为空)。")
        
        # --- 关键的模拟逻辑 ---
        if self.mode != "OPEN":
            # 这模拟了 ANC_setDcVoltage 的核心约束
            raise Exception(f"[MOCK] 致命错误: 无法在“{self.mode}”模式下调用 set_voltage！\n"
                            f"必须首先设置为“OPEN”模式。")
        # ------------------------
            
        # (为防止打印过多信息，在模拟器中也注释掉)
        # print(f"[MOCK] 轴 {self.axis_to_scan}: 电压设为 {voltage:.3f} V")
        self.voltage = voltage

    def get_voltage(self) -> float:
        """读回目标轴的当前模拟直流电压。"""
        if not self.is_connected:
            raise Exception("[MOCK] 错误: 尚未连接 (handle 为空)。")
        
        return self.voltage

    def get_axis_status(self) -> dict:
        """
        [V1.6 MOCK]
        获取当前轴的模拟物理状态。
        """
        if not self.is_connected:
            raise Exception("[MOCK] 错误: 尚未连接 (handle 为空)。")

        # 模拟 get_axis_status 的返回
        # "output_on" 模拟 ANC_getAxisStatus 的 "enabled" 标志
        output_on_status = (self.mode == "OPEN" or self.mode == "CLOSED")
        
        return {
            "physically_connected": True,      # 假设模拟的轴总是物理连接的
            "output_on": output_on_status,   # 报告轴输出是否激活
            "error_detected": False          # 假设模拟的轴没有错误
        }