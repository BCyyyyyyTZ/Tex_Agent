# 部分或功能接口说明

## tool的开发和使用

**所有tools（如果是集成子tools.base_tool.BaseTool），需要满足：（目前是基于 OpenAI 的接口做的，可能对本地的llm支持不够）**

1. name 属性：定义工具名称。注意：只能使用字母、数字、下划线和连字符
2. description 属性：写给 LLM 看的说明书。告诉大模型“这个工具是干嘛的”、“什么时候用”。
3. parameters 属性：定义输入参数的数据结构（必须严格遵循 JSON Schema 格式）。
4. execute 方法：实际的 Python 运行逻辑。（要求：**返回值必须是 str 类型**， 因为最终这个结果是要作为上下文塞回给 LLM 的，大模型只能阅读纯文本。）

目前构建了一个简单的查询论文并给出摘要的tool：`ArxivSearchTool`，调用arxiv的public API（应该需要挂梯子才能正常使用吧？），目前限制返回条目数为3，输出纯文本的论文title+summary

在大家的架子搭起来以后，我可以再改一改tools的格式