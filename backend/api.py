"""
FastAPI application for AutoAltText.

Provides REST API endpoints for alt-text generation.
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import tempfile
import os
import copy
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import secrets
from urllib.parse import urlencode
from starlette.middleware.base import BaseHTTPMiddleware

# Load environment variables from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()  # Silently loads .env if present, does nothing if not present
except ImportError:
    pass  # python-dotenv not installed, environment variables must be set at system level

# Import from the app module
from app import (
    analyze_image_with_openai,
    analyze_image_with_ollama,
    load_and_merge_prompts,
    load_vision_prompt,
    load_translation_prompt,
    load_translation_system_prompt,
    load_config,
    get_absolute_folder_path,
    get_llm_credentials,
    log_message,
    ECB_LLM_AVAILABLE,
    OLLAMA_AVAILABLE,
    GEMINI_AVAILABLE,
    genai as gemini_client,
    configure_gemini
)

# Custom middleware to handle CloudFront/ALB proxy headers
class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to trust and process proxy headers from CloudFront + ALB.

    CloudFront and ALB add these headers:
    - X-Forwarded-For: Original client IP
    - X-Forwarded-Proto: Original protocol (https)
    - X-Forwarded-Host: Original host header
    - X-Forwarded-Port: Original port

    This middleware reconstructs the original request context.
    """
    async def dispatch(self, request: Request, call_next):
        # Get forwarded headers
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        forwarded_host = request.headers.get("X-Forwarded-Host")
        forwarded_port = request.headers.get("X-Forwarded-Port")
        forwarded_for = request.headers.get("X-Forwarded-For")

        # Update request scope with trusted proxy information
        if forwarded_proto:
            request.scope["scheme"] = forwarded_proto

        if forwarded_host:
            # Handle host:port format
            if ":" in forwarded_host and not forwarded_port:
                host_parts = forwarded_host.split(":")
                request.scope["server"] = (host_parts[0], int(host_parts[1]))
            else:
                port = int(forwarded_port) if forwarded_port else (443 if forwarded_proto == "https" else 80)
                request.scope["server"] = (forwarded_host, port)

        if forwarded_for:
            # X-Forwarded-For can be a comma-separated list: "client, proxy1, proxy2"
            # First IP is the original client
            client_ip = forwarded_for.split(",")[0].strip()
            request.scope["client"] = (client_ip, 0)

        response = await call_next(request)
        return response


