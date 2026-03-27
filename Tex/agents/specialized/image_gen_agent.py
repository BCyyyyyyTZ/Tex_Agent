# ============================================================
# agents/specialized/image_gen_agent.py
# ImageGenAgent —— 学术图像生成智能体
# ============================================================
# ImageGenAgent 负责根据用户描述生成论文所需的精确图像，
# 包括流程图、架构图、概念图等，接入 DALL-E 和 Stable Diffusion。
#
# 【需要实现的内容】
#
# 1. ImageGenRequest — 图像生成请求
#    字段:
#    - user_description: str         # 用户原始描述
#    - image_type: str               # diagram/flowchart/architecture/concept/photo
#    - style: str                    # academic/technical/minimalist
#    - size: str                     # 1024x1024 / 1792x1024 / 1024x1792
#    - enhanced_prompt: str          # LLM 增强后的提示词（自动填充）
#    - negative_prompt: str          # SD 专用的负面提示词
#    - backend: str                  # "dalle" / "stable_diffusion" / "auto"
#    - quality: str                  # "standard" / "hd" (DALL-E 3 专用)
#
# 2. ImageGenResult — 生成结果
#    字段:
#    - request_id: str
#    - image_path: str               # 本地保存路径
#    - thumbnail_path: str           # 缩略图路径
#    - original_prompt: str
#    - enhanced_prompt: str
#    - backend_used: str
#    - revised_prompt: str           # DALL-E 自动修订后的提示词
#    - latex_figure_code: str        # 插入 LaTeX 的代码
#    - generation_time_ms: int
#
# 3. ImageGenAgent 类（继承 SimpleAgent）
#    agent_type = "image_gen"
#
#    核心方法:
#
#    async generate_image(
#        request: ImageGenRequest
#    ) -> ImageGenResult:
#    - 根据 backend 选择调用 DALL-E 或 Stable Diffusion
#    - "auto" 模式：简单图像用 DALL-E，复杂技术图用 SD
#    - 下载并保存生成的图像
#    - 生成对应的 LaTeX 代码
#
#    async enhance_prompt(
#        user_description: str,
#        image_type: str,
#        context: str = ""
#    ) -> str:
#    - 调用 LLM 将用户的简短描述增强为详细的生成提示词
#    - 添加学术图像所需的风格词（如 "clean lines, white background"）
#    - 针对不同图像类型优化提示词策略
#
#    async generate_diagram(
#        components: list[str],
#        relationships: list[dict],
#        diagram_type: str = "flowchart"
#    ) -> ImageGenResult:
#    - 专门用于生成结构化图表（流程图、架构图等）
#    - 将组件和关系转换为生成提示词
#    - 建议：流程图优先使用 mermaid/tikz 代码方案
#    - 注意：本方法也可以考虑生成 TikZ LaTeX 代码而非位图
#
#    async generate_tikz_diagram(
#        description: str,
#        diagram_type: str
#    ) -> str:
#    - 生成 TikZ/PGF LaTeX 代码来绘制图表（非 AI 图像生成）
#    - 对精确图表（如算法流程图）优先使用此方法
#    - 调用 LLM 生成 TikZ 代码并验证语法
#
#    async batch_generate(
#        requests: list[ImageGenRequest]
#    ) -> list[ImageGenResult]:
#    - 批量生成多张图像（并发处理）
#
#    _select_backend(request: ImageGenRequest) -> str:
#    - 根据图像类型和复杂度选择后端
#    - 技术/精确图 -> DALL-E 3
#    - 艺术/概念图 -> Stable Diffusion
#    - 简单示意图 -> 考虑 TikZ
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.base.simple_agent import SimpleAgent
from core.base_agent import AgentResult, TaskContext


@dataclass
class ImageGenRequest:
    """图像生成请求，【实现字段见上方注释】"""
    user_description: str = ""
    image_type: str = "diagram"
    style: str = "technical"
    size: str = "1024x1024"
    enhanced_prompt: str = ""
    negative_prompt: str = ""
    backend: str = "auto"
    quality: str = "standard"


@dataclass
class ImageGenResult:
    """图像生成结果，【实现字段见上方注释】"""
    request_id: str = ""
    image_path: str = ""
    thumbnail_path: str = ""
    original_prompt: str = ""
    enhanced_prompt: str = ""
    backend_used: str = ""
    revised_prompt: str = ""
    latex_figure_code: str = ""
    generation_time_ms: int = 0


class ImageGenAgent(SimpleAgent):
    """
    学术图像生成专家 Agent。
    集成 DALL-E 和 Stable Diffusion，支持多种图像类型。
    【完整实现规范见上方注释】
    """

    agent_type: str = "image_gen"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str = "ImageGenAgent",
        config: Optional[Any] = None,
    ) -> None:
        super().__init__(name=name, config=config)
        self.preferred_backend: str = "dalle"
        self.default_image_size: str = "1024x1024"
        self.max_images_per_request: int = 4
        self.enable_prompt_enhancement: bool = True
        self.output_dir: str = "./data/exports/images"

    async def generate_image(
        self, request: ImageGenRequest
    ) -> ImageGenResult:
        """生成图像主入口，【需要实现】"""
        pass

    async def enhance_prompt(
        self,
        user_description: str,
        image_type: str,
        context: str = "",
    ) -> str:
        """LLM 提示词增强，【需要实现】"""
        pass

    async def generate_diagram(
        self,
        components: List[str],
        relationships: List[Dict[str, Any]],
        diagram_type: str = "flowchart",
    ) -> ImageGenResult:
        """结构化图表生成，【需要实现】"""
        pass

    async def generate_tikz_diagram(
        self, description: str, diagram_type: str
    ) -> str:
        """生成 TikZ LaTeX 图表代码，【需要实现】"""
        pass

    async def batch_generate(
        self, requests: List[ImageGenRequest]
    ) -> List[ImageGenResult]:
        """批量图像生成，【需要实现】"""
        pass

    def _select_backend(self, request: ImageGenRequest) -> str:
        """选择图像生成后端，【需要实现】"""
        pass
