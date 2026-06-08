"""
模型与 JSON 互转，供 Tool、metadata、测试复用。
"""
from __future__ import annotations

from typing import Any, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def to_json(model: BaseModel, *, indent: int | None = None) -> str:
    return model.model_dump_json(indent=indent)


def from_json(model_cls: Type[T], data: str | bytes) -> T:
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return model_cls.model_validate_json(data)


def to_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def from_dict(model_cls: Type[T], data: dict[str, Any]) -> T:
    return model_cls.model_validate(data)
