"""
Shared Utility Functions for myAssist Calendar Agent

Provides common utilities for data validation, error handling, logging,
date/time processing, text parsing, and other shared functionality used
across the calendar agent components.
"""

import asyncio
import logging
import re
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta, date, time
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
import pytz
import json
from functools import wraps
from enum import Enum
import traceback

# Configure module logger
logger = logging.getLogger(__name__)

class TimeUnit(Enum):
    """Time unit enumeration for duration calculations"""
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"

class Priority(Enum):
    """Priority levels for scheduling requests"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

# =============================================================================
# Date and Time Utilities
# =============================================================================

def parse_natural_datetime(
    date_text: Optional[str] = None,
    time_text: Optional[str] = None,
    context_timezone: str = "UTC",
    reference_date: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    """
    Parse natural language date and time expressions
    
    Args:
        date_text: Natural language date (e.g., "tomorrow", "next Monday")
        time_text: Natural language time (e.g., "2 PM", "morning")
        context_timezone: Timezone for interpretation
        reference_date: Reference date for relative expressions
        
    Returns:
        Dictionary with parsed datetime information or None
    """
    try:
        if not date_text and not time_text:
            return None
        
        # Use reference date or current time
        base_dt = reference_date or datetime.now(pytz.timezone(context_timezone))
        
        # Parse date component
        target_date = None
        if date_text:
            target_date = parse_date_expression(date_text.lower(), base_dt.date())
        else:
            target_date = base_dt.date()
        
        # Parse time component
        target_time = None
        if time_text:
            target_time = parse_time_expression(time_text.lower())
        else:
            # Default to next available hour
            target_time = (base_dt + timedelta(hours=1)).time().replace(minute=0, second=0)
        
        if target_date and target_time:
            # Combine date and time
            combined_dt = datetime.combine(target_date, target_time)
            
            # Apply timezone
            tz = pytz.timezone(context_timezone)
            localized_dt = tz.localize(combined_dt)
            
            return {
                "datetime": localized_dt,
                "date": target_date,
                "time": target_time,
                "timezone": context_timezone,
                "original_date_text": date_text,
                "original_time_text": time_text,
                "formatted": localized_dt.strftime("%A, %B %d at %I:%M %p %Z")
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error parsing natural datetime: {str(e)}")
        return None

def parse_date_expression(date_text: str, reference_date: date) -> Optional[date]:
    """Parse natural language date expressions"""
    try:
        # Remove common words
        date_text = re.sub(r'\b(on|at|the)\b', '', date_text).strip()
        
        # Handle relative dates
        if "today" in date_text:
            return reference_date
        elif "tomorrow" in date_text:
            return reference_date + timedelta(days=1)
        elif "yesterday" in date_text:
            return reference_date - timedelta(days=1)
        elif "next week" in date_text:
            return reference_date + timedelta(weeks=1)
        elif "next month" in date_text:
            return reference_date + relativedelta(months=1)
        
        # Handle specific weekdays
        weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
        }
        
        for day_name, day_num in weekdays.items():
            if day_name in date_text:
                days_ahead = day_num - reference_date.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                return reference_date + timedelta(days=days_ahead)
        
        # Try parsing with dateutil
        try:
            parsed_date = date_parser.parse(date_text, default=datetime.combine(reference_date, time.min))
            return parsed_date.date()
        except:
            pass
        
        return None
        
    except Exception as e:
        logger.error(f"Error parsing date expression '{date_text}': {str(e)}")
        return None

def parse_time_expression(time_text: str) -> Optional[time]:
    """Parse natural language time expressions"""
    try:
        # Remove common words
        time_text = re.sub(r'\b(at|around)\b', '', time_text).strip()
        
        # Handle general time periods
        if any(word in time_text for word in ['morning', 'am']):
            if 'early' in time_text:
                return time(8, 0)
            elif 'late' in time_text:
                return time(11, 0)
            else:
                return time(9, 0)
        elif any(word in time_text for word in ['afternoon', 'pm']):
            if 'early' in time_text:
                return time(13, 0)
            elif 'late' in time_text:
                return time(16, 0)
            else:
                return time(14, 0)
        elif 'evening' in time_text:
            return time(18, 0)
        elif 'night' in time_text:
            return time(20, 0)
        elif 'noon' in time_text or 'midday' in time_text:
            return time(12, 0)
        elif 'midnight' in time_text:
            return time(0, 0)
        
        # Handle specific times (e.g., "2 PM", "14:30")
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)?',
            r'(\d{1,2})\s*(am|pm)',
            r'(\d{1,2})\.(\d{2})',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, time_text.lower())
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if len(match.groups()) > 2 and match.group(2) else 0
                
                # Handle AM/PM
                if len(match.groups()) >= 3 and match.group(3):
                    am_pm = match.group(3).lower()
                    if am_pm == 'pm' and hour != 12:
                        hour += 12
                    elif am_pm == 'am' and hour == 12:
                        hour = 0
                
                return time(hour, minute)
        
        return None
        
    except Exception as e:
        logger.error(f"Error parsing time expression '{time_text}': {str(e)}")
        return None

def calculate_duration(
    start_time: datetime,
    end_time: datetime,
    unit: TimeUnit = TimeUnit.MINUTES
) -> int:
    """Calculate duration between two datetimes in specified unit"""
    try:
        duration = end_time - start_time
        total_seconds = duration.total_seconds()
        
        if unit == TimeUnit.MINUTES:
            return int(total_seconds / 60)
        elif unit == TimeUnit.HOURS:
            return int(total_seconds / 3600)
        elif unit == TimeUnit.DAYS:
            return duration.days
        elif unit == TimeUnit.WEEKS:
            return int(duration.days / 7)
        elif unit == TimeUnit.MONTHS:
            return int(duration.days / 30)  # Approximate
        
        return int(total_seconds / 60)  # Default to minutes
        
    except Exception as e:
        logger.error(f"Error calculating duration: {str(e)}")
        return 0

def format_duration(minutes: int) -> str:
    """Format duration in minutes to human-readable string"""
    try:
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif minutes < 1440:  # Less than 24 hours
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes == 0:
                return f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours != 1 else ''} and {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
        else:  # Days
            days = minutes // 1440
            remaining_hours = (minutes % 1440) // 60
            if remaining_hours == 0:
                return f"{days} day{'s' if days != 1 else ''}"
            else:
                return f"{days} day{'s' if days != 1 else ''} and {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
                
    except Exception as e:
        logger.error(f"Error formatting duration: {str(e)}")
        return f"{minutes} minutes"

def get_business_hours(timezone_str: str = "UTC") -> Tuple[time, time]:
    """Get standard business hours for a timezone"""
    try:
        # Standard business hours: 9 AM to 5 PM
        return time(9, 0), time(17, 0)
    except Exception as e:
        logger.error(f"Error getting business hours: {str(e)}")
        return time(9, 0), time(17, 0)

def is_business_day(target_date: date) -> bool:
    """Check if a date is a business day (Monday-Friday)"""
    return target_date.weekday() < 5  # 0-4 are Monday-Friday

# =============================================================================
# Text Processing Utilities
# =============================================================================

def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(email_pattern, text)

def extract_phone_numbers(text: str) -> List[str]:
    """Extract phone numbers from text"""
    phone_patterns = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # US format
        r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b',  # (123) 456-7890
        r'\b\+\d{1,3}[-.\s]?\d{1,14}\b'  # International
    ]
    
    phones = []
    for pattern in phone_patterns:
        phones.extend(re.findall(pattern, text))
    
    return list(set(phones))  # Remove duplicates

def clean_text(text: str) -> str:
    """Clean and normalize text input"""
    try:
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove special characters that might interfere with parsing
        text = re.sub(r'[^\w\s@.-]', ' ', text)
        
        # Normalize case for better processing
        return text.strip()
        
    except Exception as e:
        logger.error(f"Error cleaning text: {str(e)}")
        return text or ""

def extract_names(text: str) -> List[str]:
    """Extract potential names from text"""
    try:
        # Simple name extraction - looks for capitalized words
        name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        potential_names = re.findall(name_pattern, text)
        
        # Filter out common non-names
        common_words = {
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December',
            'Morning', 'Afternoon', 'Evening', 'Night', 'Today', 'Tomorrow'
        }
        
        names = [name for name in potential_names if name not in common_words]
        return names
        
    except Exception as e:
        logger.error(f"Error extracting names: {str(e)}")
        return []

# =============================================================================
# Data Validation Utilities
# =============================================================================

def validate_email(email: str) -> bool:
    """Validate email address format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))

