"""
Agent Communication - Multi-Agent Communication Protocols

Implements secure agent-to-agent communication protocols, handles agent discovery,
authentication, and connection management, manages multi-party scheduling 
conversations and negotiations, and provides secure messaging framework for 
inter-agent coordination.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import json
import uuid
import hashlib
import secrets
import jwt
from urllib.parse import urljoin
import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from ..utils.config import config
from ..utils.helpers import (
    generate_secure_token, create_hash, safe_execute, 
    create_error_response, create_success_response
)
from ..services.agent_registry import AgentInfo, SchedulingProposal, SchedulingResponse

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Types of inter-agent messages"""
    HANDSHAKE = "handshake"
    SCHEDULING_PROPOSAL = "scheduling_proposal"
    PROPOSAL_RESPONSE = "proposal_response"
    AVAILABILITY_REQUEST = "availability_request"
    AVAILABILITY_RESPONSE = "availability_response"
    MEETING_CONFIRMATION = "meeting_confirmation"
    MEETING_UPDATE = "meeting_update"
    MEETING_CANCELLATION = "meeting_cancellation"
    STATUS_UPDATE = "status_update"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

class CommunicationProtocol(Enum):
    """Supported communication protocols"""
    HTTP_REST = "http_rest"
    WEBSOCKET = "websocket"
    DIRECT_TCP = "direct_tcp"

@dataclass
class AgentMessage:
    """Standard inter-agent message format"""
    message_id: str
    from_agent_id: str
    to_agent_id: str
    message_type: MessageType
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = None
    expires_at: Optional[datetime] = None
    conversation_id: Optional[str] = None
    requires_response: bool = False
    response_timeout: int = 300  # seconds
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.expires_at is None and self.requires_response:
            self.expires_at = self.timestamp + timedelta(seconds=self.response_timeout)

@dataclass
class ConversationSession:
    """Multi-agent conversation session"""
    session_id: str
    participants: List[str]
    initiator_id: str
    topic: str
    status: str  # active, completed, failed, timeout
    created_at: datetime
    last_activity: datetime
    messages: List[AgentMessage]
    metadata: Dict[str, Any]

@dataclass
class AgentConnection:
    """Active connection to another agent"""
    agent_id: str
    agent_info: AgentInfo
    connection_type: CommunicationProtocol
    endpoint: str
    websocket: Optional[websockets.WebSocketServerProtocol] = None
    http_session: Optional[aiohttp.ClientSession] = None
    last_heartbeat: Optional[datetime] = None
    connection_status: str = "disconnected"  # connected, disconnected, error
    trust_score: float = 5.0

