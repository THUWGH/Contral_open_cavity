import win32com.client
import sys
import time

def print_header(title):
    print("\n" + "="*60)
    print(f"--- {title} ---")
    print("="*60)

def get_com_error_details(ex):
    """ 辅助函数，用于解析详细的 COM 错误信息。"""
    try:
        hresult = ex.hresult
        message = ex.strerror
        excepinfo = ex.excepinfo
        
        print(f"  [!] COM 错误 (HRESULT): {hresult}")
        print(f"  [!] 错误消息: {message}")
        if excepinfo:
            print(f"  [!] 额外信息 (来自驱动): {excepinfo[2]}")
    except Exception:
        print(f"  [!] 发生了非 COM 错误: {ex}")

# --- 主程序 ---
if __name__ == "__main__":
    
    print_header("步骤 1: 创建 COM 对象 (ProgID 连接)")
    
    ccd_obj = None
    mono_obj = None
    
    # 1. 创建 CCD 对象
    prog_id_ccd = "JYCCD.JYMCD"
    try:
        print(f"  正在 Dispatch('{prog_id_ccd}')...")
        ccd_obj = win32com.client.Dispatch(prog_id_ccd)
        print(f"  [成功] 已创建 '{prog_id_ccd}' 对象。")
    except Exception as e:
        print(f"  [失败] 无法创建 '{prog_id_ccd}' 对象。")
        get_com_error_details(e)

    # 2. 创建 Mono 对象
    prog_id_mono = "JYMono.Monochromator"
    try:
        print(f"  正在 Dispatch('{prog_id_mono}')...")
        mono_obj = win32com.client.Dispatch(prog_id_mono)
        print(f"  [成功] 已创建 '{prog_id_mono}' 对象。")
    except Exception as e:
        print(f"  [失败] 无法创建 '{prog_id_mono}' 对象。")
        get_com_error_details(e)

    # ---
    # 步骤 2: 测试硬件初始化 (硬编码 ID)
    # 我们直接使用从 LabSpec 6 截图中看到的 ID
    # ---
    print_header("步骤 2: 测试硬件初始化 (授权检查)")
    
    # --- 2a. 测试 CCD ---
    if ccd_obj:
        # 【关键】我们在这里硬编码你从截图 中找到的 ID
        ccd_id_to_test = "CCD1" 
        
        print(f"\n  --- 正在测试 CCD (ID: '{ccd_id_to_test}') ---")
        try:
            print(f"  1. 正在设置 Uniqueid = '{ccd_id_to_test}'...")
            ccd_obj.Uniqueid = ccd_id_to_test
            
            print("  2. 正在调用 .Load()...")
            ccd_obj.Load()
            
            print("  3. 正在调用 .OpenCommunications()... (可能需要几秒)")
            ccd_obj.OpenCommunications()
            
            print("  4. 正在调用 .Initialize()... (最关键的授权检查点)")
            ccd_obj.Initialize() # 异步调用
            
            print("     ...Initialize() 调用已发出。等待5秒...")
            time.sleep(5) 
            
            print(f"\n  [成功] CCD '{ccd_id_to_test}' 初始化调用未抛出异常！")
            
            print("  [*] 正在关闭 CCD 通信...")
            ccd_obj.CloseCommunications()
            ccd_obj.Uninitialize()
            
        except Exception as e:
            print(f"\n  [失败] CCD '{ccd_id_to_test}' 初始化失败：")
            get_com_error_details(e)
            print("  [分析] 如果此处报错，很可能是 SDK 授权问题 (需要 USB 密钥)。")
    else:
        print("\n  [跳过] CCD 对象未创建，跳过 CCD 初始化测试。")

    # --- 2b. 测试 Mono ---
    if mono_obj:
        # 【关键】我们在这里硬编码你从截图 中找到的 ID
        mono_id_to_test = "IHR 550" 
        
        print(f"\n  --- GHR_G(ID: '{mono_id_to_test}') ---")
        try:
            print(f"  1. 正在设置 Uniqueid = '{mono_id_to_test}'...")
            mono_obj.Uniqueid = mono_id_to_test
            
            print("  2. 正在调用 .Load()...")
            mono_obj.Load()
            
            print("  3. 正在调用 .OpenCommunications()... (可能需要几秒)")
            mono_obj.OpenCommunications()
            
            print("  4. 正在调用 .Initialize()...")
            mono_obj.Initialize() # 异步调用
            
            print("     ...Initialize() 调用已发出。等待5秒...")
            time.sleep(5) 
            
            print(f"\n  [成功] Mono '{mono_id_to_test}' 初始化调用未抛出异常！")

            print("  [*] 正在关闭 Mono 通信...")
            mono_obj.CloseCommunications()
            mono_obj.Uninitialize()
            
        except Exception as e:
            print(f"\n  [失败] Mono '{mono_id_to_test}' 初始化失败：")
            get_com_error_details(e)
            print("  [分析] 如果此处报错，很可能是 SDK 授权问题。")
    else:
        print("\n  [跳过] Mono 对象未创建，跳过 Mono 初始化测试。")

    # ---
    # 最终总结
    # ---
    print_header("测试结束")
    print("  请检查上面的输出。")
    print("  - 如果 CCD 和 Mono 均 [成功]，则方案 A (直接 COM 控制) 可行。")
    print("  - 如果任何一个 [失败] 并提及 'License', 'Access Denied', 'Key', 或 'Dongle'，")
    print("    则我们必须使用 方案 B (Python-LabVIEW 桥接)。")
    
    input("\n  按 Enter 键退出窗口...")