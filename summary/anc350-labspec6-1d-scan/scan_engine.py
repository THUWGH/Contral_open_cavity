# scan_engine.py (V6.0 - 终极融合版)
import threading
import queue
import time
import numpy as np
import os
from datetime import datetime

# 引入硬件接口
from scanner_interface import IAxisVoltageScanner
from mock_scanner import MockVoltageScanner
from real_scanner import RealVoltageScanner
from i_spectrometer import ISpectrometer
from mock_spectrometer import MockSpectrometer
from real_spectrometer import RealSpectrometer

class ScanEngine:
    def __init__(self):
        self.use_mock = False
        self.target_device_no = 0
        
        # --- 硬件 ---
        self.scanner: IAxisVoltageScanner = None
        self.spectrometer: ISpectrometer = None
        
        # --- 状态标志 ---
        self.is_scanner_connected = False
        self.is_spec_connected = False
        self.current_mode = "OFF"
        
        # --- 互锁标志 (Safety Interlocks) ---
        self.is_moving = False     # 正在移动电压
        self.is_acquiring = False  # 正在采集光谱
        self.is_scanning = False   # 扫描任务是否正在运行 (Run或Pause)
        
        # --- 扫描控制 ---
        self.scan_thread = None
        self.stop_requested = False
        self.is_paused = False
        self.pause_after_first = False # 首点暂停标志
        self.run_one_step = threading.Event()
        
        self.step_direction = 0 # 0=无, 1=Next, -1=Prev
        self.current_scan_index = 0
        self.scan_points = []
        
        # --- 数据缓存 ---
        self.last_spectrum = None # (wl, inten) 用于空闲时手动保存
        self.base_save_dir = ""
        self.file_prefix = ""
        self.metadata_text = ""
        self.current_save_dir = "" # 扫描时的保存目录
        
        self.gui_queue = queue.Queue()

    def set_config(self, use_mock: bool, device_no: int):
        self.use_mock = use_mock
        self.target_device_no = device_no

    # ==========================================
    #  连接管理 (保持原样，略去部分以节省空间)
    # ==========================================
    def connect_anc350(self, axis_no: int):
        def _worker():
            try:
                if self.use_mock:
                    self.scanner = MockVoltageScanner(self.target_device_no, axis_no)
                else:
                    self.scanner = RealVoltageScanner(self.target_device_no, axis_no)
                self.scanner.connect()
                status = self.scanner.get_axis_status()
                self.is_scanner_connected = True
                self.current_mode = "CLOSED" if status.get("output_on", False) else "OFF"
                self.gui_queue.put(("connect_anc_success", (axis_no, status, self.current_mode)))
            except Exception as e:
                self.scanner = None; self.is_scanner_connected = False
                self.gui_queue.put(("connect_anc_fail", e))
        threading.Thread(target=_worker).start()

    def connect_spectrometer(self):
        def _worker():
            try:
                if self.use_mock: self.spectrometer = MockSpectrometer()
                else: self.spectrometer = RealSpectrometer()
                self.spectrometer.connect('localhost', 1234)
                self.is_spec_connected = True
                self.gui_queue.put(("connect_spec_success", None))
            except Exception as e:
                self.spectrometer = None; self.is_spec_connected = False
                self.gui_queue.put(("connect_spec_fail", e))
        threading.Thread(target=_worker).start()

    def disconnect_all(self):
        def _worker():
            if self.spectrometer:
                try: self.spectrometer.disconnect()
                except: pass
                self.is_spec_connected = False; self.spectrometer = None
                self.gui_queue.put(("disconnect_spec_success", None))
            if self.scanner:
                try: self.scanner.disconnect()
                except: pass
                self.is_scanner_connected = False; self.scanner = None
                self.gui_queue.put(("disconnect_anc_success", None))
        threading.Thread(target=_worker).start()

    def set_anc_mode(self, mode: str):
        def _worker():
            try:
                if self.scanner:
                    self.scanner.set_axis_mode(mode)
                    self.current_mode = mode
                    self.gui_queue.put(("mode_change_success", mode))
            except Exception as e:
                self.gui_queue.put(("mode_change_fail", e))
        threading.Thread(target=_worker).start()

    # ==========================================
    #  核心业务逻辑 (V6.0 重构)
    # ==========================================

    def start_scan(self, scan_params: dict, save_config: dict, pause_after_first: bool):
        """启动自动扫描"""
        # 1. 检查
        if not self.is_scanner_connected:
            self.gui_queue.put(("scan_error", Exception("错误: 扫描控制器未连接")))
            return
        if self.current_mode != "OPEN":
            self.gui_queue.put(("scan_error", Exception("错误: 扫描器必须处于 OPEN 模式")))
            return
        
        # 2. 检查光谱仪 (V6.0: 允许无光谱仪运行，但在日志中警告)
        if not self.is_spec_connected:
            self.gui_queue.put(("status", "警告: 光谱仪未连接，仅执行电压扫描，不采集数据。"))

        # 3. 参数解析
        try:
            start_v = float(scan_params["start_v"])
            end_v = float(scan_params["end_v"])
            points = int(scan_params["num_points"])
            self.settle_time = float(scan_params["settle_time"])
            self.int_time = float(scan_params["int_time"])
            self.avg_cnt = int(scan_params["avg"])
            
            self.base_save_dir = save_config["save_path"]
            self.file_prefix = save_config["prefix"]
            self.metadata_text = save_config["metadata"]
            
            if points < 2: raise ValueError("点数必须 >= 2")
            self.scan_points = np.linspace(start_v, end_v, points)
            
        except ValueError as e:
            self.gui_queue.put(("scan_error", Exception(f"参数错误: {e}")))
            return

        # 4. 创建目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{timestamp}_{self.file_prefix}"
        self.current_save_dir = os.path.join(self.base_save_dir, folder_name)
        try:
            os.makedirs(self.current_save_dir, exist_ok=True)
        except Exception as e:
            self.gui_queue.put(("scan_error", Exception(f"无法创建文件夹: {e}")))
            return

        # 5. 初始化状态
        self.current_scan_index = 0
        self.stop_requested = False
        self.is_paused = False
        self.pause_after_first = pause_after_first
        self.run_one_step.set()
        self.step_direction = 0
        
        self.is_scanning = True
        self.scan_thread = threading.Thread(target=self._scan_worker)
        self.scan_thread.start()

    def _scan_worker(self):
        """后台扫描主循环"""
        try:
            self.gui_queue.put(("scan_started", None))
            
            if self.is_spec_connected:
                self.gui_queue.put(("status", "配置光谱仪..."))
                self.spectrometer.set_parameters(self.int_time, self.avg_cnt)
            
            num_points = len(self.scan_points)
            
            while self.current_scan_index < num_points:
                # --- 停止检查 ---
                if self.stop_requested: break

                # --- 暂停检查 (含首点暂停逻辑) ---
                if self.is_paused:
                    self._handle_pause_loop() # 阻塞
                    if self.stop_requested: break
                    
                    # 响应单步移动 (电压已在 handle_pause_loop 中通过 manual_move 移动了)
                    # 这里只需要处理索引变更
                    if self.step_direction != 0:
                        # 仅调整索引，不执行下面的自动流程
                        if self.step_direction == 1:
                            pass # 下一点：直接进入下一次循环
                        elif self.step_direction == -1:
                            self.current_scan_index = max(0, self.current_scan_index - 1)
                            # 继续循环，会重新执行当前索引(即上一点)的流程
                        
                        self.step_direction = 0 # 复位
                        continue # 跳过下方自动流程，重新进入循环头部
                
                # --- 执行标准流程 ---
                if self.current_scan_index >= num_points: break
                
                idx = self.current_scan_index
                target_v = self.scan_points[idx]
                
                # 1. 移动 (自动模式)
                self._move_voltage_safe(target_v)
                self.gui_queue.put(("scan_progress", (idx, target_v))) # 更新红准星
                
                # 2. 稳定
                if not self.is_paused:
                    time.sleep(self.settle_time)
                
                # 3. 采集 & 自动保存
                self._acquire_and_save(idx, target_v)
                
                # 4. 首点暂停逻辑
                if idx == 0 and self.pause_after_first:
                    self.pause_after_first = False # 只触发一次
                    self.pause_toggle() # 触发暂停
                    continue # 暂停后不增加索引，等待用户决定
                
                # 5. 索引递增
                self.current_scan_index += 1
                
            msg = "扫描终止" if self.stop_requested else "扫描完成"
            self.gui_queue.put(("status", msg))
            
        except Exception as e:
            self.gui_queue.put(("scan_error", e))
        finally:
            self.is_scanning = False
            self.gui_queue.put(("scan_finished", None))

    def _handle_pause_loop(self):
        """暂停时的忙等待，同时允许响应 manual_acquire 和 manual_move"""
        self.run_one_step.clear()
        self.gui_queue.put(("status", f"暂停中 (点 {self.current_scan_index+1})。"))
        
        while not self.run_one_step.is_set():
            if self.stop_requested: return
            time.sleep(0.05)
            # 在此循环中，主线程可以通过调用 manual_acquire / manual_move 来插入动作

    # ==========================================
    #  原子操作 (互锁保护)
    # ==========================================

    def _move_voltage_safe(self, voltage):
        """互锁保护的移动"""
        if self.is_acquiring:
            raise Exception("正在采谱，禁止移动电压！")
        
        self.is_moving = True
        try:
            self.scanner.set_voltage(voltage)
        finally:
            self.is_moving = False

    def _acquire_and_save(self, idx, voltage):
        """采集并保存 (自动模式)"""
        if not self.is_spec_connected: return
        if self.is_moving:
            raise Exception("电压不稳定，禁止采谱！")

        self.is_acquiring = True
        try:
            self.gui_queue.put(("status", "正在采集光谱..."))
            wl, inten = self.spectrometer.acquire_data()
            self.last_spectrum = (wl, inten) # 缓存
            
            # 自动保存 (带时间戳防覆盖)
            timestamp = datetime.now().strftime("%H-%M-%S")
            fname = f"Step{idx+1:03d}_V{voltage:.4f}_{timestamp}.txt"
            path = os.path.join(self.current_save_dir, fname)
            self._save_file(path, wl, inten, voltage)
            
            # 更新图表 (History + Live)
            self.gui_queue.put(("plot_data_saved", (idx, voltage, wl, inten)))
            
        finally:
            self.is_acquiring = False

    def _save_file(self, path, x, y, v):
        """底层保存函数"""
        header = (
            f"LabSpec Auto Data (V6.0)\n"
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Voltage: {v:.6f}\n"
            f"Int_Time: {self.int_time}\n"
            f"Metadata:\n{self.metadata_text}\n"
            f"--------------------------\n"
            f"Wavelength\tIntensity\n"
        )
        data = np.column_stack((x, y))
        with open(path, 'w', encoding='utf-8') as f:
            f.write(header)
            np.savetxt(f, data, fmt='%.6f\t%.6f')

    # ==========================================
    #  GUI 手动指令 (External Commands)
    # ==========================================

    def manual_move_step(self, direction):
        """手动单步 (不采谱，仅移动)"""
        if not self.is_scanning: return # 仅在暂停时有效
        if self.is_acquiring:
            self.gui_queue.put(("status", "警告: 正在采谱，无法移动！"))
            return
            
        # 计算新索引
        new_idx = self.current_scan_index + direction
        if 0 <= new_idx < len(self.scan_points):
            target_v = self.scan_points[new_idx]
            self.gui_queue.put(("status", f"手动移至点 {new_idx+1}: {target_v:.3f}V"))
            
            # 执行移动
            self._move_voltage_safe(target_v)
            self.gui_queue.put(("scan_progress", (new_idx, target_v))) # 更新红准星
            
            # 更新内部状态，通知 scan_worker 跳过逻辑
            self.current_scan_index = new_idx
            self.step_direction = direction
            self.run_one_step.set() # 唤醒 worker

    def manual_acquire(self):
        """手动采集 (适用于空闲调试 或 暂停重测)"""
        if self.is_moving:
            self.gui_queue.put(("status", "警告: 电压正在移动，无法采谱！"))
            return
        if not self.is_spec_connected:
            self.gui_queue.put(("status", "错误: 光谱仪未连接"))
            return

        def _acq_worker():
            self.is_acquiring = True
            try:
                self.gui_queue.put(("status", "手动采集..."))
                # 如果是空闲，可能需要先设参数
                if not self.is_scanning:
                    self.spectrometer.set_parameters(self.int_time, self.avg_cnt) # 使用当前UI参数
                
                wl, inten = self.spectrometer.acquire_data()
                self.last_spectrum = (wl, inten)
                
                # 场景分支
                if self.is_scanning: # 暂停重测模式 -> 自动保存
                    idx = self.current_scan_index
                    v = self.scan_points[idx]
                    ts = datetime.now().strftime("%H-%M-%S")
                    fname = f"Step{idx+1:03d}_V{v:.4f}_{ts}_Manual.txt"
                    path = os.path.join(self.current_save_dir, fname)
                    self._save_file(path, wl, inten, v)
                    self.gui_queue.put(("plot_data_saved", (idx, v, wl, inten))) # 画蓝点
                    self.gui_queue.put(("status", f"重测数据已保存: {fname}"))
                else: # 空闲调试模式 -> 仅刷新图，不保存
                    # 对于空闲模式，我们没有 index，voltage 需要现读
                    curr_v = 0.0
                    if self.scanner and self.is_scanner_connected:
                        try: curr_v = self.scanner.get_voltage()
                        except: pass
                    self.gui_queue.put(("plot_live_only", (wl, inten)))
                    self.gui_queue.put(("status", "手动采集完成 (未保存，请点击 Save 保存)。"))
                    
            except Exception as e:
                self.gui_queue.put(("scan_error", e))
            finally:
                self.is_acquiring = False
        
        threading.Thread(target=_acq_worker).start()

    def manual_save_idle(self, path):
        """空闲模式下的手动保存"""
        if self.last_spectrum is None: return
        try:
            curr_v = 0.0
            if self.scanner and self.is_scanner_connected:
                curr_v = self.scanner.get_voltage()
            self._save_file(path, self.last_spectrum[0], self.last_spectrum[1], curr_v)
            self.gui_queue.put(("status", f"文件已保存: {os.path.basename(path)}"))
        except Exception as e:
            self.gui_queue.put(("scan_error", e))

    # --- 控制 ---
    def stop_scan(self):
        self.stop_requested = True
        self.run_one_step.set()

    def pause_toggle(self):
        if self.is_paused:
            self.is_paused = False
            self.step_direction = 0 # 继续时方向置0
            self.run_one_step.set()
        else:
            self.is_paused = True