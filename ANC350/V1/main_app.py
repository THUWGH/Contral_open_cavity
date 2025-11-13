# main_app.py
import tkinter as tk
from tkinter import ttk, messagebox, font
import threading
import queue
import time
import numpy
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- 导入您的接口和实现 ---
from scanner_interface import IAxisVoltageScanner
from mock_scanner import MockVoltageScanner
from real_scanner import RealVoltageScanner 
# (我们导入您提供的 real_scanner.py 和 mock_scanner.py 中的类)

# -----------------------------------------------------------------
# 这是您在开发和部署之间切换的“唯一”开关
# True:  使用 MockVoltageScanner (用于GUI开发，无需硬件)
# False: 使用 RealVoltageScanner (用于现场部署，控制真实硬件)
USE_MOCK = False 
# -----------------------------------------------------------------

# --- ANC350 配置 (与您的 real_scanner.py 匹配) ---
TARGET_DEVICE_NO = 0 # 目标设备编号 (dev_no)
TARGET_AXIS_NO = 1   # 目标轴 (axis_to_scan)


def create_controller(use_mock_flag: bool, dev_no: int, axis_no: int) -> IAxisVoltageScanner:
    """
    这个“工厂”函数会根据开关，返回一个“符合标准”的控制器。
    """
    if use_mock_flag:
        print("--- 正在创建 MOCK 模拟控制器 ---")
        return MockVoltageScanner(dev_no=dev_no, axis_to_scan=axis_no)
    else:
        print("--- 正在创建 REAL 真实硬件控制器 ---")
        return RealVoltageScanner(dev_no=dev_no, axis_to_scan=axis_no)


