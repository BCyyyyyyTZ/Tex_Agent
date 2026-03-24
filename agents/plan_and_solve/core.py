import os
from openai import OpenAI
from agents.base_agent import BaseAgent
from prompt.plan_and_solve_prompt import PLAN_PROMPT, SOLVE_PROMPT, MERGE_PROMPT

class PlanSolveAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="PlanSolveAgent")
        # 使用与 SimpleAgent 相同的 API 配置
        self.client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL")
        )
        self.model = os.environ.get("DEEPSEEK_MODEL")
        self.max_subtasks = 5  # 最大子任务数量
    
    def run(self, task_input: str, **kwargs) -> dict:
        """
        Plan & Solve 范式：先规划，再分步执行，最后合并
        :param task_input: 任务描述
        :param kwargs: 可选参数
            - context: 上下文信息
            - max_subtasks: 最大子任务数
        :return: {'status', 'agent_used', 'result', 'plan', 'sub_results'}
        """
        print(f"[DEBUG: {self.name}] 正在执行 Plan & Solve 任务...")
        
        # 可选：覆盖最大子任务数
        self.max_subtasks = kwargs.get("max_subtasks", self.max_subtasks)
        
        try:
            # 1. 【PLAN】阶段：拆解任务
            plan = self._create_plan(task_input, kwargs.get("context", ""))
            print(f"[DEBUG: {self.name}] 生成计划：{len(plan)} 个子任务")
            
            # 2. 【SOLVE】阶段：逐步执行
            sub_results = []
            for i, subtask in enumerate(plan):
                print(f"[DEBUG: {self.name}] 执行子任务 {i+1}/{len(plan)}")
                sub_result = self._execute_subtask(subtask, task_input, kwargs.get("context", ""))
                sub_results.append({
                    "step": i + 1,
                    "task": subtask,
                    "result": sub_result
                })
            
            # 3. 【MERGE】阶段：合并结果
            final_result = self._merge_results(plan, sub_results, task_input)
            
            return {
                "status": "success",
                "agent_used": self.name,
                "result": final_result,
                "plan": plan,
                "sub_results": sub_results
            }
            
        except Exception as e:
            print(f"[ERROR: {self.name}] {str(e)}")
            return {
                "status": "error",
                "agent_used": self.name,
                "result": str(e),
                "plan": [],
                "sub_results": []
            }
    
    def _create_plan(self, task_input: str, context: str) -> list:
        """
        使用 LLM 将任务拆解为子步骤
        """
        prompt = PLAN_PROMPT.format(
            task=task_input,
            context=context,
            max_subtasks=self.max_subtasks
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个任务规划专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        
        plan_text = response.choices[0].message.content
        return self._parse_plan(plan_text)
    
    def _execute_subtask(self, subtask: str, original_task: str, context: str) -> str:
        """
        执行单个子任务
        """
        prompt = SOLVE_PROMPT.format(
            original_task=original_task,
            subtask=subtask,
            context=context
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个学术写作助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content
    
    def _merge_results(self, plan: list, sub_results: list, original_task: str) -> str:
        """
        合并所有子任务结果
        """
        # 简单合并
        merged_content = "\n\n".join([
            f"### {r['task']}\n{r['result']}"
            for r in sub_results
        ])
        
        # LLM 润色
        prompt = MERGE_PROMPT.format(
            original_task=original_task,
            merged_content=merged_content
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个学术编辑。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content
    
    def _parse_plan(self, llm_output: str) -> list:
        """
        解析 LLM 输出的计划列表
        """
        import re
        
        patterns = [
            r'\d+\.\s*(.+)',      # 1. 内容
            r'\d+\)\s*(.+)',      # 1) 内容
            r'-\s*(.+)',          # - 内容
        ]
        
        plan = []
        lines = llm_output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    plan.append(match.group(1).strip())
                    break
            else:
                if len(line) > 10:
                    plan.append(line)
        
        return plan[:self.max_subtasks]