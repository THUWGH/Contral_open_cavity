# gui_plugins/spectrometer_widget.py (V6.0)
import tkinter as tk
from tkinter import ttk, filedialog

def create_spec_frame(parent, app):
    """
    创建光谱仪控制面板。
    包含：连接、参数、手动采集/保存。
    """
    frame = ttk.LabelFrame(parent, text="光谱仪控制 & 数据保存", padding="10")
    
    # --- 1. 连接 ---
    conn_frame = ttk.Frame(frame)
    conn_frame.pack(fill=tk.X, pady=5)
    
    app.spec_connect_btn = ttk.Button(conn_frame, text="连接光谱仪", command=app.handle_spec_connect_toggle)
    app.spec_connect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    # --- 2. 参数 ---
    param_frame = ttk.Frame(frame)
    param_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(param_frame, text="积分(s):").grid(row=0, column=0, sticky=tk.W)
    app.spec_int_time_var = tk.DoubleVar(value=0.1)
    ttk.Entry(param_frame, textvariable=app.spec_int_time_var, width=6).grid(row=0, column=1, padx=2)
    
    ttk.Label(param_frame, text="平均:").grid(row=0, column=2, sticky=tk.W)
    app.spec_avg_var = tk.IntVar(value=1)
    ttk.Entry(param_frame, textvariable=app.spec_avg_var, width=6).grid(row=0, column=3, padx=2)
    btn_apply = ttk.Button(param_frame, text="Set", width=4, command=app.handle_spec_set_params)
    btn_apply.grid(row=0, column=4, padx=5) # 放在输入框后面
    # --- 3. [新增] 手动控制 ---
    ctrl_frame = ttk.LabelFrame(frame, text="手动操作 (Manual)", padding="5")
    ctrl_frame.pack(fill=tk.X, pady=5)
    
    # 采集按钮 (空闲或暂停时可用)
    app.btn_manual_acquire = ttk.Button(ctrl_frame, text="采集单帧 (Acquire)", command=app.handle_manual_acquire, state=tk.DISABLED)
    app.btn_manual_acquire.pack(fill=tk.X, pady=2)
    
    # 保存按钮 (仅空闲且有数据时可用)
    app.btn_manual_save = ttk.Button(ctrl_frame, text="保存当前光谱 (Save)", command=app.handle_manual_save, state=tk.DISABLED)
    app.btn_manual_save.pack(fill=tk.X, pady=2)

    # --- 4. 保存配置 ---
    save_frame = ttk.LabelFrame(frame, text="自动保存配置", padding="5")
    save_frame.pack(fill=tk.X, pady=5)
    
    # 路径
    path_container = ttk.Frame(save_frame)
    path_container.pack(fill=tk.X, pady=2)
    ttk.Label(path_container, text="路径:").pack(side=tk.LEFT)
    app.spec_save_path_var = tk.StringVar(value=app.default_save_path)
    ttk.Entry(path_container, textvariable=app.spec_save_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def browse_folder():
        d = filedialog.askdirectory()
        if d: app.spec_save_path_var.set(d)
    ttk.Button(path_container, text="...", width=3, command=browse_folder).pack(side=tk.RIGHT)
    
    # 前缀
    prefix_container = ttk.Frame(save_frame)
    prefix_container.pack(fill=tk.X, pady=2)
    ttk.Label(prefix_container, text="前缀:").pack(side=tk.LEFT)
    app.spec_prefix_var = tk.StringVar(value="Sample")
    ttk.Entry(prefix_container, textvariable=app.spec_prefix_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    # --- 5. 元数据 ---
    meta_frame = ttk.LabelFrame(frame, text="实验备注", padding="5")
    meta_frame.pack(fill=tk.BOTH, expand=True, pady=5)
    app.spec_metadata_text = tk.Text(meta_frame, height=3, width=30, font=("Consolas", 9))
    app.spec_metadata_text.pack(fill=tk.BOTH, expand=True)
    app.spec_metadata_text.insert(tk.END, "Grating: 600g/mm\nMiddle: 532nm\nSplit:200")
    
    return frame