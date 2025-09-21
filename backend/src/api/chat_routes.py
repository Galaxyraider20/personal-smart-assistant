"""
Chat Routes - User Interaction Endpoints

Provides REST endpoints for user chat interactions, processes natural language
scheduling requests, returns conversational responses and calendar confirmations,
and handles real-time chat functionality.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from ..agent.calendar_agent import CalendarAgent, CalendarRequest, AgentResponse
from ..utils.config import config

logger = logging.getLogger(__name__)

# Request/Response models
class ChatMessage(BaseModel):
    """User chat message model"""
    message: str = Field(..., description="User's natural language message")
    user_id: str = Field(..., description="Unique user identifier")
    conversation_id: Optional[str] = Field(None, description="Conversation session ID")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    
class ChatResponse(BaseModel):
    """Agent response model"""
    message: str = Field(..., description="Agent's response message")
    success: bool = Field(..., description="Whether the request was successful")
    conversation_id: str = Field(..., description="Conversation session ID")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")
    suggestions: Optional[List[str]] = Field(None, description="Suggested follow-up actions")
    requires_confirmation: bool = Field(False, description="Whether user confirmation is needed")
    agent_actions: Optional[List[str]] = Field(None, description="Actions taken by the agent")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")

class ConversationHistory(BaseModel):
    """Conversation history model"""
    conversation_id: str
    messages: List[Dict[str, Any]]
    user_id: str
    created_at: datetime
    last_updated: datetime

class UserPreferences(BaseModel):
    """User preferences model"""
    user_id: str
    preferences: Dict[str, Any]
    last_updated: datetime

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time chat"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept WebSocket connection and add to user's connection list"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user: {user_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        logger.info(f"WebSocket disconnected for user: {user_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        """Send message to all connections for a specific user"""
        if user_id in self.active_connections:
            disconnected = []
            
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending WebSocket message: {str(e)}")
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for connection in disconnected:
                self.active_connections[user_id].remove(connection)

# Global connection manager
connection_manager = ConnectionManager()

# Create router
chat_router = APIRouter()

# Dependency to get calendar agent
async def get_calendar_agent() -> CalendarAgent:
    """Get calendar agent instance from app state"""
    from ..api.main import app
    
    if not hasattr(app.state, 'agent') or app.state.agent is None:
        raise HTTPException(
            status_code=503,
            detail="Calendar agent not initialized"
        )
    return app.state.agent

@chat_router.post("/message", response_model=ChatResponse)
async def send_message(
    chat_message: ChatMessage,
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Process a user chat message and return agent response
    
    Args:
        chat_message: User's natural language message and context
        calendar_agent: Calendar agent instance
        
    Returns:
        ChatResponse: Agent's response with actions and suggestions
    """
    try:
        # Generate conversation ID if not provided
        if not chat_message.conversation_id:
            chat_message.conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        
        logger.info(f"Processing message from user {chat_message.user_id}: {chat_message.message}")
        
        # Process the user request through the calendar agent
        agent_response = await calendar_agent.process_user_request(
            user_message=chat_message.message,
            user_id=chat_message.user_id,
            conversation_id=chat_message.conversation_id
        )
        
        # Convert agent response to API response format
        response = ChatResponse(
            message=agent_response.message,
            success=agent_response.success,
            conversation_id=chat_message.conversation_id,
            data=agent_response.data,
            suggestions=agent_response.suggestions,
            requires_confirmation=agent_response.requires_confirmation,
            agent_actions=agent_response.agent_actions,
            timestamp=datetime.now()
        )
        
        # Send real-time update to WebSocket connections
        ws_message = {
            "type": "agent_response",
            "conversation_id": chat_message.conversation_id,
            "response": response.dict(),
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_personal_message(ws_message, chat_message.user_id)
        
        logger.info(f"Processed message successfully: {agent_response.success}")
        return response
        
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        
        error_response = ChatResponse(
            message=f"I encountered an error processing your request: {str(e)}",
            success=False,
            conversation_id=chat_message.conversation_id or f"conv_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now()
        )
        
        return error_response

@chat_router.get("/conversations/{conversation_id}", response_model=ConversationHistory)
async def get_conversation_history(
    conversation_id: str,
    user_id: str,
    limit: int = 50,
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Retrieve conversation history for a specific conversation
    
    Args:
        conversation_id: Conversation session identifier
        user_id: User identifier for security filtering
        limit: Maximum number of messages to retrieve
        calendar_agent: Calendar agent instance
        
    Returns:
        ConversationHistory: Complete conversation history
    """
    try:
        logger.info(f"Retrieving conversation history: {conversation_id} for user: {user_id}")
        
        # Get conversation context from memory
        context = await calendar_agent.memory_client.get_conversation_context(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=limit
        )
        
        # Get relevant context to build message history
        relevant_memories = await calendar_agent.memory_client.get_relevant_context(
            user_id=user_id,
            query=f"conversation_id:{conversation_id}",
            limit=limit
        )
        
        # Build message list from memories
        messages = []
        for memory in relevant_memories:
            metadata = memory.get("metadata", {})
            interaction_type = metadata.get("interaction_type", "unknown")
            timestamp_str = metadata.get("timestamp", datetime.now().isoformat())
            
            message_entry = {
                "type": interaction_type,
                "content": memory.get("content", ""),
                "timestamp": timestamp_str,
                "metadata": metadata
            }
            messages.append(message_entry)
        
        # Sort messages by timestamp
        messages.sort(key=lambda x: x["timestamp"])
        
        history = ConversationHistory(
            conversation_id=conversation_id,
            messages=messages,
            user_id=user_id,
            created_at=datetime.fromisoformat(messages[0]["timestamp"]) if messages else datetime.now(),
            last_updated=datetime.fromisoformat(messages[-1]["timestamp"]) if messages else datetime.now()
        )
        
        logger.info(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
        return history
        
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation history: {str(e)}"
        )

@chat_router.get("/conversations", response_model=List[Dict[str, Any]])
async def list_user_conversations(
    user_id: str,
    limit: int = 20,
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    List all conversations for a user
    
    Args:
        user_id: User identifier
        limit: Maximum number of conversations to return
        calendar_agent: Calendar agent instance
        
    Returns:
        List of conversation summaries
    """
    try:
        logger.info(f"Listing conversations for user: {user_id}")
        
        # Search for all conversation contexts for the user
        contexts = await calendar_agent.memory_client.get_relevant_context(
            user_id=user_id,
            query="memory_type:context_update",
            limit=limit
        )
        
        conversations = []
        seen_conversations = set()
        
        for context in contexts:
            metadata = context.get("metadata", {})
            conv_id = metadata.get("conversation_id")
            
            if conv_id and conv_id not in seen_conversations:
                seen_conversations.add(conv_id)
                
                # Get latest interaction timestamp
                timestamp_str = metadata.get("timestamp", datetime.now().isoformat())
                
                conversations.append({
                    "conversation_id": conv_id,
                    "last_updated": timestamp_str,
                    "summary": f"Conversation {conv_id[:8]}...",
                    "message_count": 0,  # Could be computed if needed
                    "status": "active"
                })
        
        # Sort by last updated time
        conversations.sort(key=lambda x: x["last_updated"], reverse=True)
        
        logger.info(f"Found {len(conversations)} conversations for user {user_id}")
        return conversations
        
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}"
        )

