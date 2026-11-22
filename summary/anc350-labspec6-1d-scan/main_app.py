# main_app.py (V8.0 - AutoSave & Export Tools)
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import sys
import numpy as np
from datetime import datetime

# 确保你的插件目录下有这些文件
import gui_plugins.anc350_widget as anc_gui
import gui_plugins.spectrometer_widget as spec_gui
from scan_engine import ScanEngine

# 配置 
USE_MOCK = False
TARGET_DEVICE_NO = 0

class ScanningApp:
    def __init__(self, root):
        self.root = root
        self.root.title("多维扫描控制平台 (V8.0 - Pro)")
        self.root.geometry("1200x900") 

        self.engine = ScanEngine()
        self.engine.set_config(USE_MOCK, TARGET_DEVICE_NO)
        self.gui_queue = self.engine.gui_queue
        
        self.default_save_path = os.path.join(os.getcwd(), "Data")
        self.entries = {}
        self.axis_mode_var = tk.StringVar(value="OFF")
        
        # --- 绘图与数据状态 ---
        self.scan_x_history = [] 
        self.scan_y_history = [] 
        
        # 2D Mapping 专用状态
        self.map_data = None          # 强度矩阵
        self.current_scan_vals = None # Y轴坐标 (电压)
        self.current_wavelengths = None # X轴坐标 (波长)
        
        self.im_map = None         
        self.cbar = None           
        
        self._create_layout()
        self._set_ui_state('idle')
        self.periodic_queue_check()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_layout(self):
        # 主容器：PanedWindow
        self.paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- 左侧控制区 ---
        left_outer_frame = ttk.Frame(self.paned_window, width=420)
        self.paned_window.add(left_outer_frame, weight=0)
        
        # 滚动条逻辑
        canvas = tk.Canvas(left_outer_frame, width=400, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_outer_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        def _configure_canvas(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _configure_canvas)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定滚轮
        def _on_mousewheel(event):
            if event.delta: canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            elif event.num == 4: canvas.yview_scroll(-1, "units")
            elif event.num == 5: canvas.yview_scroll(1, "units")
        self.root.bind_all("<MouseWheel>", _on_mousewheel)
        self.root.bind_all("<Button-4>", _on_mousewheel) # Linux
        self.root.bind_all("<Button-5>", _on_mousewheel)

        # 加载插件
        anc_gui.create_anc_frame(self.scrollable_frame, self).pack(fill=tk.X, pady=5, padx=5)
        spec_gui.create_spec_frame(self.scrollable_frame, self).pack(fill=tk.X, pady=5, padx=5)
        self._create_scan_control(self.scrollable_frame)
        
        # --- 右侧绘图区 ---
        right_panel = ttk.Frame(self.paned_window)
        self.paned_window.add(right_panel, weight=1) 
        
        self._init_plots(right_panel)
        
        # 底部状态栏
        self.status_var = tk.StringVar(value="系统就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN).pack(side=tk.BOTTOM, fill=tk.X)

    def _create_scan_control(self, parent):
        frame = ttk.LabelFrame(parent, text="扫描执行 (Execution)", padding="10")
        frame.pack(fill=tk.X, pady=10, side=tk.BOTTOM)
        
        self.var_pause_first = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="采集首点后暂停 (Pause after 1st)", variable=self.var_pause_first).pack(anchor=tk.W)
        
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=5)
        self.btn_preview = ttk.Button(row, text="预览路径", command=self.handle_preview)
        self.btn_preview.pack(side=tk.LEFT, padx=2)
        
        self.btn_start = ttk.Button(row, text="开始扫描", command=self.handle_start_scan)
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.btn_stop = ttk.Button(row, text="终止", command=self.handle_stop_scan)
        self.btn_stop.pack(side=tk.RIGHT, padx=2)
        
        self.btn_pause = ttk.Button(frame, text="暂停 / 继续", command=self.handle_pause_toggle)
        self.btn_pause.pack(fill=tk.X, pady=2)

    def _init_plots(self, parent):
        # === 1. 上半部分：Scan Monitor ===
        top_frame = ttk.Frame(parent)
        top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.fig_scan = plt.Figure(figsize=(6, 3.5), dpi=100)
        self.ax_scan = self.fig_scan.add_subplot(111)
        self.ax_scan.set_title("Scan Monitor")
        self.ax_scan.set_ylabel("Voltage (V)")
        self.ax_scan.grid(True)
        
        self.scat_preview = self.ax_scan.scatter([], [], c='gray', marker='o', facecolors='none', label='Plan')
        self.scat_history = self.ax_scan.scatter([], [], c='blue', marker='.', label='Acquired')
        self.scat_current = self.ax_scan.scatter([], [], c='red', s=100, marker='+', label='Current')
        self.ax_scan.legend(loc='upper right')

        self.canvas_scan = FigureCanvasTkAgg(self.fig_scan, master=top_frame)
        self.canvas_scan.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # === 2. 下半部分：Tab 选项卡 ===
        self.tab_control = ttk.Notebook(parent)
        self.tab_control.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(5, 0))

        # --- Tab 1: 实时 1D 光谱 ---
        self.tab1 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab1, text='实时光谱 (1D Live)')

        self.fig_spec = plt.Figure(figsize=(6, 3.5), dpi=100)
        self.ax_spec = self.fig_spec.add_subplot(111)
        self.ax_spec.set_title("Live Spectrum")
        self.ax_spec.set_xlabel("Wavelength (nm)")
        self.ax_spec.set_ylabel("Intensity")
        self.ax_spec.grid(True)
        self.line_spec, = self.ax_spec.plot([], [], 'r-', linewidth=1)

        self.canvas_spec = FigureCanvasTkAgg(self.fig_spec, master=self.tab1)
        self.canvas_spec.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # --- Tab 2: 扫描成像 2D (带工具栏) ---
        self.tab2 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab2, text='扫描成像 (2D Map)')

        # >> 2.1 右侧工具栏 <<
        toolbar_frame = ttk.Frame(self.tab2, padding=5, relief=tk.RIDGE)
        toolbar_frame.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(toolbar_frame, text="Export Tools", font=("Arial", 9, "bold")).pack(pady=(0, 10))
        
        ttk.Button(toolbar_frame, text="保存图片\n(Standard)", width=12, command=self.handle_save_map_std).pack(pady=5)
        ttk.Button(toolbar_frame, text="自定义导出\n(Custom)", width=12, command=self.handle_save_map_custom).pack(pady=5)
        ttk.Separator(toolbar_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(toolbar_frame, text="Save Data", font=("Arial", 9, "bold")).pack(pady=(0, 5))
        ttk.Button(toolbar_frame, text="手动保存数据\n(TXT Matrix)", width=12, command=self.auto_save_2d_data).pack(pady=5)

        # >> 2.2 左侧绘图区 <<
        plot_frame_2d = ttk.Frame(self.tab2)
        plot_frame_2d.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.fig_map = plt.Figure(figsize=(6, 3.5), dpi=100)
        self.ax_map = self.fig_map.add_subplot(111)
        self.ax_map.set_title("2D Hyperspectral Map")
        self.ax_map.set_xlabel("Wavelength (nm)")
        self.ax_map.set_ylabel("Voltage / Step (V)")
        
        self.im_map = None 
        self.canvas_map = FigureCanvasTkAgg(self.fig_map, master=plot_frame_2d)
        self.canvas_map.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # --- 核心逻辑 ---

    def handle_preview(self):
        try:
            sv = float(self.entries["start_v"].get())
            ev = float(self.entries["end_v"].get())
            np_pts = int(self.entries["num_points"].get())
            
            pts = np.linspace(sv, ev, np_pts)
            idxs = np.arange(np_pts)
            
            preview_data = np.column_stack((idxs, pts))
            self.scat_preview.set_offsets(preview_data)
            
            self.ax_scan.set_xlim(-0.5, np_pts - 0.5)
            v_min, v_max = min(sv, ev), max(sv, ev)
            margin = (v_max - v_min) * 0.1 if v_max != v_min else 1.0
            self.ax_scan.set_ylim(v_min - margin, v_max + margin)
            
            self.canvas_scan.draw()
        except Exception as e:
            messagebox.showerror("参数错误", f"预览失败: {e}")

    def handle_start_scan(self):
        try:
            # 收集参数
            params = {k: v.get() for k, v in self.entries.items()}
            params["int_time"] = self.spec_int_time_var.get()
            params["avg"] = self.spec_avg_var.get()
            
            save_cfg = {
                "save_path": self.spec_save_path_var.get(),
                "prefix": self.spec_prefix_var.get(),
                "metadata": self.spec_metadata_text.get("1.0", tk.END).strip()
            }
            if not os.path.exists(save_cfg["save_path"]):
                os.makedirs(save_cfg["save_path"], exist_ok=True)
            
            # 复位图表
            self.scan_x_history = []
            self.scan_y_history = []
            self.scat_history.set_offsets(np.c_[[],[]])
            self.handle_preview() 
            
            # 启动引擎
            self.engine.start_scan(params, save_cfg, self.var_pause_first.get())
            
        except Exception as e:
            messagebox.showerror("无法启动", str(e))

    def auto_save_2d_data(self):
        """
        自动保存完整的 2D 数据矩阵。
        格式：Tab分隔的TXT
        Row 0: 0, Wavelengths...
        Row 1..N: Voltage, Intensity...
        """
        if self.map_data is None or self.current_wavelengths is None:
            # 如果是手动调用且无数据，提示
            # print("No data to save.") 
            return

        try:
            # 确定保存路径
            base_dir = self.spec_save_path_var.get()
            prefix = self.spec_prefix_var.get()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_2DMapMatrix_{timestamp}.txt"
            filepath = os.path.join(base_dir, filename)

            # 准备数据
            # 1. 头部: [0, wl1, wl2, ...]
            header_row = np.insert(self.current_wavelengths, 0, 0)
            
            # 2. 只有已经扫描过的行才保存
            # 通过判断 map_data 是否全为 NaN 来切片
            valid_mask = ~np.isnan(self.map_data).all(axis=1)
            valid_data = self.map_data[valid_mask]
            valid_y = self.current_scan_vals[valid_mask]
            
            # 拼接 [Y, Data]
            data_block = np.column_stack((valid_y, valid_data))
            
            # 3. 最终堆叠
            final_matrix = np.vstack((header_row, data_block))
            
            # 保存
            np.savetxt(filepath, final_matrix, fmt='%.6f', delimiter='\t')
            
            msg = f"2D数据已自动保存:\n{filename}"
            print(msg)
            self.status_var.set(msg.replace("\n", " "))
            
        except Exception as e:
            print(f"Auto save failed: {e}")
            messagebox.showerror("自动保存错误", str(e))

    # --- 绘图导出工具 ---
    def handle_save_map_std(self):
        """标准保存：当前目录，高清PNG"""
        if self.map_data is None: return
        try:
            init_dir = self.spec_save_path_var.get()
            f = filedialog.asksaveasfilename(
                initialdir=init_dir,
                title="Save 2D Map",
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png")]
            )
            if f:
                self.fig_map.savefig(f, dpi=300, bbox_inches='tight')
                messagebox.showinfo("Saved", f"File saved: {os.path.basename(f)}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def handle_save_map_custom(self):
        """自定义保存弹窗"""
        if self.map_data is None: return
        
        win = tk.Toplevel(self.root)
        win.title("Export Settings")
        win.geometry("250x200")
        
        ttk.Label(win, text="DPI:").pack(pady=5)
        var_dpi = tk.IntVar(value=300)
        ttk.Entry(win, textvariable=var_dpi).pack()
        
        ttk.Label(win, text="Format:").pack(pady=5)
        var_fmt = tk.StringVar(value="pdf")
        ttk.Combobox(win, textvariable=var_fmt, values=["png", "pdf", "svg", "jpg"]).pack()
        
        def _do_save():
            try:
                init_dir = self.spec_save_path_var.get()
                fmt = var_fmt.get()
                f = filedialog.asksaveasfilename(
                    initialdir=init_dir,
                    defaultextension=f".{fmt}",
                    filetypes=[(f"{fmt.upper()}", f"*.{fmt}")]
                )
                if f:
                    self.fig_map.savefig(f, dpi=var_dpi.get(), format=fmt, bbox_inches='tight')
                    win.destroy()
                    messagebox.showinfo("Saved", "Export successful.")
            except Exception as e: messagebox.showerror("Error", str(e))
            
        ttk.Button(win, text="Save", command=_do_save).pack(pady=15)

    def periodic_queue_check(self):
        try:
            while not self.gui_queue.empty():
                msg, data = self.gui_queue.get_nowait()
                
                if msg == "connect_anc_success":
                    self.status_var.set(f"ANC350 已连接 (Axis {data[0]})")
                    self.connect_button.config(text="断开")
                    self.axis_mode_var.set(data[2])
                    self._set_ui_state('idle')
                elif msg == "disconnect_anc_success":
                    self.connect_button.config(text="连接")
                    self.axis_mode_var.set("OFF")
                    self._set_ui_state('idle')
                    self._set_mode_btns(tk.DISABLED)
                elif msg == "connect_spec_success":
                    self.spec_connect_btn.config(text="已连接", state=tk.DISABLED)
                elif msg == "disconnect_spec_success":
                    self.spec_connect_btn.config(text="连接光谱仪", state=tk.NORMAL)
                
                # --- 扫描流程控制 ---
                elif msg == "scan_started": 
                    self._set_ui_state('scanning')
                    # 初始化绘图数据
                    try:
                        sv = float(self.entries["start_v"].get())
                        ev = float(self.entries["end_v"].get())
                        np_pts = int(self.entries["num_points"].get())
                        self.current_scan_vals = np.linspace(sv, ev, np_pts)
                        self.map_data = None 
                        self.current_wavelengths = None
                        
                        # 清空图表
                        self.ax_map.clear()
                        self.ax_map.set_title("2D Hyperspectral Map")
                        self.ax_map.set_xlabel("Wavelength (nm)")
                        self.ax_map.set_ylabel("Voltage / Step (V)")
                        self.im_map = None
                        self.canvas_map.draw()
                    except: pass

                elif msg == "scan_finished": 
                    self._set_ui_state('idle')
                    # [自动保存]
                    self.auto_save_2d_data()

                elif msg == "scan_error": 
                    messagebox.showerror("错误", str(data))
                    self._set_ui_state('idle')
                elif msg == "status": 
                    self.status_var.set(str(data))
                    if "暂停" in str(data): self._set_ui_state('paused')
                    elif "继续" in str(data): self._set_ui_state('scanning')

                # --- 绘图更新 ---
                elif msg == "scan_progress": 
                    idx, v = data
                    self.scat_current.set_offsets([[idx, v]])
                    self.canvas_scan.draw_idle()
                    
                elif msg == "plot_data_saved": 
                    idx, v, wl, inten = data
                    self.current_wavelengths = wl # 保存波长信息
                    
                    # 1. 更新 Monitor
                    self.scan_x_history.append(idx)
                    self.scan_y_history.append(v)
                    self.scat_history.set_offsets(np.column_stack((self.scan_x_history, self.scan_y_history)))
                    self.canvas_scan.draw_idle()
                    
                    # 2. 更新 1D
                    self.line_spec.set_data(wl, inten)
                    self.ax_spec.relim(); self.ax_spec.autoscale_view()
                    if self.tab_control.select() == str(self.tab1):
                        self.canvas_spec.draw_idle()

                    # 3. 更新 2D Map
                    if self.map_data is None:
                        num_steps = len(self.current_scan_vals)
                        num_pixels = len(wl)
                        self.map_data = np.full((num_steps, num_pixels), np.nan)
                        
                        extent = [wl[0], wl[-1], self.current_scan_vals[0], self.current_scan_vals[-1]]
                        self.im_map = self.ax_map.imshow(
                            self.map_data, 
                            aspect='auto', origin='lower', cmap='viridis',
                            extent=extent, interpolation='nearest'
                        )
                        self.fig_map.colorbar(self.im_map, ax=self.ax_map, label='Intensity')
                    
                    if idx < len(self.map_data):
                        self.map_data[idx, :] = inten
                        
                        if self.tab_control.select() == str(self.tab2):
                            self.im_map.set_data(self.map_data)
                            valid_data = self.map_data[~np.isnan(self.map_data)]
                            if len(valid_data) > 0:
                                self.im_map.set_clim(np.min(valid_data), np.max(valid_data))
                            self.canvas_map.draw_idle()
                    
                elif msg == "plot_live_only": 
                    wl, inten = data
                    self.line_spec.set_data(wl, inten)
                    self.ax_spec.relim(); self.ax_spec.autoscale_view()
                    self.canvas_spec.draw_idle()

        finally:
            self.root.after(100, self.periodic_queue_check)

    # --- 其他 Helper ---
    def handle_connect_toggle(self):
        if self.engine.is_scanner_connected: self.engine.disconnect_all()
        else: 
            try: self.engine.connect_anc350(int(self.axis_combo.get()))
            except: pass
    def handle_spec_connect_toggle(self): self.engine.connect_spectrometer()
    def handle_pause_toggle(self): self.engine.pause_toggle()
    def handle_stop_scan(self): self.engine.stop_scan()
    def handle_set_mode(self): self.engine.set_anc_mode(self.axis_mode_var.get())
    def handle_spec_set_params(self):
        try:
            t = self.spec_int_time_var.get()
            avg = self.spec_avg_var.get()
            if self.engine.spectrometer:
                self.engine.spectrometer.set_parameters(t, avg)
                self.engine.int_time = t
                self.engine.avg_cnt = avg
                messagebox.showinfo("成功", f"参数已发送")
            else: messagebox.showwarning("警告", "光谱仪未连接")
        except Exception as e: messagebox.showerror("错误", str(e))
    def handle_step_prev(self): self.engine.manual_move_step(-1)
    def handle_step_next(self): self.engine.manual_move_step(1)
    def handle_manual_acquire(self): 
        try:
            self.engine.int_time = self.spec_int_time_var.get()
            self.engine.avg_cnt = self.spec_avg_var.get()
        except: pass
        self.engine.manual_acquire()
    def handle_manual_save(self):
        f = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if f: self.engine.manual_save_idle(f)

    def _set_ui_state(self, state):
        if state == 'idle':
            self.connect_button.config(state=tk.NORMAL)
            self.spec_connect_btn.config(state=tk.NORMAL)
            self.axis_combo.config(state=tk.NORMAL)
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.btn_pause.config(state=tk.DISABLED, text="暂停 / 继续")
            self._set_mode_btns(tk.NORMAL)
            self.btn_step_prev.config(state=tk.DISABLED)
            self.btn_step_next.config(state=tk.DISABLED)
            self.btn_manual_acquire.config(state=tk.NORMAL)
            self.btn_manual_save.config(state=tk.NORMAL)
        elif state == 'scanning':
            self.connect_button.config(state=tk.DISABLED)
            self.spec_connect_btn.config(state=tk.DISABLED)
            self.axis_combo.config(state=tk.DISABLED)
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_pause.config(state=tk.NORMAL, text="暂停")
            self._set_mode_btns(tk.DISABLED)
            self.btn_step_prev.config(state=tk.DISABLED)
            self.btn_step_next.config(state=tk.DISABLED)
            self.btn_manual_acquire.config(state=tk.DISABLED)
            self.btn_manual_save.config(state=tk.DISABLED)
        elif state == 'paused':
            self.btn_pause.config(text="继续")
            self.btn_step_prev.config(state=tk.NORMAL)
            self.btn_step_next.config(state=tk.NORMAL)
            self.btn_manual_acquire.config(state=tk.NORMAL)

    def _set_mode_btns(self, s):
        try:
            self.mode_rb_off.config(state=s)
            self.mode_rb_open.config(state=s)
            self.mode_rb_closed.config(state=s)
        except: pass

    def on_closing(self):
        if messagebox.askyesno("退出", "确定退出？"):
            self.engine.disconnect_all()
            self.root.destroy()
            sys.exit(0)

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    
    try:
        from ttkthemes import ThemedTk
        root = ThemedTk(theme="arc")
    except:
        root = tk.Tk()
        
    app = ScanningApp(root)
    root.mainloop()