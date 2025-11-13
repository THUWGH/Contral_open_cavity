# main_app.py (V3.1 - GUI 插件化)
import tkinter as tk
from tkinter import ttk, messagebox, font
import queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os # [V3.1] 新增

# --- [V3.1] 导入新的 GUI 插件 ---
import gui_plugins.anc350_widget as anc_gui

# --- [V3.0] 导入扫描引擎 ---
from scan_engine import ScanEngine

# -----------------------------------------------------------------
USE_MOCK = True

TARGET_DEVICE_NO = 0
# -----------------------------------------------------------------


class ScanningApp:
    """
    主应用程序类 (V3.1 - 视图层)
    - _create_widgets 方法已被清理，
      ANC350 相关的控件被移至 gui_plugins/anc350_widget.py
    """
    def __init__(self, root):
        self.root = root
        self.root.title("ANC350 直流电压扫描控制器 (V3.1 - 插件化)")
        self.root.geometry("800x600")

        self.engine = ScanEngine()
        self.engine.set_config(USE_MOCK, TARGET_DEVICE_NO)
        
        self.gui_queue = self.engine.gui_queue
        
        self.is_connected_state = False
        self.is_paused_state = False
        
        self.plot_x_data = []
        self.plot_y_data = []

        # --- [V3.1] 这些变量必须在 _create_widgets 之前定义 ---
        # --- 因为插件函数会向它们填充内容 ---
        self.axis_mode_var = tk.StringVar(value="OFF")
        self.entries = {} # 插件将填充此字典
        
        # [V3.1] 确保插件目录存在
        os.makedirs('gui_plugins', exist_ok=True)

        self._create_widgets()
        self._init_plot()

        self.periodic_queue_check()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        """ (V3.1 重大修改) """
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- [V3.1] 1. & 2. ANC350 插件 ---
        # (原 V3.0 中的 "连接框架" 和 "参数框架" 已移出)
        # 我们调用插件函数，它会创建控件，并将它们
        # (如 axis_combo, entries) 附加到 'self' (app) 实例上。
        anc_plugin_frame = anc_gui.create_anc_frame(main_frame, self)
        anc_plugin_frame.pack(fill=tk.X, expand=False)


        # --- 3. 控制框架 ---
        # (此部分保持不变)
        control_frame = ttk.Frame(main_frame, padding="10 0")
        control_frame.pack(fill=tk.X, expand=False)
        default_font = font.nametofont("TkDefaultFont")
        button_font = default_font.copy()
        button_font.configure(size=default_font.cget("size") + 2)
        style = ttk.Style()
        style.configure("Accent.TButton", font=button_font)
        
        self.start_button = ttk.Button(control_frame, text="开始扫描",
                                       command=self.handle_start_scan, style="Accent.TButton", state=tk.DISABLED)
        self.start_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.pause_button = ttk.Button(control_frame, text="暂停",
                                       command=self.handle_pause_toggle, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.stop_button = ttk.Button(control_frame, text="终止扫描",
                                      command=self.handle_stop_scan, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # --- 4. 单步控制框架 ---
        # (此部分保持不变)
        step_frame = ttk.Frame(main_frame, padding="10 0")
        step_frame.pack(fill=tk.X, expand=False)
        
        self.prev_button = ttk.Button(step_frame, text="< 上一个点",
                                      command=self.engine.step_prev, state=tk.DISABLED)
        self.prev_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.next_button = ttk.Button(step_frame, text="下一个点 >",
                                      command=self.engine.step_next, state=tk.DISABLED)
        self.next_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # --- 5. 绘图框架 ---
        # (此部分保持不变)
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- 6. 状态栏 ---
        # (此部分保持不变)
        self.status_var = tk.StringVar()
        self.status_var.set("空闲。请选择轴并连接。")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding="5 2")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)


    # ==================================================================
    #
    #   V3.0 中的所有其他方法 (_init_plot, periodic_queue_check,
    #   _handle_... 系列, handle_... 系列, on_closing)
    #   保持完全不变。
    #
    #   因为插件函数 create_anc_frame 已经将 self.axis_combo,
    #   self.connect_button, self.entries 等控件正确地
    #   附加到了 'self' 实例上，所以 handle_connect_toggle
    #   和 handle_start_scan 等方法仍然可以正常工作。
    #
    # ==================================================================
    
    def _init_plot(self):
        """(V3.0 代码, 无变化)"""
        self.plot_x_data.clear()
        self.plot_y_data.clear()
        self.ax.clear()
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei']
            plt.rcParams['axes.unicode_minus'] = False
        except Exception:
            print("警告: 未找到 'SimHei' 字体，图表可能显示方框。")
        self.ax.set_title(f"实时电压扫描 (V3.1)")
        self.ax.set_xlabel("扫描点序号")
        self.ax.set_ylabel("设定电压 (V)")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], 'bo-')
        self.canvas.draw()
        
    def periodic_queue_check(self):
        """(V3.0 代码, 无变化)"""
        try:
            while not self.gui_queue.empty():
                msg_type, data = self.gui_queue.get_nowait()
                
                if msg_type == "connect_success":
                    self._handle_connect_success(data[0], data[1], data[2]) 
                elif msg_type == "connect_fail":
                    self._handle_connect_fail(data)
                elif msg_type == "disconnect_success":
                    self._handle_disconnect_success()
                    
                elif msg_type == "mode_change_success":
                    mode = data
                    self._update_status(f"轴模式已设为: {mode}")
                    self._set_radio_buttons_state(tk.NORMAL)
                elif msg_type == "mode_change_fail":
                    self._handle_scan_error(data)
                    self._set_radio_buttons_state(tk.NORMAL)
                
                elif msg_type == "single_step_ready":
                    index, voltage = data
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
            
    # --- GUI 辅助函数 (V3.0 代码, 无变化) ---
    
    def _set_radio_buttons_state(self, state):
        # (插件已将这些控件附加到 self)
        self.mode_rb_off.config(state=state)
        self.mode_rb_open.config(state=state)
        self.mode_rb_closed.config(state=state)

    # --- GUI 状态机函数 (V3.0 代码, 无变化) ---
    
    def _handle_connect_success(self, axis_no, status_dict, current_mode):
        self.is_connected_state = True
        self.connect_button.config(text=f"断开 (Disconnect Axis {axis_no})", state=tk.NORMAL)
        self.axis_combo.config(state=tk.DISABLED)

        is_phys_connected = status_dict.get("physically_connected", False)
        is_error = status_dict.get("error_detected", False)
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
        self.axis_mode_var.set(current_mode) 
        mode_text = f"{current_mode}"
        self._set_radio_buttons_state(tk.NORMAL)
        self._update_status(f"轴 {axis_no} 连接成功。当前模式: {mode_text}。")
        self._init_plot()
        self.ax.set_title(f"实时电压扫描 (Axis {axis_no})")

    def _handle_connect_fail(self, error):
        self.is_connected_state = False
        self.connect_button.config(text="连接 (Connect)", state=tk.NORMAL)
        self.axis_combo.config(state=tk.NORMAL)
        self._handle_disconnect_success() 
        error_msg = f"连接失败: {error}"
        self._update_status(error_msg)
        print(f"--- 错误详情 --- \n{error}")
        messagebox.showerror("连接错误", error_msg)

    def _handle_disconnect_success(self):
        self.is_connected_state = False
        self.connect_button.config(text="连接 (Connect)", state=tk.NORMAL)
        self.start_button.config(state=tk.DISABLED)
        self.axis_combo.config(state=tk.NORMAL)
        self._set_radio_buttons_state(tk.DISABLED)
        self.axis_mode_var.set("OFF")
        self._update_status("空闲。")

    # --- GUI 更新方法 (V3.0 代码, 无变化) ---

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
        self.prev_button.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)
        
        self.connect_button.config(state=tk.NORMAL)
        self._set_radio_buttons_state(tk.NORMAL)
        self.axis_combo.config(state=tk.DISABLED)
        
        self.is_paused_state = False
        
        if self.is_connected_state:
             mode = self.axis_mode_var.get()
             self._update_status(f"扫描完成。仍连接 (模式: {mode})。")

    def _handle_scan_error(self, error: Exception):
        self._handle_scan_finished()
        error_msg = f"操作出错: {error}"
        self._update_status(error_msg)
        print(f"--- 错误详情 --- \n{error}")
        messagebox.showerror("错误", error_msg)
        if not self.is_connected_state:
            self._handle_disconnect_success()


    # --- 按钮回调 (V3.0 代码, 无变化) ---
    
    def handle_connect_toggle(self):
        if self.is_connected_state:
            self.connect_button.config(text="断开中...", state=tk.DISABLED)
            self.start_button.config(state=tk.DISABLED)
            self._set_radio_buttons_state(tk.DISABLED)
            self.engine.disconnect_anc350()
        else:
            try:
                axis_no = int(self.axis_combo.get())
            except ValueError:
                messagebox.showerror("错误", "无效的轴号。")
                return
            
            self.connect_button.config(text="连接中...", state=tk.DISABLED)
            self.axis_combo.config(state=tk.DISABLED)
            self.engine.connect_anc350(axis_no)
            
    def handle_set_mode(self):
        try:
            mode = self.axis_mode_var.get()
            self._update_status(f"正在设置 {mode} 模式...")
            self._set_radio_buttons_state(tk.DISABLED)
            self.engine.set_anc_mode(mode)
        except Exception as e:
            self._handle_scan_error(e)
            self._set_radio_buttons_state(tk.NORMAL)

    def handle_start_scan(self):
        try:
            params = {key: entry.get() for key, entry in self.entries.items()}
            float(params["start_v"])
            float(params["end_v"])
            int(params["num_points"])
            float(params["settle_time"])
        except ValueError as e:
            messagebox.showerror("参数错误", f"无效的输入: {e}")
            return
        
        self.start_button.config(state=tk.DISABLED)
        self.connect_button.config(state=tk.DISABLED)
        self._set_radio_buttons_state(tk.DISABLED)
        self.is_paused_state = False
        self.engine.start_scan(params)

    def handle_pause_toggle(self):
        if self.is_paused_state:
            self.is_paused_state = False
            self.pause_button.config(text="暂停")
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)
        else:
            self.is_paused_state = True
            self.pause_button.config(text="继续")
        self.engine.pause_toggle()

    def handle_stop_scan(self):
        self.stop_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED)
        self.prev_button.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)
        self.engine.stop_scan()

    def on_closing(self):
        """ (V3.0 代码, 无变化) """
        if messagebox.askyesno("退出", "您确定要退出程序吗？\n(将自动停止扫描并断开硬件连接)"):
            self.engine.shutdown()
            self.root.after(100, self.wait_for_engine_shutdown)
            
    def wait_for_engine_shutdown(self):
        """ (V3.0 代码, 无变化) """
        if self.engine.is_shutting_down():
            self.root.after(100, self.wait_for_engine_shutdown)
        else:
            print("[GUI] 引擎已关闭，销毁窗口。")
            self.root.destroy()
            

# --- 程序入口 (V3.0 代码, 无变化) ---
if __name__ == "__main__":
    
    app_root = None 
    
    try:
        from ttkthemes import ThemedTk
        app_root = ThemedTk(theme="arc")
        print("--- ttkthemes 'arc' 主题已成功加载。 ---")
        
    except Exception as e:
        print(f"警告: 应用 'arc' 题失败 ({e})。使用默认主题。")
        app_root = tk.Tk() 

    app = ScanningApp(app_root)
    app_root.mainloop()