# Initialize FastAPI app
app = FastAPI(
    title="MyAccessibilityBuddy API",
    description="WCAG 2.2 compliant alt-text generation API",
    version="1.0.9",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add proxy headers middleware FIRST (before CORS)
# This must be added before CORS to ensure proper origin handling
app.add_middleware(ProxyHeadersMiddleware)

# Configure CORS to allow frontend access
# When allow_credentials=True, must specify exact origins (not "*")

# Build allowed origins list dynamically based on environment
allowed_origins = [
    "http://localhost:8080",      # Local frontend development
    "http://localhost:8000",      # Direct backend access
    "http://127.0.0.1:8080",      # Alternative localhost
    "http://127.0.0.1:8000",      # Alternative localhost
]

# Add production/AWS origins from environment variable if set
# Set ALLOWED_ORIGINS="https://your-cloudfront-domain.cloudfront.net,https://your-alb-domain.amazonaws.com"
additional_origins = os.environ.get("ALLOWED_ORIGINS", "")
if additional_origins:
    # Split by comma and strip whitespace
    for origin in additional_origins.split(","):
        origin = origin.strip()
        if origin and origin not in allowed_origins:
            allowed_origins.append(origin)
            print(f"Added CORS origin from environment: {origin}")

print(f"CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load configuration on startup
@app.on_event("startup")
async def startup_event():
    """Load configuration when API starts."""
    load_config()
    # Schedule session cleanup task
    import asyncio
    asyncio.create_task(periodic_session_cleanup())

async def periodic_session_cleanup():
    """
    Periodically clean up old sessions.
    Runs every hour and removes sessions older than 24 hours.
    """
    import asyncio
    while True:
        try:
            cleanup_old_sessions(max_age_hours=24)
        except Exception as e:
            print(f"Error during session cleanup: {e}")
        # Wait 1 hour before next cleanup
        await asyncio.sleep(3600)


# In-memory session storage for U2A credentials
# In production, use Redis or a proper session store
USER_SESSIONS = {}

# OAuth2 state storage (for CSRF protection)
# Maps state string -> session_id
OAUTH_STATES = {}

# Session data storage for web app uploads
# Maps session_id -> {"created": timestamp, "last_accessed": timestamp}
WEB_APP_SESSIONS = {}

# Job status storage for async operations (polling support)
# Maps job_id -> {"status": "running"|"complete"|"error", "percent": 0-100, "message": str, ...}
JOB_STATUS = {}

def get_or_create_session_id(request: Request) -> str:
    """
    Get existing session ID from cookie or create a new one.
    Session IDs are prefixed with 'web-' to distinguish from CLI sessions.

    Sessions persist across container restarts by checking folder existence on disk.

    Args:
        request: FastAPI Request object

    Returns:
        str: Session ID with 'web-' prefix
    """
    session_id = request.cookies.get("web_session_id")

    # Check if session exists (either in memory or on disk)
    if session_id:
        # Validate session exists on disk
        base_images = get_absolute_folder_path('images')
        session_image_folder = os.path.join(base_images, session_id)

        if os.path.exists(session_image_folder):
            # Session exists on disk, restore to memory if needed
            if session_id not in WEB_APP_SESSIONS:
                WEB_APP_SESSIONS[session_id] = {
                    "created": datetime.now(),
                    "last_accessed": datetime.now(),
                    "type": "web"
                }
            else:
                # Update last accessed time
                WEB_APP_SESSIONS[session_id]["last_accessed"] = datetime.now()

            return session_id

    # No valid session found, create new one with datetime prefix
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    session_id = f"{timestamp}-{uuid.uuid4()}"
    WEB_APP_SESSIONS[session_id] = {
        "created": datetime.now(),
        "last_accessed": datetime.now(),
        "type": "web"
    }

    return session_id

def get_session_type(session_id: str) -> str:
    """
    Determine session type from session ID.

    Args:
        session_id: Session ID (e.g., '20260122-143052-abc123')

    Returns:
        str: Session type ('session' or 'shared')
    """
    if session_id == 'shared':
        return 'shared'
    else:
        return 'session'

def clear_session_data(session_id: str) -> dict:
    """
    Clear session-specific data from images, context, alt-text, and reports folders.

    Supports both web- and cli- prefixed session IDs.

    Returns:
        dict with success, message, files_deleted, folders_deleted, session_id, and cleared details
    """
    import shutil

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")

    cleared = {}
    files_deleted = 0
    folders_deleted = 0

    try:
        base_images = get_absolute_folder_path('images')
        base_context = get_absolute_folder_path('context')
        base_alt_text = get_absolute_folder_path('alt_text')
        base_reports = get_absolute_folder_path('reports')
        base_logs = get_absolute_folder_path('logs')

        targets = {
            "images": os.path.join(base_images, session_id),
            "context": os.path.join(base_context, session_id),
            "alt_text": os.path.join(base_alt_text, session_id),
            "reports": os.path.join(base_reports, session_id),
            "logs": os.path.join(base_logs, session_id)
        }

        for key, path in targets.items():
            if os.path.exists(path):
                try:
                    # Count files before deletion
                    if os.path.isdir(path):
                        for root, dirs, files in os.walk(path):
                            files_deleted += len(files)

                    # Remove the entire folder
                    shutil.rmtree(path)
                    folders_deleted += 1
                    cleared[key] = True
                    log_message(f"Cleared {key} folder for session {session_id}", "INFORMATION")
                except Exception as e:
                    log_message(f"Failed to clear {key} for session {session_id}: {e}", "WARNING")
                    cleared[key] = False
            else:
                cleared[key] = False

        # Remove from in-memory tracking for web sessions
        if session_id in WEB_APP_SESSIONS:
            WEB_APP_SESSIONS.pop(session_id, None)

        return {
            "success": True,
            "message": f"Session {session_id} cleared successfully",
            "files_deleted": files_deleted,
            "folders_deleted": folders_deleted,
            "session_id": session_id,
            "cleared": cleared
        }
    except HTTPException:
        raise
    except Exception as e:
        log_message(f"Clear session error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))

def get_session_folders(session_id: str) -> dict:
    """
    Get session-specific folder paths for images and alt-text output.
    Supports both web- and cli- prefixed session IDs.

    Args:
        session_id: Session ID with prefix (e.g., 'web-abc123')

    Returns:
        dict: Dictionary with 'images', 'alt_text' folder paths, and 'type'
    """
    # Get base folders from config
    base_images_folder = get_absolute_folder_path('images')
    base_output_folder = get_absolute_folder_path('output/alt-text')

    # Create session-specific subfolders (session_id already has prefix)
    session_images_folder = os.path.join(base_images_folder, session_id)
    session_output_folder = os.path.join(base_output_folder, session_id)

    # Ensure folders exist
    os.makedirs(session_images_folder, exist_ok=True)
    os.makedirs(session_output_folder, exist_ok=True)

    return {
        "images": session_images_folder,
        "alt_text": session_output_folder,
        "type": get_session_type(session_id),
        "session_id": session_id
    }

def cleanup_old_sessions(max_age_hours: int = 24, session_type: str = None):
    """
    Clean up session folders older than max_age_hours.
    Supports filtering by session type (web, cli) via prefix.

    Args:
        max_age_hours: Maximum age in hours before session is cleaned up
        session_type: Filter by session type ('web', 'cli', or None for all)
    """
    import shutil

    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    sessions_to_remove = []

    for session_id, session_data in WEB_APP_SESSIONS.items():
        # Filter by session type if specified
        if session_type and not session_id.startswith(f"{session_type}_"):
            continue

        if session_data["last_accessed"] < cutoff_time:
            sessions_to_remove.append(session_id)

    # Remove old sessions
    removed_count = 0
    for session_id in sessions_to_remove:
        try:
            # Remove session folders
            folders = get_session_folders(session_id)
            for key, folder in folders.items():
                if key in ['images', 'alt_text'] and os.path.exists(folder):
                    shutil.rmtree(folder)
                    removed_count += 1

            # Remove from session storage
            del WEB_APP_SESSIONS[session_id]
        except Exception as e:
            print(f"Error cleaning up session {session_id}: {e}")

    if removed_count > 0:
        session_filter = f"{session_type} " if session_type else ""
        print(f"Cleaned up {removed_count} old {session_filter}session folder(s)")

def count_sessions_by_type() -> dict:
    """
    Count active sessions by type.

    Returns:
        dict: Session counts by type {'web': count, 'cli': count, 'total': count}
    """
    counts = {'web': 0, 'cli': 0, 'unknown': 0}

    for session_id in WEB_APP_SESSIONS.keys():
        session_type = get_session_type(session_id)
        counts[session_type] = counts.get(session_type, 0) + 1

    counts['total'] = sum(counts.values())
    return counts

def list_active_sessions(session_type: str = None) -> list:
    """
    List active sessions, optionally filtered by type.

    Args:
        session_type: Filter by type ('web', 'cli', or None for all)

    Returns:
        list: List of session info dicts
    """
    sessions = []

    for session_id, session_data in WEB_APP_SESSIONS.items():
        # Filter by type if specified
        if session_type and not session_id.startswith(f"{session_type}_"):
            continue

        sessions.append({
            'session_id': session_id,
            'type': get_session_type(session_id),
            'created': session_data['created'].isoformat(),
            'last_accessed': session_data['last_accessed'].isoformat(),
            'age_hours': (datetime.now() - session_data['created']).total_seconds() / 3600
        })

    return sorted(sessions, key=lambda x: x['last_accessed'], reverse=True)

# Response models
class AltTextResponse(BaseModel):
    """Response model for alt-text generation."""
    success: bool
    alt_text: str
    image_type: str
    reasoning: Optional[str] = None
    character_count: int
    language: str
    image_id: Optional[str] = None
    json_file_path: Optional[str] = None
    error: Optional[str] = None


class SaveReviewedAltTextRequest(BaseModel):
    """Request model for saving human-reviewed alt text."""
    image_id: str
    reviewed_alt_text: str
    language: str
    reviewed_alt_text_length: Optional[int] = None


class SaveReviewedAltTextResponse(BaseModel):
    """Response model for saving human-reviewed alt text."""
    success: bool
    message: str
    json_file_path: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    llm_provider: str
    service: str


class AuthStatusResponse(BaseModel):
    """Response model for auth status check."""
    authenticated: bool
    requires_u2a: bool
    has_credentials: bool
    login_url: Optional[str] = None


# API Endpoints

@app.get("/api/auth/status", response_model=AuthStatusResponse)
async def auth_status(request: Request):
    """
    Check authentication status.

    Returns:
        AuthStatusResponse: Current authentication status
    """
    from config import settings

    llm_provider = settings.get("llm_provider", "OpenAI")

    # ECB-LLM uses CredentialManager for U2A authentication (no browser redirect needed)
    # OpenAI uses API key
    # Both are handled automatically by the backend, so no user action needed in Web UI
    requires_u2a = False
    has_credentials = True  # Backend handles authentication automatically
    login_url = None

    return AuthStatusResponse(
        authenticated=True,
        requires_u2a=requires_u2a,
        has_credentials=has_credentials,
        login_url=login_url
    )


@app.get("/api/auth/redirect")
async def auth_redirect():
    """
    Initiate OAuth2 authorization code flow by redirecting to ECB login.

    This endpoint:
    1. Generates a random state for CSRF protection
    2. Builds the OAuth2 authorization URL with required parameters
    3. Redirects the user to ECB's login page
    """
    from config import settings

    # Get OAuth2 configuration
    ecb_llm_config = settings.get("ecb_llm", {})
    authorize_url = ecb_llm_config.get("authorize_url")
    client_id = os.environ.get('CLIENT_ID_U2A')

    if not authorize_url or not client_id:
        raise HTTPException(
            status_code=500,
            detail="OAuth2 configuration incomplete - missing authorize_url or client_id"
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Create temporary session
    session_id = str(uuid.uuid4())
    OAUTH_STATES[state] = {
        "session_id": session_id,
        "created_at": datetime.now()
    }

    # Clean up old states (older than 10 minutes)
    cutoff_time = datetime.now() - timedelta(minutes=10)
    expired_states = [
        s for s, data in OAUTH_STATES.items()
        if data["created_at"] < cutoff_time
    ]
    for s in expired_states:
        del OAUTH_STATES[s]

    # Build OAuth2 authorization URL
    # Note: The callback URL must match what's registered in the ECB OAuth2 application
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": "http://localhost:3001/callback",
        "scope": ecb_llm_config.get("scope", "exdi-default.read"),
        "state": state
    }

    auth_url = f"{authorize_url}?{urlencode(params)}"

    return RedirectResponse(url=auth_url)


@app.get("/callback")
@app.get("/api/auth/callback")
async def auth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """
    OAuth2 callback endpoint that receives the authorization code.

    This endpoint:
    1. Validates the state parameter (CSRF protection)
    2. Exchanges the authorization code for an access token
    3. Stores the credentials in the session
    4. Redirects back to the frontend

    Args:
        code: Authorization code from OAuth2 provider
        state: State parameter for CSRF validation
        error: Error message if authentication failed
    """
    import requests
    import urllib3
    from config import settings

    # Disable SSL warnings for self-signed certificates
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Check for OAuth2 errors
    if error:
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Authentication Failed</title></head>
            <body>
                <h1>Authentication Failed</h1>
                <p>Error: {error}</p>
                <p><a href="file:///home/developer/AutoAltText/frontend/index.html">Return to application</a></p>
            </body>
            </html>
            """,
            status_code=400
        )

    # Validate required parameters
    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing required parameters (code or state)"
        )

    # Validate state (CSRF protection)
    if state not in OAUTH_STATES:
        raise HTTPException(
            status_code=400,
            detail="Invalid state parameter"
        )

    state_data = OAUTH_STATES[state]
    session_id = state_data["session_id"]

    # Clean up used state
    del OAUTH_STATES[state]

    try:
        # Exchange authorization code for access token
        ecb_llm_config = settings.get("ecb_llm", {})
        token_url = ecb_llm_config.get("token_url")
        client_id = os.environ.get('CLIENT_ID_U2A')
        client_secret = os.environ.get('CLIENT_SECRET_U2A')

        if not token_url or not client_id or not client_secret:
            raise HTTPException(
                status_code=500,
                detail="OAuth2 configuration incomplete"
            )

        # Token exchange request
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:3001/callback",
            "client_id": client_id,
            "client_secret": client_secret
        }

        response = requests.post(
            token_url,
            data=token_data,
            timeout=30,
            verify=False  # Disable SSL verification for self-signed certs
        )

        if response.status_code != 200:
            return HTMLResponse(
                content=f"""
                <html>
                <head><title>Token Exchange Failed</title></head>
                <body>
                    <h1>Token Exchange Failed</h1>
                    <p>Could not exchange authorization code for access token.</p>
                    <p>Status: {response.status_code}</p>
                    <p><a href="file:///home/developer/AutoAltText/frontend/index.html">Return to application</a></p>
                </body>
                </html>
                """,
                status_code=400
            )

        token_response = response.json()
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")

        if not access_token:
            raise HTTPException(
                status_code=500,
                detail="No access token received"
            )

        # Store tokens in session
        USER_SESSIONS[session_id] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "created_at": datetime.now(),
            "auth_method": "oauth2"
        }

        # Return HTML that sets cookie and redirects to frontend
        html_content = f"""
        <html>
        <head>
            <title>Authentication Successful</title>
            <script>
                // Set cookie
                document.cookie = "session_id={session_id}; path=/; max-age=3600; SameSite=Lax";

                // Redirect to frontend
                setTimeout(function() {{
                    window.location.href = "file:///home/developer/AutoAltText/frontend/index.html";
                }}, 1000);
            </script>
        </head>
        <body>
            <h1>Authentication Successful!</h1>
            <p>Redirecting to application...</p>
            <p>If not redirected, <a href="file:///home/developer/AutoAltText/frontend/index.html">click here</a></p>
        </body>
        </html>
        """

        response = HTMLResponse(content=html_content)
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=3600,
            httponly=True,
            samesite="lax",
            domain="localhost"  # Allow cookie to work across both ports 8000 and 3001
        )

        return response

    except requests.RequestException as e:
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Authentication Error</title></head>
            <body>
                <h1>Authentication Error</h1>
                <p>Error communicating with authentication server: {str(e)}</p>
                <p><a href="file:///home/developer/AutoAltText/frontend/index.html">Return to application</a></p>
            </body>
            </html>
            """,
            status_code=500
        )
    except Exception as e:
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Unexpected Error</title></head>
            <body>
                <h1>Unexpected Error</h1>
                <p>An unexpected error occurred: {str(e)}</p>
                <p><a href="file:///home/developer/AutoAltText/frontend/index.html">Return to application</a></p>
            </body>
            </html>
            """,
            status_code=500
        )


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        HealthResponse: API status and configuration info
    """
    from config import settings

    return HealthResponse(
        status="healthy",
        version="1.0.9",
        llm_provider=settings.get("llm_provider", "OpenAI"),
        service="MyAccessibilityBuddy"
    )


@app.get("/api/available-providers")
async def get_available_providers():
    """
    Get list of available providers based on installed libraries and enabled status.

    Only returns providers that are both installed AND enabled in config.json.

    Returns:
        Dictionary with available providers and their models from config
    """
    from app import CONFIG

    if not CONFIG:
        load_config()
        from app import CONFIG

    available_providers = {}

    # Check OpenAI - only include if enabled
    if CONFIG.get('openai', {}).get('enabled', False):
        available_providers['openai'] = CONFIG.get('openai', {}).get('available_models', {})

    # Check Claude - only include if enabled
    if CONFIG.get('claude', {}).get('enabled', False):
        available_providers['claude'] = CONFIG.get('claude', {}).get('available_models', {})

    # Only include ECB-LLM if the library is installed AND enabled
    if ECB_LLM_AVAILABLE and CONFIG.get('ecb_llm', {}).get('enabled', False):
        available_providers['ecb-llm'] = CONFIG.get('ecb_llm', {}).get('available_models', {})

    # Only include Ollama if the library is installed AND enabled
    if OLLAMA_AVAILABLE and CONFIG.get('ollama', {}).get('enabled', False):
        available_providers['ollama'] = CONFIG.get('ollama', {}).get('available_models', {})

    # Check Gemini - only include if the library is installed AND enabled
    if GEMINI_AVAILABLE and CONFIG.get('gemini', {}).get('enabled', False):
        available_providers['gemini'] = CONFIG.get('gemini', {}).get('available_models', {})

    # Get current config defaults from steps
    current_config = CONFIG.get('steps', {
        'vision': {'provider': 'OpenAI', 'model': 'gpt-4o'},
        'processing': {'provider': 'OpenAI', 'model': 'gpt-4o'},
        'translation': {'provider': 'OpenAI', 'model': 'gpt-4o'}
    })
    current_config['alt_text_max_chars'] = CONFIG.get('alt_text_max_chars', 125)
    current_config['geo_boost_increase_percent'] = CONFIG.get('geo_boost_increase_percent', 20)
    current_config['time_estimation'] = CONFIG.get('time_estimation', {})
    current_config['pages_visibility'] = CONFIG.get('pages_visibility', {
        'home': True,
        'content_creator': True,
        'accessibility_compliance': True,
        'prompt_optimization': True,
        'remediation': True,
        'admin': True
    })
    current_config['menu_position'] = CONFIG.get('menu_position', 'fixed')

    return {
        'providers': available_providers,
        'ecb_llm_available': ECB_LLM_AVAILABLE and CONFIG.get('ecb_llm', {}).get('enabled', False),
        'ollama_available': OLLAMA_AVAILABLE and CONFIG.get('ollama', {}).get('enabled', False),
        'gemini_available': GEMINI_AVAILABLE and CONFIG.get('gemini', {}).get('enabled', False),
        'config_defaults': current_config
    }


@app.get("/api/provider-status")
async def get_provider_status():
    """
    Get the status of all LLM providers including connectivity test.

    Returns:
        Dictionary with status for each provider:
        - enabled: Whether the provider is enabled in config
        - configured: Whether API key is set
        - status: 'connected', 'error', 'disabled', or 'not_configured'
        - latency_ms: Response time in milliseconds (if connected)
        - error: Error message (if any)
    """
    import time
    import os
    from app import CONFIG

    if not CONFIG:
        load_config()
        from app import CONFIG

    providers_status = {}

    # Check OpenAI
    openai_config = CONFIG.get('openai', {})
    openai_enabled = openai_config.get('enabled', False)
    openai_key = os.environ.get('OPENAI_API_KEY', '')

    providers_status['openai'] = {
        'name': 'OpenAI',
        'enabled': openai_enabled,
        'configured': bool(openai_key),
        'status': 'disabled' if not openai_enabled else ('not_configured' if not openai_key else 'unknown'),
        'latency_ms': None,
        'error': None,
        'models': openai_config.get('available_models', {})
    }

    if openai_enabled and openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            start_time = time.time()
            # Use a simple models list call to test connectivity
            models = client.models.list()
            latency = int((time.time() - start_time) * 1000)
            providers_status['openai']['status'] = 'connected'
            providers_status['openai']['latency_ms'] = latency
        except Exception as e:
            providers_status['openai']['status'] = 'error'
            providers_status['openai']['error'] = str(e)[:200]

    # Check Claude (Anthropic)
    claude_config = CONFIG.get('claude', {})
    claude_enabled = claude_config.get('enabled', False)
    claude_key = os.environ.get('ANTHROPIC_API_KEY', '') or os.environ.get('CLAUDE_API_KEY', '')

    providers_status['claude'] = {
        'name': 'Claude (Anthropic)',
        'enabled': claude_enabled,
        'configured': bool(claude_key),
        'status': 'disabled' if not claude_enabled else ('not_configured' if not claude_key else 'unknown'),
        'latency_ms': None,
        'error': None,
        'models': claude_config.get('available_models', {})
    }

    if claude_enabled and claude_key:
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=claude_key)
            start_time = time.time()
            # Use a minimal message to test connectivity
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            latency = int((time.time() - start_time) * 1000)
            providers_status['claude']['status'] = 'connected'
            providers_status['claude']['latency_ms'] = latency
        except Exception as e:
            providers_status['claude']['status'] = 'error'
            providers_status['claude']['error'] = str(e)[:200]

    # Check Gemini
    gemini_config = CONFIG.get('gemini', {})
    gemini_config_enabled = gemini_config.get('enabled', False)
    gemini_enabled = gemini_config_enabled and GEMINI_AVAILABLE
    gemini_key = os.environ.get('GOOGLE_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')

    # Determine Gemini status
    if not GEMINI_AVAILABLE:
        gemini_status = 'library_not_installed'
        gemini_error = 'google-generativeai package not installed'
    elif not gemini_config_enabled:
        gemini_status = 'disabled'
        gemini_error = None
    elif not gemini_key:
        gemini_status = 'not_configured'
        gemini_error = None
    else:
        gemini_status = 'unknown'
        gemini_error = None

    providers_status['gemini'] = {
        'name': 'Google Gemini',
        'enabled': gemini_enabled,
        'configured': bool(gemini_key),
        'status': gemini_status,
        'latency_ms': None,
        'error': gemini_error,
        'models': gemini_config.get('available_models', {})
    }

    if gemini_enabled and gemini_key and GEMINI_AVAILABLE and gemini_client:
        try:
            configure_gemini(gemini_key)
            start_time = time.time()
            # Test connectivity by getting a model - works with both google.genai and google.generativeai
            default_model = gemini_config.get('available_models', {}).get('vision', ['gemini-1.5-flash'])[0]
            if hasattr(gemini_client, 'GenerativeModel'):
                # google.generativeai style
                model = gemini_client.GenerativeModel(default_model)
            elif hasattr(gemini_client, 'Client'):
                # google.genai style
                client = gemini_client.Client(api_key=gemini_key)
            # If we got here without exception, connection is good
            latency = int((time.time() - start_time) * 1000)
            providers_status['gemini']['status'] = 'connected'
            providers_status['gemini']['latency_ms'] = latency
        except Exception as e:
            providers_status['gemini']['status'] = 'error'
            providers_status['gemini']['error'] = str(e)[:200]

    # Check Ollama
    ollama_config = CONFIG.get('ollama', {})
    ollama_config_enabled = ollama_config.get('enabled', False)
    ollama_enabled = ollama_config_enabled and OLLAMA_AVAILABLE
    ollama_url = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')

    # Determine Ollama status
    if not OLLAMA_AVAILABLE:
        ollama_status = 'library_not_installed'
        ollama_error = 'ollama package not installed'
    elif not ollama_config_enabled:
        ollama_status = 'disabled'
        ollama_error = None
    else:
        ollama_status = 'unknown'
        ollama_error = None

    providers_status['ollama'] = {
        'name': 'Ollama (Local)',
        'enabled': ollama_enabled,
        'configured': True,  # Ollama doesn't need API key
        'status': ollama_status,
        'latency_ms': None,
        'error': ollama_error,
        'models': ollama_config.get('available_models', {}),
        'host': ollama_url
    }

    if ollama_enabled and OLLAMA_AVAILABLE:
        try:
            import httpx
            start_time = time.time()
            # Test Ollama API endpoint
            response = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
            latency = int((time.time() - start_time) * 1000)
            if response.status_code == 200:
                providers_status['ollama']['status'] = 'connected'
                providers_status['ollama']['latency_ms'] = latency
                # Get available models
                data = response.json()
                if 'models' in data:
                    providers_status['ollama']['available_local_models'] = [m.get('name', '') for m in data['models']]
            else:
                providers_status['ollama']['status'] = 'error'
                providers_status['ollama']['error'] = f"HTTP {response.status_code}"
        except Exception as e:
            providers_status['ollama']['status'] = 'error'
            providers_status['ollama']['error'] = str(e)[:200]

    # Check ECB-LLM
    ecb_config = CONFIG.get('ecb_llm', {})
    ecb_config_enabled = ecb_config.get('enabled', False)
    ecb_enabled = ecb_config_enabled and ECB_LLM_AVAILABLE

    # Determine ECB-LLM status
    if not ECB_LLM_AVAILABLE:
        ecb_status = 'library_not_installed'
        ecb_error = 'ecb_llm_client package not installed'
    elif not ecb_config_enabled:
        ecb_status = 'disabled'
        ecb_error = None
    else:
        ecb_status = 'unknown'
        ecb_error = None

    providers_status['ecb_llm'] = {
        'name': 'ECB-LLM',
        'enabled': ecb_enabled,
        'configured': ECB_LLM_AVAILABLE,
        'status': ecb_status,
        'latency_ms': None,
        'error': ecb_error,
        'models': ecb_config.get('available_models', {})
    }

    if ecb_enabled and ECB_LLM_AVAILABLE:
        try:
            # ECB-LLM specific connectivity test would go here
            # For now, mark as connected if the library is available
            providers_status['ecb_llm']['status'] = 'available'
        except Exception as e:
            providers_status['ecb_llm']['status'] = 'error'
            providers_status['ecb_llm']['error'] = str(e)[:200]

    return {
        'providers': providers_status,
        'checked_at': time.strftime('%Y-%m-%d %H:%M:%S')
    }


@app.post("/api/generate-alt-text")
async def generate_alt_text(
    request: Request,
    response: Response,
    image: UploadFile = File(..., description="Image file to analyze"),
    language: str = Form("en", description="Language code (en, it, de, fr, etc.)"),
    context: Optional[str] = Form(None, description="Optional context about the image"),
    vision_provider: Optional[str] = Form(None, description="Vision provider (openai, claude, ecb-llm, ollama)"),
    vision_model: Optional[str] = Form(None, description="Vision model (e.g., gpt-4o, claude-3-5-sonnet-20241022, granite3.2-vision)"),
    processing_provider: Optional[str] = Form(None, description="Processing provider (openai, claude, ecb-llm, ollama)"),
    processing_model: Optional[str] = Form(None, description="Processing model (e.g., gpt-4o-mini, phi3)"),
    translation_provider: Optional[str] = Form(None, description="Translation provider (openai, claude, ecb-llm, ollama)"),
    translation_model: Optional[str] = Form(None, description="Translation model (e.g., gpt-4o-mini, phi3)"),
    use_geo_boost: bool = Form(False, description="Enable GEO (Generative Engine Optimization) boost for alt-text")
):
    """
    Generate WCAG 2.2 compliant alt-text for an image with per-step provider/model override support.

    This endpoint uses the same CLI function (generate_alt_text_json) that handles
    U2A authentication automatically via CredentialManager.

    Args:
        image: Uploaded image file
        language: Target language for alt-text (default: en)
        context: Optional context information about the image
        vision_provider: Provider for vision step (optional, uses config if not specified)
        vision_model: Model for vision step (optional, uses config if not specified)
        processing_provider: Provider for processing step (optional, uses config if not specified)
        processing_model: Model for processing step (optional, uses config if not specified)
        translation_provider: Provider for translation step (optional, uses config if not specified)
        translation_model: Model for translation step (optional, uses config if not specified)

    Returns:
        AltTextResponse: Generated alt-text and metadata

    Raises:
        HTTPException: If image processing fails
    """
    from app import generate_alt_text_json, CONFIG
    import shutil

    # Store original CONFIG.steps values to restore later (use deep copy to avoid mutation)
    original_steps = copy.deepcopy(CONFIG.get('steps', {}))

    # Apply per-step overrides if specified
    if not 'steps' in CONFIG:
        CONFIG['steps'] = {}

    # Helper function to normalize provider names from frontend to backend format
    def normalize_provider_name(provider_name):
        """Convert frontend provider names to backend format"""
        provider_map = {
            'openai': 'OpenAI',
            'claude': 'Claude',
            'ecb-llm': 'ECB-LLM',
            'ollama': 'Ollama',
            'gemini': 'Gemini'
        }
        return provider_map.get(provider_name.lower(), provider_name)

    # Vision step override
    if vision_provider:
        if 'vision' not in CONFIG['steps']:
            CONFIG['steps']['vision'] = {}
        CONFIG['steps']['vision']['provider'] = normalize_provider_name(vision_provider)
    if vision_model:
        if 'vision' not in CONFIG['steps']:
            CONFIG['steps']['vision'] = {}
        CONFIG['steps']['vision']['model'] = vision_model

    # Processing step override
    if processing_provider:
        if 'processing' not in CONFIG['steps']:
            CONFIG['steps']['processing'] = {}
        CONFIG['steps']['processing']['provider'] = normalize_provider_name(processing_provider)
    if processing_model:
        if 'processing' not in CONFIG['steps']:
            CONFIG['steps']['processing'] = {}
        CONFIG['steps']['processing']['model'] = processing_model

    # Translation step override
    if translation_provider:
        if 'translation' not in CONFIG['steps']:
            CONFIG['steps']['translation'] = {}
        CONFIG['steps']['translation']['provider'] = normalize_provider_name(translation_provider)
    if translation_model:
        if 'translation' not in CONFIG['steps']:
            CONFIG['steps']['translation'] = {}
        CONFIG['steps']['translation']['model'] = translation_model

    # Get or create session ID
    session_id = get_or_create_session_id(request)

    # Set session cookie in response
    response.set_cookie(
        key="web_session_id",
        value=session_id,
        max_age=86400,  # 24 hours
        httponly=True,
        samesite="lax"
    )

    # Create temporary directories for processing
    tmp_dir = tempfile.mkdtemp(prefix='myaccessibilitybuddy_')
    tmp_images_dir = os.path.join(tmp_dir, 'images')
    tmp_context_dir = os.path.join(tmp_dir, 'context')
    tmp_output_dir = os.path.join(tmp_dir, 'output')

    try:
        # Validate image file
        if not image.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image"
            )

        # Create temporary subdirectories
        os.makedirs(tmp_images_dir, exist_ok=True)
        os.makedirs(tmp_context_dir, exist_ok=True)
        os.makedirs(tmp_output_dir, exist_ok=True)

        # Save uploaded image with original filename
        image_filename = image.filename or 'uploaded_image.png'
        tmp_image_path = os.path.join(tmp_images_dir, image_filename)

        content = await image.read()
        with open(tmp_image_path, 'wb') as f:
            f.write(content)

        # Save context to file if provided (must match image filename base name)
        if context and context.strip():
            context_filename = os.path.splitext(image_filename)[0] + '.txt'
            tmp_context_path = os.path.join(tmp_context_dir, context_filename)
            with open(tmp_context_path, 'w', encoding='utf-8') as f:
                f.write(context.strip())

        # Call the same function used by CLI with -g flag
        # This handles U2A authentication via CredentialManager automatically
        # Returns: (json_path, success) tuple
        json_path, success = generate_alt_text_json(
            image_filename=image_filename,
            images_folder=tmp_images_dir,
            context_folder=tmp_context_dir,
            alt_text_folder=tmp_output_dir,
            languages=[language],
            use_geo_boost=use_geo_boost
        )

        if not success or not json_path:
            # Try to get more detailed error information
            error_detail = "Failed to generate alt-text"
            if vision_provider == 'claude' or vision_provider == 'Claude':
                error_detail += ". Check that ANTHROPIC_API_KEY is set correctly."

            # Try to read the JSON file to get specific error information
            if json_path and os.path.exists(json_path):
                try:
                    import json
                    with open(json_path, 'r', encoding='utf-8') as f:
                        error_result = json.load(f)

                    # Check if it's a generation error with reasoning that might indicate quota issues
                    if error_result.get('image_type') == 'generation_error':
                        reasoning = error_result.get('reasoning', '')

                        # Detect quota or rate limit errors
                        if 'quota' in reasoning.lower() or 'insufficient_quota' in reasoning.lower():
                            error_detail = f"API Quota Exceeded: Your {vision_provider} API has run out of credits. Please add credits to your account or switch to a different provider."
                        elif 'rate limit' in reasoning.lower() or 'rate_limit' in reasoning.lower():
                            error_detail = f"API Rate Limit: Your {vision_provider} API rate limit has been exceeded. Please wait a moment and try again, or switch to a different provider."
                        elif reasoning:
                            error_detail = f"Generation Error: {reasoning}"
                except Exception:
                    pass  # If we can't read the error details, use the generic message

            raise HTTPException(
                status_code=500,
                detail=error_detail
            )

        # Read the generated JSON file
        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            result = json.load(f)

        # Extract alt-text for the requested language
        proposed_alt_text = result.get('proposed_alt_text', '')

        # Handle both single language (string) and multilingual (list of tuples) formats
        def extract_lang_value(entries, target_lang):
            """Helper to safely extract values from multilingual structures."""
            if not isinstance(entries, list):
                return ""
            target = str(target_lang).upper()
            fallback = ""
            for entry in entries:
                lang_code = None
                text_val = None
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    lang_code, text_val = entry[0], entry[1]
                elif isinstance(entry, dict):
                    lang_code = entry.get('language') or entry.get('lang') or entry.get('code')
                    text_val = entry.get('text') or entry.get('value')
                elif isinstance(entry, str):
                    parts = entry.split(':', 1)
                    if len(parts) == 2:
                        lang_code, text_val = parts[0], parts[1]
                if lang_code and text_val:
                    if str(lang_code).upper() == target:
                        return str(text_val)
                    if not fallback:
                        fallback = str(text_val)
            return fallback

        if isinstance(proposed_alt_text, list):
            alt_text_str = extract_lang_value(proposed_alt_text, language)
        else:
            alt_text_str = proposed_alt_text

        # Extract reasoning (handle multilingual format)
        reasoning_value = result.get('reasoning', '')
        if isinstance(reasoning_value, list) and reasoning_value:
            reasoning_str = extract_lang_value(reasoning_value, language)
        else:
            reasoning_str = reasoning_value

        # Calculate character count
        char_count = len(alt_text_str) if alt_text_str else 0

        # Get image_id from result
        image_id = result.get('image_id', image_filename)

        # Get session-specific folders
        session_folders = get_session_folders(session_id)

        # Copy JSON to session-specific output folder
        permanent_output_dir = session_folders['alt_text']

        # Generate permanent filename based on image_id and language
        image_name_without_ext = os.path.splitext(image_id)[0]
        permanent_json_filename = f"{image_name_without_ext}_{language}.json"
        permanent_json_path = os.path.join(permanent_output_dir, permanent_json_filename)

        # Copy the JSON file to session folder
        shutil.copy2(json_path, permanent_json_path)

        # Copy the image to session-specific images folder for report generation
        permanent_images_dir = session_folders['images']
        permanent_image_path = os.path.join(permanent_images_dir, image_id)

        # Always copy to ensure we have the latest version
        # (different images may have the same filename)
        shutil.copy2(tmp_image_path, permanent_image_path)

        return AltTextResponse(
            success=True,
            alt_text=alt_text_str,
            image_type=result.get('image_type', 'informative'),
            reasoning=reasoning_str,
            character_count=char_count,
            language=language,
            image_id=image_id,
            json_file_path=permanent_json_path,
            error=None
        )

    except HTTPException:
        raise
    except Exception as e:
        # Check if this is a known API error
        error_message = str(e)

        # Detect quota errors from API exceptions
        if 'quota' in error_message.lower() or 'insufficient_quota' in error_message.lower():
            error_message = f"API Quota Exceeded: Your API provider has run out of credits. Please add credits to your account or switch to a different provider in Advanced Processing Mode."
        elif 'rate limit' in error_message.lower() or 'rate_limit' in error_message.lower():
            error_message = f"API Rate Limit Exceeded: Too many requests. Please wait a moment and try again, or switch to a different provider."
        elif 'authentication' in error_message.lower() or 'api key' in error_message.lower() or 'unauthorized' in error_message.lower():
            error_message = f"API Authentication Error: {error_message}. Please verify your API keys are configured correctly."

        return AltTextResponse(
            success=False,
            alt_text="",
            image_type="generation_error",
            reasoning=None,
            character_count=0,
            language=language,
            error=error_message
        )
    finally:
        # Restore original CONFIG.steps settings
        CONFIG['steps'] = original_steps

        # Clean up temporary directory and all its contents
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


