"""
Memory Search Module
Semantic search across all conversations using ChromaDB
"""

import chromadb
from chromadb.config import Settings
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class MemorySearch:
    """Semantic memory search using ChromaDB vector database"""
    
    def __init__(self, persist_directory: str = "./memory_store"):
        """
        Initialize memory search
        
        Args:
            persist_directory: Directory to store ChromaDB data
        """
        self.persist_directory = persist_directory
        
        # Create directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection for messages
        self.collection = self.client.get_or_create_collection(
            name="conversation_memories",
            metadata={"description": "All conversation messages with embeddings"}
        )
        
        logger.info(f"Memory search initialized. Collection size: {self.collection.count()}")
    
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
        Add a message to the memory store
        
        Args:
            message_id: Unique message ID
            conversation_id: Conversation this message belongs to
            role: 'user' or 'assistant'
            content: Message text
            embedding: Vector embedding of the message
            timestamp: When the message was created
            metadata: Additional metadata
        """
        meta = {
            "conversation_id": conversation_id,
            "role": role,
            "timestamp": timestamp.isoformat(),
        }
        
        if metadata:
            meta.update(metadata)
        
        try:
            self.collection.add(
                ids=[message_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[meta]
            )
            logger.debug(f"Added message to memory: {message_id}")
        except Exception as e:
            logger.error(f"Failed to add message to memory: {e}")
    
    def search_similar(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        conversation_id_filter: Optional[str] = None,
        exclude_conversation: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar messages by embedding
        
        Args:
            query_embedding: Query vector
            n_results: Number of results to return
            conversation_id_filter: Only search within this conversation
            exclude_conversation: Exclude this conversation from results
        
        Returns:
            List of similar messages with metadata and similarity scores
        """
        try:
            # Build where filter
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
            
            # Format results
            formatted_results = []
            if results and results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        'id': results['ids'][0][i],
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if 'distances' in results else None
                    })
            
            logger.info(f"Memory search returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []
    
    def search_by_text(
        self,
        query_text: str,
        embedding_generator,
        n_results: int = 5,
        exclude_conversation: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search by text (will generate embedding automatically)
        
        Args:
            query_text: Text to search for
            embedding_generator: EmbeddingGenerator instance
            n_results: Number of results
            exclude_conversation: Conversation ID to exclude
        
        Returns:
            List of similar messages
        """
        # Generate embedding for query
        query_embedding = embedding_generator.generate_embedding(query_text)
        
        # Search
        return self.search_similar(
            query_embedding=query_embedding,
            n_results=n_results,
            exclude_conversation=exclude_conversation
        )
    
    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages from a specific conversation
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            List of messages
        """
        try:
            results = self.collection.get(
                where={"conversation_id": conversation_id}
            )
            
            formatted_results = []
            if results and results['ids']:
                for i in range(len(results['ids'])):
                    formatted_results.append({
                        'id': results['ids'][i],
                        'content': results['documents'][i],
                        'metadata': results['metadatas'][i]
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to get conversation messages: {e}")
            return []
    
    def get_user_facts(self, embedding_generator, n_results: int = 10) -> List[str]:
        """
        Extract key facts about the user from past conversations
        
        Args:
            embedding_generator: EmbeddingGenerator instance
            n_results: Number of messages to analyze
        
        Returns:
            List of user facts/information
        """
        # Search for user introductions and personal information
        queries = [
            "my name is",
            "I am",
            

            "remember that"
        ]
        
        facts = []
        seen_content = set()
        
        for query in queries:
            results = self.search_by_text(
                query_text=query,
                embedding_generator=embedding_generator,
                n_results=3
            )
            
            for result in results:
                content = result['content']
                role = result['metadata'].get('role')
                
                # Only consider user messages
                if role == 'user' and content not in seen_content:
                    seen_content.add(content)
                    facts.append(content)
        
        return facts[:n_results]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory store"""
        return {
            "total_messages": self.collection.count(),
            "persist_directory": self.persist_directory
        }


def initialize_memory_search(persist_directory: str = "./memory_store") -> MemorySearch:
    """Initialize and return memory search"""
    try:
        memory = MemorySearch(persist_directory)
        logger.info("Memory search initialized successfully")
        return memory
    except Exception as e:
        logger.error(f"Failed to initialize memory search: {e}")
        raise
