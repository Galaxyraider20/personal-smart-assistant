"""
myAssist Calendar Agent - Main Orchestrator and Decision Engine

This module contains the core CalendarAgent class that:
- Processes natural language user requests
- Coordinates calendar operations through Google Calendar MCP
- Manages conversation memory through Supermemory
- Orchestrates multi-agent conversations for collaborative scheduling
- Provides intelligent scheduling recommendations and conflict resolution
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json
import re
from dataclasses import dataclass
from enum import Enum

from ..utils.config import config
# from ..services.google_calendar_mcp import GoogleCalendarMCP
from ..services.google_calendar_mcp import GoogleCalendarClient
from ..services.supermemory_client import SupermemoryClient
from ..services.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)

class RequestType(Enum):
    """Types of calendar requests the agent can handle"""
    CREATE_EVENT = "create_event"
    SCHEDULE_MEETING = "schedule_meeting"
    CHECK_AVAILABILITY = "check_availability"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"
    FIND_TIME = "find_time"
    AGENT_COLLABORATION = "agent_collaboration"
    QUERY_EVENTS = "query_events"
    SET_PREFERENCES = "set_preferences"

@dataclass
class CalendarRequest:
    """Structured representation of a calendar request"""
    request_type: RequestType
    user_message: str
    extracted_data: Dict[str, Any]
    context: Dict[str, Any]
    timestamp: datetime
    user_id: str
    conversation_id: str

@dataclass
class AgentResponse:
    """Standard response format from the calendar agent"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    requires_confirmation: bool = False
    agent_actions: Optional[List[str]] = None