@app.post("/api/save-reviewed-alt-text", response_model=SaveReviewedAltTextResponse)
async def save_reviewed_alt_text(fastapi_request: Request, request: SaveReviewedAltTextRequest):
    """
    Save human-reviewed alt text to the JSON file.

    Args:
        fastapi_request: FastAPI Request object
        request: SaveReviewedAltTextRequest containing image_id, reviewed_alt_text, and language

    Returns:
        SaveReviewedAltTextResponse: Success status and file path

    Raises:
        HTTPException: If file not found or save fails
    """
    import json

    try:
        # Get session ID from cookie
        session_id = fastapi_request.cookies.get("web_session_id")

        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="No active session found. Please upload images first."
            )

        # Validate session exists (check folder instead of in-memory dict for persistence)
        base_images = get_absolute_folder_path('images')
        session_image_folder = os.path.join(base_images, session_id)
        if not os.path.exists(session_image_folder):
            raise HTTPException(
                status_code=400,
                detail="Session not found or expired. Please upload images first."
            )

        # Restore session to in-memory dict if missing (after container restart)
        if session_id not in WEB_APP_SESSIONS:
            from datetime import datetime
            WEB_APP_SESSIONS[session_id] = {
                "created": datetime.now(),
                "last_accessed": datetime.now(),
                "type": "web"
            }

        # Get session-specific folders
        session_folders = get_session_folders(session_id)
        permanent_output_dir = session_folders['alt_text']

        # Generate filename based on image_id and language
        image_name_without_ext = os.path.splitext(request.image_id)[0]
        json_filename = f"{image_name_without_ext}_{request.language}.json"
        json_file_path = os.path.join(permanent_output_dir, json_filename)

        # Check if file exists
        if not os.path.exists(json_file_path):
            raise HTTPException(
                status_code=404,
                detail=f"JSON file not found for image_id: {request.image_id}"
            )

        # Read existing JSON
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        # Calculate length if not provided
        reviewed_length = request.reviewed_alt_text_length
        if reviewed_length is None:
            reviewed_length = len(request.reviewed_alt_text)

        # Add or update the human_reviewed_alt_text field
        # Handle both single language and multilingual formats
        if isinstance(json_data.get('proposed_alt_text'), list):
            # Multilingual format
            if 'human_reviewed_alt_text' not in json_data:
                json_data['human_reviewed_alt_text'] = []
            if 'human_reviewed_alt_text_length' not in json_data:
                json_data['human_reviewed_alt_text_length'] = []

            # Update or add the reviewed text for this language
            existing_entry = None
            for i, (lang_code, _) in enumerate(json_data['human_reviewed_alt_text']):
                if lang_code.upper() == request.language.upper():
                    existing_entry = i
                    break

            if existing_entry is not None:
                json_data['human_reviewed_alt_text'][existing_entry] = (request.language, request.reviewed_alt_text)
                json_data['human_reviewed_alt_text_length'][existing_entry] = (request.language, reviewed_length)
            else:
                json_data['human_reviewed_alt_text'].append((request.language, request.reviewed_alt_text))
                json_data['human_reviewed_alt_text_length'].append((request.language, reviewed_length))
        else:
            # Single language format
            json_data['human_reviewed_alt_text'] = request.reviewed_alt_text
            json_data['human_reviewed_alt_text_length'] = reviewed_length

        # Add reviewed timestamp
        from datetime import datetime
        json_data['reviewed_timestamp'] = datetime.now().isoformat()

        # Reorganize JSON field order
        # Move human_reviewed fields right after proposed_alt_text and move ai_model after language
        ordered_data = {}
        for key in json_data.keys():
            if key not in ['human_reviewed_alt_text', 'human_reviewed_alt_text_length', 'reviewed_timestamp', 'ai_model']:
                ordered_data[key] = json_data[key]
                # Insert human_reviewed fields after proposed_alt_text_length
                if key == 'proposed_alt_text_length':
                    if 'human_reviewed_alt_text' in json_data:
                        ordered_data['human_reviewed_alt_text'] = json_data['human_reviewed_alt_text']
                    if 'human_reviewed_alt_text_length' in json_data:
                        ordered_data['human_reviewed_alt_text_length'] = json_data['human_reviewed_alt_text_length']
                    if 'reviewed_timestamp' in json_data:
                        ordered_data['reviewed_timestamp'] = json_data['reviewed_timestamp']
                # Insert ai_model after language
                elif key == 'language':
                    if 'ai_model' in json_data:
                        ordered_data['ai_model'] = json_data['ai_model']

        # Save updated JSON with ordered fields
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(ordered_data, f, indent=2, ensure_ascii=False)

        return SaveReviewedAltTextResponse(
            success=True,
            message="Human-reviewed alt text saved successfully",
            json_file_path=json_file_path,
            error=None
        )

    except HTTPException:
        raise
    except Exception as e:
        return SaveReviewedAltTextResponse(
            success=False,
            message="Failed to save reviewed alt text",
            json_file_path=None,
            error=str(e)
        )


