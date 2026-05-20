"""
Memory Search Module - Mem0 + Qdrant
Replaces ChromaDB with Mem0-managed Qdrant for superior fact-based recall.

Architecture:
- Qdrant (local, on-disk): stores raw message vectors — fast semantic search
- Mem0 (local): extracts and stores discrete facts from conversations
- ChromaDB (legacy): dual-write kept during transition, read-fallback only

Retrieval on every query:
1. Qdrant vector search  — finds semantically similar raw messages
2. Mem0 fact search      — finds extracted facts matching the query
3. Results merged and deduplicated before returning to core.py

All interfaces identical to original memory_search.py — core.py unchanged.
"""

import logging
import os
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

# ChromaDB - legacy dual-write
import chromadb
from chromadb.config import Settings

# Qdrant - new primary vector store
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter,
    FieldCondition, MatchValue, MatchAny
)

# Mem0 - fact extraction layer
from mem0 import Memory as Mem0Memory

logger = logging.getLogger(__name__)

# Qdrant collection name
QDRANT_COLLECTION = "neximus_memories"

# Embedding dimension — must match MiniLM (384)
EMBEDDING_DIM = 384


class MemorySearch:
    """
    Dual-layer memory search:
    - Qdrant for fast vector similarity search
    - Mem0 for structured fact extraction and recall
    - ChromaDB legacy dual-write for safety
    """

    def __init__(self, persist_directory: str = "./memory_store", grok_client=None):
        self.persist_directory = persist_directory
        self.grok_client = grok_client
        self.qdrant_path = persist_directory.rstrip("/") + "_qdrant"
        self.mem0_path = persist_directory.rstrip("/") + "_mem0"

        os.makedirs(persist_directory, exist_ok=True)
        os.makedirs(self.qdrant_path, exist_ok=True)
        os.makedirs(self.mem0_path, exist_ok=True)

        # ── ChromaDB (legacy dual-write) ──────────────────────────────────
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name="conversation_memories",
                metadata={"description": "All conversation messages with embeddings"}
            )
            logger.info(f"ChromaDB loaded: {self.collection.count()} messages")
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")
            self.collection = None

        # ── Qdrant (new primary vector store) ────────────────────────────
        try:
            self.qdrant = QdrantClient(path=self.qdrant_path)
            self._ensure_qdrant_collection()
            logger.info("Qdrant initialized")
        except Exception as e:
            logger.error(f"Qdrant init failed: {e}")
            self.qdrant = None

        # ── Mem0 (fact extraction) ────────────────────────────────────────
        try:
            self.mem0 = self._init_mem0()
            logger.info("Mem0 initialized")
        except Exception as e:
            logger.error(f"Mem0 init failed: {e}")
            self.mem0 = None

        logger.info("MemorySearch initialized (Qdrant + Mem0 + ChromaDB legacy)")

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def _ensure_qdrant_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        existing = [c.name for c in self.qdrant.get_collections().collections]
        if QDRANT_COLLECTION not in existing:
            self.qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
            )
            logger.info(f"Qdrant collection '{QDRANT_COLLECTION}' created")

    def _init_mem0(self):
        """
        Initialize Mem0 with local Qdrant backend.
        Fact extraction uses simple_chat() from the existing grok client
        so no separate API key is needed.
        """
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "neximus_facts",
                    "path": self.mem0_path,
                    "embedding_model_dims": EMBEDDING_DIM,
                    "on_disk": True,
                }
            },
            # Grok API is OpenAI-compatible — use openai provider with xAI base URL
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "grok-3-fast",
                    "api_key": os.environ.get("GROK_API_KEY", ""),
                    "openai_base_url": "https://api.x.ai/v1",
                    "temperature": 0,
                    "max_tokens": 2000,
                }
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": "sentence-transformers/all-MiniLM-L6-v2",
                }
            },
        }
        return Mem0Memory.from_config(config)

    # ------------------------------------------------------------------
    # Public API - identical signatures to original memory_search.py
    # ------------------------------------------------------------------

    def add_message(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content: str,
        embedding: List[float],
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add a message to all memory stores.
        - ChromaDB: synchronous dual-write (legacy safety)
        - Qdrant: synchronous vector store
        - Mem0: async fact extraction (non-blocking, background thread)
        """
        meta = {
            "conversation_id": conversation_id,
            "role": role,
            "timestamp": timestamp.isoformat(),
        }
        if metadata:
            meta.update(metadata)

        # 1. ChromaDB legacy dual-write
        if self.collection:
            try:
                self.collection.add(
                    ids=[message_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[meta]
                )
            except Exception as e:
                logger.debug(f"ChromaDB add skipped (likely duplicate): {e}")

        # 2. Qdrant vector store
        if self.qdrant:
            try:
                self.qdrant.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=[PointStruct(
                        id=self._id_to_int(message_id),
                        vector=embedding,
                        payload={
                            "message_id": message_id,
                            "conversation_id": conversation_id,
                            "role": role,
                            "content": content,
                            "timestamp": timestamp.isoformat(),
                        }
                    )]
                )
            except Exception as e:
                logger.error(f"Qdrant add failed: {e}")

        # 3. Mem0 fact extraction — background thread so it doesn't block chat
        if self.mem0 and role == "user":
            threading.Thread(
                target=self._mem0_add_background,
                args=(content, conversation_id),
                daemon=True
            ).start()

    def search_similar(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        conversation_id_filter: Optional[str] = None,
        exclude_conversation: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search by embedding vector using Qdrant."""
        if not self.qdrant:
            return self._chroma_search_similar(
                query_embedding, n_results,
                conversation_id_filter, exclude_conversation
            )

        try:
            # Build filter
            qdrant_filter = None
            if conversation_id_filter:
                qdrant_filter = Filter(must=[
                    FieldCondition(key="conversation_id",
                                   match=MatchValue(value=conversation_id_filter))
                ])
            elif exclude_conversation:
                # Qdrant doesn't have $ne directly — use must_not
                from qdrant_client.models import IsEmptyCondition
                qdrant_filter = Filter(must_not=[
                    FieldCondition(key="conversation_id",
                                   match=MatchValue(value=exclude_conversation))
                ])

            # qdrant-client >= 1.7 uses query_points(); older uses search()
            if hasattr(self.qdrant, 'query_points'):
                response = self.qdrant.query_points(
                    collection_name=QDRANT_COLLECTION,
                    query=query_embedding,
                    limit=n_results,
                    query_filter=qdrant_filter,
                    with_payload=True
                )
                hits = response.points
            else:
                hits = self.qdrant.search(
                    collection_name=QDRANT_COLLECTION,
                    query_vector=query_embedding,
                    limit=n_results,
                    query_filter=qdrant_filter,
                    with_payload=True
                )

            formatted = []
            for r in hits:
                payload = r.payload or {}
                formatted.append({
                    'id': payload.get('message_id', str(r.id)),
                    'content': payload.get('content', ''),
                    'metadata': {
                        'conversation_id': payload.get('conversation_id', ''),
                        'role': payload.get('role', 'unknown'),
                        'timestamp': payload.get('timestamp', ''),
                    },
                    'distance': 1.0 - r.score  # Convert cosine similarity to distance
                })

            logger.info(f"Qdrant search returned {len(formatted)} results")
            return formatted

        except Exception as e:
            logger.error(f"Qdrant search failed, falling back to ChromaDB: {e}")
            return self._chroma_search_similar(
                query_embedding, n_results,
                conversation_id_filter, exclude_conversation
            )

    def search_by_text(
        self,
        query_text: str,
        embedding_generator,
        n_results: int = 5,
        exclude_conversation: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search by text — combines Qdrant vector search with Mem0 fact search.
        Returns merged, deduplicated results.
        """
        # 1. Qdrant vector search
        query_embedding = embedding_generator.generate_embedding(query_text)
        vector_results = self.search_similar(
            query_embedding=query_embedding,
            n_results=n_results,
            exclude_conversation=exclude_conversation
        )

        # 2. Mem0 fact search
        mem0_results = self._mem0_search(query_text, n_results)

        # 3. Merge and deduplicate
        seen = set()
        merged = []

        # Mem0 facts first — they're higher quality extracted facts
        for r in mem0_results:
            content = r['content']
            if content not in seen and len(content.strip()) > 10:
                seen.add(content)
                merged.append(r)

        # Then vector results
        for r in vector_results:
            content = r['content']
            if content not in seen and len(content.strip()) > 10:
                seen.add(content)
                merged.append(r)

        logger.info(f"Merged search: {len(mem0_results)} facts + {len(vector_results)} vectors = {len(merged)} unique")
        return merged[:n_results * 2]  # Return more since we have two sources

    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all messages from a specific conversation."""
        if self.qdrant:
            try:
                results, _ = self.qdrant.scroll(
                    collection_name=QDRANT_COLLECTION,
                    scroll_filter=Filter(must=[
                        FieldCondition(key="conversation_id",
                                       match=MatchValue(value=conversation_id))
                    ]),
                    limit=1000,
                    with_payload=True
                )
                return [{
                    'id': p.payload.get('message_id', str(p.id)),
                    'content': p.payload.get('content', ''),
                    'metadata': {
                        'conversation_id': p.payload.get('conversation_id', ''),
                        'role': p.payload.get('role', 'unknown'),
                        'timestamp': p.payload.get('timestamp', ''),
                    }
                } for p in results]
            except Exception as e:
                logger.error(f"Qdrant get_conversation_messages failed: {e}")

        # Fallback to ChromaDB
        if self.collection:
            try:
                results = self.collection.get(
                    where={"conversation_id": conversation_id}
                )
                formatted = []
                if results and results['ids']:
                    for i in range(len(results['ids'])):
                        formatted.append({
                            'id': results['ids'][i],
                            'content': results['documents'][i],
                            'metadata': results['metadatas'][i]
                        })
                return formatted
            except Exception as e:
                logger.error(f"ChromaDB get_conversation_messages failed: {e}")
        return []

    def get_user_facts(self, embedding_generator, n_results: int = 10) -> List[str]:
        """
        Get key facts about the user.
        Mem0 is the primary source — it stores extracted facts, not raw messages.
        Falls back to ChromaDB keyword search if Mem0 is unavailable.
        """
        facts = []
        seen = set()

        # Primary: Mem0 fact retrieval
        if self.mem0:
            try:
                queries = [
                    "user name preferences family",
                    "PLC camera boom syntax commands",
                    "remember that important fact",
                    "Tony Dredge Group Neximus"
                ]
                for q in queries:
                    results = self._mem0_search(q, n_results=5)
                    for r in results:
                        content = r['content']
                        if content not in seen and len(content.strip()) > 10:
                            seen.add(content)
                            facts.append(content)
            except Exception as e:
                logger.warning(f"Mem0 get_user_facts failed: {e}")

        # Fallback: ChromaDB keyword search
        if len(facts) < n_results and self.collection:
            queries = ["my name is", "I am", "remember that"]
            for query in queries:
                query_embedding = embedding_generator.generate_embedding(query)
                results = self._chroma_search_similar(query_embedding, n_results=3)
                for r in results:
                    content = r['content']
                    if r['metadata'].get('role') == 'user' and content not in seen:
                        seen.add(content)
                        facts.append(content)

        return facts[:n_results]

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory store."""
        stats = {"persist_directory": self.persist_directory}

        if self.collection:
            stats["chroma_messages"] = self.collection.count()

        if self.qdrant:
            try:
                info = self.qdrant.get_collection(QDRANT_COLLECTION)
                stats["qdrant_vectors"] = info.points_count
            except Exception:
                stats["qdrant_vectors"] = 0

        if self.mem0:
            try:
                all_facts = self.mem0.get_all(filters={"user_id": "neximus"})
                stats["mem0_facts"] = len(all_facts.get("results", []))
            except Exception:
                stats["mem0_facts"] = 0

        # total_messages key kept for compatibility with core.py
        stats["total_messages"] = stats.get("chroma_messages",
                                   stats.get("qdrant_vectors", 0))
        return stats

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mem0_add_background(self, content: str, conversation_id: str):
        """Background thread: extract facts from message via Mem0."""
        try:
            self.mem0.add(
                content,
                user_id="neximus",
                metadata={"conversation_id": conversation_id}
            )
        except Exception as e:
            logger.debug(f"Mem0 background add failed: {e}")

    def _mem0_search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search Mem0 facts store."""
        if not self.mem0:
            return []
        try:
            results = self.mem0.search(query, filters={"user_id": "neximus"}, limit=n_results)
            facts = results.get("results", []) if isinstance(results, dict) else results
            formatted = []
            for f in facts:
                memory_text = f.get("memory", f.get("text", ""))
                if memory_text:
                    formatted.append({
                        'id': f.get("id", ""),
                        'content': memory_text,
                        'metadata': {'role': 'fact', 'source': 'mem0'},
                        'distance': 1.0 - float(f.get("score", 0.5))
                    })
            return formatted
        except Exception as e:
            logger.debug(f"Mem0 search failed: {e}")
            return []

    def _chroma_search_similar(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        conversation_id_filter: Optional[str] = None,
        exclude_conversation: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """ChromaDB fallback search."""
        if not self.collection:
            return []
        try:
            where_filter = None
            if conversation_id_filter:
                where_filter = {"conversation_id": conversation_id_filter}
            elif exclude_conversation:
                where_filter = {"conversation_id": {"$ne": exclude_conversation}}

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter
            )

            formatted = []
            if results and results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    formatted.append({
                        'id': results['ids'][0][i],
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if 'distances' in results else None
                    })
            return formatted
        except Exception as e:
            logger.error(f"ChromaDB fallback search failed: {e}")
            return []

    def _id_to_int(self, message_id: str) -> int:
        """
        Convert string message ID to int for Qdrant.
        Qdrant requires integer or UUID point IDs.
        Uses hash — collision risk is negligible for this scale.
        """
        return abs(hash(message_id)) % (2 ** 53)


def initialize_memory_search(
    persist_directory: str = "./memory_store",
    grok_client=None
) -> MemorySearch:
    """Initialize and return memory search."""
    try:
        memory = MemorySearch(persist_directory, grok_client=grok_client)
        logger.info("Memory search initialized successfully (Mem0 + Qdrant)")
        return memory
    except Exception as e:
        logger.error(f"Failed to initialize memory search: {e}")
        raise
