# ============================================================
# tests/unit/test_config.py
# 配置模块与日志模块的单元测试
# ============================================================
import unittest
import time
import os
import sys

# 动态将项目根目录添加到 sys.path 中
# 这样无论是怎么运行这个文件，都能正确找到项目根目录下的 config 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入我们需要测试的模块
# 注意：这里导入 config 将触发 __init__.py 中的魔法，但暂不加载 settings
import config
from config.settings import Settings

class TestConfigModule(unittest.TestCase):
    
    def test_01_instantiation(self):
        """测试 settings 是否能被正确实例化"""
        self.assertTrue(hasattr(config, "settings"))
        settings_instance = config.settings
        self.assertIsInstance(settings_instance, Settings)
        self.assertEqual(settings_instance.app_name, "Tex_Agent")
        
    def test_02_singleton_behavior(self):
        """测试 settings 是否保持单例（避免重复读取 .env）"""
        settings_1 = config.settings
        settings_2 = config.get_settings() # 直接调用底层获取方法
        
        # 两个对象在内存中应该是同一个实例
        self.assertIs(settings_1, settings_2)

    def test_03_log_execution_time_decorator(self):
        """测试耗时记录装饰器是否正常工作且不影响函数返回值"""
        
        @config.log_execution_time(threshold=0.1)
        def dummy_task(x, y):
            time.sleep(0.15) # 模拟耗时任务，触发 threshold
            return x + y
            
        result = dummy_task(3, 5)
        
        # 验证函数的核心逻辑未受装饰器干扰
        self.assertEqual(result, 8)

    def test_04_debug_print(self):
        """测试 debug_print 函数在不同配置下是否能稳定运行"""
        # 临时将 DEBUG 设置为 True 测试输出逻辑（不会真正破坏系统，仅针对此测试）
        original_debug = config.settings.debug
        config.settings.debug = True
        
        try:
            config.debug_print("这是一条测试 Debug 输出，你应该能看到蓝色的前缀，并且带有正确的文件名和行号。")
        except Exception as e:
            self.fail(f"debug_print 抛出了异常: {e}")
            
        # 恢复原状态
        config.settings.debug = original_debug

if __name__ == '__main__':
    unittest.main()