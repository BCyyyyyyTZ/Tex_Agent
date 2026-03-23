# main.py
import os
from dotenv import load_dotenv
from router import TaskRouter

def main():
    # 加载 .env 文件中的环境变量
    load_dotenv()
    
    # 检查 API Key 是否配置
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("[ERROR: ]错误: 未找到 API_KEY。请在根目录创建 .env 文件并配置。")
        return

    # 初始化路由调度器
    router = TaskRouter()
    
    # 模拟用户输入
    print("=== Tex_Agent 论文协作智能体 (Demo) ===")
    user_task = "请帮我用一句话总结什么是 LaTeX？"
    print(f"用户输入: {user_task}\n")
    
    # 路由分发并获取结果
    response = router.route_and_execute(user_task)
    
    # 打印结果
    print("\n=== 执行结果 ===")
    if response.get("status") == "success":
        print(f"[DEBUG: ]负责 Agent: {response.get('agent_used')}")
        print(f"输出内容:\n{response.get('result')}")
    else:
        print(f"[ERROR: ]执行失败: {response.get('result')}")

if __name__ == "__main__":
    main()