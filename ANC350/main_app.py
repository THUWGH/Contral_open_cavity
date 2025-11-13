# main_app.py (V2.0 - 修复单步延迟)
import tkinter as tk
from tkinter import ttk, messagebox, font
import threading
import queue
import time
import numpy
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- 导入您的接口和实现 (V1.6) ---
from scanner_interface import IAxisVoltageScanner
from mock_scanner import MockVoltageScanner 
from real_scanner import RealVoltageScanner 

# -----------------------------------------------------------------
USE_MOCK = False 
# -----------------------------------------------------------------
TARGET_DEVICE_NO = 0
# -----------------------------------------------------------------


def create_controller(use_mock_flag: bool, dev_no: int, axis_no: int) -> IAxisVoltageScanner:
    """
    (V1.6 代码, 无变化)
    """
    if use_mock_flag:
        print("--- 正在创建 MOCK 模拟控制器 ---")
        return MockVoltageScanner(dev_no=dev_no, axis_to_scan=axis_no)
    else:
        print("--- 正在创建 REAL 真实硬件控制器 ---")
        return RealVoltageScanner(dev_no=dev_no, axis_to_scan=axis_no)


class ScanningApp:
    """
    主应用程序类 (V2.0)
    - 修复了 V1.9 中 "上一个/下一个" 按钮会错误执行 settle_time 的问题。
    """
    def __init__(self, root):
        self.root = root
        self.root.title("ANC350 直流电压扫描控制器 (V2.0)")
        self.root.geometry("800x600")

        # --- 状态变量 ---
        self.scanner: IAxisVoltageScanner = None
        self.is_connected = False
        self.current_connected_axis = -1
        
        self.scan_thread = None
        
        # --- [V1.8] 线程同步 ---
        self.stop_requested = False
        self.is_paused = False                  
        self.run_one_step = threading.Event()   
        self.step_direction = 0                 # 0=自动, 1=下一个, -1=上一个
        self.single_step_running = False        
        
        # --- [V1.8] 扫描状态 ---
        self.current_scan_index = 0
        self.scan_points = []
        
        self.plot_x_data = []
        self.plot_y_data = []

        self.gui_queue = queue.Queue()

        # --- [V1.8] GUI 变量 ---
        self.axis_mode_var = tk.StringVar(value="OFF") 

        self._create_widgets() 
        self._init_plot()      

        self.periodic_queue_check()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        """(V1.7 代码, 无变化) 创建所有的GUI组件。"""
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 1. 连接框架 ---
        connect_frame = ttk.LabelFrame(main_frame, text="设备控制", padding="10")
        connect_frame.pack(fill=tk.X, expand=False, pady=(0, 5))
        connect_frame.columnconfigure(2, weight=1) 
        
        ttk.Label(connect_frame, text="目标轴 (Axis):").grid(row=0, column=0, sticky=tk.W, padx=5)
        
        self.axis_combo = ttk.Combobox(connect_frame, values=["0", "1", "2"], width=5)
        self.axis_combo.set("0")
        self.axis_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        self.connect_button = ttk.Button(connect_frame, text="连接 (Connect)", 
                                         command=self.on_connect_toggle)
        self.connect_button.grid(row=0, column=2, sticky=tk.EW, padx=5)
        
        mode_frame = ttk.Frame(connect_frame)
        mode_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        
        self.mode_rb_off = ttk.Radiobutton(mode_frame, 
                                           text="轴关闭 (OFF / GND)", 
                                           variable=self.axis_mode_var,
                                           value="OFF",
                                           command=self.on_set_mode,
                                           state=tk.DISABLED)
        self.mode_rb_off.pack(side=tk.LEFT, padx=5)

        self.mode_rb_open = ttk.Radiobutton(mode_frame, 
                                            text="开环 (OPEN / Scan)", 
                                            variable=self.axis_mode_var,
                                            value="OPEN",
                                            command=self.on_set_mode,
                                            state=tk.DISABLED)
        self.mode_rb_open.pack(side=tk.LEFT, padx=5)

        self.mode_rb_closed = ttk.Radiobutton(mode_frame, 
                                              text="闭环 (CLOSED)", 
                                              variable=self.axis_mode_var,
                                              value="CLOSED",
                                              command=self.on_set_mode,
                                              state=tk.DISABLED)
        self.mode_rb_closed.pack(side=tk.LEFT, padx=5)


        # --- 2. 参数框架 ---
        params_frame = ttk.LabelFrame(main_frame, text="扫描参数 (仅限'开环'模式)", padding="10")
        params_frame.pack(fill=tk.X, expand=False, pady=5)
        params_frame.columnconfigure(1, weight=1)
        # (省略了参数框架的内部实现, 与 V1.7 相同)
        self.entries = {}
        param_list = [
            ("start_v", "起始电压 (V):", "0.0"),
            ("end_v", "终止电压 (V):", "50.0"),
            ("num_points", "点数 (N):", "51"),
            ("settle_time", "稳定时间 (s):", "0.5"),
        ]
        for i, (key, text, default_val) in enumerate(param_list):
            ttk.Label(params_frame, text=text).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            entry = ttk.Entry(params_frame, width=15)
            entry.insert(0, default_val)
            entry.grid(row=i, column=1, sticky=tk.EW, padx=5, pady=2)
            self.entries[key] = entry


        # --- 3. 控制框架 ---
        control_frame = ttk.Frame(main_frame, padding="10 0")
        control_frame.pack(fill=tk.X, expand=False)
        # (省略了 style 定义)
        default_font = font.nametofont("TkDefaultFont")
        button_font = default_font.copy()
        button_font.configure(size=default_font.cget("size") + 2)
        style = ttk.Style()
        style.configure("Accent.TButton", font=button_font)
        self.start_button = ttk.Button(control_frame, text="开始扫描", 
                                       command=self.on_start_scan, style="Accent.TButton", state=tk.DISABLED)
        self.start_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.pause_button = ttk.Button(control_frame, text="暂停", 
                                      command=self.on_pause_toggle, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.stop_button = ttk.Button(control_frame, text="终止扫描", 
                                      command=self.on_stop_scan, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # --- 4. 单步控制框架 ---
        step_frame = ttk.Frame(main_frame, padding="10 0")
        step_frame.pack(fill=tk.X, expand=False)
        self.prev_button = ttk.Button(step_frame, text="< 上一个点", 
                                      command=self.on_prev_point, state=tk.DISABLED)
        self.prev_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.next_button = ttk.Button(step_frame, text="下一个点 >", 
                                      command=self.on_next_point, state=tk.DISABLED)
        self.next_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # --- 5. 绘图框架 ---
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111) 
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- 6. 状态栏 ---
        self.status_var = tk.StringVar()
        self.status_var.set("空闲。请选择轴并连接。")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding="5 2")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)


    def _init_plot(self):
        """(V1.9 代码, 修改标题)"""
        self.plot_x_data.clear()
        self.plot_y_data.clear()
        self.ax.clear()
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei']
            plt.rcParams['axes.unicode_minus'] = False
        except Exception:
            print("警告: 未找到 'SimHei' 字体，图表可能显示方框。")
        self.ax.set_title(f"实时电压扫描 (V2.0)")
        self.ax.set_xlabel("扫描点序号")
        self.ax.set_ylabel("设定电压 (V)")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], 'bo-')
        self.canvas.draw()
        
    def periodic_queue_check(self):
        """(V1.9 代码, 无变化)"""
        try:
            while not self.gui_queue.empty():
                msg_type, data = self.gui_queue.get_nowait()
                
                if msg_type == "connect_success":
                    self._handle_connect_success(data)
                elif msg_type == "connect_fail":
                    self._handle_connect_fail(data)
                elif msg_type == "disconnect_success":
                    self._handle_disconnect_success()
                    
                elif msg_type == "mode_change_success":
                    mode = data
                    self._update_status(f"轴 {self.current_connected_axis} 模式已设为: {mode}")
                    self._set_radio_buttons_state(tk.NORMAL) 
                elif msg_type == "mode_change_fail":
                    self._handle_scan_error(data) 
                    self._set_radio_buttons_state(tk.NORMAL) 
                
                elif msg_type == "single_step_ready":
                    index, voltage = data 
                    self.single_step_running = False
                    self.prev_button.config(state=tk.NORMAL)
                    self.next_button.config(state=tk.NORMAL)
                    self._update_status(f"暂停于点 {index+1} (V: {voltage:.3f} V)。等待指令...")
                
                elif msg_type == "status":
                    self._update_status(data)
                elif msg_type == "plot_data":
                    self._update_plot(data[0], data[1])
                elif msg_type == "enable_controls":
                    self.pause_button.config(state=tk.NORMAL)
                    self.stop_button.config(state=tk.NORMAL)
                elif msg_type == "scan_finished":
                    self._handle_scan_finished()
                elif msg_type == "scan_error":
                    self._handle_scan_error(data)
        finally:
            self.root.after(100, self.periodic_queue_check)
            
    # --- GUI 辅助函数 (V1.6 代码, 无变化) ---
    
    def _set_radio_buttons_state(self, state):
        self.mode_rb_off.config(state=state)
        self.mode_rb_open.config(state=state)
        self.mode_rb_closed.config(state=state)

    # --- GUI 状态机函数 (V1.6 代码, 无变化) ---
    
    def _handle_connect_success(self, data):
        axis_no, status_dict = data
        is_phys_connected = status_dict.get("physically_connected", False)
        is_output_on = status_dict.get("output_on", False)
        is_error = status_dict.get("error_detected", False)

        self.connect_button.config(text=f"断开 (Disconnect Axis {axis_no})", state=tk.NORMAL)
        self.axis_combo.config(state=tk.DISABLED)

        if not is_phys_connected or is_error:
            phys_conn = "未连接" if not is_phys_connected else "已连接"
            err_text = " (有错误!)" if is_error else ""
            error_msg = f"错误: 轴 {axis_no} 状态异常 (物理: {phys_conn}{err_text})。无法继续操作。"
            self._update_status(error_msg)
            messagebox.showerror("连接错误", error_msg + "\n\n请检查物理线缆，然后断开并重试。")
            self.start_button.config(state=tk.DISABLED)
            self._set_radio_buttons_state(tk.DISABLED)
            return 
            
        self.start_button.config(state=tk.NORMAL)
        
        if is_output_on:
            self.axis_mode_var.set("CLOSED") 
            mode_text = "闭环 (未知)"
        else:
            self.axis_mode_var.set("OFF") 
            mode_text = "轴关闭 (OFF)"
            
        self._set_radio_buttons_state(tk.NORMAL) 
        
        self._update_status(f"轴 {axis_no} 连接成功。物理状态: 已连接{err_text}。当前模式: {mode_text}。")
        self._init_plot()
        self.ax.set_title(f"实时电压扫描 (Axis {axis_no})")

    def _handle_connect_fail(self, error):
        self.connect_button.config(text="连接 (Connect)", state=tk.NORMAL)
        self.axis_combo.config(state=tk.NORMAL)
        self._handle_disconnect_success() 
        
        error_msg = f"连接失败: {error}"
        self._update_status(error_msg)
        print(f"--- 错误详情 --- \n{error}")
        messagebox.showerror("连接错误", error_msg)

    def _handle_disconnect_success(self):
        self.connect_button.config(text="连接 (Connect)", state=tk.NORMAL)
        self.start_button.config(state=tk.DISABLED)
        self.axis_combo.config(state=tk.NORMAL)
        self._set_radio_buttons_state(tk.DISABLED) 
        self.axis_mode_var.set("OFF") 
        self._update_status("空闲。")
        self.is_connected = False 

    # --- GUI 更新方法 (V1.6 代码, 无变化) ---

    def _update_status(self, message: str):
        self.status_var.set(message)

    def _update_plot(self, x, y):
        self.plot_x_data.append(x)
        self.plot_y_data.append(y)
        self.line.set_data(self.plot_x_data, self.plot_y_data)
        self.ax.relim()
        self.ax.autoscale_view(True, True, True)
        self.canvas.draw_idle()

    def _handle_scan_finished(self):
        """(V1.8 代码, 无变化)"""
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="暂停")
        self.stop_button.config(state=tk.DISABLED)
        self.prev_button.config(state=tk.DISABLED)  
        self.next_button.config(state=tk.DISABLED)  
        
        self.connect_button.config(state=tk.NORMAL) 
        self._set_radio_buttons_state(tk.NORMAL) 
        self.axis_combo.config(state=tk.DISABLED)
        
        self.scan_thread = None
        self.is_paused = False
        self.current_scan_index = 0 
        self.scan_points = []       
        self.step_direction = 0
        self.single_step_running = False
        
        if self.is_connected:
             mode = self.axis_mode_var.get()
             self._update_status(f"扫描完成。仍连接到轴 {self.current_connected_axis} (模式: {mode})。")

    def _handle_scan_error(self, error: Exception):
        """(V1.8 代码, 无变化)"""
        self._handle_scan_finished() 
        
        error_msg = f"操作出错: {error}"
        self._update_status(error_msg)
        print(f"--- 错误详情 --- \n{error}")
        messagebox.showerror("错误", error_msg)

        if not self.is_connected:
            self._handle_disconnect_success() 


    # --- 按钮回调 (V1.8 代码, 无变化) ---
    
    def on_connect_toggle(self):
        if self.scan_thread and self.scan_thread.is_alive():
            messagebox.showwarning("操作无效", "请先终止当前扫描，然后再断开连接。")
            return
        if self.is_connected:
            self.connect_button.config(text="断开中...", state=tk.DISABLED)
            self.start_button.config(state=tk.DISABLED)
            self._set_radio_buttons_state(tk.DISABLED)
            self._update_status("正在断开连接...")
            disconnect_thread = threading.Thread(target=self.disconnect_thread)
            disconnect_thread.start()
        else:
            try:
                axis_no = int(self.axis_combo.get())
            except ValueError:
                messagebox.showerror("错误", "无效的轴号。")
                return
            
            self.connect_button.config(text="连接中...", state=tk.DISABLED)
            self.axis_combo.config(state=tk.DISABLED)
            self._update_status(f"正在连接设备 {TARGET_DEVICE_NO} (轴 {axis_no})...")
            connect_thread = threading.Thread(target=self.connect_thread, args=(axis_no,))
            connect_thread.start()
            
    def on_set_mode(self):
        if (self.scan_thread and self.scan_thread.is_alive()) or not self.is_connected:
            return 
        try:
            mode = self.axis_mode_var.get()
            self._update_status(f"正在将轴 {self.current_connected_axis} 设为 {mode} 模式...")
            self._set_radio_buttons_state(tk.DISABLED) 
            mode_thread = threading.Thread(target=self.toggle_mode_thread, 
                                           args=(mode,))
            mode_thread.start()
        except Exception as e:
            self._handle_scan_error(e)
            self._set_radio_buttons_state(tk.NORMAL)

    def on_start_scan(self):
        if not self.is_connected or self.scanner is None:
            messagebox.showerror("错误", "未连接到硬件。请先连接。")
            return
            
        current_mode = self.axis_mode_var.get()
        if current_mode != "OPEN": 
            messagebox.showerror("扫描错误", 
                                 f"无法在“{current_mode}”模式下进行直流电压扫描。\n\n"
                                 "请先在'设备控制'中选择“开环 (OPEN / Scan)”模式后再试。")
            return
        
        try:
            params = {key: entry.get() for key, entry in self.entries.items()}
            start_v = float(params["start_v"])
            end_v = float(params["end_v"])
            num_points = int(params["num_points"])
            settle_time = float(params["settle_time"])
            if num_points < 2:
                raise ValueError("点数必须至少为 2")
            
            self.scan_points = numpy.linspace(start_v, end_v, num_points)
            self.current_scan_index = 0
            
        except ValueError as e:
            messagebox.showerror("参数错误", f"无效的输入: {e}")
            return
        
        self.start_button.config(state=tk.DISABLED)
        self.connect_button.config(state=tk.DISABLED)
        self._set_radio_buttons_state(tk.DISABLED) 
        
        self.stop_requested = False
        self.is_paused = False          
        self.run_one_step.set()         
        self.step_direction = 0         
        self.single_step_running = False
        
        thread_args = (settle_time,) 
        self.scan_thread = threading.Thread(target=self.start_scan_thread, args=thread_args)
        self.scan_thread.start()

    def on_pause_toggle(self):
        if self.is_paused:
            self.is_paused = False
            self.step_direction = 0 
            self.run_one_step.set() 
            
            self.pause_button.config(text="暂停")
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)
            self.single_step_running = False 
            
            self._update_status("正在继续...")
        else:
            self.is_paused = True
            
            self.pause_button.config(text="继续")
            
            self._update_status("正在暂停... (将在当前点完成后暂停)")

    def on_prev_point(self):
        if not self.is_paused or self.single_step_running:
            return 
        
        self.single_step_running = True
        self.prev_button.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)

        self.step_direction = -1
        self.run_one_step.set() 

    def on_next_point(self):
        if not self.is_paused or self.single_step_running:
            return
            
        self.single_step_running = True
        self.prev_button.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)
        
        if self.current_scan_index >= len(self.scan_points) - 1:
            messagebox.showinfo("提示", "已是最后一个点。")
            self.single_step_running = False
            self.prev_button.config(state=tk.NORMAL)
            self.next_button.config(state=tk.NORMAL)
            return

        self.step_direction = 1
        self.run_one_step.set() 

    def on_stop_scan(self):
        self.stop_requested = True
        self.is_paused = False      
        self.run_one_step.set()     
        
        self.stop_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED)
        self.prev_button.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)
        
        self._update_status("正在终止...")

    def on_closing(self):
        # (V1.8 代码, 无变化)
        if self.scan_thread and self.scan_thread.is_alive():
            if messagebox.askyesno("扫描正在进行", "扫描正在进行中，您确定要退出吗？"):
                self.on_stop_scan() 
                self.root.after(100, self.wait_for_scan_to_quit)
            else:
                return 
        elif self.is_connected:
            if messagebox.askyesno("设备已连接", "设备已连接。您想在退出前断开连接吗？"):
                self.on_connect_toggle()
                self.root.after(100, self.wait_for_disconnect_to_quit)
            else:
                self.root.destroy()
        else:
            self.root.destroy()
            
    def wait_for_scan_to_quit(self):
        # (V1.8 代码, 无变化)
        if self.scan_thread and self.scan_thread.is_alive():
            self.root.after(100, self.wait_for_scan_to_quit)
            return
        if self.is_connected:
            self.on_connect_toggle()
            self.root.after(100, self.wait_for_disconnect_to_quit)
        else:
            self.root.destroy()
            
    def wait_for_disconnect_to_quit(self):
        # (V1.8 代码, 无变化)
        if self.is_connected:
            self.root.after(100, self.wait_for_disconnect_to_quit)
        else:
            self.root.destroy()
            
    # --- 核心线程 (connect/disconnect/toggle_mode V1.6 代码, 无变化) ---

    def connect_thread(self, axis_no: int):
        try:
            self.scanner = create_controller(USE_MOCK, TARGET_DEVICE_NO, axis_no)
            self.scanner.connect()
            status_dict = self.scanner.get_axis_status()
            self.is_connected = True
            self.current_connected_axis = axis_no
            self.gui_queue.put(("connect_success", (axis_no, status_dict)))
        except Exception as e:
            self.scanner = None
            self.is_connected = False
            self.current_connected_axis = -1
            self.gui_queue.put(("connect_fail", e))

    def disconnect_thread(self):
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
            self.gui_queue.put(("disconnect_success", None))
    
    def toggle_mode_thread(self, mode: str):
        try:
            self.scanner.set_axis_mode(mode)
            self.gui_queue.put(("mode_change_success", mode))
        except Exception as e:
            self.gui_queue.put(("mode_change_fail", e))
            
            
    # --- [V2.0 重大修改] 核心扫描逻辑 (条件等待) ---
    def start_scan_thread(self, settle_time):
        """
        [V2.0 修改]
        - 修复了 V1.7 的竞态条件。
        - 在 "single_step_ready" 消息中发送电压信息。
        - [关键] 在单步模式下 (is_paused=True) 跳过 settle_time。
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
                    self.gui_queue.put(("single_step_ready", (i, voltage_at_pause)))
                    
                    # "忙等待"
                    while not self.run_one_step.is_set():
                        if self.stop_requested: 
                            break
                        time.sleep(0.05) 
                    
                    if self.stop_requested: 
                        self.gui_queue.put(("status", "扫描被用户终止。"))
                        break
                    
                    if self.step_direction == 1:
                        self.current_scan_index += 1
                    elif self.step_direction == -1:
                        self.current_scan_index = max(0, self.current_scan_index - 1)
                    pass
                
                # --- 3. 执行扫描点 ---
                if self.current_scan_index >= num_points:
                    break
                    
                i = self.current_scan_index
                voltage = self.scan_points[i]
                
                status_msg = f"点 {i+1}/{num_points}: 设置电压 {voltage:.3f} V"
                self.gui_queue.put(("status", status_msg))

                self.scanner.set_voltage(voltage)
                
                # --- 4. [V2.0 关键修改] 条件等待 ---
                # 只有在 "自动运行" 模式下才执行等待
                if not self.is_paused:
                    start_wait = time.time()
                    while (time.time() - start_wait) < settle_time:
                        if self.stop_requested:
                            break
                        time.sleep(0.05)
                # (如果是暂停模式 (单步)，则跳过等待)
                
                if self.stop_requested:
                     self.gui_queue.put(("status", "扫描被用户终止。"))
                     break

                # --- 5. 更新图表 ---
                self.gui_queue.put(("plot_data", (i, voltage)))

                # --- 6. 推进索引 ---
                if not self.is_paused:
                    self.current_scan_index += 1
                
                # (如果 is_paused = True, 不推进索引, 循环回顶部)

            # --- 循环结束 ---
            if not self.stop_requested:
                self.gui_queue.put(("status", "扫描完成。"))

        except Exception as e:
            self.gui_queue.put(("scan_error", e))
        finally:
            self.gui_queue.put(("scan_finished", None))
            print("扫描子线程已结束。")


# --- 程序入口 (V1.5 最终修正版) ---
if __name__ == "__main__":
    
    app_root = None 
    
    try:
        from ttkthemes import ThemedTk
        app_root = ThemedTk(theme="arc")
        print("--- ttkthemes 'arc' 主题已成功加载。 ---")
        
    except Exception as e:
        print(f"警告: 应用 'arc' 主题失败 ({e})。使用默认主题。")
        app_root = tk.Tk() 

    app = ScanningApp(app_root)
    app_root.mainloop()