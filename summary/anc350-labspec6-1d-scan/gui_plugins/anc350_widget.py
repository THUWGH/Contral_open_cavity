# gui_plugins/anc350_widget.py (V6.0)
import tkinter as tk
from tkinter import ttk

def create_anc_frame(parent, app):
    """
    创建 ANC350 控制面板。
    包含：连接、模式选择、参数设置、单步调试(移动)。
    """
    frame = ttk.LabelFrame(parent, text="ANC350 电机控制", padding="10")
    
    # --- 1. 连接区域 ---
    conn_frame = ttk.Frame(frame)
    conn_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(conn_frame, text="目标轴:").pack(side=tk.LEFT)
    app.axis_combo = ttk.Combobox(conn_frame, values=[0, 1, 2], width=3, state="readonly")
    app.axis_combo.current(0)
    app.axis_combo.pack(side=tk.LEFT, padx=5)
    
    app.connect_button = ttk.Button(conn_frame, text="连接 (Connect)", command=app.handle_connect_toggle)
    app.connect_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # --- 2. 模式选择 ---
    mode_frame = ttk.LabelFrame(frame, text="轴工作模式", padding="5")
    mode_frame.pack(fill=tk.X, pady=5)
    
    app.mode_rb_off = ttk.Radiobutton(mode_frame, text="关闭 (OFF/GND)", 
                                      variable=app.axis_mode_var, value="OFF", 
                                      command=app.handle_set_mode, state=tk.DISABLED)
    app.mode_rb_off.pack(anchor=tk.W)
    
    app.mode_rb_open = ttk.Radiobutton(mode_frame, text="开环 (OPEN / Scan)", 
                                       variable=app.axis_mode_var, value="OPEN", 
                                       command=app.handle_set_mode, state=tk.DISABLED)
    app.mode_rb_open.pack(anchor=tk.W)
    
    app.mode_rb_closed = ttk.Radiobutton(mode_frame, text="闭环 (CLOSED / Servo)", 
                                         variable=app.axis_mode_var, value="CLOSED", 
                                         command=app.handle_set_mode, state=tk.DISABLED)
    app.mode_rb_closed.pack(anchor=tk.W)

    # --- 3. 扫描参数 ---
    param_frame = ttk.LabelFrame(frame, text="电压扫描参数", padding="5")
    param_frame.pack(fill=tk.X, pady=5)
    
    def _create_entry(label, default, key):
        row = ttk.Frame(param_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text=label, width=12).pack(side=tk.LEFT)
        entry = ttk.Entry(row)
        entry.insert(0, str(default))
        entry.pack(side=tk.RIGHT, expand=True, fill=tk.X)
        app.entries[key] = entry

    _create_entry("起始电压 (V):", 0.0, "start_v")
    _create_entry("终止电压 (V):", 10.0, "end_v")
    _create_entry("扫描点数:", 11, "num_points")
    _create_entry("稳定时间 (s):", 0.1, "settle_time")

    # --- 4. [新增] 单步移动控制 ---
    step_frame = ttk.LabelFrame(frame, text="单步调试 (仅移动电压)", padding="5")
    step_frame.pack(fill=tk.X, pady=5)
    
    app.btn_step_prev = ttk.Button(step_frame, text="< 上一点", command=app.handle_step_prev, state=tk.DISABLED)
    app.btn_step_prev.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
    
    app.btn_step_next = ttk.Button(step_frame, text="下一点 >", command=app.handle_step_next, state=tk.DISABLED)
    app.btn_step_next.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=2)

    return frame