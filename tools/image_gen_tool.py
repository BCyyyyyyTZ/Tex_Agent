"""
[扩展] ImageGenTool 接口定义。
预留接入 DALL-E / Stable Diffusion 等图像生成 API 的工具接口。

TODO: 开发者 C 负责实现此类（第四阶段任务）
"""
from abc import abstractmethod
from typing import Optional

from tools.base_tool import BaseTool
from core.message import ToolResult


class ImageGenTool(BaseTool):
    """
    [扩展] 图像生成工具抽象基类。

    功能规划：
        1. 根据用户文字描述（prompt）生成精确的学术示意图、流程图
        2. 支持 DALL-E 3 / Stable Diffusion XL 等主流图像生成模型
        3. 支持风格控制（简洁线框图、彩色流程图、学术示意图等）
        4. 支持图像保存与 URL 返回两种输出模式

    TODO: 开发者 C 实现建议：
          - DALL-E 3：通过 openai 库的 client.images.generate() 调用
          - SD：通过 stability-sdk 或 Replicate API 调用
          - 生成的图像可直接嵌入 LaTeX 文档（\\includegraphics）
    """

    @property
    def name(self) -> str:
        """返回工具唯一标识符（用于路由与注册）。"""
        return "image_generation"

    @property
    def description(self) -> str:
        """返回工具用途说明（用于向模型/用户展示能力与输入输出）。"""
        return (
            "根据文字描述（prompt）生成图像，适用于论文配图、流程图、示意图等场景。"
            "支持 DALL-E / Stable Diffusion 等主流图像生成模型。"
            "输入图像描述文本，返回生成的图像文件路径或 URL。"
        )

    @abstractmethod
    def generate(
        self,
        prompt: str,
        style: Optional[str] = None,
        size: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> str:
        """
        根据 prompt 生成图像。

        Args:
            prompt: 图像内容描述（自然语言，建议英文以获得最佳效果）。
            style: 图像风格提示（如 "academic diagram", "flowchart", "minimal white background"）。
            size: 图像尺寸（如 "1024x1024", "1792x1024"）。
            save_path: 图像本地保存路径（None 则只返回 URL 不保存）。

        Returns:
            图像文件的本地路径或远程 URL。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def run(self, input: str) -> ToolResult:
        """
        执行图像生成任务（占位实现）。

        TODO: 开发者 C 在此实现 prompt 解析与图像生成调用逻辑，
              将 input 字符串解析为 prompt 和可选参数后调用 generate()。
        """
        raise NotImplementedError(
            "ImageGenTool.run() 尚未实现。"
            "请参考 generate() 接口文档进行实现，接入 DALL-E / SD API。"
        )
