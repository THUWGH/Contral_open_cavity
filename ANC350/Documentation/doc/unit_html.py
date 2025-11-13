import os
import html
from bs4 import BeautifulSoup

# 1. 定义要提取内容的文件列表 (与您上传的名称一致)
files_to_extract = [
    'index.html',
    'globals_type.html',
    'globals_enum.html',
    'globals_eval.html',
    'globals_defs.html',
    'anc350res_8h.html',
    'anc350num_8h.html',
    'anc350fps_8h.html',
    'example0.c'
]

output_filename = "ANC350_Reference.html"

# 2. 定义新HTML文件的头部 (包含Doxygen的关键CSS样式，使其看起来正确)
html_header = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>ANC350 库综合参考</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            margin: 20px; 
            max-width: 1200px; 
            margin: auto; 
            line-height: 1.6;
        }
        h1 { 
            color: #253555;
            border-bottom: 3px solid #5373B4; 
            padding-bottom: 10px;
        }
        h2 { 
            color: #333; 
            border-bottom: 1px solid #ccc; 
            padding-bottom: 5px;
            margin-top: 40px;
        }
        /* 示例代码样式 */
        pre { 
            background-color: #f4f4f4; 
            border: 1px solid #ddd; 
            padding: 15px; 
            border-radius: 5px; 
            overflow-x: auto;
        }
        code { font-family: "Consolas", "Monaco", monospace; }
        
        /* Doxygen 表格样式 (从 doxygen.css 提取) */
        table.memberdecls { 
            border-spacing: 0px; 
            padding: 0px; 
            width: 100%; 
        }
        .memItemLeft, .memItemRight { 
            background-color: #F9FAFC; 
            border: none; 
            margin: 4px; 
            padding: 1px 0 0 8px;
            vertical-align: top;
        }
        .memItemRight { width: 100%; }
        .memSeparator { 
            border-bottom: 1px solid #DEE4F0; 
            line-height: 1px; 
            margin: 0px; 
            padding: 0px; 
        }
        .mdescLeft, .mdescRight { 
            padding: 0px 8px 4px 8px; 
            color: #555;
            font-size: 0.9em;
        }
        .memproto { 
            border: 1px solid #A8B8D9; 
            padding: 6px 0px 6px 0px;
            color: #253555;
            font-weight: bold;
            background-image: url('nav_f.png');
            background-repeat: repeat-x;
            background-color: #E2E8F2;
            border-top-right-radius: 4px;
            border-top-left-radius: 4px;
        }
        .memdoc { 
            border-bottom: 1px solid #A8B8D9;      
            border-left: 1px solid #A8B8D9;      
            border-right: 1px solid #A8B8D9; 
            padding: 6px 10px 2px 10px;
            background-color: #FBFCFD;
            border-bottom-left-radius: 4px;
            border-bottom-right-radius: 4px;
        }
        .contents {
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <h1>ANC350 库综合参考</h1>
"""

html_footer = """
</body>
</html>
"""

# 3. 开始整合
try:
    with open(output_filename, 'w', encoding='utf-8') as f_out:
        f_out.write(html_header)
        
        print(f"开始创建 {output_filename}...")

        for filename in files_to_extract:
            if not os.path.exists(filename):
                print(f"  [警告] 未找到文件: {filename}")
                continue

            print(f"  > 正在处理: {filename}")
            
            # 特殊处理 C 示例代码文件
            if filename.endswith('.c'):
                f_out.write(f"<h2>C 语言示例代码 (example0.c)</h2>\n")
                with open(filename, 'r', encoding='utf-8') as f_in:
                    code_content = f_in.read()
                    escaped_code = html.escape(code_content)
                    f_out.write(f"<pre><code>{escaped_code}</code></pre>\n")
            
            # 处理 HTML 文件
            elif filename.endswith('.html'):
                with open(filename, 'r', encoding='utf-8') as f_in:
                    soup = BeautifulSoup(f_in.read(), 'html.parser')
                    
                    # 提取Doxygen生成的标题
                    title_div = soup.find('div', class_='title')
                    if title_div:
                        f_out.write(f"<h2>{title_div.get_text()}</h2>\n")
                    else:
                        f_out.write(f"<h2>{filename}</h2>\n")

                    # 提取核心内容区域
                    content_div = soup.find('div', class_='contents')
                    if content_div:
                        # 写入提取到的内容
                        f_out.write(str(content_div))
                    else:
                        print(f"  [警告] 在 {filename} 中未找到 'div.contents'。")
                
            f_out.write('<hr style="margin-top: 40px;">\n')

        f_out.write(html_footer)
        print(f"\n[成功] 整合完毕! 文件已保存为: {output_filename}")

except ImportError:
    print("[错误] 未找到 'beautifulsoup4' 库。")
    print("请先通过 'pip install beautifulsoup4' 命令安装它。")
except Exception as e:
    print(f"[发生错误] {e}")