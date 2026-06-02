"""顶会投稿日历：读取静态 JSON，计算倒计时（不接入 Agent tools）。"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_JSON = _PROJECT_ROOT / "config" / "conferences" / "deadlines_2026.json"

_cache: Optional[Dict[str, Any]] = None


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s or not str(s).strip():
        return None
    try:
        return datetime.strptime(str(s).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_until(d: Optional[date], today: date) -> Optional[int]:
    if d is None:
        return None
    return (d - today).days


def load_conferences_config(path: Optional[Path] = None) -> Dict[str, Any]:
    global _cache
    p = path or _DEFAULT_JSON
    if _cache is not None and path is None:
        return _cache
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if path is None:
        _cache = data
    return data


def list_deadlines(
    *,
    fields: Optional[List[str]] = None,
    include_past: bool = False,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    返回 Web UI 用的日历数据。

    fields: 如 ["cv", "nlp"]；含 "all" 或空则不过滤领域。
    """
    raw = load_conferences_config()
    today = today or date.today()
    field_defs = raw.get("fields") or []
    wanted = {f.strip().lower() for f in (fields or []) if f and f.strip().lower() != "all"}

    items: List[Dict[str, Any]] = []
    for conf in raw.get("conferences") or []:
        if not isinstance(conf, dict):
            continue
        conf_fields = [str(x).lower() for x in (conf.get("fields") or [])]
        if wanted and not wanted.intersection(conf_fields):
            continue

        ab_d = _parse_date(conf.get("abstract_deadline"))
        full_d = _parse_date(conf.get("full_deadline"))
        conf_start = _parse_date(conf.get("conference_start"))

        future_deadlines: List[tuple[str, date]] = []
        if ab_d and _days_until(ab_d, today) is not None and _days_until(ab_d, today) >= 0:
            future_deadlines.append(("abstract", ab_d))
        if full_d and _days_until(full_d, today) is not None and _days_until(full_d, today) >= 0:
            future_deadlines.append(("full", full_d))

        primary_type = None
        primary_date = None
        days_left = None
        if future_deadlines:
            future_deadlines.sort(key=lambda x: x[1])
            primary_type, primary_date = future_deadlines[0]
            days_left = _days_until(primary_date, today)
        else:
            if not include_past:
                continue
            # 已过期：取最近截止日展示
            candidates = [(t, d) for t, d in (("abstract", ab_d), ("full", full_d)) if d]
            if not candidates:
                continue
            candidates.sort(key=lambda x: x[1], reverse=True)
            primary_type, primary_date = candidates[0]
            days_left = _days_until(primary_date, today)

        urgency = "past"
        if days_left is not None:
            if days_left < 0:
                urgency = "past"
            elif days_left <= 14:
                urgency = "critical"
            elif days_left <= 45:
                urgency = "soon"
            else:
                urgency = "normal"

        items.append(
            {
                "id": conf.get("id", ""),
                "name": conf.get("name", ""),
                "fields": conf_fields,
                "abstract_deadline": conf.get("abstract_deadline"),
                "full_deadline": conf.get("full_deadline"),
                "primary_deadline": primary_date.isoformat() if primary_date else None,
                "primary_type": primary_type,
                "days_left": days_left,
                "urgency": urgency,
                "conference_start": conf.get("conference_start"),
                "venue": conf.get("venue", ""),
                "url": conf.get("url", ""),
                "note": conf.get("note", ""),
            }
        )

    def sort_key(it: Dict[str, Any]) -> tuple:
        dl = it.get("days_left")
        if dl is None:
            return (2, 9999)
        if dl < 0:
            return (1, -dl)
        return (0, dl)

    items.sort(key=sort_key)

    return {
        "meta": raw.get("meta", {}),
        "today": today.isoformat(),
        "fields": field_defs,
        "count": len(items),
        "deadlines": items,
    }
