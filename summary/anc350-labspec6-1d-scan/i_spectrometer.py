import abc
import numpy as np

class ISpectrometer(abc.ABC):
    """
    光谱仪通用接口 (Interface)
    定义了所有光谱仪驱动（无论是真实的 LabSpec 还是模拟器）必须实现的方法。
    """

    @abc.abstractmethod
    def connect(self, ip: str, port: int):
        """连接到光谱仪软件/服务器"""
        pass

    @abc.abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abc.abstractmethod
    def set_parameters(self, integration_time_sec: float, averages: int):
        """
        设置采集参数。
        :param integration_time_sec: 积分时间 (秒)
        :param averages: 平均次数 (Accumulations)
        """
        pass

    @abc.abstractmethod
    def acquire_data(self) -> tuple[np.ndarray, np.ndarray]:
        """
        执行一次采集。
        :return: (wavelengths, intensities) 两个 numpy 数组的元组
        """
        pass