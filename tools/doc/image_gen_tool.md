# image_gen_tool.py

## 模块说明

[扩展] ImageGenTool 接口定义。
预留接入 DALL-E / Stable Diffusion 等图像生成 API 的工具接口。

TODO: 开发者 C 负责实现此类（第四阶段任务）

## API 概览

### 类

- `ImageGenTool`：[扩展] 图像生成工具抽象基类。

## 类与方法

### ImageGenTool

[扩展] 图像生成工具抽象基类。

方法：

- `name(self)`：返回工具唯一标识符（用于路由与注册）。
- `description(self)`：返回工具用途说明（用于向模型/用户展示能力与输入输出）。
- `generate(self, prompt, style=..., size=..., save_path=...)`：根据 prompt 生成图像。
- `run(self, input)`：执行图像生成任务（占位实现）。
