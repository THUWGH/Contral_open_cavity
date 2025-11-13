import win32com.client
import tkinter as tk
from tkinter import ttk, scrolledtext
import time
import sys

# --- 全局变量 ---
log_text_widget = None
root = None

def log_to_gui(message):
    """向 GUI 文本框中打印日志"""
    if log_text_widget:
        print(message) # 同时打印到控制台
        log_text_widget.insert(tk.END, f"{message}\n")
        log_text_widget.see(tk.END)
        root.update_idletasks() # 刷新GUI

def get_com_error_details(ex):
    """ 辅助函数，用于解析详细的 COM 错误信息。"""
    try:
        hresult = ex.hresult
        message = ex.strerror
        excepinfo = ex.excepinfo
        
        log_to_gui(f"  [!] COM 错误 (HRESULT): {hresult}")
        log_to_gui(f"  [!] 错误消息: {message}")
        if excepinfo:
            log_to_gui(f"  [!] 额外信息 (来自驱动): {excepinfo[2]}")
    except Exception:
        log_to_gui(f"  [!] 发生了非 COM 错误: {ex}")

def run_test():
    """
    按下按钮时执行的测试函数
    """
    ccd = None
    mono = None
    
    # 【关键】从你的截图中 获取的硬编码 ID
    CCD_ID = "CCD1"
    MONO_ID = "IHR 550"
    
    try:
        # --- 1. 创建 COM 对象 ---
        log_to_gui("--- 步骤 1: 创建 COM 对象 ---")
        try:
            ccd = win32com.client.Dispatch("JYCCD.JYMCD")
            log_to_gui(f"[成功] 已创建 'JYCCD.JYMCD' 对象。")
        except Exception as e:
            log_to_gui(f"[失败] 无法创建 'JYCCD.JYMCD'。")
            get_com_error_details(e)
            return

        try:
            mono = win32com.client.Dispatch("JYMono.Monochromator")
            log_to_gui(f"[成功] 已创建 'JYMono.Monochromator' 对象。")
        except Exception as e:
            log_to_gui(f"[失败] 无法创建 'JYMono.Monochromator'。")
            get_com_error_details(e)
            return

        # --- 2. 初始化 CCD ---
        log_to_gui(f"\n--- 步骤 2: 测试 CCD (ID: '{CCD_ID}') ---")
        ccd.Uniqueid = CCD_ID
        log_to_gui("  1. 正在调用 .Load()...")
        ccd.Load()
        log_to_gui("  2. 正在调用 .OpenCommunications()...")
        ccd.OpenCommunications()
        log_to_gui("  3. 正在调用 .Initialize()... (异步)")
        ccd.Initialize() 
        
        # --- 轮询反馈 (解决你的"逻辑不对"问题) ---
        log_to_gui("  4. 正在轮询 'ReadyforAcquisition' 状态...")
        timeout = 30 # 最多等待30秒
        start_time = time.time()
        is_ready = False
        
        while time.time() - start_time < timeout:
            # 轮询 ReadyforAcquisition 属性 
            status = ccd.ReadyforAcquisition
            log_to_gui(f"    ...ReadyforAcquisition = {status} (True/False)")
            
            if status: # VB/COM 的布尔值 True/False
                is_ready = True
                break
            time.sleep(0.5) # 轮询间隔

        if not is_ready:
            raise Exception(f"CCD 初始化超时（30秒）。ReadyforAcquisition 始终为 False。")
        
        log_to_gui(f"\n  [成功] CCD '{CCD_ID}' 已就绪！")

        # --- 3. 初始化 Mono ---
        log_to_gui(f"\n--- 步骤 3: 测试 Mono (ID: '{MONO_ID}') ---")
        mono.Uniqueid = MONO_ID
        log_to_gui("  1. 正在调用 .Load()...")
        mono.Load()
        log_to_gui("  2. 正在调用 .OpenCommunications()...")
        mono.OpenCommunications()
        log_to_gui("  3. 正在调用 .Initialize()... (异步)")
        mono.Initialize()
        
        log_to_gui("  4. 正在轮询 'IsReady' 状态...")
        timeout = 30
        start_time = time.time()
        is_ready = False
        
        while time.time() - start_time < timeout:
            # 轮询 IsReady 属性 [cite: 2714-2715]
            status = mono.IsReady
            log_to_gui(f"    ...IsReady = {status} (True/False)")
            
            if status:
                is_ready = True
                break
            time.sleep(0.5)

        if not is_ready:
            raise Exception(f"Mono 初始化超时（30秒）。IsReady 始终为 False。")
            
        log_to_gui(f"\n  [成功] Mono '{MONO_ID}' 已就绪！")
        
        log_to_gui("\n" + "="*60)
        log_to_gui("  [重大成功!] 两个设备都已初始化。")
        log_to_gui("  方案 A (直接 COM 控制) 验证通过！")
        log_to_gui("  我们可以开始编写 real_spectrometer.py 了。")

    except Exception as e:
        log_to_gui(f"\n--- [测试失败] ---")
        get_com_error_details(e)
        log_to_gui("\n[分析]:")
        log_to_gui("  - 如果错误是 'License', 'Access Denied', 'Key' 或 'Dongle'，")
        log_to_gui("    则 100% 是授权问题，我们必须转向方案 B (LabVIEW)。")
        log_to_gui("  - 如果错误是 'Timeout' 或 '...始终为 False'，")
        log_to_gui("    这可能还是授权问题（驱动拒绝进入就绪状态）。")
        log_to_gui("  - 如果错误是 '32/64 bit' 或窗口崩溃，请确保使用 32-bit Python。")

    finally:
        # --- 4. 清理 ---
        log_to_gui("\n--- 步骤 4: 清理 ---")
        try:
            if ccd:
                log_to_gui("  ...正在关闭 CCD 通信...")
                ccd.CloseCommunications()
                ccd.Uninitialize()
            if mono:
                log_to_gui("  ...正在关闭 Mono 通信...")
                mono.CloseCommunications()
                mono.Uninitialize()
            log_to_gui("  [成功] 清理完成。")
        except Exception as e:
            log_to_gui("  [警告] 清理过程中发生错误 (在初始化失败时很常见):")
            get_com_error_details(e)

# --- 创建主窗口 (防止一闪而过) ---
root = tk.Tk()
root.title("SDK 最终测试 (V5 - 轮询版)")
root.geometry("700x500")

main_frame = ttk.Frame(root, padding="10")
main_frame.pack(fill=tk.BOTH, expand=True)

test_button = ttk.Button(main_frame, text="1. 开始测试 (连接并初始化 CCD1 和 IHR 550)", command=run_test)
test_button.pack(pady=10)

log_label = ttk.Label(main_frame, text="测试日志:")
log_label.pack(anchor="w")

log_text_widget = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=20, font=("Courier New", 9))
log_text_widget.pack(fill=tk.BOTH, expand=True, pady=5)

log_to_gui("请确保已安装 pywin32 (pip install pywin32)")
log_to_gui("强烈建议在 32-bit Python 环境中运行此脚本。")
log_to_gui("准备就绪后，请点击 '开始测试' 按钮。")

root.mainloop() # 运行 GUI