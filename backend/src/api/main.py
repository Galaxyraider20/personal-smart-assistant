"""
myAssist Calendar Agent - FastAPI Application Setup

Main FastAPI application that provides:
- User interaction endpoints for conversational calendar management
- Inter-agent communication endpoints for collaborative scheduling
- Real-time chat functionality and WebSocket support
- Health monitoring and agent status management
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from ..utils.config import config
from ..agent.calendar_agent import CalendarAgent
from ..services.google_calendar_mcp import GoogleCalendarClient
from ..services.supermemory_client import SupermemoryClient
from ..services.agent_registry import AgentRegistry, AgentStatus
from .chat_routes import chat_router
from .agent_routes import agent_router
from .auth_routes import router as auth_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.api.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instances
calendar_agent: Optional[CalendarAgent] = None
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    try:
        logger.info("Starting myAssist Calendar Agent...")
        
        # Initialize services
        from ..services.google_calendar_mcp import GoogleCalendarClient
        from ..services.supermemory_client import SupermemoryClient
        from ..services.agent_registry import AgentRegistry
        from ..agent.calendar_agent import CalendarAgent
        
        # Initialize Google Calendar client (no MCP process to start)
        calendar_client = GoogleCalendarClient()
        calendar_initialized = await calendar_client.initialize()
        
        if not calendar_initialized:
            logger.warning("Google Calendar client initialization failed - will require authentication")
        
        # Initialize other services
        supermemory_client = SupermemoryClient()
        supermemory_initialized = await supermemory_client.initialize()
        
        agent_registry = AgentRegistry()
        registry_initialized = await agent_registry.initialize()
        
        # Initialize main agent
        agent = CalendarAgent()
        # agent_initialized = await agent.initialize(
        #     calendar_client=calendar_client,
        #     supermemory_client=supermemory_client,
        #     agent_registry=agent_registry
        # )

        # Set the service clients on the agent instance first## making fix REMIND TO LOOK INTO LATER.
        agent.calendar_client = calendar_client
        agent.memory_client = supermemory_client  # Note: property name is 'memory_client', not 'supermemory_client'
        agent.agent_registry = agent_registry

        # Then initialize (no parameters)
        agent_initialized = await agent.initialize()
        
        if not agent_initialized:
            logger.error("Failed to initialize calendar agent services")
            raise Exception("Service initialization failed")
        
        # Store for cleanup
        app.state.calendar_client = calendar_client
        app.state.supermemory_client = supermemory_client
        app.state.agent_registry = agent_registry
        app.state.agent = agent
        
        logger.info("myAssist Calendar Agent started successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start calendar agent: {str(e)}")
        raise
    finally:
        logger.info("Shutting down myAssist Calendar Agent...")
        
        # Cleanup in reverse order
        if hasattr(app.state, 'calendar_client'):
            await app.state.calendar_client.cleanup()
        if hasattr(app.state, 'supermemory_client'):
            await app.state.supermemory_client.cleanup()
        if hasattr(app.state, 'agent_registry'):
            await app.state.agent_registry.cleanup()
            
        logger.info("Calendar agent shutdown complete")

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application
    
    Returns:
        FastAPI: Configured application instance
    """
    app = FastAPI(
        title="myAssist Calendar Agent",
        description="Intelligent AI-based calendar management system with multi-agent collaboration",
        version="1.0.0",
        docs_url="/docs" if config.api.debug else None,
        redoc_url="/redoc" if config.api.debug else None,
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Add custom middleware for request logging
    @app.middleware("http")
    async def log_requests(request, call_next):
        start_time = asyncio.get_event_loop().time()
        response = await call_next(request)
        process_time = asyncio.get_event_loop().time() - start_time
        
        logger.info(
            f"{request.method} {request.url.path} "
            f"completed in {process_time:.3f}s with status {response.status_code}"
        )
        return response
    
    # Include API routers
    app.include_router(
        chat_router,
        prefix="/api/chat",
        tags=["User Chat Interface"]
    )
    
    app.include_router(
        agent_router,
        prefix="/api/agents",
        tags=["Agent Communication"]
    )

    app.include_router(
        auth_router,
        tags=["Authentication"]
        )
    
    return app

# Create the app instance
app = create_app()

# Dependency to get calendar agent instance
async def get_calendar_agent() -> CalendarAgent:
    """Dependency to provide calendar agent instance"""
    if not hasattr(app.state, 'calendar_agent') or app.state.calendar_agent is None:
        raise HTTPException(
            status_code=503,
            detail="Calendar agent not initialized"
        )
    return app.state.calendar_agent

# Dependency for agent authentication
async def authenticate_agent(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Authenticate inter-agent requests
    
    Returns:
        str: Authenticated agent ID
    """
    try:
        # Verify JWT token for agent authentication
        token = credentials.credentials
        payload = jwt.decode(
            token,
            config.agent.auth_secret,
            algorithms=["HS256"]
        )
        
        agent_id = payload.get("agent_id")
        if not agent_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid agent token"
            )
        
        return agent_id
        
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

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with basic service information"""
    return {
        "service": "myAssist Calendar Agent",
        "version": "1.0.0",
        "status": "operational",
        "agent_id": config.agent.agent_id,
        "capabilities": [
            "calendar_management",
            "scheduling",
            "availability_checking",
            "multi_agent_collaboration"
        ],
        "endpoints": {
            "chat": "/api/chat",
            "agents": "/api/agents",
            "health": "/health",
            "metrics": "/metrics"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancing
    
    Returns:
        Dict: Health status of all services
    """
    try:
        calendar_agent = await get_calendar_agent()
        
        # Check all service health
        health_status = {
            "status": "healthy",
            "timestamp": asyncio.get_event_loop().time(),
            "services": {
                "calendar_agent": "healthy",
                "google_calendar_mcp": "unknown",
                "supermemory": "unknown",
                "agent_registry": "unknown"
            },
            "agent_info": {
                "agent_id": config.agent.agent_id,
                "agent_name": config.agent.agent_name,
                "status": "online"
            }
        }
        
        # Test Google Calendar MCP connection
        try:
            if calendar_agent.calendar_client.is_initialized:
                health_status["services"]["google_calendar_mcp"] = "healthy"
            else:
                health_status["services"]["google_calendar_mcp"] = "unhealthy"
                health_status["status"] = "degraded"
        except Exception:
            health_status["services"]["google_calendar_mcp"] = "error"
            health_status["status"] = "degraded"
        
        # Test Supermemory connection
        try:
            if calendar_agent.memory_client.is_initialized:
                health_status["services"]["supermemory"] = "healthy"
            else:
                health_status["services"]["supermemory"] = "unhealthy"
                health_status["status"] = "degraded"
        except Exception:
            health_status["services"]["supermemory"] = "error"
            health_status["status"] = "degraded"
        
        # Test Agent Registry connection
        try:
            if calendar_agent.agent_registry.is_initialized:
                health_status["services"]["agent_registry"] = "healthy"
            else:
                health_status["services"]["agent_registry"] = "unhealthy"
                health_status["status"] = "degraded"
        except Exception:
            health_status["services"]["agent_registry"] = "error"
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }
        )

# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """
    Basic metrics endpoint for monitoring
    
    Returns:
        Dict: Service metrics and statistics
    """
    try:
        calendar_agent = await get_calendar_agent()
        
        metrics = {
            "timestamp": asyncio.get_event_loop().time(),
            "agent_metrics": {
                "active_conversations": len(calendar_agent.active_conversations),
                "pending_confirmations": len(calendar_agent.pending_confirmations),
                "uptime": asyncio.get_event_loop().time(),  # Simplified uptime
            },
            "service_metrics": {
                "calendar_operations": {
                    "total_events_created": 0,  # Would be tracked in production
                    "total_meetings_scheduled": 0,
                    "collaboration_sessions": 0
                },
                "memory_operations": {
                    "conversations_stored": 0,
                    "preferences_learned": 0,
                    "context_retrievals": 0
                },
                "agent_communications": {
                    "proposals_sent": 0,
                    "proposals_received": 0,
                    "active_collaborations": 0
                }
            },
            "performance": {
                "average_response_time": 0.0,
                "success_rate": 100.0,
                "error_rate": 0.0
            }
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Metrics collection failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to collect metrics",
                "details": str(e)
            }
        )

# Agent status endpoint
@app.get("/status")
async def get_agent_status():
    """
    Get current agent status and configuration
    
    Returns:
        Dict: Agent status and configuration
    """
    try:
        return {
            "agent_id": config.agent.agent_id,
            "agent_name": config.agent.agent_name,
            "status": "online",
            "capabilities": [
                "calendar_management",
                "scheduling", 
                "availability_checking",
                "multi_agent_collaboration"
            ],
            "endpoints": {
                "discovery_port": config.agent.discovery_port,
                "communication_port": config.agent.communication_port
            },
            "version": "1.0.0",
            "configuration": {
                "debug_mode": config.api.debug,
                "log_level": config.api.log_level,
                "environment": "production" if config.is_production() else "development"
            }
        }
        
    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to get agent status",
                "details": str(e)
            }
        )

# Configuration endpoint (admin only in production)
@app.get("/config")
async def get_configuration():
    """
    Get agent configuration (filtered for security)
    
    Returns:
        Dict: Safe configuration details
    """
    try:
        if config.is_production():
            # Return minimal config in production
            return {
                "agent_id": config.agent.agent_id,
                "agent_name": config.agent.agent_name,
                "version": "1.0.0",
                "environment": "production"
            }
        else:
            # Return detailed config in development
            return {
                "agent": {
                    "agent_id": config.agent.agent_id,
                    "agent_name": config.agent.agent_name,
                    "discovery_port": config.agent.discovery_port,
                    "communication_port": config.agent.communication_port
                },
                "api": {
                    "host": config.api.host,
                    "port": config.api.port,
                    "debug": config.api.debug,
                    "cors_origins": config.api.cors_origins
                },
                "services": {
                    "mcp_server_url": config.mcp.server_url,
                    "supermemory_api_url": config.supermemory.api_url,
                    "agent_registry_url": config.agent.registry_url
                },
                "environment": "development"
            }
            
    except Exception as e:
        logger.error(f"Configuration request failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to get configuration",
                "details": str(e)
            }
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url.path)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "details": str(exc) if config.api.debug else "An unexpected error occurred"
        }
    )

# Background task for periodic maintenance
async def periodic_maintenance():
    """Background task for periodic maintenance"""
    while True:
        try:
            if hasattr(app.state, 'calendar_agent') and app.state.calendar_agent:
                # Perform periodic maintenance tasks
                # - Clean up old conversations
                # - Update agent status
                # - Sync with registry
                pass
                
            await asyncio.sleep(300)  # Run every 5 minutes
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Maintenance task error: {str(e)}")
            await asyncio.sleep(60)

# Start the server
def start_server():
    """Start the FastAPI server with uvicorn"""
    uvicorn.run(
        "src.api.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
        log_level=config.api.log_level.lower(),
        access_log=True
    )

if __name__ == "__main__":
    start_server()
