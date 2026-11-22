import numpy as np
import time
from i_spectrometer import ISpectrometer

class MockSpectrometer(ISpectrometer):
    def __init__(self):
        self.is_connected = False
        self.int_time = 0.1
        # 模拟一个 1024 像素的 CCD
        self.pixels = 1024
        self.wavelengths = np.linspace(500, 600, self.pixels)

    def connect(self, ip='localhost', port=1234):
        print("[Mock-Spec] 正在模拟连接...")
        time.sleep(0.5)
        self.is_connected = True
        print("[Mock-Spec] 已连接。")

    def disconnect(self):
        print("[Mock-Spec] 断开连接。")
        self.is_connected = False

    def set_parameters(self, integration_time_sec: float, averages: int):
        self.int_time = integration_time_sec
        print(f"[Mock-Spec] 模拟设置参数: {integration_time_sec}s, avg={averages}")
        time.sleep(0.1)

    def acquire_data(self) -> tuple[np.ndarray, np.ndarray]:
        if not self.is_connected:
            raise ConnectionError("Mock Spectrometer not connected")
        
        # 模拟采集耗时
        time.sleep(self.int_time)
        
        # 生成模拟光谱 (带噪声的高斯峰)
        noise = np.random.normal(0, 5, self.pixels)
        center = 550 + np.random.uniform(-1, 1) # 让峰稍微动一下
        peak = 1000 * np.exp(-0.5 * ((self.wavelengths - center) / 5)**2)
        intensities = peak + noise + 50 # 基线 50
        
        return self.wavelengths, intensities