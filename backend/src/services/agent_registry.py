"""
Agent Registry and Discovery Service

Manages the directory of discoverable customer agents, handles agent authentication
and capability registration, and provides secure communication channels for 
multi-agent collaborative scheduling.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
import json
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import hashlib
import secrets
import jwt
from urllib.parse import urljoin

from ..utils.config import config

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    """Agent availability status"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    MAINTENANCE = "maintenance"

class AgentCapability(Enum):
    """Types of capabilities agents can provide"""
    CALENDAR_MANAGEMENT = "calendar_management"
    SCHEDULING = "scheduling"
    AVAILABILITY_CHECKING = "availability_checking"
    MEETING_COORDINATION = "meeting_coordination"
    CONFLICT_RESOLUTION = "conflict_resolution"
    TIME_ZONE_HANDLING = "time_zone_handling"
    PREFERENCE_LEARNING = "preference_learning"

class CommunicationProtocol(Enum):
    """Supported communication protocols"""
    HTTP_REST = "http_rest"
    WEBSOCKET = "websocket"
    GRPC = "grpc"

@dataclass
class AgentInfo:
    """Complete agent information and metadata"""
    agent_id: str
    agent_name: str
    agent_type: str
    user_id: Optional[str] = None
    endpoint: str = ""
    capabilities: List[AgentCapability] = None
    supported_protocols: List[CommunicationProtocol] = None
    status: AgentStatus = AgentStatus.OFFLINE
    last_heartbeat: Optional[datetime] = None
    reputation_score: float = 5.0
    trust_level: int = 1
    metadata: Optional[Dict[str, Any]] = None
    registered_at: Optional[datetime] = None
    version: str = "1.0.0"
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.supported_protocols is None:
            self.supported_protocols = [CommunicationProtocol.HTTP_REST]
        if self.metadata is None:
            self.metadata = {}

@dataclass
class SchedulingProposal:
    """Proposal for collaborative scheduling"""
    proposal_id: str
    from_agent_id: str
    to_agent_id: str
    meeting_title: str
    proposed_times: List[Dict[str, Any]]
    participants: List[str]
    duration_minutes: int
    priority: str = "normal"
    deadline: Optional[datetime] = None
    constraints: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

@dataclass
class SchedulingResponse:
    """Response to a scheduling proposal"""
    response_id: str
    proposal_id: str
    from_agent_id: str
    to_agent_id: str
    status: str  # accepted, declined, counter_proposal
    available_times: Optional[List[Dict[str, Any]]] = None
    counter_proposal: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

