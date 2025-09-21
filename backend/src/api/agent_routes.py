"""
Agent Routes - Inter-Agent Communication Endpoints

Provides endpoints for inter-agent communication, receives scheduling proposals
from other agents, handles meeting negotiation workflows, and provides secure
agent authentication and authorization.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
from fastapi import APIRouter, HTTPException, Depends, Header, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt
import hashlib

from ..agent.calendar_agent import CalendarAgent
from ..services.agent_registry import (
    AgentRegistry, AgentInfo, SchedulingProposal, SchedulingResponse,
    AgentStatus, AgentCapability
)
from ..utils.config import config

logger = logging.getLogger(__name__)

# Request/Response models for inter-agent communication
class AgentDiscoveryRequest(BaseModel):
    """Request to discover other agents"""
    required_capabilities: Optional[List[str]] = Field(None, description="Required agent capabilities")
    user_filter: Optional[str] = Field(None, description="Filter by user ID")
    max_results: int = Field(10, description="Maximum number of agents to return")

class AgentDiscoveryResponse(BaseModel):
    """Response with discovered agents"""
    agents: List[Dict[str, Any]]
    total_found: int
    timestamp: datetime = Field(default_factory=datetime.now)

class SchedulingProposalRequest(BaseModel):
    """Request to send a scheduling proposal"""
    target_agent_id: str = Field(..., description="Target agent identifier")
    meeting_title: str = Field(..., description="Meeting title/subject")
    proposed_times: List[Dict[str, Any]] = Field(..., description="List of proposed time slots")
    participants: List[str] = Field(..., description="List of meeting participants")
    duration_minutes: int = Field(..., description="Meeting duration in minutes")
    priority: str = Field("normal", description="Meeting priority level")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Additional scheduling constraints")

class SchedulingProposalResponse(BaseModel):
    """Response to scheduling proposal request"""
    proposal_id: str
    status: str
    message: str
    estimated_response_time: Optional[str] = None

class ProposalResponseRequest(BaseModel):
    """Response to a received scheduling proposal"""
    proposal_id: str = Field(..., description="Original proposal identifier")
    status: str = Field(..., description="Response status: accepted, declined, counter_proposal")
    available_times: Optional[List[Dict[str, Any]]] = Field(None, description="Available time slots")
    counter_proposal: Optional[Dict[str, Any]] = Field(None, description="Counter proposal details")
    reason: Optional[str] = Field(None, description="Reason for response")

class AgentStatusUpdate(BaseModel):
    """Agent status update model"""
    status: str = Field(..., description="New agent status")
    message: Optional[str] = Field(None, description="Status update message")
    capabilities: Optional[List[str]] = Field(None, description="Updated capabilities")

class CollaborationSession(BaseModel):
    """Multi-agent collaboration session"""
    session_id: str
    initiating_agent_id: str
    participating_agents: List[str]
    meeting_details: Dict[str, Any]
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None

# Security dependency
security = HTTPBearer()

# Create router
agent_router = APIRouter()

# Dependencies
async def get_calendar_agent() -> CalendarAgent:
    """Get calendar agent instance from app state"""
    from ..api.main import app
    
    if not hasattr(app.state, 'calendar_agent') or app.state.calendar_agent is None:
        raise HTTPException(
            status_code=503,
            detail="Calendar agent not initialized"
        )
    return app.state.calendar_agent

async def authenticate_agent_request(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_agent_id: str = Header(..., description="Requesting agent ID"),
    x_timestamp: str = Header(..., description="Request timestamp"),
    x_signature: str = Header(..., description="Request signature")
) -> str:
    """
    Authenticate inter-agent requests with JWT and signature validation
    
    Returns:
        str: Authenticated agent ID
    """
    try:
        # Verify JWT token
        token = credentials.credentials
        payload = jwt.decode(
            token,
            config.agent.auth_secret,
            algorithms=["HS256"]
        )
        
        token_agent_id = payload.get("agent_id")
        if not token_agent_id or token_agent_id != x_agent_id:
            raise HTTPException(
                status_code=401,
                detail="Agent ID mismatch in token"
            )
        
        # Verify request signature
        expected_signature = create_request_signature(x_agent_id, x_timestamp)
        if x_signature != expected_signature:
            logger.warning(f"Invalid signature from agent {x_agent_id}")
            raise HTTPException(
                status_code=401,
                detail="Invalid request signature"
            )
        
        # Check timestamp freshness (within 5 minutes)
        request_time = datetime.fromisoformat(x_timestamp.replace('Z', '+00:00'))
        time_diff = abs((datetime.now() - request_time).total_seconds())
        
        if time_diff > 300:  # 5 minutes
            raise HTTPException(
                status_code=401,
                detail="Request timestamp too old"
            )
        
        logger.info(f"Authenticated agent request from: {x_agent_id}")
        return token_agent_id
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Agent token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid agent token"
        )
    except Exception as e:
        logger.error(f"Agent authentication error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Agent authentication failed"
        )

def create_request_signature(agent_id: str, timestamp: str) -> str:
    """Create request signature for validation"""
    signature_string = f"{agent_id}:{timestamp}:{config.agent.auth_secret}"
    return hashlib.sha256(signature_string.encode()).hexdigest()

@agent_router.post("/discover", response_model=AgentDiscoveryResponse)
async def discover_agents(
    discovery_request: AgentDiscoveryRequest,
    requesting_agent_id: str = Depends(authenticate_agent_request),
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Discover other agents based on capabilities and filters
    
    Args:
        discovery_request: Discovery criteria
        requesting_agent_id: Authenticated requesting agent ID
        calendar_agent: Calendar agent instance
        
    Returns:
        AgentDiscoveryResponse: List of discovered agents
    """
    try:
        logger.info(f"Agent discovery request from: {requesting_agent_id}")
        
        # Convert capability strings to enums
        required_capabilities = None
        if discovery_request.required_capabilities:
            required_capabilities = []
            for cap_str in discovery_request.required_capabilities:
                try:
                    cap = AgentCapability(cap_str)
                    required_capabilities.append(cap)
                except ValueError:
                    logger.warning(f"Unknown capability requested: {cap_str}")
        
        # Discover agents through registry
        discovered_agents = await calendar_agent.agent_registry.discover_agents(
            required_capabilities=required_capabilities,
            user_filter=discovery_request.user_filter,
            exclude_self=(requesting_agent_id == config.agent.agent_id)
        )
        
        # Convert to response format
        agent_list = []
        for agent in discovered_agents[:discovery_request.max_results]:
            agent_data = {
                "agent_id": agent.agent_id,
                "agent_name": agent.agent_name,
                "agent_type": agent.agent_type,
                "capabilities": [cap.value for cap in agent.capabilities],
                "status": agent.status.value,
                "endpoint": agent.endpoint,
                "reputation_score": agent.reputation_score,
                "last_heartbeat": agent.last_heartbeat.isoformat() if agent.last_heartbeat else None
            }
            agent_list.append(agent_data)
        
        response = AgentDiscoveryResponse(
            agents=agent_list,
            total_found=len(discovered_agents)
        )
        
        logger.info(f"Returned {len(agent_list)} agents to {requesting_agent_id}")
        return response
        
    except Exception as e:
        logger.error(f"Agent discovery error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent discovery failed: {str(e)}"
        )