def validate_datetime_range(start: datetime, end: datetime) -> bool:
    """Validate that datetime range is logical"""
    return start < end

def sanitize_input(input_data: Any) -> Any:
    """Sanitize user input to prevent injection attacks"""
    try:
        if isinstance(input_data, str):
            # Remove potentially dangerous characters
            sanitized = re.sub(r'[<>"\';]', '', input_data)
            return sanitized.strip()
        elif isinstance(input_data, dict):
            return {key: sanitize_input(value) for key, value in input_data.items()}
        elif isinstance(input_data, list):
            return [sanitize_input(item) for item in input_data]
        else:
            return input_data
    except Exception as e:
        logger.error(f"Error sanitizing input: {str(e)}")
        return input_data

# =============================================================================
# Error Handling and Logging
# =============================================================================

def safe_execute(func):
    """Decorator for safe function execution with error logging"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

def create_error_response(
    error_message: str,
    error_code: str = "GENERAL_ERROR",
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create standardized error response"""
    return {
        "success": False,
        "error": {
            "message": error_message,
            "code": error_code,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
    }

def create_success_response(
    data: Any = None,
    message: str = "Operation completed successfully"
) -> Dict[str, Any]:
    """Create standardized success response"""
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }

# =============================================================================
# Security and Hashing Utilities
# =============================================================================

