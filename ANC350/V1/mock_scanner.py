# mock_scanner.py
from scanner_interface import IAxisVoltageScanner
import time

class MockVoltageScanner(IAxisVoltageScanner):
    """
    电压扫描器的“模拟”版本。
    它不连接任何真实硬件，只用于 GUI 开发和逻辑测试。
    """
    def __init__(self, dev_no: int, axis_to_scan: int):
        self.dev_no = dev_no
        self.axis_to_scan = axis_to_scan
        self._mock_voltage = 0.0
        print(f"[MOCK] 模拟扫描器已为设备 {dev_no} / 轴 {axis_to_scan} 初始化。")

    def connect(self):
        print(f"[MOCK] 正在连接到设备 {self.dev_no}...")
        time.sleep(0.5) # 模拟连接耗时
        print(f"[MOCK] 连接成功。轴 {self.axis_to_scan} 已设置为开环电压模式。")

    def disconnect(self):
        self.set_voltage(0.0) # 模拟电压清零
        print(f"[MOCK] 已断开与设备 {self.dev_no} 的连接。")

    def set_voltage(self, voltage: float):
        self._mock_voltage = voltage
        print(f"[MOCK] 轴 {self.axis_to_scan}: 直流电压设置为 {voltage:.3f} V")

    def get_voltage(self) -> float:
        print(f"[MOCK] 轴 {self.axis_to_scan}: 正在读取电压... (当前为 {self._mock_voltage:.3f} V)")
        return self._mock_voltage