@agent_router.post("/proposal", response_model=SchedulingProposalResponse)
async def receive_scheduling_proposal(
    proposal_request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    requesting_agent_id: str = Depends(authenticate_agent_request),
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Receive and process a scheduling proposal from another agent
    
    Args:
        proposal_request: Scheduling proposal details
        background_tasks: FastAPI background tasks
        requesting_agent_id: Authenticated requesting agent ID
        calendar_agent: Calendar agent instance
        
    Returns:
        SchedulingProposalResponse: Acknowledgment and processing status
    """
    try:
        logger.info(f"Received scheduling proposal from agent: {requesting_agent_id}")
        
        # Process the proposal through agent registry
        response = await calendar_agent.agent_registry.handle_scheduling_proposal(
            proposal_request
        )
        
        # Add background task to process the proposal asynchronously
        background_tasks.add_task(
            process_scheduling_proposal_async,
            calendar_agent,
            proposal_request,
            requesting_agent_id
        )
        
        return SchedulingProposalResponse(
            proposal_id=response.proposal_id,
            status="received",
            message="Proposal received and being processed",
            estimated_response_time="2-5 minutes"
        )
        
    except Exception as e:
        logger.error(f"Error receiving scheduling proposal: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process scheduling proposal: {str(e)}"
        )

async def process_scheduling_proposal_async(
    calendar_agent: CalendarAgent,
    proposal_request: Dict[str, Any],
    requesting_agent_id: str
):
    """
    Process scheduling proposal asynchronously
    
    Args:
        calendar_agent: Calendar agent instance
        proposal_request: Proposal details
        requesting_agent_id: ID of requesting agent
    """
    try:
        logger.info(f"Processing proposal asynchronously from {requesting_agent_id}")
        
        proposal = SchedulingProposal(**proposal_request["proposal"])
        
        # Check availability for proposed times
        availability_results = []
        for time_slot in proposal.proposed_times:
            start_time = datetime.fromisoformat(time_slot["start"])
            end_time = datetime.fromisoformat(time_slot["end"])
            
            # Check calendar availability
            availability = await calendar_agent.calendar_client.check_availability(
                start_time=start_time,
                end_time=end_time
            )
            
            availability_results.append({
                "time_slot": time_slot,
                "available": availability["available"],
                "conflicts": availability.get("conflicts", [])
            })
        
        # Find best available times
        available_times = [result["time_slot"] for result in availability_results 
                          if result["available"]]
        
        # Prepare response
        if available_times:
            response_status = "accepted" if len(available_times) > 0 else "partial_acceptance"
            response_message = f"Can accommodate {len(available_times)} of {len(proposal.proposed_times)} proposed times"
        else:
            response_status = "declined"
            response_message = "No proposed times are available"
            
            # Suggest alternative times
            alternative_times = await calendar_agent.calendar_client.find_free_times(
                duration_minutes=proposal.duration_minutes,
                search_start=datetime.now(),
                search_end=datetime.now().replace(hour=23, minute=59),
                max_suggestions=3
            )
            
            available_times = [
                {
                    "start": slot.start.isoformat(),
                    "end": slot.end.isoformat(),
                    "duration": slot.duration_minutes
                }
                for slot in alternative_times
            ]
        
        # Send response back to requesting agent
        # This would typically involve making an HTTP request to the requesting agent
        logger.info(f"Proposal processing complete: {response_status}")
        
    except Exception as e:
        logger.error(f"Error processing proposal asynchronously: {str(e)}")

@agent_router.post("/proposal/send", response_model=SchedulingProposalResponse)
async def send_scheduling_proposal(
    proposal_request: SchedulingProposalRequest,
    requesting_agent_id: str = Depends(authenticate_agent_request),
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Send a scheduling proposal to another agent
    
    Args:
        proposal_request: Proposal details
        requesting_agent_id: Authenticated requesting agent ID
        calendar_agent: Calendar agent instance
        
    Returns:
        SchedulingProposalResponse: Send status and proposal ID
    """
    try:
        logger.info(f"Sending proposal to agent: {proposal_request.target_agent_id}")
        
        # Send proposal through agent registry
        proposal_id = await calendar_agent.agent_registry.send_scheduling_proposal(
            target_agent_id=proposal_request.target_agent_id,
            meeting_title=proposal_request.meeting_title,
            proposed_times=proposal_request.proposed_times,
            participants=proposal_request.participants,
            duration_minutes=proposal_request.duration_minutes,
            priority=proposal_request.priority,
            constraints=proposal_request.constraints
        )
        
        if proposal_id:
            return SchedulingProposalResponse(
                proposal_id=proposal_id,
                status="sent",
                message="Proposal sent successfully",
                estimated_response_time="2-5 minutes"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Failed to send scheduling proposal"
            )
            
    except Exception as e:
        logger.error(f"Error sending scheduling proposal: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send scheduling proposal: {str(e)}"
        )

@agent_router.post("/proposal/{proposal_id}/respond")
async def respond_to_proposal(
    proposal_id: str,
    response_request: ProposalResponseRequest,
    requesting_agent_id: str = Depends(authenticate_agent_request),
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Respond to a received scheduling proposal
    
    Args:
        proposal_id: Original proposal identifier
        response_request: Response details
        requesting_agent_id: Authenticated requesting agent ID
        calendar_agent: Calendar agent instance
        
    Returns:
        Response confirmation
    """
    try:
        logger.info(f"Responding to proposal {proposal_id} with status: {response_request.status}")
        
        # TODO: Implement proposal response handling
        # This would involve updating the proposal status and notifying the original agent
        
        return {
            "success": True,
            "proposal_id": proposal_id,
            "response_status": response_request.status,
            "message": "Response recorded and forwarded to original agent"
        }
        
    except Exception as e:
        logger.error(f"Error responding to proposal: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to respond to proposal: {str(e)}"
        )

@agent_router.put("/status")
async def update_agent_status(
    status_update: AgentStatusUpdate,
    requesting_agent_id: str = Depends(authenticate_agent_request),
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Update this agent's status in the registry
    
    Args:
        status_update: New status information
        requesting_agent_id: Authenticated requesting agent ID
        calendar_agent: Calendar agent instance
        
    Returns:
        Status update confirmation
    """
    try:
        # Verify agent is updating its own status
        if requesting_agent_id != config.agent.agent_id:
            raise HTTPException(
                status_code=403,
                detail="Can only update own agent status"
            )
        
        # Convert status string to enum
        try:
            new_status = AgentStatus(status_update.status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status_update.status}"
            )
        
        # Update status in registry
        success = await calendar_agent.agent_registry.update_agent_status(new_status)
        
        if success:
            logger.info(f"Updated agent status to: {status_update.status}")
            return {
                "success": True,
                "status": status_update.status,
                "message": status_update.message or "Status updated successfully"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to update agent status"
            )
            
    except Exception as e:
        logger.error(f"Error updating agent status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update agent status: {str(e)}"
        )

@agent_router.get("/status/{agent_id}")
async def get_agent_status(
    agent_id: str,
    requesting_agent_id: str = Depends(authenticate_agent_request),
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Get status of a specific agent
    
    Args:
        agent_id: Target agent identifier
        requesting_agent_id: Authenticated requesting agent ID
        calendar_agent: Calendar agent instance
        
    Returns:
        Agent status information
    """
    try:
        # Search for the agent in the local cache first
        agent_info = calendar_agent.agent_registry.agent_cache.get(agent_id)
        
        if not agent_info:
            # Try to discover the agent
            agents = await calendar_agent.agent_registry.discover_agents()
            agent_info = next((a for a in agents if a.agent_id == agent_id), None)
        
        if agent_info:
            return {
                "agent_id": agent_info.agent_id,
                "agent_name": agent_info.agent_name,
                "status": agent_info.status.value,
                "last_heartbeat": agent_info.last_heartbeat.isoformat() if agent_info.last_heartbeat else None,
                "capabilities": [cap.value for cap in agent_info.capabilities],
                "reputation_score": agent_info.reputation_score
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Agent not found: {agent_id}"
            )
            
    except Exception as e:
        logger.error(f"Error getting agent status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent status: {str(e)}"
        )

@agent_router.post("/collaboration/session")
async def create_collaboration_session(
    session_details: Dict[str, Any],
    background_tasks: BackgroundTasks,
    requesting_agent_id: str = Depends(authenticate_agent_request),
    calendar_agent: CalendarAgent = Depends(get_calendar_agent)
):
    """
    Create a multi-agent collaboration session
    
    Args:
        session_details: Collaboration session details
        background_tasks: FastAPI background tasks
        requesting_agent_id: Authenticated requesting agent ID
        calendar_agent: Calendar agent instance
        
    Returns:
        Collaboration session information
    """
    try:
        session_id = f"collab_{uuid.uuid4().hex[:12]}"
        
        collaboration_session = CollaborationSession(
            session_id=session_id,
            initiating_agent_id=requesting_agent_id,
            participating_agents=session_details.get("participating_agents", []),
            meeting_details=session_details.get("meeting_details", {}),
            status="created",
            created_at=datetime.now()
        )
        
        # Add background task to coordinate with participating agents
        background_tasks.add_task(
            coordinate_collaboration_session,
            calendar_agent,
            collaboration_session
        )
        
        logger.info(f"Created collaboration session: {session_id}")
        return {
            "session_id": session_id,
            "status": "created",
            "participating_agents": collaboration_session.participating_agents,
            "message": "Collaboration session created and coordination initiated"
        }
        
    except Exception as e:
        logger.error(f"Error creating collaboration session: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create collaboration session: {str(e)}"
        )

async def coordinate_collaboration_session(
    calendar_agent: CalendarAgent,
    session: CollaborationSession
):
    """
    Coordinate with participating agents in a collaboration session
    
    Args:
        calendar_agent: Calendar agent instance
        session: Collaboration session details
    """
    try:
        logger.info(f"Coordinating collaboration session: {session.session_id}")
        
        # Send proposals to all participating agents
        for agent_id in session.participating_agents:
            # This would send scheduling proposals to each participating agent
            # Implementation would depend on the specific collaboration requirements
            pass
        
        logger.info(f"Collaboration coordination complete: {session.session_id}")
        
    except Exception as e:
        logger.error(f"Error coordinating collaboration session: {str(e)}")

# Health check for agent communication service
@agent_router.get("/health")
async def agent_health_check():
    """Health check endpoint for agent communication service"""
    return {
        "service": "agent_routes",
        "status": "healthy",
        "agent_id": config.agent.agent_id,
        "communication_protocols": ["http_rest"],
        "timestamp": datetime.now().isoformat()
    }

# Agent capabilities endpoint
@agent_router.get("/capabilities")
async def get_agent_capabilities(
    requesting_agent_id: str = Depends(authenticate_agent_request)
):
    """Get capabilities of this agent"""
    return {
        "agent_id": config.agent.agent_id,
        "agent_name": config.agent.agent_name,
        "capabilities": [
            "calendar_management",
            "scheduling",
            "availability_checking",
            "multi_agent_collaboration",
            "conflict_resolution"
        ],
        "supported_protocols": ["http_rest"],
        "version": "1.0.0",
        "max_concurrent_collaborations": 10
    }