@app.post("/api/generate-report")
async def generate_report_endpoint(request: Request, clear_after: bool = True, return_path: bool = False):
    """
    Generate HTML report for content creator tool.

    Args:
        request: FastAPI Request object
        clear_after: If True, clears session data after generating report
        return_path: If True, returns JSON with report path instead of file download

    Returns:
        FileResponse: HTML report file for download (if return_path=False)
        JSON: Report path and metadata (if return_path=True)

    Raises:
        HTTPException: If report generation fails or no images to report
    """
    from app import generate_html_report, CONFIG
    from datetime import datetime
    from fastapi.responses import FileResponse
    import os

    try:
        # Get session ID from cookie
        session_id = request.cookies.get("web_session_id")

        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="No active session found. Please upload images first."
            )

        # Validate session exists (check folder instead of in-memory dict for persistence)
        base_images = get_absolute_folder_path('images')
        session_image_folder = os.path.join(base_images, session_id)
        if not os.path.exists(session_image_folder):
            raise HTTPException(
                status_code=400,
                detail="Session not found or expired. Please upload images first."
            )

        # Restore session to in-memory dict if missing (after container restart)
        if session_id not in WEB_APP_SESSIONS:
            from datetime import datetime
            WEB_APP_SESSIONS[session_id] = {
                "created": datetime.now(),
                "last_accessed": datetime.now(),
                "type": "web"
            }

        # Get session-specific folders
        session_folders = get_session_folders(session_id)

        # Generate timestamp for filename (match other report formats: date first, then type)
        timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        output_filename = f"{timestamp}-content-creator-report.html"

        # Use session-specific alt-text folder
        alt_text_folder = session_folders['alt_text']

        # Temporarily override config for web app reports
        # Disable tag/attribute display (not relevant for web uploads)
        original_config = copy.deepcopy(CONFIG.get('html_report_display', {}))
        if 'html_report_display' not in CONFIG:
            CONFIG['html_report_display'] = {}

        CONFIG['html_report_display']['display_html_tags_used'] = False
        CONFIG['html_report_display']['display_html_attributes_used'] = False
        CONFIG['html_report_display']['display_current_alt_text'] = False
        CONFIG['html_report_display']['display_image_tag_attribute'] = False

        try:
            # Generate report with session-specific images folder
            report_path = generate_html_report(
                alt_text_folder=alt_text_folder,
                images_folder=session_folders['images'],
                output_filename=output_filename
            )

            if not report_path:
                raise HTTPException(
                    status_code=500,
                    detail="Report generation failed - no images found or internal error"
                )

            # Check if file exists
            if not os.path.exists(report_path):
                raise HTTPException(
                    status_code=500,
                    detail="Report file was not created"
                )

            # Clear session data if requested (AFTER successful report generation)
            if clear_after:
                import shutil
                # Clear both JSON files and images from session folders
                try:
                    if os.path.exists(session_folders['alt_text']):
                        shutil.rmtree(session_folders['alt_text'])
                    if os.path.exists(session_folders['images']):
                        shutil.rmtree(session_folders['images'])
                    # Remove session from tracking
                    if session_id in WEB_APP_SESSIONS:
                        del WEB_APP_SESSIONS[session_id]
                    print(f"Cleared session {session_id} data")
                except Exception as e:
                    # Log but don't fail - clearing is optional cleanup
                    print(f"Warning: Could not clear session data: {e}")

            # Return JSON with path or file for download
            if return_path:
                return {
                    "success": True,
                    "report_path": report_path,
                    "filename": os.path.basename(report_path),
                    "message": "Report generated successfully"
                }
            else:
                return FileResponse(
                    path=report_path,
                    media_type='text/html',
                    filename=os.path.basename(report_path),
                    headers={
                        "Content-Disposition": f'attachment; filename="{os.path.basename(report_path)}"'
                    }
                )

        finally:
            # Restore original config
            CONFIG['html_report_display'] = original_config

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating report: {str(e)}"
        )


@app.get("/api/languages")
async def get_supported_languages():
    """
    Get list of supported languages.

    Returns:
        List of supported language codes and names
    """
    from config import settings

    languages_config = settings.get("languages", {})
    allowed_languages = languages_config.get("allowed", [])
    default_language = languages_config.get("default", "en")

    return {
        "supported_languages": allowed_languages,
        "default_language": default_language
    }


@app.get("/api/test/env-check")
async def test_env_check():
    """
    Test endpoint to check if environment variables are properly loaded.
    SECURITY WARNING: This endpoint exposes partial API key info - use only for testing!
    Should be removed or secured in production.

    Returns:
        Dictionary with environment variable status
    """
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    client_id = os.environ.get('CLIENT_ID_U2A', '')
    client_secret = os.environ.get('CLIENT_SECRET_U2A', '')

    # Function to safely mask sensitive values
    def mask_value(value):
        if not value:
            return None
        if len(value) <= 8:
            return "***"
        return f"{value[:4]}...{value[-4:]}"

    return {
        "environment": "ECS" if os.environ.get('ECS_CONTAINER_METADATA_URI') else "local/docker",
        "ecs_metadata_available": bool(os.environ.get('ECS_CONTAINER_METADATA_URI')),
        "openai_api_key_present": bool(openai_key),
        "openai_api_key_masked": mask_value(openai_key),
        "openai_api_key_length": len(openai_key) if openai_key else 0,
        "client_id_u2a_present": bool(client_id),
        "client_id_u2a_masked": mask_value(client_id),
        "client_secret_u2a_present": bool(client_secret),
        "client_secret_u2a_masked": mask_value(client_secret),
        "dotenv_loaded": "dotenv" in str(type(load_dotenv)) if 'load_dotenv' in dir() else False,
        "warning": "This endpoint exposes partial credential info - disable in production!"
    }


