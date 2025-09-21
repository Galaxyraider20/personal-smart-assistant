# myAssist Calendar Agent

> Intelligent AI-based calendar management system with multi-agent collaboration and secure Google Calendar integration

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)

## Overview

myAssist is an intelligent calendar management agent that autonomously handles Google Calendar operations while maintaining conversational memory and enabling multi-agent collaboration for scheduling coordination. The system integrates **Google Calendar MCP** for secure calendar access and **Supermemory** for context persistence.

## Core Capabilities

### 🗓️ Intelligent Calendar Management
- Automated event creation, scheduling, conflict resolution, and meeting coordination
- Natural language processing for intuitive scheduling requests ("Schedule a meeting with John tomorrow at 2 PM")
- Smart scheduling algorithms with preference learning and pattern recognition

### 🧠 Memory & Context
- Persistent conversation history and user preference learning through Supermemory integration
- Context-aware decision making with long-term relationship data
- Automatic pattern recognition for improved scheduling suggestions over time

### 🤝 Multi-Agent Communication
- Direct communication with other customer agents for collaborative scheduling
- Meeting negotiation workflows and multi-party coordination across organizations
- Secure agent discovery and authentication protocols

### 🔒 Secure Access
- Google Calendar operations through MCP (Model Context Protocol) for controlled access
- OAuth 2.0 integration with encrypted communication channels
- Privacy-compliant memory storage with configurable retention policies

## Architecture

myAssist uses a **single monolithic agent approach** that consolidates all calendar management capabilities while maintaining comprehensive functionality for scheduling intelligence, memory management, and inter-agent communication.

### Integration Stack
- **Google Calendar MCP**: Secure, scoped access to calendar operations without full API access
- **Supermemory**: Universal memory API for persistent context, user preferences, and conversation history
- **Agent Communication Protocol**: Framework for discovering and communicating with other customer agents

## Project Structure

```
myAssist/
└── backend/
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── calendar_agent.py          \# Main agent orchestrator and decision engine
│   │   ├── agent_communication.py     \# Agent-to-agent communication protocols
│   │   └── scheduling_intelligence.py \# Smart scheduling and conflict resolution
│   ├── services/
│   │   ├── __init__.py
│   │   ├── google_calendar_mcp.py     \# Google Calendar MCP integration client
│   │   ├── supermemory_client.py      \# Supermemory API integration
│   │   └── agent_registry.py          \# Agent discovery and relationship management
│   ├── api/
│   │   ├── __init__.py
│   │   ├── chat_routes.py             \# User interaction endpoints
│   │   ├── agent_routes.py            \# Inter-agent communication endpoints
│   │   └── main.py                    \# FastAPI application setup
│   └── utils/
│       ├── __init__.py
│       ├── config.py                  \# Configuration and environment management
│       └── helpers.py                 \# Shared utility functions
├── config/
│   ├── mcp-config.json               \# MCP server configurations
│   └── .env.example                  \# Environment variables template
├── requirements.txt                  \# Python dependencies
└── README.md                         \# Project documentation
```


## Quick Start

### Prerequisites

- **Python 3.9+**
- **Node.js 18+** (for MCP server)
- **Google Cloud Console Account** (for Calendar API)
- **Supermemory Account** (for memory management - **required**)

### 1. Installation



### Clone/create the project
```
mkdir myAssist
cd myAssist/backend
```
### Create virtual environment

```
python -m venv venv
source venv/bin/activate  \# On Windows: venv\Scripts\activate
```
### Install dependencies

```
pip install -r requirements.txt
```


### 2. Google Calendar Setup (Required)

1. **Create Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project: "myAssist Calendar Agent"
   - Enable **Google Calendar API**

2. **Create OAuth 2.0 Credentials**:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth 2.0 Client IDs**
   - Application type: **Web application**
   - Name: "myAssist Local Development"
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
   - **Download credentials JSON** or copy Client ID and Client Secret

3. **Configure OAuth Consent Screen**:
   - User Type: **External** (for testing)
   - Add required scopes: 
     - `https://www.googleapis.com/auth/calendar`
     - `https://www.googleapis.com/auth/calendar.events`
   - Add test users (your email for development)