class ScanningApp:
    """
    主应用程序类，封装了所有GUI和控制逻辑。
    """
    def __init__(self, root):
        self.root = root
        self.root.title("ANC350 直流电压扫描控制器")
        self.root.geometry("800x600")

        # --- 状态变量 ---
        self.scanner: IAxisVoltageScanner = None
        self.scan_thread = None
        self.is_scan_connected = False # 内部状态，跟踪硬件连接
        
        # --- 线程同步 ---
        self.stop_requested = False             # 用于“终止”
        self.pause_event = threading.Event()    # 用于“暂停/继续”
        self.is_paused = False                  # GUI 状态跟踪
        
        self.plot_x_data = []
        self.plot_y_data = []

        # --- 线程安全队列 ---
        self.gui_queue = queue.Queue()

        # --- 构建GUI ---
        # 
        # [*** 已修正 ***]
        # 必须先调用 _create_widgets() 来创建 self.ax (图表)
        # 然后才能调用 _init_plot() 来清空它。
        #
        self._create_widgets() 
        self._init_plot()      
        #
        # [*** 修正结束 ***]
        #

        # 启动GUI队列检查器
        self.periodic_queue_check()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        """创建所有的GUI组件。"""
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 1. 参数框架 ---
        params_frame = ttk.LabelFrame(main_frame, text="扫描参数", padding="10")
        params_frame.pack(fill=tk.X, expand=False)
        params_frame.columnconfigure(1, weight=1)

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

        # --- 2. 控制框架 ---
        control_frame = ttk.Frame(main_frame, padding="10 0")
        control_frame.pack(fill=tk.X, expand=False)
        
        default_font = font.nametofont("TkDefaultFont")
        button_font = default_font.copy()
        button_font.configure(size=default_font.cget("size") + 2)
        style = ttk.Style()
        style.configure("Accent.TButton", font=button_font)

        self.start_button = ttk.Button(control_frame, text="开始扫描", 
                                       command=self.on_start_scan, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # [新增] 暂停/继续 按钮
        self.pause_button = ttk.Button(control_frame, text="暂停", 
                                      command=self.on_pause_toggle, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # [修改] 终止 按钮
        self.stop_button = ttk.Button(control_frame, text="终止扫描", 
                                      command=self.on_stop_scan, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # --- 3. 绘图框架 ---
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.fig = plt.Figure(figsize=(5, 4), dpi=100)
        
        # [*** 修正 ***]
        # self.ax 在这里被创建
        self.ax = self.fig.add_subplot(111) 
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- 4. 状态栏 ---
        self.status_var = tk.StringVar()
        self.status_var.set("空闲。")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding="5 2")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)


    def _init_plot(self):
        """初始化/重置绘图区域。"""
        self.plot_x_data.clear()
        self.plot_y_data.clear()
        self.ax.clear()
        
        # [修改] 添加中文字体解决方案
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei'] # 使用黑体
            plt.rcParams['axes.unicode_minus'] = False # 解决负号显示问题
        except Exception:
            print("警告: 未找到 'SimHei' 字体，图表可能显示方框。")
            
        self.ax.set_title("实时电压扫描")
        self.ax.set_xlabel("扫描点序号")
        self.ax.set_ylabel("设定电压 (V)")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], 'bo-') # 'bo-' = blue circle markers
        self.canvas.draw()
        
    def periodic_queue_check(self):
        """
        在GUI主线程中周期性地检查队列，并安全地更新GUI。
        """
        try:
            while not self.gui_queue.empty():
                msg_type, data = self.gui_queue.get_nowait()
                
                if msg_type == "status":
                    self._update_status(data)
                elif msg_type == "plot_data":
                    self._update_plot(data[0], data[1])
                # [新增] 允许子线程启用暂停按钮
                elif msg_type == "enable_controls":
                    self.pause_button.config(state=tk.NORMAL)
                    self.stop_button.config(state=tk.NORMAL)
                elif msg_type == "scan_finished":
                    self._handle_scan_finished()
                elif msg_type == "scan_error":
                    self._handle_scan_error(data)
        finally:
            self.root.after(100, self.periodic_queue_check) # 100ms后再次调用自己
            
    # --- GUI 更新方法 (只能在主线程中调用) ---

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
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="暂停")
        self.stop_button.config(state=tk.DISABLED)
        self.scan_thread = None
        self.is_paused = False

    def _handle_scan_error(self, error: Exception):
        self._handle_scan_finished() # 结束时的状态重置是一样的
        error_msg = f"扫描出错: {error}"
        self._update_status(error_msg)
        print(f"--- 错误详情 --- \n{error}")
        messagebox.showerror("扫描错误", error_msg)

    # --- 按钮回调 ---

    def on_start_scan(self):
        """
        “开始扫描”按钮的回调。
        """
        try:
            params = {key: entry.get() for key, entry in self.entries.items()}
            start_v = float(params["start_v"])
            end_v = float(params["end_v"])
            num_points = int(params["num_points"])
            settle_time = float(params["settle_time"])
            if num_points < 2:
                raise ValueError("点数必须至少为 2")
        except ValueError as e:
            messagebox.showerror("参数错误", f"无效的输入: {e}")
            return
        
        # [修改] 重置所有状态
        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED, text="暂停") # 初始禁用
        self.stop_button.config(state=tk.DISABLED) # 初始禁用
        
        self.stop_requested = False
        self.is_paused = False
        self.pause_event.set() # 设置为 "绿灯" (非暂停状态)
        
        # 您截图的地方在这里，它是正确的
        self._init_plot()
        
        # 启动扫描子线程
        thread_args = (start_v, end_v, num_points, settle_time)
        self.scan_thread = threading.Thread(target=self.start_scan_thread, args=thread_args)
        self.scan_thread.start()

    # [新增] 暂停/继续 按钮的回调
    def on_pause_toggle(self):
        """
        切换暂停和继续状态。
        """
        if self.is_paused:
            # --- 当前是暂停状态，我们要继续 ---
            self.is_paused = False
            self.pause_event.set() # 亮起 "绿灯"
            self.pause_button.config(text="暂停")
            self._update_status("正在继续...")
        else:
            # --- 当前是运行状态，我们要暂停 ---
            self.is_paused = True
            self.pause_event.clear() # 亮起 "红灯"
            self.pause_button.config(text="继续")
            self._update_status("正在暂停... (将在当前点完成后暂停)")

    # [修改] 终止 按钮的回调
    def on_stop_scan(self):
        """
        “终止扫描”按钮的回调。
        """
        self.stop_requested = True
        self.pause_event.set() # [关键] 必须解除暂停，以便线程能检查 stop_requested 标志
        
        self.stop_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED)
        self._update_status("正在终止...")

    def on_closing(self):
        """处理窗口关闭事件。"""
        if self.scan_thread and self.scan_thread.is_alive():
            if messagebox.askyesno("扫描正在进行", "扫描正在进行中，您确定要退出吗？"):
                self.on_stop_scan()
                self.root.after(500, self.wait_for_thread_and_quit)
            else:
                return # 取消退出
        else:
            self.root.destroy()
            
    def wait_for_thread_and_quit(self):
        """辅助函数，等待子线程结束后再关闭窗口。"""
        if self.scan_thread and self.scan_thread.is_alive():
            self.root.after(100, self.wait_for_thread_and_quit)
        else:
            self.root.destroy()
            
    # --- 核心扫描逻辑 (在子线程中运行) ---

    def start_scan_thread(self, start_v, end_v, num_points, settle_time):
        """
        这是在“子线程”中运行的核心扫描逻辑。
        """
        self.is_scan_connected = False
        try:
            scan_points = numpy.linspace(start_v, end_v, num_points)
            self.scanner = create_controller(USE_MOCK, TARGET_DEVICE_NO, TARGET_AXIS_NO)
            
            # --- 连接仪器 ---
            self.gui_queue.put(("status", f"正在连接设备 {TARGET_DEVICE_NO} (轴 {TARGET_AXIS_NO})..."))
            self.scanner.connect()
            self.is_scan_connected = True 
            
            # [修改] 仪器连接成功后，才启用暂停和终止按钮
            self.gui_queue.put(("enable_controls", None))
            self.gui_queue.put(("status", "连接成功，开始扫描..."))

            # --- 主循环 ---
            for i, voltage in enumerate(scan_points):
                
                # --- [新增] 暂停点 ---
                # 线程将在此处“卡住”，直到 pause_event 为 "绿灯" (set)
                self.pause_event.wait() 

                # --- 终止点 ---
                if self.stop_requested:
                    self.gui_queue.put(("status", "扫描被用户终止。"))
                    break
                
                # --- 正常扫描逻辑 ---
                status_msg = f"点 {i+1}/{num_points}: 设置电压 {voltage:.3f} V"
                self.gui_queue.put(("status", status_msg))

                self.scanner.set_voltage(voltage)
                
                # 等待稳定
                # [修改] 我们将 time.sleep 分成小块
                # 这样即使在稳定期间，也能快速响应“终止”信号
                start_wait = time.time()
                while (time.time() - start_wait) < settle_time:
                    if self.stop_requested:
                        break # 提前跳出等待
                    time.sleep(0.05) # 检查的最小间隔
                
                if self.stop_requested:
                     self.gui_queue.put(("status", "扫描被用户终止。"))
                     break

                # --- 未来扩展点 (光谱仪) ---
                # self.gui_queue.put(("status", f"点 {i+1}/{num_points}: 正在采集光谱..."))
                # data = self.spectrometer.acquire_data() 
                # ... (检查 stop_requested)
                
                # 更新图表
                self.gui_queue.put(("plot_data", (i, voltage)))

            # 扫描循环正常结束
            if not self.stop_requested:
                self.gui_queue.put(("status", "扫描完成。"))

        except Exception as e:
            # 捕获所有可能的错误 (包括硬件错误)
            self.gui_queue.put(("scan_error", e))
        finally:
            # --- 收尾工作 ---
            if self.scanner and self.is_scan_connected:
                self.gui_queue.put(("status", "正在断开硬件连接..."))
                self.scanner.disconnect()
                self.is_scan_connected = False
            
            # 无论如何，都通知GUI扫描已结束（以重置按钮状态）
            self.gui_queue.put(("scan_finished", None))
            print("扫描子线程已结束。")


# --- 程序入口 ---
if __name__ == "__main__":
    app_root = tk.Tk()
    
    # --- 设置 ttk 主题 (可选, 但能让界面更好看) ---
    try:
        from ttkthemes import ThemedTk
        app_root = ThemedTk(theme="arc")
    except ImportError:
        print("未找到 'ttkthemes' 库, 使用默认主题。 (pip install ttkthemes 可选)")
        # [*** 修正 ***]
        # 当 ttkthemes 失败时，我们必须确保 app_root 仍然是一个有效的 tk.Tk() 对象
        # 之前的代码在 except 块中什么也没做，导致 app_root 可能不是一个窗口。
        # 但在这个版本中，app_root = tk.Tk() 在 try 块之前被调用，所以是安全的。
        pass 

    app = ScanningApp(app_root)
    app_root.mainloop()