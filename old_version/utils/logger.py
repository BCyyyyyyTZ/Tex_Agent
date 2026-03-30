import inspect
import os

# 全局调试开关，默认关闭
_DEBUG_MODE = False

def set_debug_mode(mode: bool):
    """在 main.py 中调用此函数来开启或关闭 DEBUG 模式"""
    global _DEBUG_MODE
    _DEBUG_MODE = mode

def debug(*args, **kwargs):
    """
    在 _DEBUG_MODE 开启时，不仅输出内容，还会自动附加调用者的父目录、文件名和行号。
    例如: [DEBUG: tools/arxiv_search.py, line 35] 你的输出内容...
    """
    if _DEBUG_MODE:
        # 获取调用者的栈帧 (f_back 表示向上一层)
        caller_frame = inspect.currentframe().f_back
        
        if caller_frame:
            # 获取完整的文件路径
            full_path = caller_frame.f_code.co_filename
            line_no = caller_frame.f_lineno
            
            # 获取父文件夹名和文件名
            parent_dir = os.path.basename(os.path.dirname(full_path))
            file_name = os.path.basename(full_path)
            
            # 拼接展示路径。如果是根目录下的文件（如 main.py），就只显示文件名
            display_path = f"{parent_dir}/{file_name}" if parent_dir else file_name
            
            # 构建智能前缀
            prefix = f"[DEBUG: {display_path}, line {line_no}]"
            
            # 将前缀与用户真正想打印的内容拼接，像正常 print 一样输出
            print(prefix, *args, **kwargs)
        else:
            # 兜底机制
            print("[DEBUG: Unknown]", *args, **kwargs)