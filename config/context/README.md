# 上下文 / Prompt 配置说明

## 改哪里

| 需求 | 文件 |
|------|------|
| 四种模式（legacy / pipeline / dialogue / auto_single）的全部行为 | **`config/context_profiles.py`** → `PROFILES` |
| Web mode / workflow 用哪个 Profile | 同文件 → `ROUTING` |
| 意图关键词（记住我、echo、3000字…） | 同文件 → `INTENT_PATTERNS` |
| 简答/长篇终节点契约全文 | 同文件 → `DELIVERY_BRIEF_DEFAULT` / `DELIVERY_FULL_DEFAULT` |
| Plan 规划额外原则 | 同文件 → `PLANNER` |
| 单次流水线契约、Planner LLM schema | `config/planner_config.py`（与「模式」无关的 Plan 引擎） |
| 某 checklist 节点专家人设 | `config/workflow/workflow_*.json` |

## 四种 Profile 与入口

| Profile | 入口 | 说明 |
|---------|------|------|
| `legacy` | `checklist_*` / `latex_*` / `thesis_*` | 旧 checklist，画像常开、metadata 全开 |
| `pipeline` | `task` 默认 | 通用任务，本轮输入优先 |
| `dialogue` | `plan` | 动态规划图 |
| `auto_single` | `auto` | 单轮对话；`agent` 小节含 SYSTEM 人设 |

## 代码如何加载

```
context_profiles.py  （配置正文）
        ↓
context_settings.py  （解析、合并节点覆盖、拼 prompt）
        ↓
workflow/nodes.py    （执行时调用）
```

可选：`CONTEXT_CONFIG_PATH=某.json` 在 Python 配置之上做 **局部覆盖**（高级用法）。

## 不再使用

- 勿再编辑 `context_config.json` 作为主配置（已标 `_deprecated`）。