@app.post("/api/check-url")
async def check_url(request: Request):
    """
    Check if a URL is reachable.

    Request body:
    {
        "url": "https://example.com"
    }

    Returns:
    {
        "reachable": true/false,
        "status_code": 200,
        "error": "error message if not reachable"
    }
    """
    try:
        import requests
        from requests.exceptions import RequestException, Timeout, ConnectionError

        data = await request.json()
        url = data.get('url')

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        # Validate URL format
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception:
            return {
                "reachable": False,
                "error": "Invalid URL format"
            }

        # Try to reach the URL with a HEAD request first (faster)
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code < 400:
                log_message(f"URL reachable: {url} (status: {response.status_code})", "INFORMATION")
                return {
                    "reachable": True,
                    "status_code": response.status_code
                }
            else:
                # If HEAD fails, try GET (some servers don't support HEAD)
                response = requests.get(url, timeout=10, allow_redirects=True, stream=True)
                response.close()  # Close immediately, we just want to check reachability

                if response.status_code < 400:
                    log_message(f"URL reachable: {url} (status: {response.status_code})", "INFORMATION")
                    return {
                        "reachable": True,
                        "status_code": response.status_code
                    }
                else:
                    log_message(f"URL not reachable: {url} (status: {response.status_code})", "WARNING")
                    return {
                        "reachable": False,
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}"
                    }
        except Timeout:
            log_message(f"URL timeout: {url}", "WARNING")
            return {
                "reachable": False,
                "error": "Connection timeout - the server took too long to respond"
            }
        except ConnectionError:
            log_message(f"URL connection error: {url}", "WARNING")
            return {
                "reachable": False,
                "error": "Connection failed - unable to reach the server"
            }
        except RequestException as e:
            log_message(f"URL request error: {url} - {str(e)}", "WARNING")
            return {
                "reachable": False,
                "error": str(e)
            }

    except HTTPException:
        raise
    except Exception as e:
        log_message(f"Check URL error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clear-session")