class AgentRegistry:
    """
    Agent Registry and Discovery Service
    
    Manages agent discovery, authentication, capability registration, and
    secure communication channels for multi-agent collaborative scheduling.
    """
    
    def __init__(self):
        """Initialize the agent registry"""
        self.config = config.agent
        self.registry_url = config.agent.registry_url
        self.session = None
        self.is_initialized = False
        
        # Local agent cache for performance
        self.agent_cache: Dict[str, AgentInfo] = {}
        self.active_proposals: Dict[str, SchedulingProposal] = {}
        self.trust_network: Dict[str, Set[str]] = {}
        
        # Authentication tokens
        self.auth_token = None
        self.agent_auth_secret = config.agent.auth_secret
        
        logger.info("Agent Registry initialized")
    
    async def initialize(self) -> bool:
        """
        Initialize agent registry connection and authenticate
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            """Initialize connection to agent registry (disabled in development)"""
            logger.info("Initializing Agent Registry connection...")
            
            if not self.registry_url or self.registry_url.strip() == "":
                logger.info("Agent registry URL not configured - running in standalone mode")
                return True  # Return True to allow startup
            #else:
            # Initialize HTTP session
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": f"myAssist-Agent/{self.config.agent_id}",
                    "Content-Type": "application/json"
                }
            )
            
            # Authenticate with registry service
            auth_success = await self.authenticate_with_registry()
            if not auth_success:
                logger.error("Failed to authenticate with agent registry")
                return False
            
            # Load existing agent directory
            await self.load_agent_directory()
            
            # Start heartbeat service
            asyncio.create_task(self.heartbeat_service())
            
            self.is_initialized = True
            logger.info("Agent Registry successfully initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Agent Registry: {str(e)}")
            return False
    
    async def authenticate_with_registry(self) -> bool:
        """Authenticate with the central agent registry"""
        try:
            auth_url = urljoin(self.registry_url, "/auth/agent")
            
            # Create authentication payload
            auth_payload = {
                "agent_id": self.config.agent_id,
                "agent_name": self.config.agent_name,
                "auth_secret": self.agent_auth_secret,
                "timestamp": datetime.now().isoformat()
            }
            
            # Sign the payload
            signature = self.create_auth_signature(auth_payload)
            auth_payload["signature"] = signature
            
            async with self.session.post(auth_url, json=auth_payload) as response:
                if response.status == 200:
                    auth_data = await response.json()
                    self.auth_token = auth_data.get("access_token")
                    
                    # Update session headers
                    self.session.headers.update({
                        "Authorization": f"Bearer {self.auth_token}"
                    })
                    
                    logger.info("Successfully authenticated with agent registry")
                    return True
                else:
                    error_data = await response.json() if response.content_type == 'application/json' else {}
                    logger.error(f"Authentication failed: {error_data}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error during registry authentication: {str(e)}")
            return False
    
    def create_auth_signature(self, payload: Dict[str, Any]) -> str:
        """Create HMAC signature for authentication"""
        try:
            # Create signature string from payload
            sig_string = f"{payload['agent_id']}:{payload['timestamp']}:{self.agent_auth_secret}"
            
            # Create HMAC hash
            signature = hashlib.sha256(sig_string.encode()).hexdigest()
            return signature
            
        except Exception as e:
            logger.error(f"Error creating auth signature: {str(e)}")
            return ""
    
    async def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        capabilities: List[str],
        endpoint: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Register this agent in the central registry
        
        Args:
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            capabilities: List of agent capabilities
            endpoint: Agent communication endpoint
            user_id: Associated user ID if applicable
            metadata: Additional agent metadata
            
        Returns:
            bool: True if registration successful
        """
        try:
            if not self.registry_url or self.registry_url.strip() == "":
                logger.info(f"Agent registry disabled - agent {agent_id} running in standalone mode")
                return True
            if not self.is_initialized:
                logger.error("Agent registry not initialized")
                return False
            
            register_url = urljoin(self.registry_url, "/agents/register")
            
            # Convert capability strings to enums
            capability_enums = []
            for cap_str in capabilities:
                try:
                    cap_enum = AgentCapability(cap_str)
                    capability_enums.append(cap_enum)
                except ValueError:
                    logger.warning(f"Unknown capability: {cap_str}")
            
            agent_info = AgentInfo(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_type="calendar_assistant",
                user_id=user_id,
                endpoint=endpoint,
                capabilities=capability_enums,
                supported_protocols=[CommunicationProtocol.HTTP_REST],
                status=AgentStatus.ONLINE,
                metadata=metadata or {},
                registered_at=datetime.now(),
                version="1.0.0"
            )
            
            # Prepare registration data
            registration_data = {
                "agent_info": {
                    "agent_id": agent_info.agent_id,
                    "agent_name": agent_info.agent_name,
                    "agent_type": agent_info.agent_type,
                    "user_id": agent_info.user_id,
                    "endpoint": agent_info.endpoint,
                    "capabilities": [cap.value for cap in agent_info.capabilities],
                    "supported_protocols": [proto.value for proto in agent_info.supported_protocols],
                    "status": agent_info.status.value,
                    "metadata": agent_info.metadata,
                    "version": agent_info.version
                },
                "registration_timestamp": agent_info.registered_at.isoformat()
            }
            
            async with self.session.post(register_url, json=registration_data) as response:
                if response.status == 201:
                    result = await response.json()
                    
                    # Update local cache
                    self.agent_cache[agent_id] = agent_info
                    
                    logger.info(f"Successfully registered agent: {agent_id}")
                    return True
                else:
                    error_data = await response.json() if response.content_type == 'application/json' else {}
                    logger.error(f"Agent registration failed: {error_data}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error registering agent: {str(e)}")
            return False
    
    async def discover_agents(
        self,
        required_capabilities: Optional[List[AgentCapability]] = None,
        user_filter: Optional[str] = None,
        exclude_self: bool = True
    ) -> List[AgentInfo]:
        """
        Discover available agents based on capabilities and filters
        
        Args:
            required_capabilities: Required agent capabilities
            user_filter: Filter by user ID
            exclude_self: Whether to exclude this agent from results
            
        Returns:
            List of discovered agents
        """
        try:
            if not self.is_initialized:
                return []
            
            discover_url = urljoin(self.registry_url, "/agents/discover")
            
            # Build query parameters
            query_params = {
                "status": AgentStatus.ONLINE.value,
                "limit": 50
            }
            
            if required_capabilities:
                query_params["capabilities"] = [cap.value for cap in required_capabilities]
            
            if user_filter:
                query_params["user_id"] = user_filter
            
            if exclude_self:
                query_params["exclude"] = self.config.agent_id
            
            async with self.session.get(discover_url, params=query_params) as response:
                if response.status == 200:
                    discovery_data = await response.json()
                    agents = discovery_data.get("agents", [])
                    
                    discovered_agents = []
                    for agent_data in agents:
                        agent_info = self.parse_agent_info(agent_data)
                        if agent_info:
                            discovered_agents.append(agent_info)
                            # Update cache
                            self.agent_cache[agent_info.agent_id] = agent_info
                    
                    logger.info(f"Discovered {len(discovered_agents)} agents")
                    return discovered_agents
                else:
                    logger.error(f"Agent discovery failed: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error during agent discovery: {str(e)}")
            return []
    
    def parse_agent_info(self, agent_data: Dict[str, Any]) -> Optional[AgentInfo]:
        """Parse agent data from registry into AgentInfo object"""
        try:
            # Parse capabilities
            capabilities = []
            for cap_str in agent_data.get("capabilities", []):
                try:
                    cap = AgentCapability(cap_str)
                    capabilities.append(cap)
                except ValueError:
                    logger.warning(f"Unknown capability in agent data: {cap_str}")
            
            # Parse protocols
            protocols = []
            for proto_str in agent_data.get("supported_protocols", ["http_rest"]):
                try:
                    proto = CommunicationProtocol(proto_str)
                    protocols.append(proto)
                except ValueError:
                    logger.warning(f"Unknown protocol in agent data: {proto_str}")
            
            # Parse status
            status = AgentStatus.OFFLINE
            try:
                status = AgentStatus(agent_data.get("status", "offline"))
            except ValueError:
                logger.warning(f"Unknown status in agent data: {agent_data.get('status')}")
            
            # Parse timestamps
            registered_at = None
            if "registered_at" in agent_data:
                registered_at = datetime.fromisoformat(agent_data["registered_at"])
            
            last_heartbeat = None
            if "last_heartbeat" in agent_data:
                last_heartbeat = datetime.fromisoformat(agent_data["last_heartbeat"])
            
            return AgentInfo(
                agent_id=agent_data.get("agent_id", ""),
                agent_name=agent_data.get("agent_name", ""),
                agent_type=agent_data.get("agent_type", "unknown"),
                user_id=agent_data.get("user_id"),
                endpoint=agent_data.get("endpoint", ""),
                capabilities=capabilities,
                supported_protocols=protocols,
                status=status,
                last_heartbeat=last_heartbeat,
                reputation_score=agent_data.get("reputation_score", 5.0),
                trust_level=agent_data.get("trust_level", 1),
                metadata=agent_data.get("metadata", {}),
                registered_at=registered_at,
                version=agent_data.get("version", "1.0.0")
            )
            
        except Exception as e:
            logger.error(f"Error parsing agent info: {str(e)}")
            return None
    
    async def find_agent_by_user(self, user_identifier: str) -> Optional[AgentInfo]:
        """
        Find an agent associated with a specific user
        
        Args:
            user_identifier: User ID, email, or other identifier
            
        Returns:
            AgentInfo if found, None otherwise
        """
        try:
            # Search local cache first
            for agent in self.agent_cache.values():
                if (agent.user_id == user_identifier or 
                    user_identifier in agent.metadata.get("user_emails", []) or
                    user_identifier in agent.metadata.get("user_names", [])):
                    return agent
            
            # Search registry
            agents = await self.discover_agents(user_filter=user_identifier, exclude_self=False)
            
            if agents:
                return agents[0]  # Return first match
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding agent by user: {str(e)}")
            return None
    
    async def send_scheduling_proposal(
        self,
        target_agent_id: str,
        meeting_title: str,
        proposed_times: List[Dict[str, Any]],
        participants: List[str],
        duration_minutes: int,
        priority: str = "normal",
        constraints: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Send a scheduling proposal to another agent
        
        Args:
            target_agent_id: Target agent identifier
            meeting_title: Title/subject of the meeting
            proposed_times: List of proposed time slots
            participants: List of meeting participants
            duration_minutes: Meeting duration in minutes
            priority: Meeting priority level
            constraints: Additional scheduling constraints
            
        Returns:
            Proposal ID if sent successfully, None otherwise
        """
        try:
            # Get target agent info
            target_agent = self.agent_cache.get(target_agent_id)
            if not target_agent:
                # Try to discover the agent
                agents = await self.discover_agents()
                target_agent = next((a for a in agents if a.agent_id == target_agent_id), None)
                
            if not target_agent:
                logger.error(f"Target agent not found: {target_agent_id}")
                return None
            
            # Create proposal
            proposal_id = f"prop_{secrets.token_hex(8)}"
            proposal = SchedulingProposal(
                proposal_id=proposal_id,
                from_agent_id=self.config.agent_id,
                to_agent_id=target_agent_id,
                meeting_title=meeting_title,
                proposed_times=proposed_times,
                participants=participants,
                duration_minutes=duration_minutes,
                priority=priority,
                constraints=constraints,
                created_at=datetime.now()
            )
            
            # Send to target agent
            proposal_url = f"{target_agent.endpoint}/scheduling/proposal"
            proposal_data = {
                "proposal": asdict(proposal),
                "sender_info": {
                    "agent_id": self.config.agent_id,
                    "agent_name": self.config.agent_name
                }
            }
            
            async with self.session.post(proposal_url, json=proposal_data) as response:
                if response.status == 200:
                    # Store in active proposals
                    self.active_proposals[proposal_id] = proposal
                    
                    logger.info(f"Sent scheduling proposal {proposal_id} to {target_agent_id}")
                    return proposal_id
                else:
                    logger.error(f"Failed to send proposal to {target_agent_id}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error sending scheduling proposal: {str(e)}")
            return None
    
    async def handle_scheduling_proposal(self, proposal_data: Dict[str, Any]) -> SchedulingResponse:
        """
        Handle incoming scheduling proposal from another agent
        
        Args:
            proposal_data: Incoming proposal data
            
        Returns:
            SchedulingResponse with agent's response
        """
        try:
            proposal = SchedulingProposal(**proposal_data["proposal"])
            sender_info = proposal_data.get("sender_info", {})
            
            logger.info(f"Received scheduling proposal {proposal.proposal_id} from {proposal.from_agent_id}")
            
            # TODO: Integrate with calendar agent for availability checking
            # For now, return a placeholder response
            
            response_id = f"resp_{secrets.token_hex(8)}"
            response = SchedulingResponse(
                response_id=response_id,
                proposal_id=proposal.proposal_id,
                from_agent_id=self.config.agent_id,
                to_agent_id=proposal.from_agent_id,
                status="received",  # Will be updated after processing
                created_at=datetime.now()
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling scheduling proposal: {str(e)}")
            return SchedulingResponse(
                response_id=f"err_{secrets.token_hex(8)}",
                proposal_id=proposal_data.get("proposal", {}).get("proposal_id", "unknown"),
                from_agent_id=self.config.agent_id,
                to_agent_id=proposal_data.get("proposal", {}).get("from_agent_id", "unknown"),
                status="error",
                reason=str(e),
                created_at=datetime.now()
            )
    
    async def update_agent_status(self, status: AgentStatus) -> bool:
        """Update this agent's status in the registry"""
        try:
            if not self.is_initialized:
                return False
            
            status_url = urljoin(self.registry_url, f"/agents/{self.config.agent_id}/status")
            
            status_data = {
                "status": status.value,
                "timestamp": datetime.now().isoformat()
            }
            
            async with self.session.put(status_url, json=status_data) as response:
                if response.status == 200:
                    logger.debug(f"Updated agent status to: {status.value}")
                    return True
                else:
                    logger.error(f"Failed to update agent status: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating agent status: {str(e)}")
            return False
    
    async def heartbeat_service(self) -> None:
        """Periodic heartbeat to maintain agent registry presence"""
        while self.is_initialized:
            try:
                await self.send_heartbeat()
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat service: {str(e)}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def send_heartbeat(self) -> bool:
        """Send heartbeat to registry"""
        try:
            heartbeat_url = urljoin(self.registry_url, f"/agents/{self.config.agent_id}/heartbeat")
            
            heartbeat_data = {
                "timestamp": datetime.now().isoformat(),
                "status": AgentStatus.ONLINE.value,
                "load": "normal"  # Could be computed based on active requests
            }
            
            async with self.session.post(heartbeat_url, json=heartbeat_data) as response:
                if response.status == 200:
                    return True
                else:
                    logger.warning(f"Heartbeat failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending heartbeat: {str(e)}")
            return False
    
    async def load_agent_directory(self) -> None:
        """Load the current agent directory from registry"""
        try:
            agents = await self.discover_agents(exclude_self=False)
            logger.info(f"Loaded {len(agents)} agents into directory")
            
        except Exception as e:
            logger.error(f"Error loading agent directory: {str(e)}")
    
    async def cleanup(self) -> None:
        """Clean up resources and deregister agent"""
        try:
            # Update status to offline
            await self.update_agent_status(AgentStatus.OFFLINE)
            
            # Close HTTP session
            if self.session:
                await self.session.close()
            
            logger.info("Agent Registry cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

# Export main classes and functions
__all__ = [
    'AgentRegistry',
    'AgentInfo',
    'SchedulingProposal',
    'SchedulingResponse',
    'AgentStatus',
    'AgentCapability',
    'CommunicationProtocol'
]
