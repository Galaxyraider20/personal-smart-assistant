"""
myAssist Configuration Management
Handles environment variables, API configurations, and system settings
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MCPConfig:
    """Google Calendar MCP Configuration"""
    server_url: str
    server_path: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]
    
    @classmethod
    def from_env(cls) -> 'MCPConfig':
        return cls(
            server_url=os.getenv('MCP_SERVER_URL', 'http://localhost:8080'),
            server_path=os.getenv('MCP_SERVER_PATH', '/mcp/calendar'),
            client_id=os.getenv('GOOGLE_CLIENT_ID', ''),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET', ''),
            redirect_uri=os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/auth/callback'),
            scopes=[
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/calendar.events'
            ]
        )

@dataclass 
class SupermemoryConfig:
    """Supermemory API Configuration"""
    api_url: str
    api_key: str
    user_id: str
    memory_space: str
    
    @classmethod
    def from_env(cls) -> 'SupermemoryConfig':
        return cls(
            api_url=os.getenv('SUPERMEMORY_API_URL', 'https://api.supermemory.ai'),
            api_key=os.getenv('SUPERMEMORY_API_KEY', ''),
            user_id=os.getenv('SUPERMEMORY_USER_ID', ''),
            memory_space=os.getenv('SUPERMEMORY_SPACE', 'myassist_calendar')
        )

@dataclass
class AgentConfig:
    """Agent Communication Configuration"""
    agent_id: str
    agent_name: str
    discovery_port: int
    communication_port: int
    registry_url: str
    auth_secret: str
    
    @classmethod
    def from_env(cls) -> 'AgentConfig':
        return cls(
            agent_id=os.getenv('AGENT_ID', 'myassist_calendar_001'),
            agent_name=os.getenv('AGENT_NAME', 'myAssist Calendar Agent'),
            discovery_port=int(os.getenv('AGENT_DISCOVERY_PORT', '9001')),
            communication_port=int(os.getenv('AGENT_COMM_PORT', '9002')),
            registry_url=os.getenv('AGENT_REGISTRY_URL', 'https://agent-registry.example.com'),
            auth_secret=os.getenv('AGENT_AUTH_SECRET', '')
        )

@dataclass
class APIConfig:
    """FastAPI Application Configuration"""
    host: str
    port: int
    debug: bool
    cors_origins: list[str]
    log_level: str
    
    @classmethod
    def from_env(cls) -> 'APIConfig':
        return cls(
            host=os.getenv('API_HOST', '0.0.0.0'),
            port=int(os.getenv('API_PORT', '8000')),
            debug=os.getenv('DEBUG', 'False').lower() == 'true',
            cors_origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(','),
            log_level=os.getenv('LOG_LEVEL', 'INFO')
        )

class Config:
    """Main Configuration Manager"""
    
    def __init__(self):
        self.load_environment()
        
        # Load all configuration sections
        self.mcp = MCPConfig.from_env()
        self.supermemory = SupermemoryConfig.from_env()
        self.agent = AgentConfig.from_env()
        self.api = APIConfig.from_env()
        
        # Load MCP server configuration
        self.mcp_server_config = self.load_mcp_server_config()
        
        # Validate critical configurations
        self.validate_config()
    
    def load_environment(self) -> None:
        """Load environment variables from .env file if it exists"""
        env_path = Path(__file__).parent.parent / 'config' / '.env'
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        os.environ.setdefault(key, value)
            logger.info(f"Loaded environment from {env_path}")
    
    def load_mcp_server_config(self) -> Dict[str, Any]:
        """Load MCP server configuration from JSON file"""
        config_path = Path(__file__).parent.parent / 'config' / 'mcp-config.json'
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded MCP server config from {config_path}")
                return config
        else:
            # Default MCP configuration
            default_config = {
                "mcpServers": {
                    "google-calendar": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-google-calendar"],
                        "env": {
                            "GOOGLE_CLIENT_ID": self.mcp.client_id,
                            "GOOGLE_CLIENT_SECRET": self.mcp.client_secret,
                            "GOOGLE_REDIRECT_URI": self.mcp.redirect_uri
                        }
                    }
                }
            }
            logger.warning(f"MCP config not found at {config_path}, using defaults")
            return default_config
    
    def validate_config(self) -> None:
        """Validate critical configuration values"""
        errors = []
        
        # Validate Google Calendar MCP settings
        if not self.mcp.client_id:
            errors.append("GOOGLE_CLIENT_ID is required")
        if not self.mcp.client_secret:
            errors.append("GOOGLE_CLIENT_SECRET is required")
            
        # Validate Supermemory settings
        if not self.supermemory.api_key:
            errors.append("SUPERMEMORY_API_KEY is required")
        if not self.supermemory.user_id:
            errors.append("SUPERMEMORY_USER_ID is required")
            
        # Validate Agent settings
        if not self.agent.auth_secret:
            errors.append("AGENT_AUTH_SECRET is required")
            
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Configuration validation passed")
    
    def get_database_url(self) -> str:
        """Get database URL if needed for local storage"""
        return os.getenv('DATABASE_URL', 'sqlite:///myassist.db')
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return os.getenv('ENVIRONMENT', 'development') == 'production'
    
    def get_log_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                },
            },
            'handlers': {
                'default': {
                    'formatter': 'default',
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout',
                },
            },
            'root': {
                'level': self.api.log_level,
                'handlers': ['default'],
            },
        }

# Global configuration instance
config = Config()

# Export commonly used configurations
__all__ = [
    'config',
    'MCPConfig', 
    'SupermemoryConfig',
    'AgentConfig',
    'APIConfig',
    'Config'
]