class AgentCommunication:
    """
    Multi-Agent Communication Manager
    
    Handles all aspects of inter-agent communication including discovery,
    authentication, message routing, conversation management, and protocol
    handling for collaborative scheduling operations.
    """
    
    def __init__(self, agent_id: str, agent_name: str):
        """Initialize agent communication manager"""
        self.agent_id = agent_id
        self.agent_name = agent_name
        
        # Connection management
        self.active_connections: Dict[str, AgentConnection] = {}
        self.conversation_sessions: Dict[str, ConversationSession] = {}
        self.pending_messages: Dict[str, AgentMessage] = {}
        self.message_handlers: Dict[MessageType, Callable] = {}
        
        # Communication settings
        self.websocket_server = None
        self.http_session = None
        self.auth_secret = config.agent.auth_secret
        self.communication_port = config.agent.communication_port
        
        # Message queues
        self.outbound_queue: asyncio.Queue = asyncio.Queue()
        self.inbound_queue: asyncio.Queue = asyncio.Queue()
        
        # Background tasks
        self.message_processor_task = None
        self.heartbeat_task = None
        self.connection_monitor_task = None
        
        self._register_default_handlers()
        
        logger.info(f"Agent Communication initialized for {agent_id}")
    
    async def initialize(self) -> bool:
        """Initialize communication subsystem"""
        try:
            logger.info("Initializing agent communication subsystem")
            
            # Initialize HTTP session
            self.http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": f"myAssist-Agent/{self.agent_id}",
                    "X-Agent-ID": self.agent_id
                }
            )
            
            # Start WebSocket server for incoming connections
            await self.start_websocket_server()
            
            # Start background tasks
            self.message_processor_task = asyncio.create_task(self.message_processor())
            self.heartbeat_task = asyncio.create_task(self.heartbeat_service())
            self.connection_monitor_task = asyncio.create_task(self.connection_monitor())
            
            logger.info("Agent communication subsystem initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize agent communication: {str(e)}")
            return False
    
    async def start_websocket_server(self) -> None:
        """Start WebSocket server for receiving agent connections"""
        try:
            async def handle_agent_connection(websocket, path):
                await self.handle_incoming_websocket(websocket, path)
            
            self.websocket_server = await websockets.serve(
                handle_agent_connection,
                "0.0.0.0",
                self.communication_port,
                ping_interval=30,
                ping_timeout=10
            )
            
            logger.info(f"WebSocket server started on port {self.communication_port}")
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {str(e)}")
            raise
    
    @safe_execute
    async def connect_to_agent(
        self,
        target_agent: AgentInfo,
        protocol: CommunicationProtocol = CommunicationProtocol.WEBSOCKET
    ) -> bool:
        """Establish connection to another agent"""
        try:
            logger.info(f"Connecting to agent {target_agent.agent_id} via {protocol.value}")
            
            if target_agent.agent_id in self.active_connections:
                # Connection already exists
                return True
            
            connection = AgentConnection(
                agent_id=target_agent.agent_id,
                agent_info=target_agent,
                connection_type=protocol,
                endpoint=target_agent.endpoint
            )
            
            if protocol == CommunicationProtocol.WEBSOCKET:
                success = await self.establish_websocket_connection(connection)
            elif protocol == CommunicationProtocol.HTTP_REST:
                success = await self.establish_http_connection(connection)
            else:
                logger.error(f"Unsupported protocol: {protocol}")
                return False
            
            if success:
                self.active_connections[target_agent.agent_id] = connection
                
                # Send handshake message
                await self.send_handshake(target_agent.agent_id)
                
                logger.info(f"Successfully connected to agent {target_agent.agent_id}")
                return True
            else:
                logger.error(f"Failed to establish connection to {target_agent.agent_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to agent {target_agent.agent_id}: {str(e)}")
            return False
    
    async def establish_websocket_connection(self, connection: AgentConnection) -> bool:
        """Establish WebSocket connection to an agent"""
        try:
            ws_url = f"ws://{connection.endpoint.replace('http://', '').replace('https://', '')}"
            
            # Add authentication headers
            auth_token = self.create_auth_token(connection.agent_id)
            extra_headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-Agent-ID": self.agent_id,
                "X-Timestamp": datetime.now().isoformat()
            }
            
            websocket = await websockets.connect(
                ws_url,
                extra_headers=extra_headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            connection.websocket = websocket
            connection.connection_status = "connected"
            connection.last_heartbeat = datetime.now()
            
            # Start listening for messages
            asyncio.create_task(self.websocket_message_listener(connection))
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {str(e)}")
            connection.connection_status = "error"
            return False
    
    async def establish_http_connection(self, connection: AgentConnection) -> bool:
        """Establish HTTP connection to an agent"""
        try:
            # Test connectivity with a ping
            ping_url = urljoin(connection.endpoint, "/agents/ping")
            
            headers = {
                "Authorization": f"Bearer {self.create_auth_token(connection.agent_id)}",
                "X-Agent-ID": self.agent_id,
                "X-Timestamp": datetime.now().isoformat()
            }
            
            async with self.http_session.get(ping_url, headers=headers) as response:
                if response.status == 200:
                    connection.connection_status = "connected"
                    connection.last_heartbeat = datetime.now()
                    return True
                else:
                    logger.error(f"HTTP ping failed with status {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"HTTP connection test failed: {str(e)}")
            connection.connection_status = "error"
            return False
    
    @safe_execute
    async def send_message(
        self,
        target_agent_id: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        requires_response: bool = False,
        conversation_id: Optional[str] = None
    ) -> Optional[str]:
        """Send message to another agent"""
        try:
            message = AgentMessage(
                message_id=f"msg_{uuid.uuid4().hex[:12]}",
                from_agent_id=self.agent_id,
                to_agent_id=target_agent_id,
                message_type=message_type,
                payload=payload,
                priority=priority,
                requires_response=requires_response,
                conversation_id=conversation_id
            )
            
            # Add to outbound queue
            await self.outbound_queue.put(message)
            
            if requires_response:
                self.pending_messages[message.message_id] = message
            
            logger.debug(f"Queued message {message.message_id} to {target_agent_id}")
            return message.message_id
            
        except Exception as e:
            logger.error(f"Error sending message to {target_agent_id}: {str(e)}")
            return None
    
    @safe_execute
    async def send_scheduling_proposal(
        self,
        target_agent_id: str,
        proposal: SchedulingProposal,
        conversation_id: Optional[str] = None
    ) -> Optional[str]:
        """Send scheduling proposal to another agent"""
        try:
            payload = {
                "proposal": asdict(proposal),
                "sender_info": {
                    "agent_id": self.agent_id,
                    "agent_name": self.agent_name
                }
            }
            
            message_id = await self.send_message(
                target_agent_id=target_agent_id,
                message_type=MessageType.SCHEDULING_PROPOSAL,
                payload=payload,
                priority=MessagePriority.HIGH,
                requires_response=True,
                conversation_id=conversation_id
            )
            
            logger.info(f"Sent scheduling proposal {proposal.proposal_id} to {target_agent_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error sending scheduling proposal: {str(e)}")
            return None
    
    @safe_execute
    async def request_availability(
        self,
        target_agent_id: str,
        time_range: Dict[str, datetime],
        participant_info: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> Optional[str]:
        """Request availability information from another agent"""
        try:
            payload = {
                "time_range": {
                    "start": time_range["start"].isoformat(),
                    "end": time_range["end"].isoformat()
                },
                "participant_info": participant_info,
                "requested_by": {
                    "agent_id": self.agent_id,
                    "agent_name": self.agent_name
                }
            }
            
            message_id = await self.send_message(
                target_agent_id=target_agent_id,
                message_type=MessageType.AVAILABILITY_REQUEST,
                payload=payload,
                priority=MessagePriority.NORMAL,
                requires_response=True,
                conversation_id=conversation_id
            )
            
            logger.info(f"Requested availability from {target_agent_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error requesting availability: {str(e)}")
            return None
    
    @safe_execute
    async def start_conversation(
        self,
        participant_agent_ids: List[str],
        topic: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Start a multi-agent conversation session"""
        try:
            session_id = f"conv_{uuid.uuid4().hex[:12]}"
            
            session = ConversationSession(
                session_id=session_id,
                participants=[self.agent_id] + participant_agent_ids,
                initiator_id=self.agent_id,
                topic=topic,
                status="active",
                created_at=datetime.now(),
                last_activity=datetime.now(),
                messages=[],
                metadata=metadata or {}
            )
            
            self.conversation_sessions[session_id] = session
            
            # Notify all participants about the new conversation
            for agent_id in participant_agent_ids:
                await self.send_message(
                    target_agent_id=agent_id,
                    message_type=MessageType.HANDSHAKE,
                    payload={
                        "action": "conversation_start",
                        "session_id": session_id,
                        "topic": topic,
                        "participants": session.participants,
                        "metadata": metadata
                    },
                    conversation_id=session_id
                )
            
            logger.info(f"Started conversation {session_id} with {len(participant_agent_ids)} participants")
            return session_id
            
        except Exception as e:
            logger.error(f"Error starting conversation: {str(e)}")
            return None
    
    async def message_processor(self) -> None:
        """Background task to process outbound messages"""
        logger.info("Message processor started")
        
        while True:
            try:
                # Process outbound messages
                try:
                    message = await asyncio.wait_for(self.outbound_queue.get(), timeout=1.0)
                    await self.deliver_message(message)
                except asyncio.TimeoutError:
                    pass
                
                # Process inbound messages
                try:
                    message = await asyncio.wait_for(self.inbound_queue.get(), timeout=0.1)
                    await self.handle_inbound_message(message)
                except asyncio.TimeoutError:
                    pass
                
                # Clean up expired messages
                await self.cleanup_expired_messages()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message processor: {str(e)}")
                await asyncio.sleep(1)
        
        logger.info("Message processor stopped")
    
    async def deliver_message(self, message: AgentMessage) -> bool:
        """Deliver message to target agent"""
        try:
            connection = self.active_connections.get(message.to_agent_id)
            
            if not connection:
                logger.error(f"No connection to agent {message.to_agent_id}")
                return False
            
            message_data = {
                "message_id": message.message_id,
                "from_agent_id": message.from_agent_id,
                "to_agent_id": message.to_agent_id,
                "message_type": message.message_type.value,
                "payload": message.payload,
                "priority": message.priority.value,
                "timestamp": message.timestamp.isoformat(),
                "conversation_id": message.conversation_id,
                "requires_response": message.requires_response
            }
            
            if connection.connection_type == CommunicationProtocol.WEBSOCKET:
                return await self.send_websocket_message(connection, message_data)
            elif connection.connection_type == CommunicationProtocol.HTTP_REST:
                return await self.send_http_message(connection, message_data)
            else:
                logger.error(f"Unsupported connection type: {connection.connection_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error delivering message {message.message_id}: {str(e)}")
            return False
    
    async def send_websocket_message(self, connection: AgentConnection, message_data: Dict) -> bool:
        """Send message via WebSocket"""
        try:
            if connection.websocket and not connection.websocket.closed:
                await connection.websocket.send(json.dumps(message_data))
                logger.debug(f"Sent WebSocket message to {connection.agent_id}")
                return True
            else:
                logger.error(f"WebSocket connection to {connection.agent_id} is closed")
                connection.connection_status = "disconnected"
                return False
                
        except (ConnectionClosed, WebSocketException) as e:
            logger.error(f"WebSocket error to {connection.agent_id}: {str(e)}")
            connection.connection_status = "error"
            return False
    
    async def send_http_message(self, connection: AgentConnection, message_data: Dict) -> bool:
        """Send message via HTTP POST"""
        try:
            message_url = urljoin(connection.endpoint, "/agents/message")
            
            headers = {
                "Authorization": f"Bearer {self.create_auth_token(connection.agent_id)}",
                "X-Agent-ID": self.agent_id,
                "X-Timestamp": datetime.now().isoformat()
            }
            
            async with self.http_session.post(
                message_url, 
                json=message_data, 
                headers=headers
            ) as response:
                
                if response.status == 200:
                    logger.debug(f"Sent HTTP message to {connection.agent_id}")
                    return True
                else:
                    logger.error(f"HTTP message failed with status {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"HTTP message error to {connection.agent_id}: {str(e)}")
            return False
    
    async def handle_inbound_message(self, message: AgentMessage) -> None:
        """Handle incoming message from another agent"""
        try:
            logger.debug(f"Handling inbound message {message.message_id} from {message.from_agent_id}")
            
            # Update conversation session if applicable
            if message.conversation_id and message.conversation_id in self.conversation_sessions:
                session = self.conversation_sessions[message.conversation_id]
                session.messages.append(message)
                session.last_activity = datetime.now()
            
            # Route to appropriate handler
            handler = self.message_handlers.get(message.message_type)
            if handler:
                await handler(message)
            else:
                logger.warning(f"No handler for message type: {message.message_type}")
            
            # Handle response requirement
            if message.requires_response and message.message_id not in self.pending_messages:
                # Send acknowledgment if no specific response was sent
                await self.send_message(
                    target_agent_id=message.from_agent_id,
                    message_type=MessageType.HEARTBEAT,
                    payload={"ack": message.message_id},
                    conversation_id=message.conversation_id
                )
            
        except Exception as e:
            logger.error(f"Error handling inbound message: {str(e)}")
    
    def _register_default_handlers(self) -> None:
        """Register default message handlers"""
        self.message_handlers = {
            MessageType.HANDSHAKE: self.handle_handshake,
            MessageType.SCHEDULING_PROPOSAL: self.handle_scheduling_proposal,
            MessageType.PROPOSAL_RESPONSE: self.handle_proposal_response,
            MessageType.AVAILABILITY_REQUEST: self.handle_availability_request,
            MessageType.AVAILABILITY_RESPONSE: self.handle_availability_response,
            MessageType.MEETING_CONFIRMATION: self.handle_meeting_confirmation,
            MessageType.MEETING_UPDATE: self.handle_meeting_update,
            MessageType.MEETING_CANCELLATION: self.handle_meeting_cancellation,
            MessageType.STATUS_UPDATE: self.handle_status_update,
            MessageType.HEARTBEAT: self.handle_heartbeat,
            MessageType.ERROR: self.handle_error_message
        }
    
    # Message Handlers
    
    async def handle_handshake(self, message: AgentMessage) -> None:
        """Handle handshake message"""
        logger.info(f"Handshake from {message.from_agent_id}")
        
        # Respond with our capabilities
        response_payload = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "capabilities": ["calendar_management", "scheduling", "availability_checking"],
            "protocol_version": "1.0",
            "status": "ready"
        }
        
        await self.send_message(
            target_agent_id=message.from_agent_id,
            message_type=MessageType.HANDSHAKE,
            payload=response_payload,
            conversation_id=message.conversation_id
        )
    
    async def handle_scheduling_proposal(self, message: AgentMessage) -> None:
        """Handle scheduling proposal from another agent"""
        logger.info(f"Scheduling proposal from {message.from_agent_id}")
        
        # This would integrate with the calendar agent's proposal handling
        # For now, send a basic acknowledgment
        response_payload = {
            "proposal_id": message.payload.get("proposal", {}).get("proposal_id"),
            "status": "received",
            "message": "Proposal received and being processed"
        }
        
        await self.send_message(
            target_agent_id=message.from_agent_id,
            message_type=MessageType.PROPOSAL_RESPONSE,
            payload=response_payload,
            conversation_id=message.conversation_id
        )
    
    async def handle_proposal_response(self, message: AgentMessage) -> None:
        """Handle response to a scheduling proposal"""
        logger.info(f"Proposal response from {message.from_agent_id}")
        # Implementation would update proposal status and notify user
    
    async def handle_availability_request(self, message: AgentMessage) -> None:
        """Handle availability request from another agent"""
        logger.info(f"Availability request from {message.from_agent_id}")
        
        # This would integrate with calendar checking
        response_payload = {
            "request_id": message.message_id,
            "availability": {
                "available_slots": [],  # Would be populated from calendar
                "busy_times": [],
                "preferences": {}
            },
            "status": "success"
        }
        
        await self.send_message(
            target_agent_id=message.from_agent_id,
            message_type=MessageType.AVAILABILITY_RESPONSE,
            payload=response_payload,
            conversation_id=message.conversation_id
        )
    
    async def handle_availability_response(self, message: AgentMessage) -> None:
        """Handle availability response from another agent"""
        logger.info(f"Availability response from {message.from_agent_id}")
        # Implementation would process availability data
    
    async def handle_meeting_confirmation(self, message: AgentMessage) -> None:
        """Handle meeting confirmation from another agent"""
        logger.info(f"Meeting confirmation from {message.from_agent_id}")
        # Implementation would confirm meeting in calendar
    
    async def handle_meeting_update(self, message: AgentMessage) -> None:
        """Handle meeting update from another agent"""
        logger.info(f"Meeting update from {message.from_agent_id}")
        # Implementation would update meeting in calendar
    
    async def handle_meeting_cancellation(self, message: AgentMessage) -> None:
        """Handle meeting cancellation from another agent"""
        logger.info(f"Meeting cancellation from {message.from_agent_id}")
        # Implementation would cancel meeting in calendar
    
    async def handle_status_update(self, message: AgentMessage) -> None:
        """Handle status update from another agent"""
        logger.debug(f"Status update from {message.from_agent_id}")
        
        if message.from_agent_id in self.active_connections:
            connection = self.active_connections[message.from_agent_id]
            connection.last_heartbeat = datetime.now()
    
    async def handle_heartbeat(self, message: AgentMessage) -> None:
        """Handle heartbeat message"""
        logger.debug(f"Heartbeat from {message.from_agent_id}")
        
        if message.from_agent_id in self.active_connections:
            connection = self.active_connections[message.from_agent_id]
            connection.last_heartbeat = datetime.now()
            connection.connection_status = "connected"
    
    async def handle_error_message(self, message: AgentMessage) -> None:
        """Handle error message from another agent"""
        logger.error(f"Error message from {message.from_agent_id}: {message.payload}")
    
    # Utility Methods
    
    def create_auth_token(self, target_agent_id: str) -> str:
        """Create JWT authentication token for agent communication"""
        payload = {
            "agent_id": self.agent_id,
            "target_agent_id": target_agent_id,
            "timestamp": datetime.now().isoformat(),
            "exp": datetime.now() + timedelta(hours=1)
        }
        
        return jwt.encode(payload, self.auth_secret, algorithm="HS256")
    
    async def send_handshake(self, target_agent_id: str) -> None:
        """Send handshake message to establish communication"""
        payload = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "protocol_version": "1.0",
            "capabilities": ["calendar_management", "scheduling"],
            "timestamp": datetime.now().isoformat()
        }
        
        await self.send_message(
            target_agent_id=target_agent_id,
            message_type=MessageType.HANDSHAKE,
            payload=payload,
            requires_response=True
        )
    
    async def heartbeat_service(self) -> None:
        """Background task to send periodic heartbeats"""
        logger.info("Heartbeat service started")
        
        while True:
            try:
                for agent_id, connection in self.active_connections.items():
                    if connection.connection_status == "connected":
                        await self.send_message(
                            target_agent_id=agent_id,
                            message_type=MessageType.HEARTBEAT,
                            payload={"timestamp": datetime.now().isoformat()}
                        )
                
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat service: {str(e)}")
                await asyncio.sleep(60)
        
        logger.info("Heartbeat service stopped")
    
    async def connection_monitor(self) -> None:
        """Monitor connection health and reconnect if needed"""
        logger.info("Connection monitor started")
        
        while True:
            try:
                current_time = datetime.now()
                disconnected_agents = []
                
                for agent_id, connection in self.active_connections.items():
                    # Check if connection is stale (no heartbeat in 2 minutes)
                    if (connection.last_heartbeat and 
                        (current_time - connection.last_heartbeat).total_seconds() > 120):
                        
                        logger.warning(f"Connection to {agent_id} appears stale")
                        connection.connection_status = "disconnected"
                        disconnected_agents.append(agent_id)
                
                # Attempt to reconnect to disconnected agents
                for agent_id in disconnected_agents:
                    connection = self.active_connections[agent_id]
                    logger.info(f"Attempting to reconnect to {agent_id}")
                    
                    if connection.connection_type == CommunicationProtocol.WEBSOCKET:
                        await self.establish_websocket_connection(connection)
                    elif connection.connection_type == CommunicationProtocol.HTTP_REST:
                        await self.establish_http_connection(connection)
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection monitor: {str(e)}")
                await asyncio.sleep(60)
        
        logger.info("Connection monitor stopped")
    
    async def cleanup_expired_messages(self) -> None:
        """Clean up expired pending messages"""
        current_time = datetime.now()
        expired_messages = []
        
        for message_id, message in self.pending_messages.items():
            if message.expires_at and current_time > message.expires_at:
                expired_messages.append(message_id)
        
        for message_id in expired_messages:
            del self.pending_messages[message_id]
            logger.debug(f"Cleaned up expired message: {message_id}")
    
    async def handle_incoming_websocket(self, websocket, path) -> None:
        """Handle incoming WebSocket connection from another agent"""
        remote_agent_id = None
        
        try:
            logger.info(f"Incoming WebSocket connection from {websocket.remote_address}")
            
            # Expect authentication message first
            auth_message = await websocket.recv()
            auth_data = json.loads(auth_message)
            
            # Verify authentication
            remote_agent_id = auth_data.get("agent_id")
            if not remote_agent_id:
                await websocket.close(code=4001, reason="Missing agent ID")
                return
            
            # Create connection record
            connection = AgentConnection(
                agent_id=remote_agent_id,
                agent_info=None,  # Would be populated from registry
                connection_type=CommunicationProtocol.WEBSOCKET,
                endpoint=f"ws://{websocket.remote_address[0]}:{websocket.remote_address[1]}",
                websocket=websocket,
                connection_status="connected",
                last_heartbeat=datetime.now()
            )
            
            self.active_connections[remote_agent_id] = connection
            
            # Listen for messages
            async for message_data in websocket:
                try:
                    message_dict = json.loads(message_data)
                    message = AgentMessage(
                        message_id=message_dict["message_id"],
                        from_agent_id=message_dict["from_agent_id"],
                        to_agent_id=message_dict["to_agent_id"],
                        message_type=MessageType(message_dict["message_type"]),
                        payload=message_dict["payload"],
                        priority=MessagePriority(message_dict.get("priority", 2)),
                        timestamp=datetime.fromisoformat(message_dict["timestamp"]),
                        conversation_id=message_dict.get("conversation_id")
                    )
                    
                    await self.inbound_queue.put(message)
                    
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in WebSocket message")
                except KeyError as e:
                    logger.error(f"Missing required field in message: {e}")
                
        except WebSocketException as e:
            logger.info(f"WebSocket connection closed: {e}")
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {str(e)}")
        finally:
            if remote_agent_id and remote_agent_id in self.active_connections:
                del self.active_connections[remote_agent_id]
                logger.info(f"Cleaned up connection for {remote_agent_id}")
    
    async def websocket_message_listener(self, connection: AgentConnection) -> None:
        """Listen for messages on a WebSocket connection"""
        try:
            async for message_data in connection.websocket:
                try:
                    message_dict = json.loads(message_data)
                    message = AgentMessage(
                        message_id=message_dict["message_id"],
                        from_agent_id=message_dict["from_agent_id"],
                        to_agent_id=message_dict["to_agent_id"],
                        message_type=MessageType(message_dict["message_type"]),
                        payload=message_dict["payload"],
                        priority=MessagePriority(message_dict.get("priority", 2)),
                        timestamp=datetime.fromisoformat(message_dict["timestamp"]),
                        conversation_id=message_dict.get("conversation_id")
                    )
                    
                    await self.inbound_queue.put(message)
                    
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in WebSocket message")
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {str(e)}")
                    
        except ConnectionClosed:
            logger.info(f"WebSocket connection to {connection.agent_id} closed")
            connection.connection_status = "disconnected"
        except Exception as e:
            logger.error(f"WebSocket listener error for {connection.agent_id}: {str(e)}")
            connection.connection_status = "error"
    
    async def cleanup(self) -> None:
        """Clean up communication resources"""
        try:
            logger.info("Cleaning up agent communication")
            
            # Cancel background tasks
            if self.message_processor_task:
                self.message_processor_task.cancel()
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
            if self.connection_monitor_task:
                self.connection_monitor_task.cancel()
            
            # Close all connections
            for connection in self.active_connections.values():
                if connection.websocket and not connection.websocket.closed:
                    await connection.websocket.close()
            
            # Close HTTP session
            if self.http_session:
                await self.http_session.close()
            
            # Close WebSocket server
            if self.websocket_server:
                self.websocket_server.close()
                await self.websocket_server.wait_closed()
            
            logger.info("Agent communication cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during communication cleanup: {str(e)}")

# Export main classes
__all__ = [
    'AgentCommunication',
    'AgentMessage',
    'ConversationSession',
    'AgentConnection',
    'MessageType',
    'MessagePriority',
    'CommunicationProtocol'
]