async def clear_session(request: Request):
    """
    Clear session data (images, context, alt-text, reports) for a specific session.

    If session_id is not provided in the request body, the web_session_id cookie is used.
    Supports both web- and cli- sessions.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    session_id = body.get("session_id") if isinstance(body, dict) else None

    if not session_id:
        session_id = request.cookies.get("web_session_id")

    if not session_id:
        return {
            "success": True,
            "message": "No active session to clear",
            "files_deleted": 0,
            "folders_deleted": 0
        }

    result = clear_session_data(session_id)
    log_message(f"Cleared session data for {session_id}", "INFORMATION")
    return result


@app.post("/api/clear-all-sessions")
async def clear_all_sessions(request: Request):
    """
    Clear ALL session data from images, context, alt-text, reports, and logs folders.

    This is a destructive operation that requires the 'force' flag to be set.

    Request body:
    {
        "force": true  # Required - must be true to confirm deletion
    }

    Returns:
    {
        "success": true,
        "message": "All session data cleared",
        "sessions_cleared": 5,
        "files_deleted": 123,
        "folders_deleted": 25
    }
    """
    import shutil

    try:
        body = await request.json()
    except Exception:
        body = {}

    force = body.get("force", False) if isinstance(body, dict) else False

    if not force:
        raise HTTPException(
            status_code=400,
            detail="This operation requires 'force: true' to confirm deletion of all session data"
        )

    sessions_cleared = 0
    files_deleted = 0
    folders_deleted = 0
    errors = []

    try:
        base_images = get_absolute_folder_path('images')
        base_context = get_absolute_folder_path('context')
        base_alt_text = get_absolute_folder_path('alt_text')
        base_reports = get_absolute_folder_path('reports')
        base_logs = get_absolute_folder_path('logs')

        base_folders = {
            "images": base_images,
            "context": base_context,
            "alt_text": base_alt_text,
            "reports": base_reports,
            "logs": base_logs
        }

        # Track unique session IDs found
        session_ids_found = set()

        for folder_type, base_path in base_folders.items():
            if not os.path.exists(base_path):
                continue

            try:
                for item in os.listdir(base_path):
                    item_path = os.path.join(base_path, item)

                    # Only delete session folders (timestamp-uuid format: YYYY-MM-DDTHH-MM-SS-uuid)
                    # Also support legacy web- or cli- prefixed folders for backward compatibility
                    is_session_folder = (
                        item.startswith('web-') or
                        item.startswith('cli-') or
                        # Match format: YYYY-MM-DDTHH-MM-SS-uuid (e.g., 2026-01-27T00-32-19-4b6cfab2...)
                        (len(item) > 20 and item[4] == '-' and item[7] == '-' and item[10] == 'T' and item[0:4].isdigit())
                    )
                    if os.path.isdir(item_path) and is_session_folder:
                        session_ids_found.add(item)

                        try:
                            # Count files before deletion
                            for root, dirs, files in os.walk(item_path):
                                files_deleted += len(files)

                            # Remove the entire folder
                            shutil.rmtree(item_path)
                            folders_deleted += 1
                            log_message(f"Cleared {folder_type}/{item}", "INFORMATION")
                        except Exception as e:
                            errors.append(f"Failed to clear {folder_type}/{item}: {str(e)}")
                            log_message(f"Failed to clear {folder_type}/{item}: {e}", "WARNING")

            except Exception as e:
                errors.append(f"Error scanning {folder_type}: {str(e)}")
                log_message(f"Error scanning {folder_type}: {e}", "WARNING")

        sessions_cleared = len(session_ids_found)

        # Clear in-memory session tracking
        WEB_APP_SESSIONS.clear()

        log_message(f"Cleared all session data: {sessions_cleared} sessions, {files_deleted} files, {folders_deleted} folders", "INFORMATION")

        return {
            "success": True,
            "message": f"All session data cleared successfully",
            "sessions_cleared": sessions_cleared,
            "files_deleted": files_deleted,
            "folders_deleted": folders_deleted,
            "errors": errors if errors else None
        }

    except HTTPException:
        raise
    except Exception as e:
        log_message(f"Clear all sessions error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/folder-contents")
async def get_folder_contents():
    """
    Get contents of input, output, and logs folders for admin view.

    Returns:
    {
        "input": {
            "images": [{"name": "web-xxx", "type": "folder", "files": 5}, ...],
            "context": [...]
        },
        "output": {
            "alt_text": [...],
            "reports": [...]
        },
        "logs": [...]
    }
    """
    import os
    from datetime import datetime

    def get_folder_info(base_path, folder_name):
        """Get list of items in a folder with metadata."""
        folder_path = os.path.join(base_path, folder_name) if folder_name else base_path
        items = []

        if not os.path.exists(folder_path):
            return items

        try:
            for item in sorted(os.listdir(folder_path)):
                # Skip hidden files (starting with .) and report_templates folder
                if item.startswith('.') or item == 'report_templates':
                    continue

                item_path = os.path.join(folder_path, item)
                try:
                    stat_info = os.stat(item_path)
                    modified_time = datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

                    if os.path.isdir(item_path):
                        # Count files in directory
                        file_count = sum(len(files) for _, _, files in os.walk(item_path))
                        items.append({
                            "name": item,
                            "type": "folder",
                            "files": file_count,
                            "modified": modified_time
                        })
                    else:
                        # Get file size
                        size_bytes = stat_info.st_size
                        if size_bytes < 1024:
                            size_str = f"{size_bytes} B"
                        elif size_bytes < 1024 * 1024:
                            size_str = f"{size_bytes / 1024:.1f} KB"
                        else:
                            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

                        items.append({
                            "name": item,
                            "type": "file",
                            "size": size_str,
                            "modified": modified_time
                        })
                except Exception:
                    # Skip items we can't stat
                    pass
        except Exception as e:
            log_message(f"Error reading folder {folder_path}: {e}", "WARNING")

        return items

    try:
        base_images = get_absolute_folder_path('images')
        base_context = get_absolute_folder_path('context')
        base_alt_text = get_absolute_folder_path('alt_text')
        base_reports = get_absolute_folder_path('reports')
        base_logs = get_absolute_folder_path('logs')

        return {
            "input": {
                "images": get_folder_info(base_images, None),
                "context": get_folder_info(base_context, None)
            },
            "output": {
                "alt_text": get_folder_info(base_alt_text, None),
                "reports": get_folder_info(base_reports, None)
            },
            "logs": get_folder_info(base_logs, None)
        }
    except Exception as e:
        log_message(f"Get folder contents error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-page")
async def analyze_page(request: Request):
    """
    Analyze a web page for accessibility compliance.

    This endpoint executes: app.py -w --url <URL> --num-images <N> --language <langs> --report
    with optional advanced options for provider/model selection.

    Request body:
    {
        "url": "https://example.com/page",
        "languages": ["en", "it"],  # optional, defaults to ["en"]
        "num_images": 10,  # optional, if omitted processes all images
        "vision_provider": "openai",  # optional
        "vision_model": "gpt-4-vision-preview",  # optional
        "processing_provider": "openai",  # optional
        "processing_model": "gpt-4",  # optional
        "translation_provider": "openai",  # optional
        "translation_model": "gpt-4",  # optional
        "advanced_translation": true,  # optional, defaults to false
        "geo_boost": true  # optional, defaults to false
    }

    Returns:
    {
        "success": true,
        "url": "https://example.com/page",
        "report_path": "output/reports/web-xxx/report.html",
        "summary": {
            "total_images": 15,
            "missing_alt": 5,
            "has_alt": 10
        }
    }
    """
    try:
        data = await request.json()
        url = data.get('url')
        languages = data.get('languages', ['en'])
        num_images = data.get('num_images')  # Can be None for all images
        session_id_override = data.get('session')

        # Debug logging for num_images
        log_message(f"[DEBUG] Received num_images from request: {num_images} (type: {type(num_images).__name__})", "INFORMATION")

        # Advanced options
        vision_provider = data.get('vision_provider')
        vision_model = data.get('vision_model')
        processing_provider = data.get('processing_provider')
        processing_model = data.get('processing_model')
        translation_provider = data.get('translation_provider')
        translation_model = data.get('translation_model')
        advanced_translation = data.get('advanced_translation', False)
        geo_boost = data.get('geo_boost', False)

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        # Validate URL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")

        # Build command line arguments
        cmd_args = ['-w', '--url', url, '--report']

        # Add languages - use single --language flag with multiple values (argparse nargs='+')
        if languages and isinstance(languages, list):
            cmd_args.append('--language')
            cmd_args.extend(languages)

        # Add num_images if specified
        if num_images is not None:
            try:
                num_images_int = int(num_images)
                if num_images_int < 1:
                    raise ValueError("num_images must be at least 1")
                cmd_args.extend(['--num-images', str(num_images_int)])
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid num_images: {str(e)}")

        # Add explicit session if provided (keeps CLI/web runs in a known session)
        if session_id_override:
            cmd_args.extend(['--session', session_id_override])

        # Add advanced options
        if vision_provider:
            cmd_args.extend(['--vision-provider', vision_provider])
        if vision_model:
            cmd_args.extend(['--vision-model', vision_model])
        if processing_provider:
            cmd_args.extend(['--processing-provider', processing_provider])
        if processing_model:
            cmd_args.extend(['--processing-model', processing_model])
        if translation_provider:
            cmd_args.extend(['--translation-provider', translation_provider])
        if translation_model:
            cmd_args.extend(['--translation-model', translation_model])
        if advanced_translation:
            cmd_args.append('--advanced-translation')
        if geo_boost:
            cmd_args.append('--geo-boost')

        # Execute the CLI command
        import subprocess
        import sys
        from pathlib import Path

        # Get the app.py path
        app_py_path = Path(__file__).parent / 'app.py'

        # Run the command
        cmd = [sys.executable, str(app_py_path)] + cmd_args

        log_message(f"Executing: {' '.join(cmd)}", "INFORMATION")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        error_msg = None
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            log_message(f"CLI execution failed: {error_msg}", "ERROR")

        # Parse output to find session info, report path, and summary stats
        output = result.stdout
        if result.stderr:
            output = f"{output}\n{result.stderr}"
        report_path = None
        session_id = None
        alt_text_folder = None

        import re
        import json

        # Look for report path, session ID, and output folder hints in CLI output
        for line in output.split('\n'):
            lower_line = line.lower()

            if not report_path and 'report' in lower_line and '.html' in lower_line:
                # Try to match the full path including session folder
                match = re.search(r'(output/reports/[^/\s]+/[^\s]+\.html)', line)
                if not match:
                    # Fallback to simpler pattern
                    match = re.search(r'([^\s]*output/reports[^\s]*\.html)', line)
                if match:
                    candidate_path = match.group(1).strip()
                    if 'report_template.html' not in candidate_path:
                        report_path = candidate_path

            if not session_id:
                session_match = re.search(r'Using session:\s*([^\s]+)', line)
                if session_match:
                    session_id = session_match.group(1).strip()

            if not alt_text_folder and 'output folder' in lower_line:
                folder_match = re.search(r'Output folder:\s*([^\s]+)', line, flags=re.IGNORECASE)
                if folder_match:
                    alt_text_folder = folder_match.group(1).strip()

        if report_path and 'report_template.html' in report_path:
            report_path = None

        # Derive alt-text folder from session when not explicitly printed
        base_alt_text = Path(get_absolute_folder_path('alt_text'))
        if not alt_text_folder and session_id:
            candidate = base_alt_text / session_id
            if candidate.exists():
                alt_text_folder = str(candidate)

        # Fallback to the most recent session folder if nothing was detected
        if not alt_text_folder:
            session_folders = [p for p in base_alt_text.glob('cli-*') if p.is_dir()]
            session_folders = sorted(session_folders, key=lambda p: p.stat().st_mtime, reverse=True)
            if session_folders:
                alt_text_folder = str(session_folders[0])

        total_images = 0
        missing_alt = 0
        has_alt = 0

        # If we have an alt-text folder, count JSON files and missing alt text values
        if alt_text_folder:
            alt_text_path = Path(alt_text_folder)
            json_files = list(alt_text_path.glob('*.json'))
            total_images = len(json_files)

            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    current_alt = (data.get('current_alt_text') or '').strip()
                    if current_alt:
                        has_alt += 1
                    else:
                        missing_alt += 1
                except Exception:
                    # Skip unreadable files but continue counting others
                    continue

        # If no JSON files were found, try to recover counts from CLI output
        if total_images == 0:
            for line in output.split('\n'):
                lower_line = line.lower()
                numbers = re.findall(r'(\d+)', line)
                last_number = int(numbers[-1]) if numbers else None

                if 'images downloaded' in lower_line or 'image sources' in lower_line:
                    if last_number is not None:
                        total_images = last_number
                elif 'json files generated' in lower_line:
                    if last_number is not None:
                        total_images = last_number
                elif 'missing alt' in lower_line:
                    if last_number is not None:
                        missing_alt = last_number

        # If no JSON files, try to parse the HTML report to count images
        if total_images == 0:
            # Find the report first
            temp_report_path = None
            if session_id:
                reports_base = Path(get_absolute_folder_path('reports'))
                candidate_folder = reports_base / session_id
                if candidate_folder.exists():
                    candidates = list(candidate_folder.glob('*.html'))
                    candidates = [c for c in candidates if c.name != 'report_template.html']
                    if candidates:
                        candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
                        temp_report_path = candidates[0]

            if temp_report_path and temp_report_path.exists():
                try:
                    from bs4 import BeautifulSoup
                    with open(temp_report_path, 'r', encoding='utf-8') as f:
                        soup = BeautifulSoup(f.read(), 'html.parser')

                    # Find the summary section and look for "Total Images Analyzed"
                    summary = soup.find('section', class_='summary')
                    if summary:
                        for p in summary.find_all('p'):
                            if 'Total Images Analyzed' in p.get_text():
                                match = re.search(r'(\d+)', p.get_text())
                                if match:
                                    total_images = int(match.group(1))
                                    break

                    # Count image cards in the report if still 0
                    if total_images == 0:
                        image_cards = soup.find_all('div', class_='image-card')
                        total_images = len(image_cards)

                    log_message(f"Parsed HTML report: found {total_images} images", "INFORMATION")
                except Exception as e:
                    log_message(f"Failed to parse HTML report for image count: {e}", "WARNING")

        # Align counts
        has_alt = max(has_alt, 0)
        if total_images:
            has_alt = max(has_alt, total_images - missing_alt)

        # If report path wasn't in stdout, try to locate it using the session folder
        if not report_path:
            reports_base = Path(get_absolute_folder_path('reports'))
            candidate_folder = reports_base / session_id if session_id else reports_base
            if candidate_folder.exists():
                # Prefer the standard generated report name if present
                candidates = list(candidate_folder.glob('*.html'))
                candidates = [c for c in candidates if c.name != 'report_template.html']
                if candidates:
                    # Use the most recently modified report
                    candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
                    report_path = str(candidates[0])

        # Normalize report path to a project-relative string when possible
        if report_path:
            project_root = Path(__file__).parent.parent
            try:
                # Resolve relative paths against project root instead of CWD
                report_path_obj = Path(report_path)
                if not report_path_obj.is_absolute():
                    report_path_obj = (project_root / report_path_obj).resolve()
                else:
                    report_path_obj = report_path_obj.resolve()
                report_path = str(report_path_obj.relative_to(project_root))
                # Ensure forward slashes for cross-platform compatibility
                report_path = report_path.replace('\\', '/')
            except Exception as e:
                # If we can't make it relative, try to extract just the output/... part
                log_message(f"Could not make path relative: {e}", "WARNING")
                report_path_str = str(report_path)
                # Try to find 'output/' in the path and use everything from there
                if 'output' in report_path_str:
                    idx = report_path_str.find('output')
                    report_path = report_path_str[idx:]
                    report_path = report_path.replace('\\', '/')
                else:
                    report_path = report_path_str.replace('\\', '/')

        if error_msg and not report_path:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {error_msg}")

        if error_msg:
            log_message("CLI reported errors but a report was generated; returning report path anyway.", "WARNING")

        return {
            "success": True,
            "url": url,
            "report_path": report_path,
            "summary": {
                "total_images": total_images,
                "missing_alt": missing_alt,
                "has_alt": has_alt
            },
            "output": output,
            "warning": error_msg
        }

    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        log_message("Analysis timeout", "ERROR")
        raise HTTPException(status_code=504, detail="Analysis timed out after 5 minutes")
    except Exception as e:
        log_message(f"Analyze page error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-page-async")
async def analyze_page_async(request: Request):
    """
    Start async web page analysis and return a job_id for polling progress.

    This endpoint starts the analysis in a background thread and returns immediately
    with a job_id that can be used to poll for progress via /api/job-status/{job_id}.

    Request body: Same as /api/analyze-page

    Returns:
    {
        "job_id": "job-abc123",
        "status": "started",
        "message": "Analysis started"
    }
    """
    import threading

    try:
        data = await request.json()
        url = data.get('url')

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        # Generate unique job ID
        job_id = f"job-{uuid.uuid4().hex[:12]}"

        # Initialize job status
        JOB_STATUS[job_id] = {
            "status": "starting",
            "percent": 0,
            "message": "Initializing analysis...",
            "url": url,
            "created": datetime.now().isoformat(),
            "result": None,
            "error": None
        }

        # Start background thread to run analysis
        def run_analysis():
            try:
                _run_analysis_with_progress(job_id, data)
            except Exception as e:
                JOB_STATUS[job_id]["status"] = "error"
                JOB_STATUS[job_id]["error"] = str(e)
                JOB_STATUS[job_id]["message"] = f"Error: {str(e)}"
                log_message(f"Background analysis error for job {job_id}: {e}", "ERROR")

        thread = threading.Thread(target=run_analysis, daemon=True)
        thread.start()

        return {
            "job_id": job_id,
            "status": "started",
            "message": "Analysis started"
        }

    except HTTPException:
        raise
    except Exception as e:
        log_message(f"Analyze page async error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


def _run_analysis_with_progress(job_id: str, data: dict):
    """
    Run the analysis CLI and update job status with progress.

    This function reads progress from a temporary progress file that the CLI writes to.
    """
    import subprocess
    import sys
    import json
    import re
    import time
    import threading

    url = data.get('url')
    languages = data.get('languages', ['en'])
    num_images = data.get('num_images')
    session_id_override = data.get('session')

    # Advanced options
    vision_provider = data.get('vision_provider')
    vision_model = data.get('vision_model')
    processing_provider = data.get('processing_provider')
    processing_model = data.get('processing_model')
    translation_provider = data.get('translation_provider')
    translation_model = data.get('translation_model')
    advanced_translation = data.get('advanced_translation', False)
    geo_boost = data.get('geo_boost', False)

    # Update status
    JOB_STATUS[job_id]["status"] = "running"
    JOB_STATUS[job_id]["percent"] = 5
    JOB_STATUS[job_id]["message"] = "Validating URL..."

    # Validate URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
    except Exception as e:
        JOB_STATUS[job_id]["status"] = "error"
        JOB_STATUS[job_id]["error"] = f"Invalid URL: {str(e)}"
        return

    # Build command line arguments
    cmd_args = ['-w', '--url', url, '--report']

    # Create progress file for CLI to write to
    progress_file = Path(tempfile.gettempdir()) / f"{job_id}-progress.json"

    # Add progress file argument
    cmd_args.extend(['--progress-file', str(progress_file)])

    # Add languages - use single --language flag with multiple values (argparse nargs='+')
    if languages and isinstance(languages, list):
        cmd_args.append('--language')
        cmd_args.extend(languages)

    # Add num_images if specified
    if num_images is not None:
        try:
            num_images_int = int(num_images)
            if num_images_int >= 1:
                cmd_args.extend(['--num-images', str(num_images_int)])
        except ValueError:
            pass

    # Add session if provided
    if session_id_override:
        cmd_args.extend(['--session', session_id_override])

    # Add advanced options
    if vision_provider:
        cmd_args.extend(['--vision-provider', vision_provider])
    if vision_model:
        cmd_args.extend(['--vision-model', vision_model])
    if processing_provider:
        cmd_args.extend(['--processing-provider', processing_provider])
    if processing_model:
        cmd_args.extend(['--processing-model', processing_model])
    if translation_provider:
        cmd_args.extend(['--translation-provider', translation_provider])
    if translation_model:
        cmd_args.extend(['--translation-model', translation_model])
    if advanced_translation:
        cmd_args.append('--advanced-translation')
    if geo_boost:
        cmd_args.append('--geo-boost')

    # Get the app.py path
    app_py_path = Path(__file__).parent / 'app.py'
    cmd = [sys.executable, str(app_py_path)] + cmd_args

    log_message(f"[Job {job_id}] Executing: {' '.join(cmd)}", "INFORMATION")

    JOB_STATUS[job_id]["percent"] = 10
    JOB_STATUS[job_id]["message"] = "Fetching web page..."

    # Start subprocess with pipes
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Use threads to consume stdout/stderr to prevent buffer deadlock
    # (subprocess can block if pipe buffers fill up)
    stdout_lines = []
    stderr_lines = []

    def read_stdout():
        for line in process.stdout:
            stdout_lines.append(line)

    def read_stderr():
        for line in process.stderr:
            stderr_lines.append(line)

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    # Poll for progress while process runs
    while process.poll() is None:
        time.sleep(0.5)  # Check every 500ms

        # Read progress file if it exists
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    progress_data = json.load(f)

                # Update job status from progress file
                if 'percent' in progress_data:
                    JOB_STATUS[job_id]["percent"] = progress_data['percent']
                if 'message' in progress_data:
                    JOB_STATUS[job_id]["message"] = progress_data['message']
                if 'current_image' in progress_data:
                    JOB_STATUS[job_id]["current_image"] = progress_data['current_image']
                if 'total_images' in progress_data:
                    JOB_STATUS[job_id]["total_images"] = progress_data['total_images']
                if 'phase' in progress_data:
                    JOB_STATUS[job_id]["phase"] = progress_data['phase']

            except (json.JSONDecodeError, IOError):
                pass  # Progress file might be being written

    # Wait for reader threads to finish
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)

    # Get collected output
    output = ''.join(stdout_lines)
    if stderr_lines:
        output = f"{output}\n{''.join(stderr_lines)}"

    # Clean up progress file
    try:
        if progress_file.exists():
            progress_file.unlink()
    except:
        pass

    # Check for errors
    if process.returncode != 0:
        error_msg = ''.join(stderr_lines) or ''.join(stdout_lines) or "Unknown error"
        log_message(f"[Job {job_id}] CLI execution failed: {error_msg}", "ERROR")
        # Don't fail yet - might still have generated a report

    # Parse output for report path and stats (same logic as sync endpoint)
    report_path = None
    session_id = None
    alt_text_folder = None

    for line in output.split('\n'):
        lower_line = line.lower()

        if not report_path and 'report' in lower_line and '.html' in lower_line:
            match = re.search(r'(output/reports/[^/\s]+/[^\s]+\.html)', line)
            if not match:
                match = re.search(r'([^\s]*output/reports[^\s]*\.html)', line)
            if match:
                candidate_path = match.group(1).strip()
                if 'report_template.html' not in candidate_path:
                    report_path = candidate_path

        if not session_id:
            session_match = re.search(r'Using session:\s*([^\s]+)', line)
            if session_match:
                session_id = session_match.group(1).strip()

        if not alt_text_folder and 'output folder' in lower_line:
            folder_match = re.search(r'Output folder:\s*([^\s]+)', line, flags=re.IGNORECASE)
            if folder_match:
                alt_text_folder = folder_match.group(1).strip()

    # Count images from alt-text folder
    total_images = 0
    missing_alt = 0
    has_alt = 0

    base_alt_text = Path(get_absolute_folder_path('alt_text'))
    if not alt_text_folder and session_id:
        candidate = base_alt_text / session_id
        if candidate.exists():
            alt_text_folder = str(candidate)

    if alt_text_folder:
        alt_text_path = Path(alt_text_folder)
        json_files = list(alt_text_path.glob('*.json'))
        total_images = len(json_files)

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                current_alt = (file_data.get('current_alt_text') or '').strip()
                if current_alt:
                    has_alt += 1
                else:
                    missing_alt += 1
            except Exception:
                continue

    # Normalize report path
    if report_path:
        project_root = Path(__file__).parent.parent
        try:
            report_path_obj = Path(report_path)
            if not report_path_obj.is_absolute():
                report_path_obj = (project_root / report_path_obj).resolve()
            else:
                report_path_obj = report_path_obj.resolve()
            report_path = str(report_path_obj.relative_to(project_root))
            report_path = report_path.replace('\\', '/')
        except Exception:
            pass

    # Update final status
    if report_path or total_images > 0:
        JOB_STATUS[job_id]["status"] = "complete"
        JOB_STATUS[job_id]["percent"] = 100
        JOB_STATUS[job_id]["message"] = "Analysis complete!"
        JOB_STATUS[job_id]["result"] = {
            "success": True,
            "url": url,
            "report_path": report_path,
            "summary": {
                "total_images": total_images,
                "missing_alt": missing_alt,
                "has_alt": has_alt
            }
        }
    else:
        JOB_STATUS[job_id]["status"] = "error"
        JOB_STATUS[job_id]["error"] = "No report generated"
        JOB_STATUS[job_id]["message"] = "Analysis failed - no report generated"

    log_message(f"[Job {job_id}] Analysis complete. Status: {JOB_STATUS[job_id]['status']}", "INFORMATION")


@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of an async analysis job.

    Returns:
    {
        "job_id": "job-abc123",
        "status": "running" | "complete" | "error",
        "percent": 0-100,
        "message": "Processing image 3 of 10...",
        "current_image": 3,  // optional
        "total_images": 10,  // optional
        "result": {...}  // only when status is "complete"
        "error": "..."  // only when status is "error"
    }
    """
    if job_id not in JOB_STATUS:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    status = JOB_STATUS[job_id].copy()

    # Clean up old completed/errored jobs after 5 minutes
    if status["status"] in ("complete", "error"):
        created = datetime.fromisoformat(status.get("created", datetime.now().isoformat()))
        if datetime.now() - created > timedelta(minutes=5):
            del JOB_STATUS[job_id]

    return {"job_id": job_id, **status}


