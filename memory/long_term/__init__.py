# memory/long_term/__init__.py
from memory.long_term.vector_store import VectorStore, ChromaVectorStore, FAISSVectorStore, create_vector_store
from memory.long_term.knowledge_graph import KnowledgeGraph, KGNode, KGEdge
from memory.long_term.user_profile import UserProfile, WritingPreference, ResearchProfile
__all__ = ["VectorStore", "ChromaVectorStore", "FAISSVectorStore", "create_vector_store",
           "KnowledgeGraph", "KGNode", "KGEdge", "UserProfile", "WritingPreference", "ResearchProfile"]
