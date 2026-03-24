import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from typing import List, Dict

MODEL_PATH = "/data/model_database/Qwen2.5-7B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

class LLM:
    def __init__(self, model_path: str = None, device: str = None):
        """
        初始化客户端。从本地路径加载模型。
        
        Args:
            model_path: 本地模型路径
            device: 运行设备，默认为cuda（如果可用）否则为cpu
        """
        self.model_path = model_path
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        if not self.model_path:
            raise ValueError("模型路径必须被提供。")

        print(f"🧠 正在加载本地模型: {self.model_path}")
        print(f"📱 使用设备: {self.device}")
        
        # 加载tokenizer和模型
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map="auto" if self.device == "cuda" else None
        )
        self.model.eval()
        print("✅ 模型加载完成！")

    def think(self, messages: List[Dict[str, str]], temperature: float = 0) -> str:
        """
        调用大语言模型进行思考，并返回其响应。
        
        Args:
            messages: 消息列表，包含role和content
            temperature: 生成温度，控制输出的随机性
            
        Returns:
            模型生成的响应文本
        """
        try:
            # 构建对话历史
            prompt = ""
            for msg in messages:
                if msg["role"] == "system":
                    prompt += f"[SYSTEM] {msg['content']}\n"
                elif msg["role"] == "user":
                    prompt += f"[USER] {msg['content']}\n"
                elif msg["role"] == "assistant":
                    prompt += f"[ASSISTANT] {msg['content']}\n"
            
            # 添加助手前缀
            prompt += "[ASSISTANT] "
            
            # 编码输入
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            
            print("🧠 正在生成响应...")
            
            # 生成响应
            output = self.model.generate(
                **inputs,
                max_new_tokens=1000,
                temperature=temperature,
                do_sample=temperature > 0,
                repetition_penalty=1.1,
            )
            
            # 解码输出
            response = self.tokenizer.decode(output[0], skip_special_tokens=True)
            
            # 提取助手部分的响应
            assistant_response = response.split("[ASSISTANT] ")[-1]
            
            return assistant_response

        except Exception as e:
            print(f"❌ 调用本地模型时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return None



# --- 客户端使用示例 ---
if __name__ == '__main__':
    try:
        # 从环境变量或直接指定路径加载模型
        llmClient = LLM(model_path=MODEL_PATH, device=DEVICE)
        
        exampleMessages = [
            {"role": "system", "content": "You are a helpful assistant that writes Python code."},
            {"role": "user", "content": "写一个快速排序算法"}
        ]
        
        print("--- 调用LLM ---")
        responseText = llmClient.think(exampleMessages)
        if responseText:
            print("\n\n--- 完整模型响应 ---")
            print(responseText)

    except ValueError as e:
        print(e)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()