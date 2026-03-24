# router.py
from agents.simple_agent.core import SimpleAgent
from agents.plan_and_solve.core import PlanSolveAgent


class TaskRouter:
    def __init__(self):
        # 初始化各个 Agent
        self.simple_agent = SimpleAgent()
        self.planandsolve_agent=PlanSolveAgent()
        
    def route_and_execute(self, task_input: str) -> dict:
        """
        简单的规则路由：目前作为 Demo，所有任务都默认交给 SimpleAgent。
        后续可以在这里接入 LLM 进行意图识别，或者使用关键词匹配来决定调用哪个 Agent
        """
        print("[DEBUG: Router] 接收到任务，正在分配给 SimpleAgent...")
        # 实际开发中，这里会有 if-elif 逻辑来选择 Agent
        return self.planandsolve_agent.run(task_input)

        return self.simple_agent.run(task_input)