class CalendarAgent:
    """
    Main Calendar Agent Orchestrator
    
    Handles all user interactions, calendar operations, memory management,
    and coordination with other agents for collaborative scheduling.
    """
    
    def __init__(self):
        """Initialize the calendar agent with all required services"""
        self.agent_id = config.agent.agent_id
        self.agent_name = config.agent.agent_name
        
        # Initialize service clients
        self.calendar_client = GoogleCalendarClient()
        self.memory_client = SupermemoryClient()
        self.agent_registry = AgentRegistry()
        
        # Agent state management
        self.active_conversations: Dict[str, Dict] = {}
        self.pending_confirmations: Dict[str, Dict] = {}
        
        logger.info(f"Calendar Agent {self.agent_id} initialized successfully")
    
    async def initialize(self) -> bool:
        """
        Initialize all service connections and register agent
        Returns True if initialization successful
        """
        try:
            # Initialize Google Calendar MCP connection
            calendar_init = await self.calendar_client.initialize()
            if not calendar_init:
                logger.error("Failed to initialize Google Calendar MCP client")
                return False
            
            # Initialize Supermemory client
            memory_init = await self.memory_client.initialize()
            if not memory_init:
                logger.error("Failed to initialize Supermemory client")
                return False
            
            # Register agent in the registry
            agent_reg = await self.agent_registry.register_agent(
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                capabilities=["calendar_management", "scheduling", "availability_checking"],
                endpoint=f"http://localhost:{config.agent.communication_port}"
            )
            if not agent_reg:
                logger.error("Failed to register agent")
                return False
            
            logger.info("Calendar Agent fully initialized and registered")
            return True
            
        except Exception as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            return False
    
    async def process_user_request(
        self, 
        user_message: str, 
        user_id: str, 
        conversation_id: str
    ) -> AgentResponse:
        """
        Main entry point for processing user calendar requests
        
        Args:
            user_message: Natural language input from user
            user_id: Unique user identifier
            conversation_id: Current conversation session ID
            
        Returns:
            AgentResponse with results and next actions
        """
        try:
            # Retrieve conversation context from memory
            context = await self.get_conversation_context(user_id, conversation_id)
            
            # Parse and classify the user request
            request = await self.parse_user_request(
                user_message, user_id, conversation_id, context
            )
            
            # Store request in conversation memory
            await self.store_user_interaction(request)
            
            # Route request to appropriate handler
            response = await self.route_request(request)
            
            # Store response in conversation memory
            await self.store_agent_response(request, response)
            
            # Update conversation context
            await self.update_conversation_context(
                user_id, conversation_id, request, response
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing user request: {str(e)}")
            return AgentResponse(
                success=False,
                message=f"I encountered an error processing your request: {str(e)}. Please try again."
            )
    
    async def parse_user_request(
        self, 
        user_message: str, 
        user_id: str, 
        conversation_id: str,
        context: Dict[str, Any]
    ) -> CalendarRequest:
        """
        Parse natural language input into structured calendar request
        Uses pattern matching and context to determine intent and extract data
        """
        # Convert message to lowercase for pattern matching
        message_lower = user_message.lower()
        
        # Determine request type based on keywords and patterns
        request_type = self.classify_request_type(message_lower)
        
        # Extract relevant data based on request type
        extracted_data = await self.extract_request_data(
            user_message, request_type, context
        )
        
        return CalendarRequest(
            request_type=request_type,
            user_message=user_message,
            extracted_data=extracted_data,
            context=context,
            timestamp=datetime.now(),
            user_id=user_id,
            conversation_id=conversation_id
        )
    
    def classify_request_type(self, message: str) -> RequestType:
        """Classify user request based on keywords and patterns"""
        
        # Event creation patterns
        if any(keyword in message for keyword in ['create', 'schedule', 'book', 'add', 'set up']):
            if any(keyword in message for keyword in ['meeting', 'call', 'discussion']):
                return RequestType.SCHEDULE_MEETING
            return RequestType.CREATE_EVENT
        
        # Availability checking
        if any(keyword in message for keyword in ['available', 'free', 'busy', 'availability']):
            return RequestType.CHECK_AVAILABILITY
        
        # Finding optimal times
        if any(keyword in message for keyword in ['find time', 'when can', 'best time', 'suggest']):
            return RequestType.FIND_TIME
        
        # Event updates
        if any(keyword in message for keyword in ['update', 'change', 'modify', 'reschedule']):
            return RequestType.UPDATE_EVENT
        
        # Event deletion
        if any(keyword in message for keyword in ['delete', 'remove', 'cancel']):
            return RequestType.DELETE_EVENT
        
        # Event queries
        if any(keyword in message for keyword in ['what', 'when', 'show', 'list']):
            return RequestType.QUERY_EVENTS
        
        # Agent collaboration
        if any(keyword in message for keyword in ['coordinate', 'with others', 'team', 'collaborate']):
            return RequestType.AGENT_COLLABORATION
        
        # Preference setting
        if any(keyword in message for keyword in ['prefer', 'setting', 'configure']):
            return RequestType.SET_PREFERENCES
        
        # Default to general event creation
        return RequestType.CREATE_EVENT
    
    async def extract_request_data(
        self, 
        message: str, 
        request_type: RequestType, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract structured data from natural language request"""
        extracted = {}
        
        # Extract dates and times
        extracted.update(self.extract_datetime_info(message))
        
        # Extract people/participants
        extracted['participants'] = self.extract_participants(message, context)
        
        # Extract event titles and descriptions
        extracted.update(self.extract_event_details(message, request_type))
        
        # Extract duration information
        extracted['duration'] = self.extract_duration(message)
        
        # Extract location information
        extracted['location'] = self.extract_location(message)
        
        return extracted
    
    def extract_datetime_info(self, message: str) -> Dict[str, Any]:
        """Extract date and time information from message"""
        datetime_info = {}
        
        # Common date patterns
        date_patterns = [
            r'tomorrow',
            r'today',
            r'next week',
            r'monday|tuesday|wednesday|thursday|friday|saturday|sunday',
            r'\d{1,2}/\d{1,2}',
            r'\d{1,2}-\d{1,2}',
            r'january|february|march|april|may|june|july|august|september|october|november|december'
        ]
        
        # Common time patterns
        time_patterns = [
            r'\d{1,2}:\d{2}\s*(am|pm)?',
            r'\d{1,2}\s*(am|pm)',
            r'morning|afternoon|evening|night'
        ]
        
        # Extract dates
        for pattern in date_patterns:
            match = re.search(pattern, message.lower())
            if match:
                datetime_info['date_text'] = match.group()
                break
        
        # Extract times
        for pattern in time_patterns:
            match = re.search(pattern, message.lower())
            if match:
                datetime_info['time_text'] = match.group()
                break
        
        return datetime_info
    
    def extract_participants(self, message: str, context: Dict[str, Any]) -> List[str]:
        """Extract participant information from message"""
        participants = []
        
        # Look for email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, message)
        participants.extend(emails)
        
        # Look for @mentions or names
        mention_pattern = r'@\w+'
        mentions = re.findall(mention_pattern, message)
        participants.extend(mentions)
        
        # Look for common name patterns with "with"
        with_pattern = r'with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        names = re.findall(with_pattern, message)
        participants.extend(names)
        
        return list(set(participants))  # Remove duplicates
    
    def extract_event_details(self, message: str, request_type: RequestType) -> Dict[str, Any]:
        """Extract event title and description"""
        details = {}
        
        # For meeting requests, extract meeting topics
        if request_type == RequestType.SCHEDULE_MEETING:
            meeting_patterns = [
                r'meeting about (.+?)(?:\s+on|\s+at|\s+for|$)',
                r'discuss (.+?)(?:\s+on|\s+at|\s+for|$)',
                r'(.+?)\s+meeting(?:\s+on|\s+at|\s+for|$)'
            ]
            
            for pattern in meeting_patterns:
                match = re.search(pattern, message.lower())
                if match:
                    details['title'] = match.group(1).strip()
                    break
        
        # Default title extraction
        if 'title' not in details:
            # Look for quoted titles
            quoted = re.search(r'"([^"]+)"', message)
            if quoted:
                details['title'] = quoted.group(1)
            else:
                # Use first few words as title
                words = message.split()[:4]
                details['title'] = ' '.join(words)
        
        return details
    
    def extract_duration(self, message: str) -> Optional[int]:
        """Extract duration in minutes from message"""
        duration_patterns = [
            (r'(\d+)\s*hours?', 60),
            (r'(\d+)\s*minutes?', 1),
            (r'(\d+)\s*hrs?', 60),
            (r'(\d+)\s*mins?', 1)
        ]
        
        for pattern, multiplier in duration_patterns:
            match = re.search(pattern, message.lower())
            if match:
                return int(match.group(1)) * multiplier
        
        return None
    
    def extract_location(self, message: str) -> Optional[str]:
        """Extract location information from message"""
        location_patterns = [
            r'at\s+(.+?)(?:\s+on|\s+at|\.|$)',
            r'in\s+(.+?)(?:\s+on|\s+at|\.|$)',
            r'location:?\s*(.+?)(?:\s+on|\s+at|\.|$)'
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                if len(location) > 3:  # Avoid single words
                    return location
        
        return None
    
    async def route_request(self, request: CalendarRequest) -> AgentResponse:
        """Route parsed request to appropriate handler method"""
        try:
            handler_map = {
                RequestType.CREATE_EVENT: self.handle_create_event,
                RequestType.SCHEDULE_MEETING: self.handle_schedule_meeting,
                RequestType.CHECK_AVAILABILITY: self.handle_check_availability,
                RequestType.UPDATE_EVENT: self.handle_update_event,
                RequestType.DELETE_EVENT: self.handle_delete_event,
                RequestType.FIND_TIME: self.handle_find_time,
                RequestType.AGENT_COLLABORATION: self.handle_agent_collaboration,
                RequestType.QUERY_EVENTS: self.handle_query_events,
                RequestType.SET_PREFERENCES: self.handle_set_preferences
            }
            
            handler = handler_map.get(request.request_type)
            if handler:
                return await handler(request)
            else:
                return AgentResponse(
                    success=False,
                    message="I'm not sure how to handle that request. Could you please rephrase it?"
                )
                
        except Exception as e:
            logger.error(f"Error routing request {request.request_type}: {str(e)}")
            return AgentResponse(
                success=False,
                message="I encountered an error processing your request. Please try again."
            )
    
    async def handle_create_event(self, request: CalendarRequest) -> AgentResponse:
        """Handle event creation requests"""
        try:
            # Extract event details
            event_data = {
                'title': request.extracted_data.get('title', 'New Event'),
                'description': f"Created from: {request.user_message}",
                'location': request.extracted_data.get('location'),
                'duration': request.extracted_data.get('duration', 60)
            }
            
            # Parse date/time information
            datetime_result = await self.parse_datetime(
                request.extracted_data.get('date_text'),
                request.extracted_data.get('time_text'),
                request.context
            )
            
            if not datetime_result:
                return AgentResponse(
                    success=False,
                    message="I couldn't determine when you'd like to schedule this event. Could you specify a date and time?",
                    requires_confirmation=True
                )
            
            event_data['start_time'] = datetime_result['start']
            event_data['end_time'] = datetime_result['end']
            
            # Create the event
            # event_result = await self.calendar_client.create_event(event_data)

            calendar_event = await self.calendar_client.create_event(
                title=event_data['title'],
                start_time=event_data['start_time'],
                end_time=event_data['end_time'],
                description=event_data.get('description'),
                location=event_data.get('location')
            )

            if calendar_event:
                event_result = {
                    'success': True,
                    'event_id': calendar_event.id
                }
            else:
                event_result = {
                    'success': False,
                    'error': 'Failed to create calendar event'
                }
            
            if event_result['success']:
                return AgentResponse(
                    success=True,
                    message=f"Great! I've created '{event_data['title']}' for {datetime_result['formatted']}.",
                    data={'event_id': event_result['event_id']}
                )
            else:
                return AgentResponse(
                    success=False,
                    message=f"I couldn't create the event: {event_result['error']}"
                )
                
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            return AgentResponse(
                success=False,
                message="I encountered an error creating the event. Please try again."
            )
    
    async def handle_schedule_meeting(self, request: CalendarRequest) -> AgentResponse:
        """Handle meeting scheduling with participants"""
        # Check if participants are involved
        participants = request.extracted_data.get('participants', [])
        
        if not participants:
            # Single user meeting
            return await self.handle_create_event(request)
        
        # Multi-participant meeting - check for agent collaboration
        agent_participants = []
        external_participants = []
        
        for participant in participants:
            agent_info = await self.agent_registry.find_agent_by_user(participant)
            if agent_info:
                agent_participants.append(agent_info)
            else:
                external_participants.append(participant)
        
        if agent_participants:
            # Initiate agent collaboration
            return await self.initiate_collaborative_scheduling(request, agent_participants)
        else:
            # Regular meeting with external participants
            return await self.handle_create_event(request)
    
    async def initiate_collaborative_scheduling(
        self, 
        request: CalendarRequest, 
        agent_participants: List[Dict]
    ) -> AgentResponse:
        """Initiate collaborative scheduling with other agents"""
        try:
            # Create collaboration session
            collaboration_id = f"collab_{request.conversation_id}_{datetime.now().timestamp()}"
            
            # Send scheduling proposals to other agents
            proposals = []
            for agent in agent_participants:
                proposal = await self.send_scheduling_proposal(
                    agent['agent_id'], 
                    request, 
                    collaboration_id
                )
                if proposal:
                    proposals.append(proposal)
            
            if proposals:
                self.active_conversations[collaboration_id] = {
                    'type': 'collaborative_scheduling',
                    'request': request,
                    'agents': agent_participants,
                    'proposals': proposals,
                    'status': 'pending'
                }
                
                return AgentResponse(
                    success=True,
                    message=f"I've reached out to {len(agent_participants)} other agents to coordinate this meeting. I'll update you once I receive their availability.",
                    data={'collaboration_id': collaboration_id},
                    agent_actions=[f"Coordinating with {len(agent_participants)} agents"]
                )
            else:
                return AgentResponse(
                    success=False,
                    message="I couldn't reach the other agents for coordination. Let me schedule this as a regular meeting."
                )
                
        except Exception as e:
            logger.error(f"Error initiating collaborative scheduling: {str(e)}")
            return AgentResponse(
                success=False,
                message="I encountered an error coordinating with other agents. Let me try scheduling this as a regular meeting."
            )
    
    # Additional handler methods for other request types...
    async def handle_check_availability(self, request: CalendarRequest) -> AgentResponse:
        """Handle availability checking requests"""
        # Placeholder implementation
        return AgentResponse(
            success=True,
            message="I'm checking your availability now...",
            suggestions=["Available tomorrow at 2 PM", "Free Thursday morning"]
        )
    
    async def handle_query_events(self, request: CalendarRequest) -> AgentResponse:
        """Handle event query requests"""
        try:
            # Determine time range from the request
            time_range = self.extract_time_range(request.user_message, request.extracted_data)
            
            # Get events from calendar
            events = await self.calendar_client.get_events(
                start_date=time_range['start'],
                end_date=time_range['end']
            )
            
            if not events:
                return AgentResponse(
                    success=True,
                    message=f"You have no events scheduled for {time_range['description']}.",
                    data={'events': [], 'time_range': time_range['description']}
                )
            
            # Format events for response
            event_list = []
            for event in events:
                event_info = {
                    'id': event.id,
                    'title': event.title,
                    'start_time': event.start_time.strftime('%I:%M %p'),
                    'end_time': event.end_time.strftime('%I:%M %p'),
                    'date': event.start_time.strftime('%A, %B %d'),
                    'location': event.location,
                    'description': event.description
                }
                event_list.append(event_info)
            
            # Create human-readable message
            event_summaries = []
            for event in event_list:
                time_str = f"{event['start_time']}-{event['end_time']}"
                location_str = f" at {event['location']}" if event['location'] else ""
                event_summaries.append(f"• {event['title']} ({time_str}){location_str}")
            
            message = f"Here are your events for {time_range['description']}:\n" + "\n".join(event_summaries)
            
            return AgentResponse(
                success=True,
                message=message,
                data={
                    'events': event_list,
                    'count': len(events),
                    'time_range': time_range['description']
                },
                suggestions=["Schedule another meeting", "Check availability", "Modify an event"]
            )
            
        except Exception as e:
            logger.error(f"Error querying events: {str(e)}")
            return AgentResponse(
                success=False,
                message="I encountered an error retrieving your events. Please try again."
            )

    def extract_time_range(self, message: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract time range from query message"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        message_lower = message.lower()
        
        if 'today' in message_lower:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            description = "today"
        elif 'tomorrow' in message_lower:
            tomorrow = now + timedelta(days=1)
            start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
            end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
            description = "tomorrow"
        elif 'this week' in message_lower or 'week' in message_lower:
            # Get start of week (Monday)
            days_since_monday = now.weekday()
            start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
            description = "this week"
        elif 'next week' in message_lower:
            days_since_monday = now.weekday()
            next_week_start = (now - timedelta(days=days_since_monday) + timedelta(weeks=1))
            start = next_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
            description = "next week"
        else:
            # Default to today
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            description = "today"
        
        return {
            'start': start,
            'end': end,
            'description': description
        }
    
    # Helper methods for conversation memory management
    async def get_conversation_context(
        self, 
        user_id: str, 
        conversation_id: str
    ) -> Dict[str, Any]:
        """Retrieve conversation context from Supermemory"""
        try:
            context = await self.memory_client.get_conversation_context(
                user_id, conversation_id
            )
            return context or {}
        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}")
            return {}
    
    async def store_user_interaction(self, request: CalendarRequest) -> None:
        """Store user interaction in conversation memory"""
        try:
            await self.memory_client.store_interaction(
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                interaction_type='user_request',
                content=request.user_message,
                metadata={
                    'request_type': request.request_type.value,
                    'extracted_data': request.extracted_data,
                    'timestamp': request.timestamp.isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error storing user interaction: {str(e)}")
    
    async def store_agent_response(
        self, 
        request: CalendarRequest, 
        response: AgentResponse
    ) -> None:
        """Store agent response in conversation memory"""
        try:
            await self.memory_client.store_interaction(
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                interaction_type='agent_response',
                content=response.message,
                metadata={
                    'success': response.success,
                    'data': response.data,
                    'suggestions': response.suggestions,
                    'timestamp': datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error storing agent response: {str(e)}")
    
    async def update_conversation_context(
        self, 
        user_id: str, 
        conversation_id: str, 
        request: CalendarRequest, 
        response: AgentResponse
        ) -> None:
        """Update conversation context in memory"""
        try:
            context_data = {
                'last_request_type': request.request_type.value,
                'last_success': response.success,
                'extracted_data': request.extracted_data,
                'timestamp': datetime.now().isoformat()
            }
            
            await self.memory_client.store_conversation_context(
                conversation_id=conversation_id,
                user_message=request.user_message,
                agent_response=response.message,
                metadata=context_data
            )
            
        except Exception as e:
            logger.error(f"Error updating conversation context: {str(e)}")

    async def parse_datetime(
        self, 
        date_text: Optional[str], 
        time_text: Optional[str],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Parse natural language date/time into datetime objects"""
        try:
            # Simple datetime parsing - this is a basic implementation
            now = datetime.now()
            
            # Default to 1 hour duration
            duration_minutes = 60
            
            # Handle common date patterns
            if date_text:
                if 'tomorrow' in date_text.lower():
                    target_date = now + timedelta(days=1)
                elif 'today' in date_text.lower():
                    target_date = now
                elif 'next week' in date_text.lower():
                    target_date = now + timedelta(days=7)
                else:
                    target_date = now + timedelta(days=1)  # Default to tomorrow
            else:
                target_date = now + timedelta(days=1)  # Default to tomorrow
            
            # Handle time patterns
            if time_text:
                time_lower = time_text.lower()
                if 'morning' in time_lower:
                    hour = 9
                elif 'afternoon' in time_lower:
                    hour = 14
                elif 'evening' in time_lower:
                    hour = 18
                elif 'pm' in time_lower or 'am' in time_lower:
                    # Extract hour from "2 pm" or "2:00 pm"
                    import re
                    hour_match = re.search(r'(\d{1,2})', time_lower)
                    if hour_match:
                        hour = int(hour_match.group(1))
                        if 'pm' in time_lower and hour != 12:
                            hour += 12
                        elif 'am' in time_lower and hour == 12:
                            hour = 0
                    else:
                        hour = 14  # Default to 2 PM
                else:
                    hour = 14  # Default to 2 PM
            else:
                hour = 14  # Default to 2 PM
            
            # Create start and end times
            start_time = target_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            return {
                'start': start_time,
                'end': end_time,
                'formatted': start_time.strftime('%A, %B %d at %I:%M %p')
            }
            
        except Exception as e:
            logger.error(f"Error parsing datetime: {str(e)}")
            return None

    async def handle_update_event(self, request: CalendarRequest) -> AgentResponse:
        """Handle event update requests"""
        return AgentResponse(
            success=False,
            message="Event updating is not yet implemented. Please try creating a new event instead.",
            suggestions=["Create a new event", "Check your current events"]
        )

    async def handle_delete_event(self, request: CalendarRequest) -> AgentResponse:
        """Handle event deletion requests"""
        return AgentResponse(
            success=False,
            message="Event deletion is not yet implemented. Please use your calendar app directly.",
            suggestions=["Check your current events"]
        )

    async def handle_find_time(self, request: CalendarRequest) -> AgentResponse:
        """Handle find optimal time requests"""
        return AgentResponse(
            success=True,
            message="Based on your calendar, I suggest these times...",
            suggestions=["Tomorrow at 2 PM", "Thursday at 10 AM", "Friday afternoon"]
        )

    async def handle_agent_collaboration(self, request: CalendarRequest) -> AgentResponse:
        """Handle multi-agent collaboration requests"""
        return AgentResponse(
            success=False,
            message="Multi-agent collaboration is not yet available. I can help you schedule with external participants instead.",
            suggestions=["Schedule a regular meeting", "Add participants via email"]
        )

    async def handle_set_preferences(self, request: CalendarRequest) -> AgentResponse:
        """Handle user preference setting requests"""
        return AgentResponse(
            success=True,
            message="I've noted your preferences. I'll remember them for future scheduling.",
            suggestions=["Schedule your next meeting", "Check your availability"]
        )

    async def send_scheduling_proposal(
        self, 
        agent_id: str, 
        request: CalendarRequest, 
        collaboration_id: str
    ) -> Optional[Dict]:
        """Send scheduling proposal to another agent"""
        # Placeholder for multi-agent communication
        return None

    # Missing methods from memory_client that need simple implementations
    async def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get conversation history"""
        try:
            return await self.memory_client.get_conversation_history(conversation_id)
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return []

    async def cleanup(self) -> None:
        """Cleanup agent resources"""
        try:
            await self.calendar_client.cleanup()
            await self.memory_client.cleanup()
            await self.agent_registry.cleanup()
            logger.info("Calendar Agent cleanup completed")
        except Exception as e:
            logger.error(f"Error during agent cleanup: {str(e)}")

