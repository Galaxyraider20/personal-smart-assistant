"""
Supermemory Client using Official Python SDK
Fixed with correct response handling
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    from supermemory import Supermemory
except ImportError:
    Supermemory = None

from ..utils.config import config
from ..utils.helpers import safe_execute

logger = logging.getLogger(__name__)

class SupermemoryClient:
    """
    Client for Supermemory using official Python SDK
    Handles persistent memory and context management for myAssist
    """
    
    def __init__(self):
        """Initialize Supermemory client"""
        self.api_key = config.supermemory.api_key
        self.user_id = config.supermemory.user_id
        self.memory_space = config.supermemory.memory_space
        self.client = None
        self.is_connected = False
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        if not Supermemory:
            logger.error("Supermemory package not installed. Run: pip install supermemory")
            return
            
        logger.info("Supermemory client initialized")
    
    async def initialize(self) -> bool:
        """Initialize Supermemory client and validate connection"""
        try:
            logger.info("Initializing Supermemory client...")
            
            if not Supermemory:
                logger.error("Supermemory package not available")
                return False
            
            if not self.api_key:
                logger.error("Supermemory API key not configured")
                return False
            
            # Initialize the official client (sync)
            try:
                self.client = Supermemory(api_key=self.api_key)
                logger.info("Supermemory client instance created")
            except Exception as e:
                logger.error(f"Failed to create Supermemory client: {str(e)}")
                return False
            
            # Test connection by adding a test memory (run in thread pool)
            try:
                test_result = await self._run_sync(
                    self._sync_add_memory,
                    "myAssist Calendar Agent initialization test - connection verified"
                )
                
                if test_result:
                    logger.info("Supermemory client authenticated successfully")
                    self.is_connected = True
                    return True
                else:
                    logger.error("Failed to validate Supermemory connection")
                    return False
                    
            except Exception as e:
                logger.error(f"Supermemory test connection failed: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Supermemory initialization error: {str(e)}")
            return False
    
    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous function in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)
    
    def _sync_add_memory(self, content: str) -> bool:
        """Synchronous add memory function"""
        try:
            if not self.client:
                logger.error("No Supermemory client available")
                return False
                
            # Use the SDK's add method - we know it returns MemoryAddResponse
            result = self.client.memories.add(content=content)
            
            # Check if we got a valid response with id and status
            if result and hasattr(result, 'id') and hasattr(result, 'status'):
                logger.info(f"Added memory successfully - ID: {result.id}, Status: {result.status}")
                return True
            else:
                logger.error(f"Unexpected response format: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Sync add memory error: {str(e)}")
            return False
    
    def _sync_search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Synchronous search memories function"""
        try:
            if not self.client:
                logger.error("No Supermemory client available")
                return []
                
            # Use the SDK's search method
            results = self.client.search.memories(q=query, limit=limit)
            
            if results and hasattr(results, 'results'):
                memories = []
                for result in results.results[:limit]:
                    memory_item = {
                        'id': getattr(result, 'id', 'unknown'),
                        'memory': getattr(result, 'memory', str(result)),
                        'similarity': getattr(result, 'similarity', 0.0),
                        'metadata': getattr(result, 'metadata', {}),
                        'updated_at': getattr(result, 'updated_at', None)
                    }
                    memories.append(memory_item)
                
                logger.info(f"Search found {len(memories)} results")
                return memories
            else:
                logger.info("Search returned no results or unexpected format")
                return []
                
        except Exception as e:
            logger.error(f"Sync search memories error: {str(e)}")
            return []
    
    @safe_execute
    async def add_memory(
        self, 
        content: str, 
        container_tag: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add content to memory using SDK (async wrapper)"""
        if not self.is_connected or not self.client:
            logger.warning("Supermemory not connected")
            return False
        
        try:
            result = await self._run_sync(self._sync_add_memory, content)
            if result:
                logger.info(f"Added memory: {content[:50]}...")
            return result
                    
        except Exception as e:
            logger.error(f"Error adding memory: {str(e)}")
            return False
    
    @safe_execute
    async def search_memories(
        self, 
        query: str, 
        limit: int = 5,
        container_tag: Optional[str] = None,
        threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """Search memories using the SDK (async wrapper)"""
        if not self.is_connected or not self.client:
            logger.warning("Supermemory not connected")
            return []
        
        try:
            memories = await self._run_sync(self._sync_search_memories, query, limit)
            logger.info(f"Found {len(memories)} memories for query: {query}")
            return memories
                    
        except Exception as e:
            logger.error(f"Error searching memories: {str(e)}")
            return []
    
    @safe_execute
    async def store_conversation_context(
        self, 
        conversation_id: str, 
        user_message: str, 
        agent_response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store conversation context for future reference"""
        try:
            context_content = f"""
Calendar Agent Conversation
Conversation ID: {conversation_id}
User: {user_message}
Assistant: {agent_response}

This conversation was between a user and myAssist Calendar Agent.
            """.strip()
            
            return await self.add_memory(context_content)
            
        except Exception as e:
            logger.error(f"Error storing conversation context: {str(e)}")
            return False
    
    @safe_execute
    async def get_conversation_history(
        self, 
        conversation_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a specific conversation"""
        try:
            query = f"Conversation ID: {conversation_id}"
            memories = await self.search_memories(query, limit)
            return memories
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return []
    
    @safe_execute
    async def get_relevant_context(
        self, 
        query: str, 
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get relevant context for a user query"""
        try:
            memories = await self.search_memories(query, limit)
            return memories
            
        except Exception as e:
            logger.error(f"Error getting relevant context: {str(e)}")
            return []
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            self.is_connected = False
            self.client = None
            if self.executor:
                self.executor.shutdown(wait=True)
            logger.info("Supermemory client cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    async def get_conversation_context(
        self, 
        user_id: str, 
        conversation_id: str
    ) -> Dict[str, Any]:
        """Get conversation context"""
        try:
            memories = await self.search_memories(f"conversation_id:{conversation_id}", limit=5)
            
            context = {
                'recent_interactions': memories,
                'user_id': user_id,
                'conversation_id': conversation_id
            }
            
            return context
        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return {}

    async def store_interaction(
        self,
        user_id: str,
        conversation_id: str, 
        interaction_type: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Store interaction in memory"""
        try:
            interaction_content = f"""
Interaction Type: {interaction_type}
Conversation: {conversation_id}
Content: {content}
User: {user_id}
            """.strip()
            
            return await self.add_memory(interaction_content, metadata=metadata)
        except Exception as e:
            logger.error(f"Error storing interaction: {str(e)}")
            return False

# Export the client
__all__ = ['SupermemoryClient']
