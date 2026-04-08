# utils/loading_spinner.py
"""
加载动画工具
提供各种风格的加载动画
"""
import threading
import time
import itertools
from contextlib import contextmanager
from typing import Optional, Iterator


class LoadingSpinner:
    """加载旋转器基类"""
    
    def __init__(self, message: str = "处理中", style: str = "spinner"):
        self.message = message
        self.style = style
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        self._animations = {
            'spinner': ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
            'dots': ['   ', '.  ', '.. ', '...'],
            'simple': ['|', '/', '-', '\\'],
            'braille': ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷'],
        }
        
        self._frames = self._animations.get(style, self._animations['spinner'])
    
    def _animate(self):
        """动画线程"""
        idx = 0
        start_time = time.time()
        
        while self.running:
            frame = self._frames[idx % len(self._frames)]
            elapsed = int(time.time() - start_time)
            
            # 不同风格显示
            if self.style == 'bar':
                bar = self._get_progress_bar(elapsed)
                print(f"\r{frame} {self.message} {bar} {elapsed}s", end='', flush=True)
            else:
                print(f"\r{frame} {self.message}... {elapsed}s", end='', flush=True)
            
            idx += 1
            time.sleep(0.1)
    
    def _get_progress_bar(self, elapsed: int, max_seconds: int = 60) -> str:
        """获取进度条"""
        bar_length = 20
        progress = min(elapsed / max_seconds, 1)
        filled = int(bar_length * progress)
        return '█' * filled + '░' * (bar_length - filled)
    
    def start(self):
        """启动动画"""
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止动画"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        print('\r' + ' ' * 50 + '\r', end='', flush=True)
    
    @contextmanager
    def run(self):
        """上下文管理器"""
        self.start()
        try:
            yield
        finally:
            self.stop()


def with_loading(message: str = "处理中", style: str = "spinner"):
    """装饰器：为函数添加加载动画"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            spinner = LoadingSpinner(message, style)
            spinner.start()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                spinner.stop()
        return wrapper
    return decorator


def run_with_loading(func, message: str = "处理中", style: str = "spinner", *args, **kwargs):
    """执行函数并显示加载动画"""
    spinner = LoadingSpinner(message, style)
    result_container = {'result': None}
    error_container = {'error': None}
    
    def worker():
        try:
            result_container['result'] = func(*args, **kwargs)
        except Exception as e:
            error_container['error'] = e
    
    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()
    
    spinner.start()
    while worker_thread.is_alive():
        time.sleep(0.1)
    spinner.stop()
    
    if error_container['error']:
        raise error_container['error']
    
    return result_container['result']