@chat_router.get("/preferences/{user_id}", response_model=UserPreferences)
async def get_user_preferences(
    user_id: str,
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Get user preferences and learned patterns
    
    Args:
        user_id: User identifier
        calendar_agent: Calendar agent instance
        
    Returns:
        UserPreferences: User's scheduling preferences
    """
    try:
        logger.info(f"Retrieving preferences for user: {user_id}")
        
        # Get user preferences from memory
        preferences = await calendar_agent.memory_client.get_user_preferences(user_id)
        
        user_prefs = UserPreferences(
            user_id=user_id,
            preferences=preferences,
            last_updated=datetime.now()
        )
        
        logger.info(f"Retrieved {len(preferences)} preferences for user {user_id}")
        return user_prefs
        
    except Exception as e:
        logger.error(f"Error retrieving user preferences: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user preferences: {str(e)}"
        )

@chat_router.put("/preferences/{user_id}")
async def update_user_preferences(
    user_id: str,
    preferences: Dict[str, Any],
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Update user preferences
    
    Args:
        user_id: User identifier
        preferences: Preferences to update
        calendar_agent: Calendar agent instance
        
    Returns:
        Success confirmation
    """
    try:
        logger.info(f"Updating preferences for user: {user_id}")
        
        # Update each preference
        for pref_type, pref_value in preferences.items():
            await calendar_agent.memory_client.store_user_preference(
                user_id=user_id,
                preference_type=pref_type,
                preference_value=pref_value,
                confidence_score=1.0  # User-set preferences have high confidence
            )
        
        logger.info(f"Updated {len(preferences)} preferences for user {user_id}")
        return {"success": True, "message": f"Updated {len(preferences)} preferences"}
        
    except Exception as e:
        logger.error(f"Error updating user preferences: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update user preferences: {str(e)}"
        )

# WebSocket endpoint for real-time chat
@chat_router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    WebSocket endpoint for real-time chat functionality
    
    Args:
        websocket: WebSocket connection
        user_id: User identifier
        calendar_agent: Calendar agent instance
    """
    await connection_manager.connect(websocket, user_id)
    
    try:
        # Send welcome message
        welcome_msg = {
            "type": "connection_established",
            "message": f"Connected to myAssist Calendar Agent",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "capabilities": [
                "calendar_management",
                "scheduling",
                "availability_checking",
                "multi_agent_collaboration"
            ]
        }
        await websocket.send_text(json.dumps(welcome_msg))
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "chat_message":
                # Process chat message
                user_message = message_data.get("message", "")
                conversation_id = message_data.get("conversation_id") or f"ws_conv_{uuid.uuid4().hex[:12]}"
                
                logger.info(f"WebSocket message from {user_id}: {user_message}")
                
                # Process through calendar agent
                agent_response = await calendar_agent.process_user_request(
                    user_message=user_message,
                    user_id=user_id,
                    conversation_id=conversation_id
                )
                
                # Send response back through WebSocket
                response_msg = {
                    "type": "agent_response",
                    "conversation_id": conversation_id,
                    "response": {
                        "message": agent_response.message,
                        "success": agent_response.success,
                        "data": agent_response.data,
                        "suggestions": agent_response.suggestions,
                        "requires_confirmation": agent_response.requires_confirmation,
                        "agent_actions": agent_response.agent_actions
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send_text(json.dumps(response_msg))
                
            elif message_data.get("type") == "ping":
                # Handle ping for connection keepalive
                pong_msg = {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_text(json.dumps(pong_msg))
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, user_id)
        logger.info(f"WebSocket disconnected for user: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        connection_manager.disconnect(websocket, user_id)

# Streaming response endpoint for long-running operations
@chat_router.post("/stream/{conversation_id}")
async def stream_response(
    conversation_id: str,
    user_id: str,
    message: str,
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Streaming response endpoint for complex operations that take time
    
    Args:
        conversation_id: Conversation session identifier
        user_id: User identifier
        message: User message
        calendar_agent: Calendar agent instance
        
    Returns:
        StreamingResponse: Server-sent events stream
    """
    async def generate_stream():
        try:
            yield f"data: {json.dumps({'type': 'started', 'message': 'Processing your request...'})}\n\n"
            
            # Process the request
            agent_response = await calendar_agent.process_user_request(
                user_message=message,
                user_id=user_id,
                conversation_id=conversation_id
            )
            
            # Stream the response
            yield f"data: {json.dumps({'type': 'response', 'data': agent_response.dict()})}\n\n"
            yield f"data: {json.dumps({'type': 'completed'})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# Health check for chat service
@chat_router.get("/health")
async def chat_health_check():
    """Health check endpoint for chat service"""
    return {
        "service": "chat_routes",
        "status": "healthy",
        "active_connections": len(connection_manager.active_connections),
        "timestamp": datetime.now().isoformat()
    }
