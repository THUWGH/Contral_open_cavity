# scanner_interface.py
import abc

class IAxisVoltageScanner(abc.ABC):
    """
    定义电压扫描器必须遵守的“格式”或“接口”。
    模拟器和真实控制器都将实现这个接口。
    """

    @abc.abstractmethod
    def connect(self):
        """连接到 ANC350 设备并准备好目标轴。"""
        pass

    @abc.abstractmethod
    def disconnect(self):
        """安全断开与设备的连接。"""
        pass

    @abc.abstractmethod
    def set_voltage(self, voltage: float):
        """在目标轴上设置直流电压。"""
        pass

    @abc.abstractmethod
    def get_voltage(self) -> float:
        """(推荐) 读回目标轴的当前直流电压。"""
        pass