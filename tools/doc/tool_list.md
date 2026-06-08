# tool_list.py

## 模块说明

工具注册表（tool_list）。

该文件负责集中实例化并注册所有可供 Agent/Workflow 调用的工具。

约定：
- key 为工具对外暴露的名称（tool_name）
- value 为对应的 BaseTool 实例

新增工具的步骤通常是：
1) 在 tools/ 目录实现 BaseTool 子类
2) 在此处 import 并加入 tool_list 字典

## API 概览

（无公开类/函数）
