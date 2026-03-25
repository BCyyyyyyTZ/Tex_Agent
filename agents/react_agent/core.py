import os
import json
import re
from openai import OpenAI
from agents.base_agent import BaseAgent
from prompt.react_prompt import (
    REACT_SYSTEM_PROMPT, 
    REACT_REASON_PROMPT, 
    REACT_OBSERVE_PROMPT
)


class ReActAgent(BaseAgent):
    def __init__(self, tools: list = None):
        super().__init__(name="ReActAgent")
        
        self.client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL")
        )
        self.model = os.environ.get("DEEPSEEK_MODEL", "gpt-3.5-turbo")
        self.max_iterations = 8  # 减少最大迭代次数
        
        # 装载工具箱
        self.tools = tools or []
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.tools_desc = self._generate_tools_description()

    def run(self, task_input: str, **kwargs) -> dict:
        print(f"[DEBUG: {self.name}] 开始执行 ReAct 任务...")
        
        self.max_iterations = kwargs.get("max_iterations", self.max_iterations)
        context = kwargs.get("context", "")
        history = []
        final_result = ""
        consecutive_think_count = 0  # 记录连续思考次数

        try:
            for iteration in range(1, self.max_iterations + 1):
                print(f"[DEBUG: {self.name}] === 迭代 {iteration}/{self.max_iterations} ===")
                
                # 1. Reason: 推理下一步行动
                action = self._reason(task_input, context, history, iteration)
                print(f"[DEBUG: {self.name}] 推理结果: {action}")
                
                # 检查连续思考次数
                if action.startswith("THINK"):
                    consecutive_think_count += 1
                    if consecutive_think_count >= 2:  # 连续思考2次后强制要求采取行动
                        print(f"[DEBUG: {self.name}] 连续思考过多，强制要求总结并完成")
                        action = self._force_finish(task_input, context, history)
                else:
                    consecutive_think_count = 0
                
                # 检查是否完成
                if action.startswith("FINISH"):
                    final_result = self._extract_finish_result(action)
                    break
                
                # 2. Action: 执行行动
                action_result = self._act(action, task_input, context)
                print(f"[DEBUG: {self.name}] 行动结果: {action_result[:150]}...")
                
                # 3. Observation: 观察总结（简化）
                observation = self._observe(action, action_result)
                print(f"[DEBUG: {self.name}] 观察: {observation[:100]}...")
                
                # 记录历史
                history.append({
                    "iteration": iteration,
                    "action": action,
                    "result": action_result,
                    "observation": observation
                })
                
                # 更新上下文（简化）
                context += f"\n第{iteration}轮: {action} -> {observation}\n"
                
                # 检查是否已收集足够信息
                if self._should_finish(history, task_input):
                    print(f"[DEBUG: {self.name}] 检测到足够信息，准备完成")
                    final_result = self._generate_final_answer(task_input, context, history)
                    break
            
            # 处理未完成情况
            if not final_result:
                final_result = self._generate_final_answer(task_input, context, history)
            
            return {
                "status": "success",
                "agent_used": self.name,
                "result": final_result,
                "history": history
            }
            
        except Exception as e:
            print(f"[ERROR: {self.name}] {str(e)}")
            return {
                "status": "error",
                "agent_used": self.name,
                "result": str(e),
                "history": history
            }

    def _reason(self, task: str, context: str, history: list, iteration: int) -> str:
        """Reason 阶段：决定下一步行动"""
        history_str = self._format_history(history)
        
        prompt = REACT_REASON_PROMPT.format(
            task=task,
            context=context or "暂无",
            history=history_str,
            tools_desc=self.tools_desc,
            current_iter=iteration,
            max_iterations=self.max_iterations
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": REACT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=150  # 减少 token 数
        )
        
        action = response.choices[0].message.content.strip()
        return self._validate_action(action)

    def _act(self, action: str, task: str, context: str) -> str:
        """Action 阶段：执行具体行动"""
        if action.startswith("THINK"):
            # 简化思考，直接返回
            think_content = action.replace("THINK|", "").strip()
            return think_content if think_content else "正在思考..."
        
        if action.startswith("TOOL"):
            return self._execute_tool(action)
        
        if action.startswith("FINISH"):
            return "任务完成"
        
        return f"未知行动类型: {action}"

    def _observe(self, action: str, action_result: str) -> str:
        """简化 Observation 阶段"""
        prompt = REACT_OBSERVE_PROMPT.format(
            action=action,
            act_result=action_result[:300]
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是观察分析专家，用一句话总结关键信息。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()

    def _force_finish(self, task: str, context: str, history: list) -> str:
        """强制生成最终答案"""
        print(f"[DEBUG: {self.name}] 强制生成最终答案")
        
        # 构建总结提示
        prompt = f"""根据以下信息，生成最终答案：
任务：{task}
收集到的信息：{context}
历史记录：{self._format_history(history)}

请直接输出最终答案："""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        return f"FINISH|{response.choices[0].message.content.strip()}"

    def _should_finish(self, history: list, task: str) -> bool:
        """判断是否应该结束任务"""
        # 如果已经执行了工具调用，且最近一次不是 THINK，可以考虑结束
        tool_calls = [h for h in history if "TOOL" in h.get("action", "")]
        if len(tool_calls) >= 1:  # 至少执行过一次工具调用
            last_action = history[-1].get("action", "") if history else ""
            if not last_action.startswith("TOOL"):  # 最后一次不是工具调用
                return True
        return False

    def _generate_final_answer(self, task: str, context: str, history: list) -> str:
        """生成最终答案"""
        print(f"[DEBUG: {self.name}] 生成最终答案...")
        
        # 提取工具结果
        tool_results = []
        for h in history:
            if "TOOL" in h.get("action", ""):
                tool_results.append(h.get("result", ""))
        
        prompt = f"""请根据以下信息回答用户问题：

用户问题：{task}

收集到的信息：
{chr(10).join(tool_results[:3])}

请给出完整的回答："""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800
        )
        
        return response.choices[0].message.content.strip()

    def _validate_action(self, action: str) -> str:
        """验证并修正行动格式"""
        valid_prefixes = ["THINK", "TOOL", "FINISH"]
        
        for prefix in valid_prefixes:
            if action.startswith(prefix):
                return action
        
        # 尝试提取有效前缀
        for prefix in valid_prefixes:
            if prefix in action:
                idx = action.find(prefix)
                return action[idx:]
        
        # 如果包含工具名称，转换为 TOOL
        if any(tool_name in action for tool_name in self.tool_map.keys()):
            return f"TOOL|arxiv_search|{{\"query\": \"{action[:50]}\", \"max_results\": 2}}"
        
        # 默认转为 FINISH
        return f"FINISH|{action[:200]}"

    def _extract_finish_result(self, action: str) -> str:
        """提取 FINISH 行动的结果"""
        match = re.match(r"FINISH\|?(.*)", action, re.DOTALL)
        if match:
            return match.group(1).strip()
        return "任务完成"

    def _generate_tools_description(self) -> str:
        """生成工具描述"""
        if not self.tools:
            return "暂无可用工具"
        
        desc = ""
        for tool in self.tools:
            desc += f"- {tool.name}: {tool.description}\n"
        return desc

    def _format_history(self, history: list) -> str:
        """格式化历史记录（简化版）"""
        if not history:
            return "暂无历史记录"
        
        lines = []
        for h in history[-3:]:  # 只保留最近3轮
            lines.append(f"第{h['iteration']}轮: {h['action']} -> {h['observation'][:80]}")
        return "\n".join(lines)

    def _execute_tool(self, action: str) -> str:
        """执行工具调用"""
        tool_match = re.match(r"TOOL\|([^|]+)\|(.+)", action, re.DOTALL)
        if not tool_match:
            return "错误：工具调用格式不正确"
        
        tool_name = tool_match.group(1).strip()
        tool_params_str = tool_match.group(2).strip()
        
        print(f"[DEBUG: {self.name}] 调用工具: {tool_name}")
        
        if tool_name not in self.tool_map:
            return f"错误：未找到工具 '{tool_name}'"
        
        # 解析参数
        try:
            params = json.loads(tool_params_str)
        except:
            params = {"query": tool_params_str, "max_results": 2}
        
        # 执行工具
        try:
            result = self.tool_map[tool_name].execute(**params)
            # 简化结果，只保留关键信息
            if len(str(result)) > 500:
                return str(result)[:500] + "..."
            return str(result)
        except Exception as e:
            return f"工具执行失败: {str(e)}"

    def _parse_tool_params(self, tool_name: str, params_str: str) -> dict:
        """解析工具参数"""
        try:
            params = json.loads(params_str)
            if isinstance(params, dict):
                return params
            return {"query": params_str, "max_results": 2}
        except:
            return {"query": params_str, "max_results": 2}