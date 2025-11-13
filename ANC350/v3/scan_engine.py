# scan_engine.py (V3.0)
import threading
import queue
import time
import numpy
from scanner_interface import IAxisVoltageScanner
from mock_scanner import MockVoltageScanner
from real_scanner import RealVoltageScanner

def create_controller(use_mock_flag: bool, dev_no: int, axis_no: int) -> IAxisVoltageScanner:
    """ (V1.6 代码, 从 main_app 移至此) """
    if use_mock_flag:
        print("--- 正在创建 MOCK 模拟控制器 ---")
        return MockVoltageScanner(dev_no=dev_no, axis_to_scan=axis_no)
    else:
        print("--- 正在创建 REAL 真实硬件控制器 ---")
        return RealVoltageScanner(dev_no=dev_no, axis_to_scan=axis_no)


class ScanEngine:
    """
    (V3.0 新增)
    扫描引擎 (第 2 层：逻辑)。
    这个类不依赖任何 GUI (Tkinter)。
    它管理所有状态、硬件连接和扫描线程。
    """
    def __init__(self):
        # --- 硬件配置 ---
        self.use_mock = False
        self.target_device_no = 0
        
        # --- 状态变量 ---
        self.scanner: IAxisVoltageScanner = None
        self.is_connected = False
        self.current_connected_axis = -1
        self.current_mode = "OFF" # 跟踪当前模式
        
        self.scan_thread = None
        
        # --- 线程同步 ---
        self.stop_requested = False
        self.is_paused = False
        self.run_one_step = threading.Event()
        self.step_direction = 0  # 0=自动, 1=下一个, -1=上一个
        self.single_step_running = False
        
        # --- 扫描状态 ---
        self.current_scan_index = 0
        self.scan_points = []
        
        # --- 与 GUI 通信 ---
        self.gui_queue = queue.Queue()
        
        # --- 关机管理 ---
        self.is_shutting_down_flag = False
        self.shutdown_thread = None


    # --- 1. 公共方法 (供 GUI 调用) ---

    def set_config(self, use_mock: bool, device_no: int):
        """GUI 在启动时调用此方法来配置引擎"""
        self.use_mock = use_mock
        self.target_device_no = device_no
        
    def connect_anc350(self, axis_no: int):
        """GUI 调用：连接按钮"""
        if self.scan_thread and self.scan_thread.is_alive():
            self.gui_queue.put(("scan_error", Exception("请先终止当前扫描，然后再断开连接。")))
            return
            
        self.gui_queue.put(("status", f"正在连接设备 {self.target_device_no} (轴 {axis_no})..."))
        connect_thread = threading.Thread(target=self._connect_thread, args=(axis_no,))
        connect_thread.start()

    def disconnect_anc350(self):
        """GUI 调用：断开按钮"""
        if self.scan_thread and self.scan_thread.is_alive():
            self.gui_queue.put(("scan_error", Exception("请先终止当前扫描，然后再断开连接。")))
            return

        self.gui_queue.put(("status", "正在断开连接..."))
        disconnect_thread = threading.Thread(target=self._disconnect_thread)
        disconnect_thread.start()
        
    def set_anc_mode(self, mode: str):
        """GUI 调用：模式单选按钮"""
        if (self.scan_thread and self.scan_thread.is_alive()) or not self.is_connected:
            self.gui_queue.put(("mode_change_fail", Exception("非连接状态或扫描中，无法更改模式。")))
            return
            
        self.gui_queue.put(("status", f"正在将轴 {self.current_connected_axis} 设为 {mode} 模式..."))
        mode_thread = threading.Thread(target=self._toggle_mode_thread, args=(mode,))
        mode_thread.start()
        
    def start_scan(self, params: dict):
        """GUI 调用：开始扫描按钮"""
        if not self.is_connected or self.scanner is None:
            self.gui_queue.put(("scan_error", Exception("未连接到硬件。请先连接。")))
            return
            
        if self.current_mode != "OPEN":
            self.gui_queue.put(("scan_error", Exception(
                f"无法在“{self.current_mode}”模式下进行直流电压扫描。\n"
                "请先选择“开环 (OPEN / Scan)”模式。")))
            return
        
        try:
            start_v = float(params["start_v"])
            end_v = float(params["end_v"])
            num_points = int(params["num_points"])
            settle_time = float(params["settle_time"])
            if num_points < 2:
                raise ValueError("点数必须至少为 2")
            
            self.scan_points = numpy.linspace(start_v, end_v, num_points)
            self.current_scan_index = 0
            
        except ValueError as e:
            self.gui_queue.put(("scan_error", Exception(f"参数错误: {e}")))
            return
        
        # --- 重置所有状态机标志 ---
        self.stop_requested = False
        self.is_paused = False
        self.run_one_step.set()
        self.step_direction = 0
        self.single_step_running = False
        
        thread_args = (settle_time,)
        self.scan_thread = threading.Thread(target=self._start_scan_thread, args=thread_args)
        self.scan_thread.start()

    def pause_toggle(self):
        """GUI 调用：暂停/继续按钮"""
        if self.is_paused:
            # --- 正在继续 ---
            self.is_paused = False
            self.step_direction = 0
            self.run_one_step.set()
            self.single_step_running = False
            self.gui_queue.put(("status", "正在继续..."))
        else:
            # --- 正在暂停 ---
            self.is_paused = True
            self.gui_queue.put(("status", "正在暂停... (将在当前点完成后暂停)"))
            
    def stop_scan(self):
        """GUI 调用：终止扫描按钮"""
        self.stop_requested = True
        self.is_paused = False
        self.run_one_step.set()
        self.gui_queue.put(("status", "正在终止..."))

    def step_prev(self):
        """GUI 调用：上一个点按钮"""
        if not self.is_paused or self.single_step_running:
            return
        self.single_step_running = True
        self.step_direction = -1
        self.run_one_step.set()

    def step_next(self):
        """GUI 调用：下一个点按钮"""
        if not self.is_paused or self.single_step_running:
            return
        if self.current_scan_index >= len(self.scan_points) - 1:
            self.gui_queue.put(("scan_error", Exception("已是最后一个点。")))
            return
            
        self.single_step_running = True
        self.step_direction = 1
        self.run_one_step.set()

    def shutdown(self):
        """GUI 调用：窗口关闭"""
        if self.is_shutting_down_flag:
            return # 已经在关闭中
            
        print("[Engine] 收到关闭指令。")
        self.is_shutting_down_flag = True
        self.gui_queue.put(("status", "正在关闭所有连接..."))
        
        # 1. 停止扫描
        self.stop_requested = True
        self.is_paused = False
        self.run_one_step.set()
        
        # 2. 启动关机工作线程
        self.shutdown_thread = threading.Thread(target=self._shutdown_worker)
        self.shutdown_thread.start()

    def is_shutting_down(self) -> bool:
        """GUI 调用：轮询是否可以安全退出"""
        return self.is_shutting_down_flag


    # --- 2. 内部线程 (V2.0 逻辑) ---

    def _connect_thread(self, axis_no: int):
        try:
            self.scanner = create_controller(self.use_mock, self.target_device_no, axis_no)
            self.scanner.connect()
            status_dict = self.scanner.get_axis_status()
            
            self.is_connected = True
            self.current_connected_axis = axis_no
            
            # 推断当前模式
            is_output_on = status_dict.get("output_on", False)
            if is_output_on:
                self.current_mode = "CLOSED" # 假设是闭环
            else:
                self.current_mode = "OFF"
                
            self.gui_queue.put(("connect_success", (axis_no, status_dict, self.current_mode)))
            
        except Exception as e:
            self.scanner = None
            self.is_connected = False
            self.current_connected_axis = -1
            self.current_mode = "OFF"
            self.gui_queue.put(("connect_fail", e))

    def _disconnect_thread(self):
        try:
            if self.scanner:
                self.scanner.disconnect()
        except Exception as e:
            print(f"断开连接时出错: {e}")
            self.gui_queue.put(("status", f"断开时出错: {e}"))
        finally:
            self.scanner = None
            self.is_connected = False
            self.current_connected_axis = -1
            self.current_mode = "OFF"
            self.gui_queue.put(("disconnect_success", None))
    
    def _toggle_mode_thread(self, mode: str):
        try:
            self.scanner.set_axis_mode(mode)
            self.current_mode = mode # 成功后更新内部状态
            self.gui_queue.put(("mode_change_success", mode))
        except Exception as e:
            # 失败，模式可能未改变，但最好是重新查询
            # 为简单起见，我们假设它保持原样
            self.gui_queue.put(("mode_change_fail", e))
            
            
    def _start_scan_thread(self, settle_time):
        """
        (V2.0 代码, 无变化)
        """
        try:
            self.gui_queue.put(("enable_controls", None))
            self.gui_queue.put(("status", "开环模式已确认，开始扫描..."))
            
            num_points = len(self.scan_points)

            # --- V2.0 主循环 (while) ---
            while self.current_scan_index < num_points:
                
                # --- 1. 检查终止 ---
                if self.stop_requested:
                    self.gui_queue.put(("status", "扫描被用户终止。"))
                    break
                
                # --- 2. 检查暂停 ---
                if self.is_paused:
                    self.run_one_step.clear()
                    self.step_direction = 0 
                    
                    i = self.current_scan_index
                    voltage_at_pause = self.scan_points[i]
                    # GUI 会根据此消息启用 "上一个/下一个" 按钮
                    self.gui_queue.put(("single_step_ready", (i, voltage_at_pause)))
                    
                    # "忙等待"
                    while not self.run_one_step.is_set():
                        if self.stop_requested: 
                            break
                        time.sleep(0.05) 
                    
                    if self.stop_requested: 
                        self.gui_queue.put(("status", "扫描被用户终止。"))
                        break
                    
                    # 检查是哪个事件唤醒了我们
                    if self.step_direction == 1:
                        self.current_scan_index += 1
                    elif self.step_direction == -1:
                        self.current_scan_index = max(0, self.current_scan_index - 1)
                    # 如果 step_direction == 0, 意味着是 "继续" 按钮,
                    # 我们什么也不做，让循环在下面 (6.) 自动 +1
                    
                    # 重置单步锁 (移到这里)
                    self.single_step_running = False
                
                # --- 3. 执行扫描点 ---
                if self.current_scan_index >= num_points:
                    break
                    
                i = self.current_scan_index
                voltage = self.scan_points[i]
                
                status_msg = f"点 {i+1}/{num_points}: 设置电压 {voltage:.3f} V"
                self.gui_queue.put(("status", status_msg))

                self.scanner.set_voltage(voltage)
                
                # --- 4. [V2.0 关键修改] 条件等待 ---
                if not self.is_paused:
                    start_wait = time.time()
                    while (time.time() - start_wait) < settle_time:
                        if self.stop_requested:
                            break
                        time.sleep(0.05)
                
                if self.stop_requested:
                     self.gui_queue.put(("status", "扫描被用户终止。"))
                     break

                # --- 5. 更新图表 ---
                self.gui_queue.put(("plot_data", (i, voltage)))

                # --- 6. 推进索引 ---
                if not self.is_paused:
                    self.current_scan_index += 1
                
            # --- 循环结束 ---
            if not self.stop_requested:
                self.gui_queue.put(("status", "扫描完成。"))

        except Exception as e:
            self.gui_queue.put(("scan_error", e))
        finally:
            self.gui_queue.put(("scan_finished", None))
            # 清理
            self.scan_thread = None
            self.scan_points = []
            self.current_scan_index = 0
            print("扫描子线程已结束。")
            
    def _shutdown_worker(self):
        """在后台线程中安全地停止扫描并断开连接"""
        print("[Engine] 关机工作线程启动...")
        try:
            # 1. 等待扫描线程结束 (如果它在运行)
            if self.scan_thread and self.scan_thread.is_alive():
                print("[Engine] 等待扫描线程结束...")
                self.scan_thread.join()
                print("[Engine] 扫描线程已结束。")
            
            # 2. 同步断开硬件连接
            if self.is_connected and self.scanner:
                print(f"[Engine] 正在断开轴 {self.current_connected_axis}...")
                self.scanner.disconnect()
                self.is_connected = False
                print("[Engine] 硬件已断开。")

        except Exception as e:
            print(f"[Engine] 关机时出错: {e}")
        finally:
            # 3. 通知主线程 (GUI) 可以安全退出了
            self.is_shutting_down_flag = False
            print("[Engine] 关机完成。")