def _resolve_report_path(path: str) -> "Path":
    """
    Resolve a report path safely within the output directory and recover the newest report
    when a folder or stale path is provided.
    """
    from pathlib import Path

    project_root = Path(__file__).parent.parent
    output_dir = project_root / 'output'

    # Resolve provided path relative to project root when it's not absolute
    report_file = Path(path)
    if not report_file.is_absolute():
        report_file = project_root / report_file

    try:
        report_file_abs = report_file.resolve()
        output_dir_abs = output_dir.resolve()

        # Ensure the requested path stays inside output/
        if not str(report_file_abs).startswith(str(output_dir_abs)):
            log_message(f"Access denied: {report_file_abs} is outside {output_dir_abs}", "WARNING")
            raise HTTPException(status_code=403, detail="Access denied: File outside output directory")
    except HTTPException:
        raise
    except Exception as e:
        log_message(f"Path validation error: {str(e)}", "ERROR")
        raise HTTPException(status_code=400, detail="Invalid file path")

    # If the exact file does not exist, attempt to recover a report within the same folder
    if not report_file_abs.exists():
        fallback_folder = report_file_abs if report_file_abs.is_dir() else report_file_abs.parent
        if fallback_folder.exists():
            candidates = list(fallback_folder.glob('*.html'))
            candidates = [c for c in candidates if c.name != 'report_template.html']
            if candidates:
                # Use most recent HTML report
                candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                recovered = candidates[0]
                log_message(f"Resolved missing report path to latest file: {recovered}", "INFORMATION")
                return recovered.resolve()

        log_message(f"Report file not found: {report_file_abs}", "WARNING")
        raise HTTPException(status_code=404, detail=f"Report file not found: {path}")

    return report_file_abs


@app.get("/api/download-report")
async def download_report(path: str):
    """Download a generated report file."""
    try:
        from fastapi.responses import FileResponse

        report_file_abs = _resolve_report_path(path)

        log_message(f"Downloading report: {report_file_abs}", "INFORMATION")
        return FileResponse(
            path=str(report_file_abs),
            filename=report_file_abs.name,
            media_type='text/html'
        )

    except HTTPException:
        raise
    except Exception as e:
        log_message(f"Download report error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/view-report")
async def view_report(path: str):
    """View a generated report file in browser."""
    try:
        from fastapi.responses import FileResponse

        report_file_abs = _resolve_report_path(path)

        log_message(f"Viewing report: {report_file_abs}", "INFORMATION")
        return FileResponse(
            path=str(report_file_abs),
            media_type='text/html'
        )

    except HTTPException:
        raise
    except Exception as e:
        log_message(f"View report error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload-test-files")
async def upload_test_files(
    request: Request,
    response: Response,
    images: List[UploadFile] = File(..., description="Image files"),
    context: Optional[List[UploadFile]] = File(None, description="Optional context files")
):
    """
    Upload test images and context files for prompt comparison.

    Creates a temporary session folder and returns the paths for use with batch-compare-prompts.

    Returns:
        dict: Contains images_folder and context_folder paths
    """
    import shutil

    try:
        # Get or create session ID
        session_id = get_or_create_session_id(request)

        # Set session cookie in response
        response.set_cookie(
            key="web_session_id",
            value=session_id,
            max_age=86400,  # 24 hours
            httponly=True,
            samesite="lax"
        )

        # Get session folders
        session_folders = get_session_folders(session_id)
        images_folder = session_folders['images']

        # Create context folder (sibling to images folder)
        base_context = get_absolute_folder_path('context')
        context_folder = os.path.join(base_context, session_id)
        os.makedirs(context_folder, exist_ok=True)

        # Save uploaded images
        image_count = 0
        for image_file in images:
            if image_file.content_type and image_file.content_type.startswith('image/'):
                # Extract just the filename (remove any directory separators)
                safe_filename = os.path.basename(image_file.filename)
                file_path = os.path.join(images_folder, safe_filename)
                content = await image_file.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
                image_count += 1

        # Save uploaded context files if any
        context_count = 0
        if context:
            for context_file in context:
                if context_file.filename.endswith('.txt'):
                    # Extract just the filename (remove any directory separators)
                    safe_filename = os.path.basename(context_file.filename)
                    file_path = os.path.join(context_folder, safe_filename)
                    content = await context_file.read()
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    context_count += 1

        return {
            "success": True,
            "images_folder": images_folder,
            "context_folder": context_folder if context_count > 0 else "",
            "images_uploaded": image_count,
            "context_files_uploaded": context_count,
            "session_id": session_id
        }

    except Exception as e:
        log_message(f"Upload test files error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/available-prompts")
async def available_prompts():
    """Get list of available processing prompts."""
    try:
        from pathlib import Path

        # Get prompt folder path
        prompt_folder = Path(__file__).parent.parent / 'prompt' / 'processing'

        if not prompt_folder.exists():
            return {"prompts": [], "default": ["v0", "v4"]}

        # List all .txt files
        prompt_files = []
        for file in prompt_folder.glob('processing_prompt_v*.txt'):
            # Extract version from filename (e.g., processing_prompt_v0.txt -> v0)
            version = file.stem.replace('processing_prompt_', '')
            prompt_files.append(version)

        # Sort versions
        prompt_files.sort()

        return {
            "prompts": prompt_files,
            "default": ["v0", "v4"] if "v0" in prompt_files and "v4" in prompt_files else prompt_files[:2] if len(prompt_files) >= 2 else prompt_files
        }

    except Exception as e:
        log_message(f"Available prompts error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/available-test-folders")
async def available_test_folders():
    """Get list of available test image folders."""
    try:
        from pathlib import Path
        import os

        # Base test folder
        test_base = Path(__file__).parent.parent / 'test' / 'input' / 'images'

        if not test_base.exists():
            return {"folders": []}

        folders = []

        # Helper: count supported image types in a folder
        def count_images(folder: Path) -> int:
            return len(list(folder.glob('*.jpg')) + list(folder.glob('*.png')) +
                       list(folder.glob('*.gif')) + list(folder.glob('*.webp')))

        # If images live directly under test_base, include that folder
        base_image_count = count_images(test_base)
        if base_image_count > 0:
            folders.append({
                "path": str(test_base),
                "name": test_base.name.replace('_', ' ').replace('-', ' ').title(),
                "image_count": base_image_count,
                "context_folder": str(test_base).replace('/images', '/context')
            })

        # Iterate through subdirectories
        for folder in test_base.iterdir():
            if folder.is_dir():
                image_count = count_images(folder)

                if image_count > 0:
                    folders.append({
                        "path": str(folder),
                        "name": folder.name.replace('_', ' ').replace('-', ' ').title(),
                        "image_count": image_count,
                        "context_folder": str(folder).replace('/images', '/context')
                    })

        # Sort by name
        folders.sort(key=lambda x: x['name'])

        return {"folders": folders}

    except Exception as e:
        log_message(f"Available test folders error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/batch-compare-prompts")
async def batch_compare_prompts(request: Request):
    """
    Start async batch prompt comparison and return a job_id for polling progress.

    This endpoint starts the comparison in a background thread and returns immediately
    with a job_id that can be used to poll for progress via /api/job-status/{job_id}.

    Request body:
    {
        "prompts": ["v0", "v4"],
        "images_folder": "/app/test/input/images/geo",
        "context_folder": "/app/test/input/context/geo",
        "languages": ["en"],
        "vision_provider": "openai",
        "vision_model": "gpt-4o",
        "processing_provider": "openai",
        "processing_model": "gpt-4o",
        "translation_provider": "openai",
        "translation_model": "gpt-4o",
        "advanced_translation": false,
        "geo_boost": false
    }

    Returns:
    {
        "job_id": "job-abc123",
        "status": "started",
        "message": "Batch comparison started"
    }
    """
    import threading

    try:
        data = await request.json()

        prompts = data.get('prompts', [])
        images_folder = data.get('images_folder')

        # Validation
        if not prompts or len(prompts) < 2:
            raise HTTPException(status_code=400, detail="At least 2 prompts required")

        if not images_folder:
            raise HTTPException(status_code=400, detail="Images folder is required")

        # Generate unique job ID
        job_id = f"job-{uuid.uuid4().hex[:12]}"

        # Count images for progress tracking
        from pathlib import Path
        images_path = Path(images_folder)
        image_count = 0
        if images_path.exists():
            image_count = len(list(images_path.glob('*.jpg')) + list(images_path.glob('*.png')) +
                             list(images_path.glob('*.gif')) + list(images_path.glob('*.webp')) +
                             list(images_path.glob('*.jpeg')))

        # Initialize job status
        JOB_STATUS[job_id] = {
            "status": "starting",
            "percent": 0,
            "message": "Initializing batch comparison...",
            "created": datetime.now().isoformat(),
            "result": None,
            "error": None,
            "total_images": image_count,
            "prompts_count": len(prompts)
        }

        # Start background thread to run comparison
        def run_comparison():
            try:
                _run_batch_compare_with_progress(job_id, data)
            except Exception as e:
                JOB_STATUS[job_id]["status"] = "error"
                JOB_STATUS[job_id]["error"] = str(e)
                JOB_STATUS[job_id]["message"] = f"Error: {str(e)}"
                log_message(f"Background batch comparison error for job {job_id}: {e}", "ERROR")

        thread = threading.Thread(target=run_comparison, daemon=True)
        thread.start()

        return {
            "job_id": job_id,
            "status": "started",
            "message": "Batch comparison started"
        }

    except HTTPException:
        raise
    except Exception as e:
        log_message(f"Batch compare error: {str(e)}", "ERROR")
        raise HTTPException(status_code=500, detail=str(e))


