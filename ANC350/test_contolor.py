# test.py
from mock_scanner import MockVoltageScanner
from scanner_interface import IAxisVoltageScanner
import time

# --- 在这里选择要测试的扫描器 ---
# 使用模拟器进行测试
scanner: IAxisVoltageScanner = MockVoltageScanner(dev_no=0, axis_to_scan=1)

# --- 运行测试逻辑 ---
try:
    scanner.connect()
    
    print("\n--- 开始扫描电压 ---")
    scanner.set_voltage(10.0)
    time.sleep(0.5)
    scanner.set_voltage(20.0)
    time.sleep(0.5)
    
    # 测试 get_voltage
    current_v = scanner.get_voltage()
    print(f"--- 读回电压: {current_v} V ---")
    
    scanner.set_voltage(0.0)
    print("--- 扫描结束 ---\n")

except Exception as e:
    print(f"测试失败: {e}")

finally:
    scanner.disconnect()