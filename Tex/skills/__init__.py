# skills/__init__.py — 技能模块统一入口
from skills.skill_registry import SkillRegistry, SkillMeta, register_skill, get_skill_registry
from skills.skill_executor import SkillExecutor, SkillInput, SkillOutput
from skills.academic import (
    LiteratureReviewSkill, AbstractWritingSkill, IntroductionWritingSkill,
    MethodologySkill, ConclusionSkill, CitationSkill,
)
from skills.technical import (
    EquationFormattingSkill, TableCreationSkill,
    AlgorithmDescriptionSkill, CodeListingSkill,
)
from skills.analytical import DataAnalysisSkill, ResultInterpretationSkill

__all__ = [
    "SkillRegistry", "SkillMeta", "register_skill", "get_skill_registry",
    "SkillExecutor", "SkillInput", "SkillOutput",
    "LiteratureReviewSkill", "AbstractWritingSkill", "IntroductionWritingSkill",
    "MethodologySkill", "ConclusionSkill", "CitationSkill",
    "EquationFormattingSkill", "TableCreationSkill",
    "AlgorithmDescriptionSkill", "CodeListingSkill",
    "DataAnalysisSkill", "ResultInterpretationSkill",
]
