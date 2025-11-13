import win32com.client
import tkinter as tk
from tkinter import ttk, scrolledtext
import time

# --- 我们需要一个事件处理器来“接收”来自 COM 的反馈 ---
# 严格按照 SynerJY_SDK.pdf (p.19, p.33) [cite: 462, 464-471, 477-479, 2832] 的定义
class CCD_Events_Handler:
    # SDK (p.101)  定义了事件: Initialized(long status, IJYEventInfo *eventInfo)
    # 在 pywin32 中，这会转换为 OnInitialized(status, eventInfo)
    def OnInitialized(self, status, eventInfo):
        """
        这就是我们等待的“反馈”！
        """
        print(f"--- [反馈] OnInitialized 事件被触发！---")
        if status == 0:
            print(f"[成功] 状态码: {status} (初始化成功)")
            log_to_gui(f"反馈: 初始化成功 (Status={status})")
        else:
            print(f"[失败] 状态码: {status} (初始化失败)")
            log_to_gui(f"反馈: 初始化失败 (Status={status})")
            
    # 我们也监听一下其他事件，以防万一
    def OnOperationStatus(self, status, eventInfo):
        print(f"--- [反馈] OnOperationStatus 事件: Status={status} ---")
        log_to_gui(f"反馈: OperationStatus={status}")

    def OnCriticalError(self, status, eventInfo):
        print(f"--- [反馈] OnCriticalError 事件: Status={status} ---")
        log_to_gui(f"反馈: 严重错误 (Status={status})")

# --- 全局变量 ---
ccd = None
ccd_with_events = None
log_text_widget = None

def log_to_gui(message):
    """向 GUI 文本框中打印日志"""
    if log_text_widget:
        log_text_widget.insert(tk.END, f"{message}\n")
        log_text_widget.see(tk.END)

def run_test():
    """
    按下按钮时执行的测试函数
    """
    global ccd, ccd_with_events
    
    # 【关键】从你的截图中 获取的硬编码 ID
    CCD_ID = "CCD1"
    MONO_ID = "IHR 550"
    
    try:
        # --- 1. 创建 COM 对象 ---
        log_to_gui(f"正在 Dispatch('JYCCD.JYMCD')...")
        ccd = win32com.client.Dispatch("JYCCD.JYMCD")
        log_to_gui(f"[成功] CCD 对象已创建。")
        
        # --- 2. 绑定事件处理器 ---
        # 这是最关键的一步：告诉 pywin32 我们要监听来自 'ccd' 对象的所有事件，
        # 并且 'CCD_Events_Handler' 类中的函数将处理它们。
        log_to_gui("正在绑定事件监听 (WithEvents)...")
        ccd_with_events = win32com.client.WithEvents(ccd, CCD_Events_Handler)
        log_to_gui("[成功] 事件监听已绑定。")

        # --- 3. 执行 SDK 中的初始化序列 ---
        log_to_gui(f"1. 正在设置 Uniqueid = '{CCD_ID}'...")
        ccd.Uniqueid = CCD_ID
        
        log_to_gui("2. 正在调用 .Load()...")
        ccd.Load()
        
        log_to_gui("3. 正在调用 .OpenCommunications()... (可能需要几秒)")
        ccd.OpenCommunications()
        
        log_to_gui("4. 正在调用 .Initialize()... (等待事件反馈)")
        # 这将触发一个异步操作。
        # 如果成功，我们的 CCD_Events_Handler.OnInitialized 方法将被调用。
        ccd.Initialize() 
        
        log_to_gui("...Initialize() 调用已发出。")
        log_to_gui("请在10秒内观察是否有 '反馈' 信息出现...")
        log_to_gui("如果没有反馈，说明授权检查失败或崩溃。")

    except Exception as e:
        log_to_gui(f"\n--- [测试失败] ---")
        log_to_gui(f"错误: {e}")
        log_to_gui("分析: 如果窗口一闪而过，请尝试 32-bit Python。")
        log_to_gui("如果错误是 'License' 或 'Access Denied'，说明需要 USB 密钥。")

# --- 创建主窗口 ---
root = tk.Tk()
root.title("SDK 最终测试 (V4)")
root.geometry("600x400")

main_frame = ttk.Frame(root, padding="10")
main_frame.pack(fill=tk.BOTH, expand=True)

test_button = ttk.Button(main_frame, text="1. 开始测试", command=run_test)
test_button.pack(pady=10)

log_label = ttk.Label(main_frame, text="测试日志:")
log_label.pack(anchor="w")

log_text_widget = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=15)
log_text_widget.pack(fill=tk.BOTH, expand=True, pady=5)

log_to_gui("请确保已安装 pywin32 (pip install pywin32)")
log_to_gui("准备就绪后，请点击 '开始测试' 按钮。")

root.mainloop() # 运行 GUI