def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token"""
    return secrets.token_hex(length)

def create_hash(data: str, salt: Optional[str] = None) -> str:
    """Create SHA-256 hash of data with optional salt"""
    try:
        if salt:
            data = f"{data}{salt}"
        return hashlib.sha256(data.encode()).hexdigest()
    except Exception as e:
        logger.error(f"Error creating hash: {str(e)}")
        return ""

def verify_hash(data: str, hash_value: str, salt: Optional[str] = None) -> bool:
    """Verify data against hash"""
    try:
        computed_hash = create_hash(data, salt)
        return computed_hash == hash_value
    except Exception as e:
        logger.error(f"Error verifying hash: {str(e)}")
        return False

# =============================================================================
# JSON and Serialization Utilities
# =============================================================================

def safe_json_serialize(data: Any) -> str:
    """Safely serialize data to JSON with datetime handling"""
    def json_serializer(obj):
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    try:
        return json.dumps(data, default=json_serializer, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error serializing to JSON: {str(e)}")
        return "{}"

def safe_json_deserialize(json_str: str) -> Any:
    """Safely deserialize JSON string"""
    try:
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Error deserializing JSON: {str(e)}")
        return None

# =============================================================================
# Performance and Caching Utilities
# =============================================================================

def measure_execution_time(func):
    """Decorator to measure function execution time"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            logger.debug(f"{func.__name__} executed in {execution_time:.3f} seconds")
            return result
        except Exception as e:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            logger.error(f"{func.__name__} failed after {execution_time:.3f} seconds: {str(e)}")
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            result = func(*args, **kwargs)
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            logger.debug(f"{func.__name__} executed in {execution_time:.3f} seconds")
            return result
        except Exception as e:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            logger.error(f"{func.__name__} failed after {execution_time:.3f} seconds: {str(e)}")
            raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

# =============================================================================
# Export all utility functions
# =============================================================================

__all__ = [
    # Date/Time utilities
    'parse_natural_datetime',
    'parse_date_expression', 
    'parse_time_expression',
    'calculate_duration',
    'format_duration',
    'get_business_hours',
    'is_business_day',
    
    # Text processing
    'extract_emails',
    'extract_phone_numbers',
    'extract_names',
    'clean_text',
    
    # Validation
    'validate_email',
    'validate_datetime_range',
    'sanitize_input',
    
    # Error handling
    'safe_execute',
    'create_error_response',
    'create_success_response',
    
    # Security
    'generate_secure_token',
    'create_hash',
    'verify_hash',
    
    # Serialization
    'safe_json_serialize',
    'safe_json_deserialize',
    
    # Performance
    'measure_execution_time',
    
    # Enums
    'TimeUnit',
    'Priority'
]
