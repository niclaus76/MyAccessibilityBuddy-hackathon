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
    ECB_LLM_AVAILABLE,
    OLLAMA_AVAILABLE
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
    version="5.0.0",
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

    # No valid session found, create new one
    session_id = f"web-{uuid.uuid4()}"
    WEB_APP_SESSIONS[session_id] = {
        "created": datetime.now(),
        "last_accessed": datetime.now(),
        "type": "web"
    }

    return session_id

def get_session_type(session_id: str) -> str:
    """
    Determine session type from session ID prefix.

    Args:
        session_id: Session ID (e.g., 'web-abc123' or 'cli-def456')

    Returns:
        str: Session type ('web', 'cli', or 'unknown')
    """
    if session_id.startswith('web-'):
        return 'web'
    elif session_id.startswith('cli-'):
        return 'cli'
    else:
        return 'unknown'

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
                <p><a href="file:///home/developer/AutoAltText/frontend/home.html">Return to application</a></p>
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
                    <p><a href="file:///home/developer/AutoAltText/frontend/home.html">Return to application</a></p>
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
                    window.location.href = "file:///home/developer/AutoAltText/frontend/home.html";
                }}, 1000);
            </script>
        </head>
        <body>
            <h1>Authentication Successful!</h1>
            <p>Redirecting to application...</p>
            <p>If not redirected, <a href="file:///home/developer/AutoAltText/frontend/home.html">click here</a></p>
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
                <p><a href="file:///home/developer/AutoAltText/frontend/home.html">Return to application</a></p>
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
                <p><a href="file:///home/developer/AutoAltText/frontend/home.html">Return to application</a></p>
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
        version="5.0.0",
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

    # Get current config defaults from steps
    current_config = CONFIG.get('steps', {
        'vision': {'provider': 'OpenAI', 'model': 'gpt-4o'},
        'processing': {'provider': 'OpenAI', 'model': 'gpt-4o'},
        'translation': {'provider': 'OpenAI', 'model': 'gpt-4o'}
    })

    return {
        'providers': available_providers,
        'ecb_llm_available': ECB_LLM_AVAILABLE and CONFIG.get('ecb_llm', {}).get('enabled', False),
        'ollama_available': OLLAMA_AVAILABLE and CONFIG.get('ollama', {}).get('enabled', False),
        'config_defaults': current_config
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
    translation_model: Optional[str] = Form(None, description="Translation model (e.g., gpt-4o-mini, phi3)")
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
            'ollama': 'Ollama'
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
            languages=[language]
        )

        if not success or not json_path:
            # Try to get more detailed error information
            error_detail = "Failed to generate alt-text"
            if vision_provider == 'claude' or vision_provider == 'Claude':
                error_detail += ". Check that ANTHROPIC_API_KEY is set correctly."
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
        if isinstance(proposed_alt_text, list):
            # Multilingual: find the requested language
            alt_text_str = next(
                (text for lang_code, text in proposed_alt_text if lang_code.upper() == language.upper()),
                proposed_alt_text[0][1] if proposed_alt_text else ''
            )
        else:
            # Single language
            alt_text_str = proposed_alt_text

        # Extract reasoning (handle multilingual format)
        reasoning_value = result.get('reasoning', '')
        if isinstance(reasoning_value, list) and reasoning_value:
            # Multilingual: find the requested language
            reasoning_str = next(
                (text for lang_code, text in reasoning_value if lang_code.upper() == language.upper()),
                reasoning_value[0][1] if reasoning_value else ''
            )
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
        return AltTextResponse(
            success=False,
            alt_text="",
            image_type="generation_error",
            reasoning=None,
            character_count=0,
            language=language,
            error=str(e)
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


@app.post("/api/clear-session")
async def clear_session(request: Request, response: Response):
    """
    Clear all data for the current user session.

    This endpoint:
    - Deletes all images in the session folder
    - Deletes all generated JSON files
    - Deletes all reports
    - Removes the session from memory
    - Clears the session cookie

    Args:
        request: FastAPI Request object
        response: FastAPI Response object

    Returns:
        dict: Success message with details of what was cleared
    """
    import shutil

    try:
        # Get current session ID
        session_id = request.cookies.get("web_session_id")

        if not session_id:
            return {
                "success": True,
                "message": "No active session to clear",
                "files_deleted": 0,
                "folders_deleted": 0
            }

        # Get session folders
        session_folders = get_session_folders(session_id)

        files_deleted = 0
        folders_deleted = 0

        # Delete session folders
        for key, folder in session_folders.items():
            if key in ['images', 'alt_text'] and os.path.exists(folder):
                try:
                    # Count files before deletion
                    if os.path.isdir(folder):
                        file_count = len([f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))])
                        files_deleted += file_count

                    # Remove the entire folder
                    shutil.rmtree(folder)
                    folders_deleted += 1
                    print(f"Cleared session folder: {folder}")
                except Exception as e:
                    print(f"Error deleting folder {folder}: {e}")

        # Delete report folder if it exists
        base_output_folder = get_absolute_folder_path('output')
        report_folder = os.path.join(base_output_folder, 'reports', session_id)
        if os.path.exists(report_folder):
            try:
                shutil.rmtree(report_folder)
                folders_deleted += 1
                print(f"Cleared report folder: {report_folder}")
            except Exception as e:
                print(f"Error deleting report folder: {e}")

        # Remove from session storage
        if session_id in WEB_APP_SESSIONS:
            del WEB_APP_SESSIONS[session_id]

        # Clear the session cookie
        response.delete_cookie(key="web_session_id")

        return {
            "success": True,
            "message": f"Session {session_id} cleared successfully",
            "files_deleted": files_deleted,
            "folders_deleted": folders_deleted,
            "session_id": session_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error clearing session: {str(e)}",
            "files_deleted": 0,
            "folders_deleted": 0
        }


@app.post("/api/generate-report")
async def generate_report_endpoint(request: Request, clear_after: bool = True):
    """
    Generate HTML report for webmaster tool.

    Args:
        request: FastAPI Request object
        clear_after: If True, clears session data after generating report

    Returns:
        FileResponse: HTML report file for download

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

        # Generate timestamp for filename
        timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')
        output_filename = f"webmaster-report-{timestamp}.html"

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

            # Return file for download
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


# Root redirect to docs
@app.get("/")
async def root():
    """Redirect to API documentation."""
    return {
        "message": "AutoAltText API",
        "version": "5.0.0",
        "docs": "/api/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
