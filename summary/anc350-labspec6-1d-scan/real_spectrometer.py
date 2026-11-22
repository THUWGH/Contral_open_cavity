import numpy as np
import time
from i_spectrometer import ISpectrometer

# 引入您之前验证通过的驱动文件
# 请确保项目目录下有 labspec6_debug_FULL.py
try:
    from labspec6_debug_FULL import Labspec6Client
except ImportError:
    raise ImportError("找不到 labspec6_debug_FULL.py，请确保该文件在项目根目录。")

class RealSpectrometer(ISpectrometer):
    def __init__(self):
        self.client = Labspec6Client()
        self.is_connected = False
        # 缓存 X 轴数据，避免每次都从服务器重新拉取，提高速度
        self._cached_wavelengths = None

    def connect(self, ip='localhost', port=1234):
        print(f"[Spec-Driver] 正在连接 LabSpec ({ip}:{port})...")
        ret, data, extra = self.client.connect(ip, port)
        if ret == 'OK':
            self.is_connected = True
            print("[Spec-Driver] 连接成功。")
        else:
            raise ConnectionError(f"LabSpec 连接失败: {ret} {data}")

    def disconnect(self):
        if self.is_connected:
            print("[Spec-Driver] 断开连接...")
            self.client.close()
            self.is_connected = False

    def set_parameters(self, integration_time_sec: float, averages: int):
        if not self.is_connected:
            raise ConnectionError("未连接光谱仪")

        print(f"[Spec-Driver] 设置参数: Time={integration_time_sec}s, Avg={averages}")
        
        # [修改 1] 先握手/准备模式 (防止它重置参数)
        # 这一步可能会把光谱仪重置为默认值
        status = self.client.prepare_N_acquisition(Npts=2)
        if status != 'ready':
            raise RuntimeError(f"LabSpec 准备失败: {status}")
        
        # [修改 2] 握手完成后，再强制写入我们的参数 (覆盖默认值)
        self.client.exposure = integration_time_sec
        self.client.accumulations = averages
        
        # 3. 刷新波长轴
        self._cached_wavelengths = np.array(self.client.get_x_axis())
        print("[Spec-Driver] 参数设置完成 (Safe Sequence)。")

    def acquire_data(self) -> tuple[np.ndarray, np.ndarray]:
        """
        阻塞式采集：会等待直到光谱仪返回数据。
        """
        if not self.is_connected:
            raise ConnectionError("未连接光谱仪")

        # 调用阻塞式的 grab_spectrum
        data_y = self.client.grab_spectrum()
        
        # 检查错误
        if isinstance(data_y, str) and "Error" in data_y:
            raise RuntimeError(f"采集失败: {data_y}")
            
        # 确保是 numpy 数组
        y_axis = np.array(data_y)
        
        # 获取 X 轴 (如果缓存了就用缓存的，否则获取一次)
        if self._cached_wavelengths is None:
            self._cached_wavelengths = np.array(self.client.get_x_axis())
            
        x_axis = self._cached_wavelengths

        # 数据对齐检查
        if len(x_axis) != len(y_axis):
            # 尝试重新获取一次 X 轴，以防万一
            self._cached_wavelengths = np.array(self.client.get_x_axis())
            x_axis = self._cached_wavelengths
            if len(x_axis) != len(y_axis):
                raise ValueError(f"数据维度不匹配: X轴 {len(x_axis)} pts, Y轴 {len(y_axis)} pts")

        return x_axis, y_axis