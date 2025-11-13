# scanner_interface.py (V1.6)
import abc

class IAxisVoltageScanner(abc.ABC):
    """
    [V1.6 修改]
    定义电压扫描器必须遵守的“格式”或“接口”。
    """

    @abc.abstractmethod
    def connect(self):
        """
        仅连接到 ANC350 设备。
        不改变任何轴的状态。
        """
        pass

    @abc.abstractmethod
    def disconnect(self):
        """安全断开与设备的连接。"""
        pass

    @abc.abstractmethod
    def set_axis_mode(self, mode: str):
        """
        [V1.6 新增]
        设置目标轴的逻辑模式。
        mode: "OFF", "OPEN" (开环), "CLOSED" (闭环)
        """
        pass

    @abc.abstractmethod
    def set_voltage(self, voltage: float):
        """
        在目标轴上设置直流电压。
        (警告: 只有在 set_axis_mode("OPEN") 之后才能安全调用)
        """
        pass

    @abc.abstractmethod
    def get_voltage(self) -> float:
        """读回目标轴的当前直流电压。"""
        pass
        
    @abc.abstractmethod
    def get_axis_status(self) -> dict:
        """
        获取当前轴的物理和逻辑状态。
        返回: 
        {
            "physically_connected": bool,
            "output_on": bool, (即 ANC_getAxisStatus 的 'enabled' 标志)
            "error_detected": bool
        }
        """
        pass