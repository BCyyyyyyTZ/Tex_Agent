#memory/simple_memory.py

import json
import math
import re
from typing import List, Any, Dict, Tuple
from memory.base_memory import BaseMemory,MemoryType
from datetime import datetime  # 正确

class SimpleMemory(BaseMemory):
    """
    基础记忆实现
    - 支持共享模式：所有 Agent 访问同一份数据
    - 支持单独模式：每个 Agent 独立数据
    """
    
    def __init__(self, memory_type: MemoryType = MemoryType.SHARED, 
                 agent_id: str = None, max_size: int = 1000):
        """
        Args:
            memory_type: SHARED（共享）或 PRIVATE（单独）
            agent_id: 当 memory_type=PRIVATE 时，用于区分不同 Agent
            max_size: 最大存储条数
        """
        self.memory_type = memory_type
        self.agent_id = agent_id
        self.max_size = max_size
        self._storage = []  # 简单列表存储
        self._index = {}    # 索引
        
    def save(self, key: str, value: Any, metadata: Dict = None) -> None:
        """保存记忆"""
        memory_item = {
            "key": key,
            "value": value,
            "metadata": metadata or {},
            "timestamp": datetime.now(),
            "agent": self.agent_id
        }
        
        self._storage.append(memory_item)
        
        # 保持大小限制
        if len(self._storage) > self.max_size:
            self._storage.pop(0)
        
        # 更新索引
        self._index[key] = memory_item

    
    def load(self, key: str = None, limit: int = None) -> List[Any]:
        """加载记忆"""
        if key:
            # 加载特定 key
            return [self._index[key]["value"]] if key in self._index else []
        
        # 加载所有
        items = self._storage
        if limit:
            items = items[-limit:]
        return [item["value"] for item in items]
    
    def search(self, query: str, limit: int = 10) -> List[Any]:
        """
        混合检索（关键词 + 重叠度 + 新近性）：
        - 子串精确匹配（query in doc）给予高权重
        - token 覆盖率 / Jaccard 相似度
        - 较新的记忆有轻微加权（避免旧内容长期压制）
        """
        lim = max(1, int(limit or 10))
        q = (query or "").strip()
        if not q:
            return [item["value"] for item in self._storage[-lim:]][::-1]

        q_tokens = self._tokenize(q)
        scored: List[Tuple[float, datetime, Any]] = []

        for idx, item in enumerate(self._storage):
            doc = self._build_search_document(item)
            if not doc:
                continue
            score = self._score_query_doc(q, q_tokens, doc, idx)
            if score <= 0:
                continue
            ts = item.get("timestamp")
            if not isinstance(ts, datetime):
                ts = datetime.min
            scored.append((score, ts, item["value"]))

        # 分数优先，其次按时间新到旧
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

        results: List[Any] = []
        seen = set()
        for _, _, value in scored:
            key = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
            if key in seen:
                continue
            seen.add(key)
            results.append(value)
            if len(results) >= lim:
                break
        return results

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        轻量 tokenizer：
        - 英文/数字按词
        - 中文按连续汉字块 + 二元切片（提升短语召回）
        """
        t = (text or "").lower().strip()
        if not t:
            return []
        en_tokens = re.findall(r"[a-z0-9_]+", t)
        zh_chunks = re.findall(r"[\u4e00-\u9fff]+", t)
        zh_tokens: List[str] = []
        for chunk in zh_chunks:
            zh_tokens.append(chunk)
            if len(chunk) >= 2:
                zh_tokens.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))
        # 去重并保序
        out: List[str] = []
        seen = set()
        for tok in en_tokens + zh_tokens:
            if tok and tok not in seen:
                seen.add(tok)
                out.append(tok)
        return out

    @staticmethod
    def _build_search_document(item: Dict[str, Any]) -> str:
        key = str(item.get("key", "") or "")
        value = item.get("value", "")
        metadata = item.get("metadata", {}) or {}
        parts = [key]
        if isinstance(value, str):
            parts.append(value)
        else:
            parts.append(json.dumps(value, ensure_ascii=False, default=str))
        if isinstance(metadata, dict) and metadata:
            parts.append(json.dumps(metadata, ensure_ascii=False, default=str))
        return "\n".join(parts).lower()

    def _score_query_doc(self, query: str, q_tokens: List[str], doc: str, idx: int) -> float:
        if not doc:
            return 0.0
        doc_tokens = set(self._tokenize(doc))
        if not doc_tokens:
            return 0.0

        q_token_set = set(q_tokens)
        overlap = q_token_set & doc_tokens
        overlap_ratio = len(overlap) / max(1, len(q_token_set))
        jaccard = len(overlap) / max(1, len(q_token_set | doc_tokens))

        contains_exact = 1.0 if query.lower() in doc else 0.0
        key_boost = 0.6 if str(self._storage[idx].get("key", "")).lower().find(query.lower()) >= 0 else 0.0
        # 越新 idx 越大，log 缓和，防止时间项过强
        recency = math.log1p(idx + 1) / max(1.0, math.log1p(len(self._storage)))

        score = (
            2.2 * contains_exact
            + 1.8 * overlap_ratio
            + 0.8 * jaccard
            + key_boost
            + 0.35 * recency
        )
        return score
    
    def clear(self) -> None:
        """清空记忆"""
        self._storage.clear()
        self._index.clear()
    
    def get_size(self) -> int:
        return len(self._storage)
