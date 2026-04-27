"""
兼容旧导入：历史上 PDF 专用；实现委托给 :mod:`ui.web.file_storage`。
"""
from __future__ import annotations

from ui.web import file_storage

REPO_ROOT = file_storage.REPO_ROOT
MAX_PDF_BYTES = file_storage.MAX_UPLOAD_BYTES
PDF_SUBDIR = file_storage.CATEGORY_PDFS  # 目录名 "pdfs"


def pdf_dir():
    return file_storage.category_dir(file_storage.CATEGORY_PDFS)


def ensure_pdf_dir():
    return file_storage.ensure_category_dir(file_storage.CATEGORY_PDFS)


def sanitize_pdf_filename(name: str) -> str:
    return file_storage.sanitize_filename(name, default_stem="document")


def unique_pdf_path(original_name: str):
    return file_storage.unique_stored_path(
        file_storage.CATEGORY_PDFS, original_name
    )


def list_pdf_files():
    return file_storage.list_files(file_storage.CATEGORY_PDFS)


def resolve_safe_pdf_path(filename: str):
    return file_storage.resolve_safe_path(
        file_storage.CATEGORY_PDFS, filename
    )
