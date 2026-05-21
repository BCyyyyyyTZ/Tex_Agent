"""
TeX_Agent LaTeX 子系统：契约、序列化、项目扫描、诊断合并与切片（阶段 0–5）。
"""
from latex.constants import (
    METADATA_LATEX_DIAGNOSTICS,
    METADATA_LATEX_DIRTY,
    METADATA_LATEX_LAST_GOOD_BUILD,
    METADATA_LATEX_PROJECT,
    METADATA_LATEX_SUGGESTIONS,
    IssueSource,
    Severity,
)
from latex.bib_index import enrich_bibliography, enrich_project_index
from latex.conventions_index import build_conventions, enrich_conventions, parse_preamble
from latex.models import (
    AlgorithmConvention,
    BibEntry,
    DiagnosticIssue,
    LabelDef,
    MacroDef,
    Position,
    ProjectConventions,
    ProjectFile,
    ProjectIndex,
    RefEntry,
    Suggestion,
    TextRange,
    make_issue_id,
)
from latex.refs_index import enrich_refs_index
from latex.paths import normalize_rel_path, path_from_user_string, resolve_tex_file
from latex.project_index import build_project_index, extract_inputs, file_checksum
from latex.serialize import from_dict, from_json, to_dict, to_json
from latex.single_file_parser import parse_tex_file, parse_tex_source
from latex.issues import merge_issue_lists, merge_issues
from latex.slice import IssueSlice, slice_around_issue, slice_issues
from latex.dirty import baseline_from_index, compute_file_dirty

__all__ = [
    "AlgorithmConvention",
    "BibEntry",
    "DiagnosticIssue",
    "IssueSource",
    "LabelDef",
    "MacroDef",
    "METADATA_LATEX_DIAGNOSTICS",
    "METADATA_LATEX_DIRTY",
    "METADATA_LATEX_LAST_GOOD_BUILD",
    "METADATA_LATEX_PROJECT",
    "METADATA_LATEX_SUGGESTIONS",
    "Position",
    "ProjectConventions",
    "ProjectFile",
    "ProjectIndex",
    "RefEntry",
    "Severity",
    "Suggestion",
    "TextRange",
    "build_conventions",
    "build_project_index",
    "enrich_bibliography",
    "enrich_conventions",
    "enrich_project_index",
    "enrich_refs_index",
    "parse_preamble",
    "extract_inputs",
    "file_checksum",
    "normalize_rel_path",
    "parse_tex_file",
    "parse_tex_source",
    "path_from_user_string",
    "resolve_tex_file",
    "IssueSlice",
    "baseline_from_index",
    "compute_file_dirty",
    "from_dict",
    "from_json",
    "make_issue_id",
    "merge_issue_lists",
    "merge_issues",
    "slice_around_issue",
    "slice_issues",
    "to_dict",
    "to_json",
]
