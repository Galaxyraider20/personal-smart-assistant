"""
Calendar Routes - REST access to Google Calendar data
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..services.google_calendar_mcp import GoogleCalendarClient

calendar_router = APIRouter(prefix="/api/calendar", tags=["Calendar API"])


def _get_calendar_client() -> GoogleCalendarClient:
    from ..api.main import app

    if not hasattr(app.state, "calendar_client") or app.state.calendar_client is None:
        raise HTTPException(status_code=503, detail="Calendar client not initialized")

    return app.state.calendar_client


def _parse_iso_datetime(value: Optional[str], param_name: str) -> datetime:
    if not value:
        raise HTTPException(status_code=400, detail=f"Missing '{param_name}' query parameter")

    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid ISO datetime for '{param_name}'") from exc

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def _ensure_timezone(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class CalendarEventPayload(BaseModel):
    id: Optional[str]
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: List[str] = []


class CalendarEventsResponse(BaseModel):
    success: bool
    count: int
    start: datetime
    end: datetime
    events: List[CalendarEventPayload]


@calendar_router.get("/events", response_model=CalendarEventsResponse)
async def list_events(
    start: Optional[str] = Query(None, description="ISO8601 start datetime (inclusive)"),
    end: Optional[str] = Query(None, description="ISO8601 end datetime (exclusive)"),
    calendar_client: GoogleCalendarClient = Depends(_get_calendar_client),
) -> CalendarEventsResponse:
    if not calendar_client.is_connected:
        raise HTTPException(status_code=401, detail="Google Calendar is not authenticated")

    start_dt = _parse_iso_datetime(start, "start") if start else datetime.now(timezone.utc)

    if end:
        end_dt = _parse_iso_datetime(end, "end")
    else:
        end_dt = start_dt + timedelta(days=30)

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="'end' must be after 'start'")

    events = await calendar_client.get_events(start_date=start_dt, end_date=end_dt)

    payload = [
        CalendarEventPayload(
            id=event.id,
            title=event.title,
            start_time=_ensure_timezone(event.start_time),
            end_time=_ensure_timezone(event.end_time),
            description=event.description,
            location=event.location,
            attendees=event.attendees or [],
        )
        for event in events
    ]

    return CalendarEventsResponse(
        success=True,
        count=len(payload),
        start=start_dt,
        end=end_dt,
        events=payload,
    )