def _run_batch_compare_with_progress(job_id: str, data: dict):
    """
    Run the batch comparison CLI and update job status with progress.
    """
    import subprocess
    import sys
    import re
    import time
    from pathlib import Path

    prompts = data.get('prompts', [])
    images_folder = data.get('images_folder')
    context_folder = data.get('context_folder', '')
    languages = data.get('languages', ['en'])

    # Advanced options
    vision_provider = data.get('vision_provider')
    vision_model = data.get('vision_model')
    processing_provider = data.get('processing_provider')
    processing_model = data.get('processing_model')
    translation_provider = data.get('translation_provider')
    translation_model = data.get('translation_model')
    advanced_translation = data.get('advanced_translation', False)
    geo_boost = data.get('geo_boost', False)

    # Update status
    JOB_STATUS[job_id]["status"] = "running"
    JOB_STATUS[job_id]["percent"] = 5
    JOB_STATUS[job_id]["message"] = "Preparing batch comparison..."

    script_path = Path(__file__).parent.parent / 'tools' / 'batch_compare_prompts.py'

    if not script_path.exists():
        JOB_STATUS[job_id]["status"] = "error"
        JOB_STATUS[job_id]["error"] = "Batch compare tool not found"
        JOB_STATUS[job_id]["message"] = "Error: Batch compare tool not found"
        return

    cmd = [sys.executable, str(script_path)]

    # Add arguments
    cmd.extend(['--images-folder', images_folder])

    if context_folder:
        cmd.extend(['--context-folder', context_folder])

    # Add languages - use single --language flag with multiple values (argparse nargs='+')
    cmd.append('--language')
    cmd.extend(languages)

    # Add prompts
    cmd.append('--prompts')
    cmd.extend(prompts)

    # Add advanced options
    if vision_provider:
        cmd.extend(['--vision-provider', vision_provider])
    if vision_model:
        cmd.extend(['--vision-model', vision_model])
    if processing_provider:
        cmd.extend(['--processing-provider', processing_provider])
    if processing_model:
        cmd.extend(['--processing-model', processing_model])
    if translation_provider:
        cmd.extend(['--translation-provider', translation_provider])
    if translation_model:
        cmd.extend(['--translation-model', translation_model])
    if advanced_translation:
        cmd.append('--advanced-translation')
    if geo_boost:
        cmd.append('--geo-boost')

    log_message(f"[Job {job_id}] Executing: {' '.join(cmd)}", "INFORMATION")

    JOB_STATUS[job_id]["percent"] = 10
    JOB_STATUS[job_id]["message"] = "Starting batch comparison..."

    try:
        # Use Popen to read output in real-time for progress updates
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        output_lines = []
        total_images = JOB_STATUS[job_id].get("total_images", 1)
        prompts_count = JOB_STATUS[job_id].get("prompts_count", 1)
        total_operations = total_images * prompts_count
        completed_operations = 0

        # Read output line by line to track progress
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break

            if line:
                output_lines.append(line)
                line_lower = line.lower()

                # Parse progress from output
                if 'processing' in line_lower or 'image' in line_lower:
                    # Try to extract image number from output
                    match = re.search(r'(?:image|processing)\s*(\d+)', line_lower)
                    if match:
                        current_image = int(match.group(1))
                        completed_operations = current_image
                        percent = min(10 + int((completed_operations / max(total_operations, 1)) * 80), 90)
                        JOB_STATUS[job_id]["percent"] = percent
                        JOB_STATUS[job_id]["message"] = f"Processing image {current_image} of {total_images}..."
                        JOB_STATUS[job_id]["current_image"] = current_image

                elif 'processing with:' in line_lower:
                    # Extract prompt label being processed (format: "Processing with: prompt_name (x/y)")
                    match = re.search(r'processing with:\s*([^\(]+)', line, re.IGNORECASE)
                    if match:
                        current_prompt = match.group(1).strip()
                        JOB_STATUS[job_id]["message"] = f"Processing with prompt: {current_prompt}"

                elif 'generating' in line_lower and 'report' in line_lower:
                    JOB_STATUS[job_id]["percent"] = 90
                    JOB_STATUS[job_id]["message"] = "Generating comparison report..."

        # Get any remaining stderr
        stderr_output = process.stderr.read()
        output = ''.join(output_lines)

        if process.returncode != 0:
            error_msg = stderr_output or output or "Unknown error"
            log_message(f"[Job {job_id}] Batch compare failed: {error_msg}", "ERROR")
            JOB_STATUS[job_id]["status"] = "error"
            JOB_STATUS[job_id]["error"] = f"Batch comparison failed: {error_msg}"
            JOB_STATUS[job_id]["message"] = f"Error: Batch comparison failed"
            return

        # Parse output to find report paths
        report_path = None
        csv_path = None

        for line in output.split('\n'):
            if '.html' in line and 'prompt_comparison' in line:
                match = re.search(r'(output/reports/prompt_comparison_[^\s]+\.html)', line)
                if match:
                    report_path = match.group(1)
            elif '.csv' in line and 'prompt_comparison' in line:
                match = re.search(r'(output/reports/prompt_comparison_[^\s]+\.csv)', line)
                if match:
                    csv_path = match.group(1)

        # Mark as complete
        JOB_STATUS[job_id]["status"] = "complete"
        JOB_STATUS[job_id]["percent"] = 100
        JOB_STATUS[job_id]["message"] = "Batch comparison complete!"
        JOB_STATUS[job_id]["result"] = {
            "success": True,
            "report_path": report_path,
            "csv_path": csv_path,
            "summary": {
                "total_images": total_images,
                "prompts_compared": prompts_count,
                "languages": len(languages),
                "processing_time_seconds": 0,
                "success_rate": 100
            },
            "output": output
        }

        log_message(f"[Job {job_id}] Batch comparison complete. Report: {report_path}", "INFORMATION")

    except subprocess.TimeoutExpired:
        log_message(f"[Job {job_id}] Batch comparison timeout", "ERROR")
        JOB_STATUS[job_id]["status"] = "error"
        JOB_STATUS[job_id]["error"] = "Batch comparison timed out"
        JOB_STATUS[job_id]["message"] = "Error: Batch comparison timed out"
    except Exception as e:
        log_message(f"[Job {job_id}] Batch compare error: {str(e)}", "ERROR")
        JOB_STATUS[job_id]["status"] = "error"
        JOB_STATUS[job_id]["error"] = str(e)
        JOB_STATUS[job_id]["message"] = f"Error: {str(e)}"

@app.get("/api/alt-text-length-config")
async def get_alt_text_length_config():
    """
    Get current alt-text length configuration.

    Returns:
        Dictionary with max_alt_text_length and geo_boost_increase_percent values
    """
    from app import CONFIG

    if not CONFIG:
        load_config()
        from app import CONFIG

    # Get values from config, with defaults
    max_length = CONFIG.get('max_alt_text_length', CONFIG.get('alt_text_max_chars', 125))
    geo_boost_increase_percent = CONFIG.get('geo_boost_increase_percent', 20)

    return {
        'max_alt_text_length': max_length,
        'geo_boost_increase_percent': geo_boost_increase_percent
    }


class AltTextLengthConfig(BaseModel):
    max_alt_text_length: int
    geo_boost_increase_percent: int = 20


@app.post("/api/alt-text-length-config")
async def update_alt_text_length_config(config: AltTextLengthConfig):
    """
    Update alt-text length configuration in memory.

    This updates the runtime configuration. Changes are not persisted to config.json
    and will be lost when the application restarts.

    Args:
        config: AltTextLengthConfig with max and geo_boost_increase_percent values

    Returns:
        Updated configuration values
    """
    from app import CONFIG

    if not CONFIG:
        load_config()
        from app import CONFIG

    # Validate values
    if config.max_alt_text_length < 1:
        raise HTTPException(status_code=400, detail="max_alt_text_length must be at least 1")

    if config.geo_boost_increase_percent < 0 or config.geo_boost_increase_percent > 100:
        raise HTTPException(status_code=400, detail="geo_boost_increase_percent must be between 0 and 100")

    # Update CONFIG in memory
    CONFIG['max_alt_text_length'] = config.max_alt_text_length
    CONFIG['alt_text_max_chars'] = config.max_alt_text_length  # Keep in sync
    CONFIG['geo_boost_increase_percent'] = config.geo_boost_increase_percent

    # Calculate GEO boost limit for logging
    geo_boost_limit = int(config.max_alt_text_length * (1 + config.geo_boost_increase_percent / 100))

    log_message("INFO", f"Alt-text length configuration updated: max={config.max_alt_text_length}, geo_boost_increase={config.geo_boost_increase_percent}% (GEO limit={geo_boost_limit})")

    return {
        'max_alt_text_length': config.max_alt_text_length,
        'geo_boost_increase_percent': config.geo_boost_increase_percent,
        'geo_boost_limit': geo_boost_limit,
        'message': 'Configuration updated successfully (runtime only, not persisted to file)'
    }


@app.get("/api/menu-position")
async def get_menu_position():
    """
    Get current menu position configuration.

    Returns:
        Dictionary with menu_position value ('fixed' or 'static')
    """
    from app import CONFIG
    return {
        'menu_position': CONFIG.get('menu_position', 'fixed')
    }


class MenuPositionConfig(BaseModel):
    menu_position: str


@app.post("/api/menu-position")
async def set_menu_position(config: MenuPositionConfig):
    """
    Update menu position configuration.

    Request body:
    {
        "menu_position": "fixed" or "static"
    }

    Returns:
        Updated configuration
    """
    from app import CONFIG

    if config.menu_position not in ['fixed', 'static']:
        raise HTTPException(status_code=400, detail="menu_position must be 'fixed' or 'static'")

    # Update CONFIG in memory
    CONFIG['menu_position'] = config.menu_position

    log_message(f"Menu position configuration updated: {config.menu_position}", "INFORMATION")

    return {
        'menu_position': config.menu_position,
        'message': 'Menu position updated successfully (runtime only, not persisted to file)'
    }


# Serve static frontend files from FastAPI (same-origin for cookies to work)
# This allows accessing the app on port 8000 where cookies are set
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Determine frontend directory
frontend_dir = Path(__file__).parent.parent / 'frontend'
if frontend_dir.exists():
    # Mount assets directory for images, icons, and SVGs
    assets_dir = frontend_dir / 'assets'
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Serve index.html at root and specific HTML pages
    @app.get("/")
    async def serve_root():
        """Redirect root to home page."""
        return RedirectResponse(url="/index.html")

    @app.get("/{filename}.html")
    async def serve_html(filename: str):
        """Serve HTML files from frontend directory."""
        file_path = frontend_dir / f"{filename}.html"
        if file_path.exists():
            return FileResponse(str(file_path), media_type="text/html")
        return {"error": f"Page {filename}.html not found"}

    @app.get("/{filename}.js")
    async def serve_js(filename: str):
        """Serve JavaScript files from frontend directory."""
        file_path = frontend_dir / f"{filename}.js"
        if file_path.exists():
            return FileResponse(str(file_path), media_type="application/javascript")
        return {"error": f"Script {filename}.js not found"}

    @app.get("/{filename}.css")
    async def serve_css(filename: str):
        """Serve CSS files from frontend directory."""
        file_path = frontend_dir / f"{filename}.css"
        if file_path.exists():
            return FileResponse(str(file_path), media_type="text/css")
        return {"error": f"Style {filename}.css not found"}

    @app.get("/site.webmanifest")
    async def serve_webmanifest():
        """Serve web manifest file."""
        file_path = frontend_dir / "site.webmanifest"
        if file_path.exists():
            return FileResponse(str(file_path), media_type="application/manifest+json")
        return {"error": "site.webmanifest not found"}

    print(f"[API] Frontend served from: {frontend_dir}")
    print(f"[API] Access application at: http://localhost:8000/index.html (same-origin, cookies work)")
else:
    # Fallback: show API info at root
    @app.get("/")
    async def root():
        """Redirect to API documentation."""
        return {
            "message": "AutoAltText API",
            "version": "5.0.1",
            "docs": "/api/docs",
            "health": "/api/health"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
