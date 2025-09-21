"""
Scheduling Intelligence - Smart Scheduling and Conflict Resolution

Advanced scheduling algorithms for optimal meeting time suggestions, conflict detection
and resolution across multiple calendars, time zone handling and availability analysis,
and meeting preference learning and pattern recognition.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime, timedelta, time, date
from dataclasses import dataclass, asdict
from enum import Enum
import statistics
from collections import defaultdict, Counter
import numpy as np
# from scipy import optimize
import pytz

from ..utils.helpers import (
    TimeUnit, Priority, get_business_hours, is_business_day,
    calculate_duration, format_duration, safe_execute
)
from ..services.google_calendar_mcp import CalendarEvent, AvailabilitySlot, CalendarConflict

logger = logging.getLogger(__name__)

class SchedulingStrategy(Enum):
    """Different scheduling optimization strategies"""
    EARLIEST_AVAILABLE = "earliest_available"
    BUSINESS_HOURS_PREFERRED = "business_hours_preferred"
    PARTICIPANT_OPTIMIZED = "participant_optimized"
    TRAVEL_TIME_AWARE = "travel_time_aware"
    PREFERENCE_BASED = "preference_based"

class ConflictResolutionStrategy(Enum):
    """Strategies for resolving scheduling conflicts"""
    RESCHEDULE_LOWER_PRIORITY = "reschedule_lower_priority"
    SUGGEST_ALTERNATIVES = "suggest_alternatives"
    SPLIT_MEETING = "split_meeting"
    EXTEND_TIMEFRAME = "extend_timeframe"
    MULTI_AGENT_NEGOTIATION = "multi_agent_negotiation"

@dataclass
class SchedulingPreference:
    """User scheduling preferences and patterns"""
    user_id: str
    preferred_start_times: List[time]
    preferred_duration: int  # minutes
    preferred_days: List[int]  # 0=Monday, 6=Sunday  
    avoid_times: List[Tuple[time, time]]
    buffer_time: int  # minutes between meetings
    max_meetings_per_day: int
    timezone: str
    work_hours_start: time
    work_hours_end: time
    confidence_score: float = 0.5

@dataclass
class MeetingContext:
    """Context information for intelligent scheduling"""
    title: str
    participants: List[str]
    duration_minutes: int
    priority: Priority
    location: Optional[str] = None
    meeting_type: str = "general"  # general, standup, interview, presentation
    requires_preparation: bool = False
    travel_time_required: int = 0  # minutes
    recurring: bool = False
    flexibility: int = 3  # 1-5 scale, higher = more flexible
    
@dataclass
class SchedulingSuggestion:
    """Intelligent scheduling suggestion"""
    start_time: datetime
    end_time: datetime
    confidence_score: float
    reasoning: str
    alternative_times: List[datetime]
    conflicts_resolved: List[str]
    participant_compatibility: float
    travel_considerations: List[str]

@dataclass
class ConflictAnalysis:
    """Analysis of scheduling conflicts"""
    conflict_type: str
    severity: int  # 1-5 scale
    affected_participants: List[str]
    conflicting_events: List[CalendarEvent]
    resolution_options: List[Dict[str, Any]]
    estimated_resolution_time: int  # minutes

class SchedulingIntelligence:
    """
    Advanced Scheduling Intelligence Engine
    
    Provides intelligent scheduling algorithms, conflict resolution,
    preference learning, and optimization across multiple calendars
    and participants.
    """
    
    def __init__(self):
        """Initialize scheduling intelligence engine"""
        self.user_preferences: Dict[str, SchedulingPreference] = {}
        self.scheduling_patterns: Dict[str, Dict[str, Any]] = {}
        self.conflict_history: List[ConflictAnalysis] = []
        self.success_metrics: Dict[str, float] = {}
        
        logger.info("Scheduling Intelligence engine initialized")
    
    @safe_execute
    async def suggest_optimal_times(
        self,
        meeting_context: MeetingContext,
        search_start: datetime,
        search_end: datetime,
        existing_events: List[CalendarEvent],
        participant_preferences: Optional[Dict[str, SchedulingPreference]] = None,
        max_suggestions: int = 5
    ) -> List[SchedulingSuggestion]:
        """
        Generate optimal meeting time suggestions using advanced algorithms
        
        Args:
            meeting_context: Meeting details and requirements
            search_start: Start of search time range
            search_end: End of search time range
            existing_events: Current calendar events to avoid
            participant_preferences: Preferences for each participant
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of optimized scheduling suggestions
        """
        try:
            logger.info(f"Generating optimal times for: {meeting_context.title}")
            
            # Get available time slots
            available_slots = await self.find_available_slots(
                meeting_context.duration_minutes,
                search_start,
                search_end,
                existing_events
            )
            
            if not available_slots:
                logger.warning("No available slots found in the specified time range")
                return []
            
            # Score each slot based on multiple factors
            scored_suggestions = []
            for slot in available_slots:
                suggestion = await self.evaluate_time_slot(
                    slot,
                    meeting_context,
                    participant_preferences or {},
                    existing_events
                )
                
                if suggestion.confidence_score > 0.3:  # Minimum threshold
                    scored_suggestions.append(suggestion)
            
            # Sort by confidence score and return top suggestions
            scored_suggestions.sort(key=lambda x: x.confidence_score, reverse=True)
            top_suggestions = scored_suggestions[:max_suggestions]
            
            # Add alternative times for each suggestion
            for suggestion in top_suggestions:
                suggestion.alternative_times = await self.generate_alternative_times(
                    suggestion, available_slots[:10]
                )
            
            logger.info(f"Generated {len(top_suggestions)} optimal scheduling suggestions")
            return top_suggestions
            
        except Exception as e:
            logger.error(f"Error generating optimal times: {str(e)}")
            return []
    
    @safe_execute
    async def find_available_slots(
        self,
        duration_minutes: int,
        search_start: datetime,
        search_end: datetime,
        existing_events: List[CalendarEvent],
        buffer_minutes: int = 15
    ) -> List[AvailabilitySlot]:
        """Find all available time slots in the given range"""
        try:
            available_slots = []
            
            # Sort existing events by start time
            sorted_events = sorted(
                [e for e in existing_events if e.start_time and e.end_time],
                key=lambda x: x.start_time
            )
            
            current_time = search_start
            
            # Find gaps between events
            for event in sorted_events:
                if event.start_time > current_time:
                    # Found a gap
                    gap_duration = calculate_duration(current_time, event.start_time)
                    
                    if gap_duration >= duration_minutes + buffer_minutes:
                        # Create availability slot
                        slot_end = min(
                            event.start_time - timedelta(minutes=buffer_minutes),
                            current_time + timedelta(minutes=gap_duration - buffer_minutes)
                        )
                        
                        available_slots.append(AvailabilitySlot(
                            start=current_time,
                            end=slot_end,
                            duration_minutes=calculate_duration(current_time, slot_end)
                        ))
                
                # Update current time to after this event
                if event.end_time > current_time:
                    current_time = event.end_time + timedelta(minutes=buffer_minutes)
            
            # Check for availability after the last event
            if current_time < search_end:
                remaining_duration = calculate_duration(current_time, search_end)
                if remaining_duration >= duration_minutes:
                    available_slots.append(AvailabilitySlot(
                        start=current_time,
                        end=search_end,
                        duration_minutes=remaining_duration
                    ))
            
            # Filter slots by business hours and preferences
            filtered_slots = await self.filter_slots_by_preferences(
                available_slots, duration_minutes
            )
            
            logger.debug(f"Found {len(filtered_slots)} available slots")
            return filtered_slots
            
        except Exception as e:
            logger.error(f"Error finding available slots: {str(e)}")
            return []
    
    @safe_execute
    async def evaluate_time_slot(
        self,
        slot: AvailabilitySlot,
        meeting_context: MeetingContext,
        participant_preferences: Dict[str, SchedulingPreference],
        existing_events: List[CalendarEvent]
    ) -> SchedulingSuggestion:
        """Evaluate and score a time slot for meeting suitability"""
        try:
            start_time = slot.start
            end_time = start_time + timedelta(minutes=meeting_context.duration_minutes)
            
            # Initialize scoring factors
            scores = {
                'business_hours': 0.0,
                'participant_preferences': 0.0,
                'time_of_day': 0.0,
                'day_of_week': 0.0,
                'buffer_time': 0.0,
                'meeting_density': 0.0,
                'travel_time': 0.0
            }
            
            reasoning_parts = []
            
            # 1. Business hours score
            business_start, business_end = get_business_hours()
            if (business_start <= start_time.time() <= business_end and
                business_start <= end_time.time() <= business_end and
                is_business_day(start_time.date())):
                scores['business_hours'] = 1.0
                reasoning_parts.append("within business hours")
            else:
                scores['business_hours'] = 0.3
                reasoning_parts.append("outside typical business hours")
            
            # 2. Participant preferences score
            if participant_preferences:
                pref_scores = []
                for user_id, prefs in participant_preferences.items():
                    user_score = await self.score_time_for_user_preferences(
                        start_time, end_time, prefs
                    )
                    pref_scores.append(user_score)
                
                scores['participant_preferences'] = statistics.mean(pref_scores) if pref_scores else 0.5
                reasoning_parts.append(f"matches {len([s for s in pref_scores if s > 0.7])} participant preferences")
            
            # 3. Time of day score (prefer mid-morning and early afternoon)
            hour = start_time.hour
            if 9 <= hour <= 11:  # Mid-morning
                scores['time_of_day'] = 1.0
                reasoning_parts.append("optimal morning time")
            elif 13 <= hour <= 15:  # Early afternoon
                scores['time_of_day'] = 0.9
                reasoning_parts.append("good afternoon time")
            elif 8 <= hour <= 9 or 15 <= hour <= 17:  # Acceptable times
                scores['time_of_day'] = 0.7
                reasoning_parts.append("acceptable time")
            else:
                scores['time_of_day'] = 0.3
                reasoning_parts.append("suboptimal time")
            
            # 4. Day of week score
            day_score = await self.score_day_of_week(start_time, meeting_context)
            scores['day_of_week'] = day_score
            
            # 5. Buffer time score (check spacing from other meetings)
            buffer_score = await self.score_buffer_time(start_time, end_time, existing_events)
            scores['buffer_time'] = buffer_score
            
            # 6. Meeting density score (avoid over-scheduling)
            density_score = await self.score_meeting_density(start_time, existing_events)
            scores['meeting_density'] = density_score
            
            # 7. Travel time considerations
            travel_score = await self.score_travel_considerations(
                start_time, meeting_context, existing_events
            )
            scores['travel_time'] = travel_score
            
            # Calculate weighted overall score
            weights = {
                'business_hours': 0.2,
                'participant_preferences': 0.25,
                'time_of_day': 0.15,
                'day_of_week': 0.1,
                'buffer_time': 0.15,
                'meeting_density': 0.1,
                'travel_time': 0.05
            }
            
            confidence_score = sum(scores[factor] * weights[factor] for factor in scores)
            
            # Adjust for meeting priority
            if meeting_context.priority == Priority.HIGH:
                confidence_score *= 1.1
            elif meeting_context.priority == Priority.URGENT:
                confidence_score *= 1.2
            elif meeting_context.priority == Priority.LOW:
                confidence_score *= 0.9
            
            # Build reasoning string
            reasoning = f"Scheduled for {start_time.strftime('%A, %B %d at %I:%M %p')}. " + \
                       ". ".join(reasoning_parts) + f". Confidence: {confidence_score:.2f}"
            
            return SchedulingSuggestion(
                start_time=start_time,
                end_time=end_time,
                confidence_score=min(confidence_score, 1.0),  # Cap at 1.0
                reasoning=reasoning,
                alternative_times=[],
                conflicts_resolved=[],
                participant_compatibility=scores['participant_preferences'],
                travel_considerations=[]
            )
            
        except Exception as e:
            logger.error(f"Error evaluating time slot: {str(e)}")
            return SchedulingSuggestion(
                start_time=slot.start,
                end_time=slot.start + timedelta(minutes=meeting_context.duration_minutes),
                confidence_score=0.1,
                reasoning=f"Error in evaluation: {str(e)}",
                alternative_times=[],
                conflicts_resolved=[],
                participant_compatibility=0.0,
                travel_considerations=[]
            )
    
    @safe_execute
    async def detect_and_resolve_conflicts(
        self,
        proposed_meeting: MeetingContext,
        proposed_time: datetime,
        existing_events: List[CalendarEvent],
        resolution_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.SUGGEST_ALTERNATIVES
    ) -> ConflictAnalysis:
        """Detect scheduling conflicts and provide resolution options"""
        try:
            logger.info(f"Analyzing conflicts for {proposed_meeting.title} at {proposed_time}")
            
            meeting_end = proposed_time + timedelta(minutes=proposed_meeting.duration_minutes)
            
            # Find conflicting events
            conflicts = []
            for event in existing_events:
                if (event.start_time and event.end_time and
                    self.times_overlap(proposed_time, meeting_end, event.start_time, event.end_time)):
                    conflicts.append(event)
            
            if not conflicts:
                return ConflictAnalysis(
                    conflict_type="none",
                    severity=0,
                    affected_participants=[],
                    conflicting_events=[],
                    resolution_options=[],
                    estimated_resolution_time=0
                )
            
            # Analyze conflict severity
            severity = await self.assess_conflict_severity(conflicts, proposed_meeting)
            
            # Generate resolution options based on strategy
            resolution_options = await self.generate_resolution_options(
                conflicts, proposed_meeting, proposed_time, resolution_strategy
            )
            
            # Estimate time to resolve
            resolution_time = len(conflicts) * 5 + len(proposed_meeting.participants) * 2
            
            conflict_analysis = ConflictAnalysis(
                conflict_type="schedule_overlap",
                severity=severity,
                affected_participants=proposed_meeting.participants,
                conflicting_events=conflicts,
                resolution_options=resolution_options,
                estimated_resolution_time=resolution_time
            )
            
            # Store for learning
            self.conflict_history.append(conflict_analysis)
            
            logger.info(f"Found {len(conflicts)} conflicts with severity {severity}")
            return conflict_analysis
            
        except Exception as e:
            logger.error(f"Error in conflict detection: {str(e)}")
            return ConflictAnalysis(
                conflict_type="analysis_error",
                severity=1,
                affected_participants=[],
                conflicting_events=[],
                resolution_options=[],
                estimated_resolution_time=0
            )
    
    @safe_execute
    async def learn_user_preferences(
        self,
        user_id: str,
        scheduled_meetings: List[Dict[str, Any]],
        user_feedback: List[Dict[str, Any]]
    ) -> SchedulingPreference:
        """Learn and update user scheduling preferences from past behavior"""
        try:
            logger.info(f"Learning preferences for user: {user_id}")
            
            # Analyze scheduled meeting patterns
            preferred_times = []
            preferred_days = []
            meeting_durations = []
            
            for meeting in scheduled_meetings:
                if meeting.get('start_time') and meeting.get('accepted', True):
                    start_dt = datetime.fromisoformat(meeting['start_time'])
                    preferred_times.append(start_dt.time())
                    preferred_days.append(start_dt.weekday())
                    
                    if meeting.get('duration'):
                        meeting_durations.append(meeting['duration'])
            
            # Calculate most common preferences
            time_counter = Counter([t.hour for t in preferred_times])
            day_counter = Counter(preferred_days)
            
            # Determine preferred start times (top 3 hours)
            top_hours = [hour for hour, _ in time_counter.most_common(3)]
            preferred_start_times = [time(hour, 0) for hour in top_hours]
            
            # Determine preferred days
            preferred_weekdays = [day for day, _ in day_counter.most_common(3)]
            
            # Calculate preferred duration
            avg_duration = int(statistics.mean(meeting_durations)) if meeting_durations else 60
            
            # Analyze feedback for avoid times
            avoid_times = []
            for feedback in user_feedback:
                if feedback.get('rating', 0) < 3 and feedback.get('time_feedback'):
                    # Low rating indicates time should be avoided
                    avoid_time = feedback['time_feedback']
                    # Parse avoid time (simplified)
                    avoid_times.append((time(9, 0), time(10, 0)))  # Placeholder
            
            # Determine work hours from patterns
            if preferred_times:
                earliest = min(preferred_times)
                latest = max(preferred_times)
                work_start = time(max(8, earliest.hour - 1), 0)
                work_end = time(min(18, latest.hour + 2), 0)
            else:
                work_start, work_end = get_business_hours()
            
            # Calculate confidence based on data volume
            confidence = min(1.0, len(scheduled_meetings) / 20.0)  # More data = higher confidence
            
            preference = SchedulingPreference(
                user_id=user_id,
                preferred_start_times=preferred_start_times,
                preferred_duration=avg_duration,
                preferred_days=preferred_weekdays,
                avoid_times=avoid_times,
                buffer_time=15,  # Default 15 minutes
                max_meetings_per_day=8,  # Default limit
                timezone="UTC",  # Should be determined from user data
                work_hours_start=work_start,
                work_hours_end=work_end,
                confidence_score=confidence
            )
            
            # Store the learned preferences
            self.user_preferences[user_id] = preference
            
            logger.info(f"Learned preferences for {user_id} with {confidence:.2f} confidence")
            return preference
            
        except Exception as e:
            logger.error(f"Error learning user preferences: {str(e)}")
            # Return default preferences
            return SchedulingPreference(
                user_id=user_id,
                preferred_start_times=[time(9, 0), time(14, 0)],
                preferred_duration=60,
                preferred_days=[0, 1, 2, 3, 4],  # Monday-Friday
                avoid_times=[],
                buffer_time=15,
                max_meetings_per_day=6,
                timezone="UTC",
                work_hours_start=time(9, 0),
                work_hours_end=time(17, 0),
                confidence_score=0.1
            )
    
    @safe_execute
    async def optimize_multi_participant_scheduling(
        self,
        meeting_context: MeetingContext,
        participant_calendars: Dict[str, List[CalendarEvent]],
        participant_preferences: Dict[str, SchedulingPreference],
        search_start: datetime,
        search_end: datetime
    ) -> List[SchedulingSuggestion]:
        """Optimize scheduling across multiple participants with different preferences"""
        try:
            logger.info(f"Optimizing schedule for {len(participant_calendars)} participants")
            
            # Find common available times across all participants
            common_slots = await self.find_common_availability(
                participant_calendars,
                meeting_context.duration_minutes,
                search_start,
                search_end
            )
            
            if not common_slots:
                logger.warning("No common availability found for all participants")
                return []
            
            # Score each common slot for all participants
            optimized_suggestions = []
            
            for slot in common_slots:
                # Calculate group compatibility score
                participant_scores = []
                group_reasoning = []
                
                for user_id, preferences in participant_preferences.items():
                    user_score = await self.score_time_for_user_preferences(
                        slot.start,
                        slot.start + timedelta(minutes=meeting_context.duration_minutes),
                        preferences
                    )
                    participant_scores.append(user_score)
                    
                    if user_score > 0.8:
                        group_reasoning.append(f"{user_id}: excellent fit")
                    elif user_score > 0.6:
                        group_reasoning.append(f"{user_id}: good fit")
                    else:
                        group_reasoning.append(f"{user_id}: acceptable")
                
                # Calculate weighted group score
                group_score = await self.calculate_group_scheduling_score(
                    participant_scores, meeting_context
                )
                
                if group_score > 0.4:  # Minimum threshold for multi-participant
                    suggestion = SchedulingSuggestion(
                        start_time=slot.start,
                        end_time=slot.start + timedelta(minutes=meeting_context.duration_minutes),
                        confidence_score=group_score,
                        reasoning=f"Multi-participant optimization: {', '.join(group_reasoning)}",
                        alternative_times=[],
                        conflicts_resolved=[],
                        participant_compatibility=statistics.mean(participant_scores),
                        travel_considerations=[]
                    )
                    optimized_suggestions.append(suggestion)
            
            # Sort by group score
            optimized_suggestions.sort(key=lambda x: x.confidence_score, reverse=True)
            
            logger.info(f"Generated {len(optimized_suggestions)} multi-participant suggestions")
            return optimized_suggestions[:5]  # Return top 5
            
        except Exception as e:
            logger.error(f"Error in multi-participant optimization: {str(e)}")
            return []
    
    # Helper methods
    
    async def filter_slots_by_preferences(
        self,
        slots: List[AvailabilitySlot],
        duration_minutes: int
    ) -> List[AvailabilitySlot]:
        """Filter availability slots based on general preferences"""
        filtered = []
        for slot in slots:
            # Ensure slot is long enough
            if slot.duration_minutes >= duration_minutes:
                # Check if it's during reasonable hours
                start_hour = slot.start.hour
                if 7 <= start_hour <= 19:  # 7 AM to 7 PM
                    filtered.append(slot)
        return filtered
    
    async def score_time_for_user_preferences(
        self,
        start_time: datetime,
        end_time: datetime,
        preferences: SchedulingPreference
    ) -> float:
        """Score a time slot against user preferences"""
        score = 0.0
        
        # Check preferred start times
        for pref_time in preferences.preferred_start_times:
            time_diff = abs((start_time.time().hour * 60 + start_time.time().minute) - 
                           (pref_time.hour * 60 + pref_time.minute))
            if time_diff <= 60:  # Within 1 hour
                score += 0.3
        
        # Check preferred days
        if start_time.weekday() in preferences.preferred_days:
            score += 0.3
        
        # Check work hours
        if (preferences.work_hours_start <= start_time.time() <= preferences.work_hours_end and
            preferences.work_hours_start <= end_time.time() <= preferences.work_hours_end):
            score += 0.4
        
        return min(score, 1.0)
    
    async def score_day_of_week(self, start_time: datetime, meeting_context: MeetingContext) -> float:
        """Score based on day of week preferences"""
        weekday = start_time.weekday()
        
        # Monday-Thursday are generally preferred for business meetings
        if weekday < 4:  # Monday-Thursday
            return 1.0
        elif weekday == 4:  # Friday
            return 0.7
        else:  # Weekend
            return 0.2 if meeting_context.priority == Priority.URGENT else 0.1
    
    async def score_buffer_time(
        self,
        start_time: datetime,
        end_time: datetime,
        existing_events: List[CalendarEvent]
    ) -> float:
        """Score based on buffer time from other meetings"""
        min_buffer_before = float('inf')
        min_buffer_after = float('inf')
        
        for event in existing_events:
            if not event.start_time or not event.end_time:
                continue
                
            # Check buffer before
            if event.end_time <= start_time:
                buffer = (start_time - event.end_time).total_seconds() / 60
                min_buffer_before = min(min_buffer_before, buffer)
            
            # Check buffer after
            if event.start_time >= end_time:
                buffer = (event.start_time - end_time).total_seconds() / 60
                min_buffer_after = min(min_buffer_after, buffer)
        
        # Score based on minimum buffers
        min_buffer = min(min_buffer_before, min_buffer_after)
        if min_buffer == float('inf'):
            return 1.0  # No adjacent meetings
        elif min_buffer >= 30:
            return 1.0
        elif min_buffer >= 15:
            return 0.8
        elif min_buffer >= 5:
            return 0.5
        else:
            return 0.2
    
    async def score_meeting_density(self, start_time: datetime, existing_events: List[CalendarEvent]) -> float:
        """Score based on meeting density on that day"""
        same_day_events = [
            e for e in existing_events 
            if e.start_time and e.start_time.date() == start_time.date()
        ]
        
        event_count = len(same_day_events)
        
        if event_count <= 3:
            return 1.0
        elif event_count <= 5:
            return 0.8
        elif event_count <= 7:
            return 0.5
        else:
            return 0.2
    
    async def score_travel_considerations(
        self,
        start_time: datetime,
        meeting_context: MeetingContext,
        existing_events: List[CalendarEvent]
    ) -> float:
        """Score based on travel time requirements"""
        if meeting_context.travel_time_required == 0:
            return 1.0
        
        # Check if there's enough time for travel from previous meeting
        prev_event = None
        for event in existing_events:
            if (event.end_time and event.end_time <= start_time and
                (prev_event is None or event.end_time > prev_event.end_time)):
                prev_event = event
        
        if prev_event:
            available_travel_time = (start_time - prev_event.end_time).total_seconds() / 60
            if available_travel_time >= meeting_context.travel_time_required:
                return 1.0
            elif available_travel_time >= meeting_context.travel_time_required * 0.8:
                return 0.7
            else:
                return 0.3
        
        return 1.0  # No previous meeting to consider
    
    def times_overlap(self, start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
        """Check if two time ranges overlap"""
        return start1 < end2 and start2 < end1
    
    async def find_common_availability(
        self,
        participant_calendars: Dict[str, List[CalendarEvent]],
        duration_minutes: int,
        search_start: datetime,
        search_end: datetime
    ) -> List[AvailabilitySlot]:
        """Find time slots available for all participants"""
        try:
            # Get availability for each participant
            participant_slots = {}
            for user_id, events in participant_calendars.items():
                slots = await self.find_available_slots(
                    duration_minutes, search_start, search_end, events
                )
                participant_slots[user_id] = slots
            
            if not participant_slots:
                return []
            
            # Find intersection of all availability
            common_slots = []
            first_user_slots = list(participant_slots.values())[0]
            
            for slot in first_user_slots:
                # Check if this slot is available for all participants
                available_for_all = True
                
                for user_id, user_slots in participant_slots.items():
                    user_available = any(
                        self.slots_overlap(slot, user_slot) for user_slot in user_slots
                    )
                    if not user_available:
                        available_for_all = False
                        break
                
                if available_for_all:
                    common_slots.append(slot)
            
            return common_slots
            
        except Exception as e:
            logger.error(f"Error finding common availability: {str(e)}")
            return []
    
    def slots_overlap(self, slot1: AvailabilitySlot, slot2: AvailabilitySlot) -> bool:
        """Check if two availability slots overlap"""
        return slot1.start < slot2.end and slot2.start < slot1.end
    
    async def assess_conflict_severity(
        self,
        conflicts: List[CalendarEvent],
        proposed_meeting: MeetingContext
    ) -> int:
        """Assess the severity of scheduling conflicts (1-5 scale)"""
        severity = 1
        
        # Number of conflicts
        if len(conflicts) > 3:
            severity += 2
        elif len(conflicts) > 1:
            severity += 1
        
        # Priority of conflicting events (if available in metadata)
        high_priority_conflicts = sum(
            1 for event in conflicts 
            if event.metadata and event.metadata.get('priority') in ['high', 'urgent']
        )
        severity += min(high_priority_conflicts, 2)
        
        # Meeting importance
        if proposed_meeting.priority in [Priority.HIGH, Priority.URGENT]:
            severity += 1
        
        return min(severity, 5)
    
    async def generate_resolution_options(
        self,
        conflicts: List[CalendarEvent],
        proposed_meeting: MeetingContext,
        proposed_time: datetime,
        strategy: ConflictResolutionStrategy
    ) -> List[Dict[str, Any]]:
        """Generate conflict resolution options based on strategy"""
        options = []
        
        if strategy == ConflictResolutionStrategy.SUGGEST_ALTERNATIVES:
            # Find alternative times
            alternative_start = proposed_time + timedelta(hours=1)
            alternative_end = proposed_time + timedelta(days=1)
            
            options.append({
                'type': 'alternative_time',
                'description': 'Suggest alternative meeting times',
                'action': 'find_alternatives',
                'time_range': {
                    'start': alternative_start.isoformat(),
                    'end': alternative_end.isoformat()
                }
            })
        
        elif strategy == ConflictResolutionStrategy.RESCHEDULE_LOWER_PRIORITY:
            # Identify lower priority conflicts that could be moved
            moveable_conflicts = [
                event for event in conflicts
                if (event.metadata and 
                    event.metadata.get('priority', 'normal') in ['low', 'normal'] and
                    proposed_meeting.priority in [Priority.HIGH, Priority.URGENT])
            ]
            
            if moveable_conflicts:
                options.append({
                    'type': 'reschedule_conflicts',
                    'description': f'Reschedule {len(moveable_conflicts)} lower priority meetings',
                    'action': 'reschedule_events',
                    'events_to_move': [event.id for event in moveable_conflicts]
                })
        
        return options
    
    async def calculate_group_scheduling_score(
        self,
        participant_scores: List[float],
        meeting_context: MeetingContext
    ) -> float:
        """Calculate overall group scheduling score"""
        if not participant_scores:
            return 0.0
        
        # Use weighted average with minimum threshold consideration
        mean_score = statistics.mean(participant_scores)
        min_score = min(participant_scores)
        
        # Penalize if any participant has very low score
        if min_score < 0.3:
            penalty = 0.3
        elif min_score < 0.5:
            penalty = 0.1
        else:
            penalty = 0.0
        
        group_score = mean_score - penalty
        
        # Boost for high-priority meetings
        if meeting_context.priority == Priority.HIGH:
            group_score *= 1.1
        elif meeting_context.priority == Priority.URGENT:
            group_score *= 1.2
        
        return max(0.0, min(1.0, group_score))
    
    async def generate_alternative_times(
        self,
        base_suggestion: SchedulingSuggestion,
        available_slots: List[AvailabilitySlot]
    ) -> List[datetime]:
        """Generate alternative start times for a suggestion"""
        alternatives = []
        base_time = base_suggestion.start_time
        
        # Look for slots near the base time
        for slot in available_slots:
            if slot.start != base_time:
                time_diff = abs((slot.start - base_time).total_seconds() / 3600)  # Hours
                if time_diff <= 24:  # Within 24 hours
                    alternatives.append(slot.start)
        
        # Sort by proximity to base time
        alternatives.sort(key=lambda t: abs((t - base_time).total_seconds()))
        
        return alternatives[:3]  # Return top 3 alternatives

# Export main classes
__all__ = [
    'SchedulingIntelligence',
    'SchedulingStrategy',
    'ConflictResolutionStrategy',
    'SchedulingPreference',
    'MeetingContext',
    'SchedulingSuggestion',
    'ConflictAnalysis'
]
