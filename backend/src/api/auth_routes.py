"""
Google Calendar OAuth Authentication Routes
"""

from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse

from ..services.google_calendar_mcp import GoogleCalendarClient

router = APIRouter(prefix="/auth", tags=["authentication"])

# Global client reference maintained for backward compatibility
calendar_client: Optional[GoogleCalendarClient] = None


def _ensure_client(request: Request) -> GoogleCalendarClient:
    global calendar_client

    state_client = getattr(request.app.state, "calendar_client", None)

    if state_client is not None and calendar_client is None:
        calendar_client = state_client

    if state_client is None:
        calendar_client = calendar_client or GoogleCalendarClient()
        request.app.state.calendar_client = calendar_client

    assert request.app.state.calendar_client is not None
    return request.app.state.calendar_client


@router.get("/google/login")
async def google_login(request: Request):
    """Initiate Google OAuth flow"""
    client = _ensure_client(request)

    try:
        await client.initialize()
        auth_url = client.get_auth_url()
        return RedirectResponse(url=auth_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth error: {str(e)}")


@router.get("/google/callback")
async def google_callback(request: Request):
    """Handle Google OAuth callback"""
    client = _ensure_client(request)

    try:
        auth_code = request.query_params.get('code')
        if not auth_code:
            raise HTTPException(status_code=400, detail="Missing authorization code")

        success = await client.handle_auth_callback(auth_code)

        if success:
            return HTMLResponse("""
                <html>
                    <body>
                        <h1>Authentication Successful!</h1>
                        <p>You can now use myAssist Calendar Agent.</p>
                        <p>Close this window and try the chat interface.</p>
                        <script>
                            setTimeout(() => window.close(), 3000);
                        </script>
                    </body>
                </html>
            """)
        else:
            raise HTTPException(status_code=400, detail="Authentication failed")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Callback error: {str(e)}")


@router.get("/status")
async def auth_status(request: Request):
    """Check authentication status"""
    client = getattr(request.app.state, "calendar_client", None)

    if not client:
        return {"authenticated": False, "message": "Calendar client not initialized"}

    return {
        "authenticated": client.is_connected,
        "message": "Connected to Google Calendar" if client.is_connected else "Not authenticated"
    }


