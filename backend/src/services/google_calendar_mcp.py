"""
Direct Google Calendar API Integration
Replaces MCP approach with direct Google API calls
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import os
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..utils.config import config
from ..utils.helpers import safe_execute

logger = logging.getLogger(__name__)

@dataclass
class CalendarEvent:
    """Calendar event data structure"""
    id: Optional[str]
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: List[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []
        if self.metadata is None:
            self.metadata = {}

@dataclass 
class AvailabilitySlot:
    """Available time slot"""
    start: datetime
    end: datetime
    duration_minutes: int



def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    formatted = dt.isoformat()
    if formatted.endswith('+00:00'):
        return formatted[:-6] + 'Z'
    return formatted

class GoogleCalendarClient:
    """
    Direct Google Calendar API Client
    Handles authentication and calendar operations without MCP
    """
    
    def __init__(self):
        """Initialize Google Calendar client"""
        self.credentials = None
        self.service = None
        self.is_connected = False
        
        # OAuth 2.0 scopes - secure but sufficient
        self.scopes = [
            'https://www.googleapis.com/auth/calendar.events'  # Events only, not full calendar
        ]
        
        # Credentials storage paths
        self.token_file = Path("config/google_token.json")
        
        logger.info("Google Calendar client initialized")
    
    async def initialize(self) -> bool:
        """Initialize the calendar client"""
        try:
            logger.info("Initializing Google Calendar client...")
            
            # Try to load existing credentials
            if await self.load_credentials():
                logger.info("Google Calendar client authenticated successfully")
                self.is_connected = True
                return True
            else:
                logger.warning("Google Calendar authentication required - use /auth/google/login")
                return True  # Still return True for startup, auth will happen on first use
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar client: {str(e)}")
            return False
    
    async def load_credentials(self) -> bool:
        """Load stored credentials"""
        try:
            if self.token_file.exists():
                self.credentials = Credentials.from_authorized_user_file(
                    str(self.token_file), self.scopes
                )
                
                # Refresh if expired
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                    self.save_credentials()
                
                if self.credentials and self.credentials.valid:
                    self.service = build('calendar', 'v3', credentials=self.credentials)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error loading credentials: {str(e)}")
            return False
    
    def save_credentials(self) -> None:
        """Save credentials to file"""
        try:
            with open(self.token_file, 'w') as token:
                token.write(self.credentials.to_json())
            logger.info("Credentials saved successfully")
        except Exception as e:
            logger.error(f"Error saving credentials: {str(e)}")
    
    def get_auth_url(self) -> str:
        """Get OAuth authorization URL"""
        try:
            # Create OAuth flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": config.mcp.client_id,
                        "client_secret": config.mcp.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [config.mcp.redirect_uri]
                    }
                },
                scopes=self.scopes
            )
            flow.redirect_uri = config.mcp.redirect_uri
            
            authorization_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            # Store flow for callback
            self._flow = flow
            
            return authorization_url
            
        except Exception as e:
            logger.error(f"Error creating auth URL: {str(e)}")
            raise
    
    async def handle_auth_callback(self, auth_code: str) -> bool:
        """Handle OAuth callback with authorization code"""
        try:
            if not hasattr(self, '_flow'):
                raise Exception("No active OAuth flow")
            
            # Fetch token
            self._flow.fetch_token(code=auth_code)
            self.credentials = self._flow.credentials
            
            # Save credentials
            self.save_credentials()
            
            # Create service
            self.service = build('calendar', 'v3', credentials=self.credentials)
            self.is_connected = True
            
            logger.info("Google Calendar authentication completed")
            return True
            
        except Exception as e:
            logger.error(f"Error handling auth callback: {str(e)}")
            return False
    
    @safe_execute
    async def create_event(
        self, 
        title: str, 
        start_time: datetime, 
        end_time: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: List[str] = None
    ) -> Optional[CalendarEvent]:
        """Create a calendar event"""
        if not self.is_connected:
            logger.error("Not authenticated with Google Calendar")
            return None
        
        try:
            event_data = {
                'summary': title,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'America/Phoenix',# HARDCODING THE VALUE....BUT HAVE TO TAKE IT FROM USER PROFILE LATER 'UTC'
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/Phoenix',# HARDCODING THE VALUE....BUT HAVE TO TAKE IT FROM USER PROFILE LATER 'UTC'
                }
            }
            
            if description:
                event_data['description'] = description
            if location:
                event_data['location'] = location
            if attendees:
                event_data['attendees'] = [{'email': email} for email in attendees]
            
            # Create the event
            event = self.service.events().insert(
                calendarId='primary',
                body=event_data
            ).execute()
            
            logger.info(f"Created calendar event: {title}")
            
            return CalendarEvent(
                id=event.get('id'),
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                location=location,
                attendees=attendees or []
            )
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
            return None
    
    @safe_execute
    async def get_events(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[CalendarEvent]:
        """Get events in date range"""
        if not self.is_connected:
            logger.warning("Not authenticated with Google Calendar")
            return []
        
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=_to_rfc3339(start_date),
                timeMax=_to_rfc3339(end_date),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            calendar_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                # Parse datetime strings
                if 'T' in start:  # dateTime format
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                else:  # date format
                    start_dt = datetime.fromisoformat(start)
                    end_dt = datetime.fromisoformat(end)
                
                calendar_events.append(CalendarEvent(
                    id=event.get('id'),
                    title=event.get('summary', 'No Title'),
                    start_time=start_dt,
                    end_time=end_dt,
                    description=event.get('description'),
                    location=event.get('location'),
                    attendees=[att.get('email', '') for att in event.get('attendees', [])]
                ))
            
            logger.info(f"Retrieved {len(calendar_events)} events")
            return calendar_events
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving events: {str(e)}")
            return []
    
    @safe_execute
    async def check_availability(
        self, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[AvailabilitySlot]:
        """Check availability in time range"""
        if not self.is_connected:
            logger.warning("Not authenticated - returning mock availability")
            return [AvailabilitySlot(start_time, end_time, 60)]
        
        try:
            # Get existing events
            existing_events = await self.get_events(start_time, end_time)
            
            # Find gaps between events (simplified)
            available_slots = []
            
            if not existing_events:
                # No events, entire range is available
                duration = int((end_time - start_time).total_seconds() / 60)
                available_slots.append(AvailabilitySlot(start_time, end_time, duration))
            else:
                # More complex logic would go here to find gaps
                # For now, return a simple slot
                duration = int((end_time - start_time).total_seconds() / 60)
                available_slots.append(AvailabilitySlot(start_time, end_time, duration))
            
            return available_slots
            
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return []
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            self.is_connected = False
            logger.info("Google Calendar client cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    

# Export the client
__all__ = ['GoogleCalendarClient', 'CalendarEvent', 'AvailabilitySlot']