### 3. Supermemory Setup (Required)

1. **Sign up**: Go to [supermemory.ai](https://supermemory.ai/)
2. **Create account** and verify email
3. **Get API credentials**:
   - Go to **Dashboard > API Keys**
   - Create new API key: "myAssist Development"
   - **Copy the API key** (save it immediately!)
   - **Note your User ID** from account settings
4. **Create memory space**:
   - Go to **Spaces** 
   - Create new space: "myassist_calendar"

### 4. Environment Configuration



- Copy environment template

```
cp config/.env.example config/.env
```

- Edit with your actual credentials

```
nano config/.env  \# or code config/.env
```

# **Required Environment Variables:**



# Application Settings
```
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
API_HOST=127.0.0.1
API_PORT=8000
```
# Google Calendar OAuth 2.0 (from step 2)
```
GOOGLE_CLIENT_ID=your_google_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```
# MCP Server Settings
```
MCP_SERVER_URL=http://localhost:8080
MCP_SERVER_PATH=/mcp/calendar
```
# Supermemory API (from step 3) - REQUIRED
```
SUPERMEMORY_API_KEY=your_supermemory_api_key_here
SUPERMEMORY_API_URL=https://api.supermemory.ai
SUPERMEMORY_USER_ID=your_user_id_here
SUPERMEMORY_SPACE=myassist_calendar
```
# Agent Communication (for local development)
```
AGENT_ID=myassist_dev_001
AGENT_NAME="myAssist Development Agent"
AGENT_DISCOVERY_PORT=9001
AGENT_COMM_PORT=9002
AGENT_REGISTRY_URL=http://localhost:9000
AGENT_AUTH_SECRET=development_secret_key_12345678901234567890
```
# Security (generate random strings for production)
```
JWT_SECRET_KEY=dev_jwt_secret_key_12345678901234567890
SESSION_SECRET_KEY=dev_session_secret_key_12345678901234567890
```

### 5. Run the Application



# Start the FastAPI server
```
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```
# The API will be available at:

 - Main API: http://localhost:8000
 - Interactive docs: http://localhost:8000/docs
 - Health check: http://localhost:8000/health


### 6. Test Your Setup



# Test health endpoint
```
curl http://localhost:8000/health
```
# Test chat message
```
curl -X POST "http://localhost:8000/api/chat/message" \
-H "Content-Type: application/json" \
-d '{
"message": "Schedule a test meeting tomorrow at 2 PM",
"user_id": "dev_user_123",
"conversation_id": "dev_conv_123"
}'
```

## Usage Examples

myAssist understands natural language requests:

### Create meetings
```
"Schedule a meeting with Sarah tomorrow at 2 PM"
"Book a 1-hour team standup every Monday at 9 AM"
"Set up a client call for Friday afternoon"
```
### Check availability
```
"When am I free on Thursday?"
"Do I have any conflicts next Tuesday morning?"
"Find me 30 minutes next week"
```
### Manage existing events
```
"Reschedule my 3 PM meeting to Friday"
"Cancel all meetings on December 25th"
"Move the team standup to 10 AM"
```


### Chat Interface (REST API)

```
curl -X POST "http://localhost:8000/api/chat/message" \
-H "Content-Type: application/json" \
-d '{
"message": "Find me a free slot next week for a team meeting",
"user_id": "user_123",
"conversation_id": "conv_abc"
}'

```

### WebSocket Real-time Chat

```

<!DOCTYPE html>

<html>
<head><title>myAssist Chat Test</title></head>
<body>
<div id="messages"></div>
<input type="text" id="messageInput" placeholder="Type your scheduling request...">
<button onclick="sendMessage()">Send</button>

<script>
const ws = new WebSocket('ws://localhost:8000/api/chat/ws/user_123');
const messages = document.getElementById('messages');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  messages.innerHTML += `<div><strong>Agent:</strong> ${data.response?.message}</div>`;
};

function sendMessage() {
  const input = document.getElementById('messageInput');
  ws.send(JSON.stringify({
    type: 'chat_message',
    message: input.value,
    conversation_id: 'test_conv'
  }));
  messages.innerHTML += `<div><strong>You:</strong> ${input.value}</div>`;
  input.value = '';
}
</script>
</body>
</html>
```

### Get Conversation History

```

curl "http://localhost:8000/api/chat/conversations/conv_123?user_id=user_123\&limit=10"

```

### Check User Preferences

```

curl "http://localhost:8000/api/chat/preferences/user_123"

```

## API Reference

### Chat Endpoints

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/api/chat/message` | POST | Send chat message | Schedule a meeting |
| `/api/chat/ws/{user_id}` | WebSocket | Real-time chat | Live conversation |
| `/api/chat/conversations/{id}` | GET | Get conversation history | Past messages |
| `/api/chat/conversations` | GET | List user conversations | All conversations |
| `/api/chat/preferences/{user_id}` | GET | Get user preferences | Scheduling patterns |
| `/api/chat/preferences/{user_id}` | PUT | Update preferences | Set work hours |

### Agent Communication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents/discover` | POST | Discover other agents |
| `/api/agents/proposal` | POST | Receive scheduling proposal |
| `/api/agents/proposal/send` | POST | Send scheduling proposal |
| `/api/agents/status` | PUT | Update agent status |
| `/api/agents/capabilities` | GET | Get agent capabilities |

### System Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/metrics` | GET | System metrics |
| `/status` | GET | Agent status |
| `/config` | GET | Configuration (dev only) |

## Development

### Running in Development Mode




# Start with hot reload and debug logging
```
uvicorn src.api.main:app --reload --log-level debug --host 127.0.0.1 --port 8000

```

### Testing

```


# Install test dependencies

pip install pytest pytest-asyncio pytest-cov

# Run all tests

pytest

# Run with coverage

pytest --cov=src tests/

# Run specific test

pytest tests/test_calendar_agent.py -v

```

### Code Quality

```


# Format code

black src/ tests/

# Sort imports

isort src/ tests/

# Lint code

flake8 src/ tests/

# Type checking

mypy src/

```

## Configuration Files

### MCP Configuration (config/mcp-config.json)

```

{
"mcpServers": {
"google-calendar": {
"command": "npx",
"args": ["-y", "@modelcontextprotocol/server-google-calendar"],
"env": {
"GOOGLE_CLIENT_ID": "${GOOGLE_CLIENT_ID}",
        "GOOGLE_CLIENT_SECRET": "${GOOGLE_CLIENT_SECRET}",
"GOOGLE_REDIRECT_URI": "\${GOOGLE_REDIRECT_URI}",
"MCP_SERVER_PORT": "8080"
},
"capabilities": [
"calendar.read",
"calendar.write",
"calendar.events.read",
"calendar.events.write"
]
}
}
}

```

### Advanced Environment Settings

```


# Scheduling Intelligence

SCHEDULING_LOOKAHEAD_DAYS=30
MAX_SCHEDULING_SUGGESTIONS=10
DEFAULT_MEETING_DURATION=60
BUSINESS_HOURS_START=09:00
BUSINESS_HOURS_END=17:00

# Agent Communication

MAX_CONCURRENT_AGENT_CONNECTIONS=50
AGENT_HEARTBEAT_INTERVAL=30
AGENT_CONNECTION_TIMEOUT=120

# Memory Management

MAX_CONVERSATION_HISTORY=100
MEMORY_CLEANUP_INTERVAL=3600

# Performance

HTTP_TIMEOUT=30
MCP_TIMEOUT=60
RATE_LIMIT_REQUESTS_PER_MINUTE=100

```

## Multi-Agent Collaboration

### Agent Discovery

```

curl -X POST "http://localhost:8000/api/agents/discover" \
-H "Authorization: Bearer YOUR_AGENT_TOKEN" \
-H "X-Agent-ID: myassist_dev_001" \
-H "X-Timestamp: \$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
-d '{
"required_capabilities": ["calendar_management", "scheduling"],
"max_results": 5
}'

```

### Send Scheduling Proposal

```

curl -X POST "http://localhost:8000/api/agents/proposal/send" \
-H "Authorization: Bearer YOUR_AGENT_TOKEN" \
-d '{
"target_agent_id": "other_agent_123",
"meeting_title": "Cross-team Collaboration",
"proposed_times": [
{"start": "2025-09-22T14:00:00Z", "end": "2025-09-22T15:00:00Z"}
],
"participants": ["user1@company.com", "user2@partner.com"],
"duration_minutes": 60,
"priority": "normal"
}'

```

## Troubleshooting

### Common Issues

**❌ Google Calendar Authentication Failed**
```


# Check credentials

echo "Client ID: \$GOOGLE_CLIENT_ID"
echo "Client Secret: \$GOOGLE_CLIENT_SECRET"

# Verify redirect URI matches Google Cloud Console exactly

# Ensure Google Calendar API is enabled in your project

```

**❌ Supermemory Connection Error**  
```


# Test API key

curl -H "Authorization: Bearer \$SUPERMEMORY_API_KEY" \
https://api.supermemory.ai/spaces

# Check user ID and space name

echo "User ID: \$SUPERMEMORY_USER_ID"
echo "Space: \$SUPERMEMORY_SPACE"

```

**❌ MCP Server Not Starting**
```


# Check Node.js

node --version  \# Should be 18+
npm --version

# Install MCP server manually

npx -y @modelcontextprotocol/server-google-calendar

# Check port availability

netstat -tulpn | grep :8080

```

**❌ Import Errors / Module Not Found**
```


# Ensure virtual environment is activated

source venv/bin/activate

# Check if all packages installed

pip list | grep fastapi
pip list | grep aiohttp

# Reinstall if needed

pip install -r requirements.txt

```

**❌ Port Already in Use**
```


# Check what's using port 8000

lsof -i :8000

# Kill process if needed

kill -9 <PID>

# Or use different port

uvicorn src.api.main:app --port 8001

```

### Debug Mode

```


# Enable verbose logging

export DEBUG=true
export LOG_LEVEL=DEBUG

# Run with detailed output

python -m uvicorn src.api.main:app --log-level debug --reload

```

### View Logs

```


# Application logs

tail -f logs/myassist.log

# Error logs

tail -f logs/errors.log

# MCP server logs

tail -f logs/mcp-google-calendar.log

```

## Security Notes

### For Development
- Use **test credentials** for Google Calendar
- Set **DEBUG=true** for detailed error messages
- Use **simple secrets** (will be shown in examples)

### For Production  
- **Never commit** real API keys to version control
- Use **environment-specific** `.env` files
- Generate **strong random secrets** (32+ characters)
- Enable **HTTPS** and proper authentication
- Set **DEBUG=false** and appropriate log levels

## Project File Checklist

Make sure you have created all these files:

```

✅ backend/src/agent/__init__.py
✅ backend/src/agent/calendar_agent.py
✅ backend/src/agent/agent_communication.py
✅ backend/src/agent/scheduling_intelligence.py
✅ backend/src/services/__init__.py
✅ backend/src/services/google_calendar_mcp.py
✅ backend/src/services/supermemory_client.py
✅ backend/src/services/agent_registry.py
✅ backend/src/api/__init__.py
✅ backend/src/api/chat_routes.py
✅ backend/src/api/agent_routes.py
✅ backend/src/api/main.py
✅ backend/src/utils/__init__.py
✅ backend/src/utils/config.py
✅ backend/src/utils/helpers.py
✅ backend/config/mcp-config.json
✅ backend/config/.env.example
✅ backend/requirements.txt
✅ backend/README.md

```

## Next Steps

1. **Set up credentials** (Google + Supermemory)
2. **Test basic functionality** with simple scheduling requests
3. **Explore the interactive docs** at http://localhost:8000/docs
4. **Try natural language** scheduling through the chat interface
5. **Monitor logs** to understand the system behavior
6. **Experiment with** multi-agent features (optional)

## Support

- **GitHub Issues**: For bugs and feature requests
- **Documentation**: This README + inline code comments  
- **Interactive API Docs**: http://localhost:8000/docs when running

---
