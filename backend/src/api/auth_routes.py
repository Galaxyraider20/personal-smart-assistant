"""
Google Calendar OAuth Authentication Routes
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse

from ..services.google_calendar_mcp import GoogleCalendarClient
from ..utils.helpers import create_success_response, create_error_response

router = APIRouter(prefix="/auth", tags=["authentication"])

# Global client instance (in production, use dependency injection)
calendar_client = None

@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth flow"""
    global calendar_client
    if not calendar_client:
        calendar_client = GoogleCalendarClient()
        await calendar_client.initialize()
    
    try:
        auth_url = calendar_client.get_auth_url()
        return RedirectResponse(url=auth_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth error: {str(e)}")

@router.get("/google/callback")
async def google_callback(request: Request):
    """Handle Google OAuth callback"""
    global calendar_client
    
    try:
        auth_code = request.query_params.get('code')
        if not auth_code:
            raise HTTPException(status_code=400, detail="Missing authorization code")
        
        success = await calendar_client.handle_auth_callback(auth_code)
        
        if success:
            return HTMLResponse("""
                <html>
                    <body>
                        <h1>✅ Authentication Successful!</h1>
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
async def auth_status():
    """Check authentication status"""
    global calendar_client
    
    if not calendar_client:
        return {"authenticated": False, "message": "Calendar client not initialized"}
    
    return {
        "authenticated": calendar_client.is_connected,
        "message": "Connected to Google Calendar" if calendar_client.is_connected else "Not authenticated"
    }
