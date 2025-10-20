"""Beautiful Gradient MCP Server - FastMCP with Stytch OAuth."""

import os
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.provider import TokenVerifier, AccessToken
from mcp.server.auth.middleware.auth_context import get_access_token
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from logger import oauth_logger, mcp_logger, startup_logger, error_logger
from auth import verify_stytch_token, verify_jwt_token, verify_stytch_session_token, extract_twitter_profile
from database import init_db, get_db, get_or_create_profile, get_profile_by_user_id, Profile
from gradients import GRADIENTS, get_gradient_css

# Load environment variables
load_dotenv()

# Configuration
STYTCH_PROJECT_ID = os.getenv("STYTCH_PROJECT_ID", "")
STYTCH_PUBLIC_TOKEN = os.getenv("STYTCH_PUBLIC_TOKEN", "")
STYTCH_CLIENT_ID = os.getenv("STYTCH_CLIENT_ID", "")
STYTCH_AUTHORIZATION_SERVER = os.getenv(
    "STYTCH_AUTHORIZATION_SERVER",
    "https://decorous-scale-5822.customers.stytch.dev"
)
# Auto-detect HTTPS based on environment or manual override
DEFAULT_PROTOCOL = "https" if os.getenv("USE_HTTPS", "false").lower() == "true" else "http"
DEFAULT_PORT = os.getenv("SERVER_PORT", "8000")
DEFAULT_HOST = os.getenv("SERVER_HOST", "localhost")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", f"{DEFAULT_PROTOCOL}://{DEFAULT_HOST}:{DEFAULT_PORT}")

# OAuth endpoints (legacy - kept for reference)
OAUTH_AUTHORIZE_URL = "https://test.stytch.com/v1/public/oauth/authorize"
OAUTH_TOKEN_URL = "https://test.stytch.com/v1/public/oauth/token"
OAUTH_REGISTER_URL = "https://test.stytch.com/v1/public/oauth/register"


# Custom AccessToken with additional JWT fields
class StytchAccessToken(AccessToken):
    """Extended AccessToken with JWT subject and claims for Stytch OAuth."""
    subject: str
    claims: Dict[str, Any]


# Stytch Token Verifier (Official FastMCP Pattern)
class StytchVerifier(TokenVerifier):
    """Verifies Stytch OAuth tokens according to FastMCP auth pattern."""

    async def verify_token(self, token: str) -> StytchAccessToken | None:
        """
        Verify JWT access token with Stytch and return StytchAccessToken if valid.

        Args:
            token: The JWT access token from OAuth flow

        Returns:
            StytchAccessToken if valid, None if invalid
        """
        try:
            oauth_logger.info(f"🔐 Verifying JWT token with Stytch (FastMCP pattern)")

            # Use JWT verification for OAuth access tokens
            jwt_claims = await verify_jwt_token(token)

            # Extract required fields from JWT claims
            subject = jwt_claims.get("sub")  # User ID is in 'sub' claim
            client_id = jwt_claims.get("azp", jwt_claims.get("client_id", ""))  # Authorized party

            if not subject:
                oauth_logger.error("❌ No 'sub' claim in JWT")
                return None

            oauth_logger.info(f"✅ JWT verified for subject: {subject}")

            # Extract scopes if present
            scopes = jwt_claims.get("scope", "").split() if "scope" in jwt_claims else []

            return StytchAccessToken(
                token=token,
                client_id=client_id,    # OAuth client ID
                subject=subject,        # User ID from JWT sub claim
                scopes=scopes,          # OAuth scopes if any
                claims=jwt_claims,      # Store full JWT claims for later use
            )

        except Exception as e:
            oauth_logger.error(f"❌ JWT verification failed: {str(e)}")
            error_logger.exception("JWT verification error", exc_info=e)
            return None


# Create FastMCP server with Authentication (Official Pattern)
mcp_server = FastMCP(
    name="beautiful-gradient-mcp",
    stateless_http=True,
    token_verifier=StytchVerifier(),
    auth=AuthSettings(
        issuer_url=STYTCH_AUTHORIZATION_SERVER,
        resource_server_url=MCP_SERVER_URL,  # Reads from MCP_SERVER_URL env var
        required_scopes=[],  # No specific scopes required
    ),
)

# Initialize database
try:
    init_db()
except Exception as e:
    startup_logger.error(f"Failed to initialize database: {str(e)}")
    # Continue anyway for testing

# Tool input schema
TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "tweetContent": {
            "type": "string",
            "description": "The content of the tweet to render"
        },
        "gradientIndex": {
            "type": "integer",
            "description": "Gradient preset index (0-24)",
            "default": 0,
            "minimum": 0,
            "maximum": 24
        }
    },
    "required": ["tweetContent"],
    "additionalProperties": False
}


@mcp_server._mcp_server.list_tools()
async def _list_tools() -> List[types.Tool]:
    """List available MCP tools."""
    mcp_logger.info("📋 Tools list requested")

    tools = [
        types.Tool(
            name="get-my-profile",
            title="Get My Profile",
            description="Get the authenticated user's profile information from OAuth",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            },
            securitySchemes=[
                {
                    "type": "oauth2",
                    "scopes": ["openid", "profile"]
                }
            ],
            annotations={
                "destructiveHint": False,
                "openWorldHint": False,
                "readOnlyHint": True
            }
        ),
        types.Tool(
            name="create-gradient-tweet",
            title="Create Gradient Tweet",
            description="Generate a beautiful tweet mockup with a vibrant gradient background",
            inputSchema=TOOL_INPUT_SCHEMA,
            securitySchemes=[
                {
                    "type": "oauth2",
                    "scopes": ["openid", "profile"]
                }
            ],
            _meta={
                "openai/widgetAccessible": True,
                "openai/resultCanProduceWidget": True
            },
            annotations={
                "destructiveHint": False,
                "openWorldHint": False,
                "readOnlyHint": True
            }
        )
    ]

    mcp_logger.info(f"✅ Returned {len(tools)} tools")
    return tools


async def _call_tool(request: types.CallToolRequest) -> types.ServerResult:
    """Handle MCP tool calls."""
    request_id = uuid.uuid4().hex[:8]

    mcp_logger.info("=" * 80)
    mcp_logger.info(f"📥 MCP Tool Call [{request_id}]")
    mcp_logger.info(f"Tool: {request.params.name}")
    mcp_logger.info(f"Arguments: {json.dumps(request.params.arguments, indent=2)}")

    # FastMCP's dependency injection will provide the verified AccessToken
    # via get_access_token() inside the tool handlers

    # Execute tool
    if request.params.name == "get-my-profile":
        return await handle_get_my_profile(request_id)
    elif request.params.name == "create-gradient-tweet":
        return await handle_create_gradient_tweet(request.params.arguments, request_id)
    else:
        mcp_logger.error(f"❌ Unknown tool: {request.params.name}")
        return types.ServerResult(
            types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Unknown tool: {request.params.name}"
                    )
                ],
                isError=True
            )
        )


async def handle_get_my_profile(
    request_id: str
) -> types.ServerResult:
    """Handle the get-my-profile tool to test OAuth authentication."""
    mcp_logger.info(f"🔧 Executing get-my-profile [{request_id}]")

    try:
        # Get the verified access token from FastMCP's dependency injection
        access_token = get_access_token()

        if not access_token:
            mcp_logger.error(f"❌ No access token available [{request_id}]")
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text="Authentication required. Please connect your account first."
                        )
                    ],
                    isError=True
                )
            )

        # Extract user information from the AccessToken
        subject = access_token.subject
        client_id = access_token.client_id
        scopes = access_token.scopes
        jwt_claims = access_token.claims

        # Build profile response
        profile_data = {
            "user_id": subject,
            "client_id": client_id,
            "scopes": scopes,
            "jwt_claims": jwt_claims
        }

        mcp_logger.info(f"✅ Profile retrieved for user: {subject} [{request_id}]")
        mcp_logger.info(f"📊 Scopes: {scopes}")

        # Create readable text response
        text_response = f"""Profile Information:
- User ID: {subject}
- Client ID: {client_id}
- Scopes: {', '.join(scopes) if scopes else 'none'}
- JWT Claims: {len(jwt_claims)} claims present"""

        return types.ServerResult(
            types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=text_response
                    )
                ],
                structuredContent=profile_data
            )
        )

    except Exception as e:
        mcp_logger.error(f"❌ Failed to get profile: {str(e)} [{request_id}]")
        error_logger.exception("Get profile error", exc_info=e)
        return types.ServerResult(
            types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Failed to retrieve profile: {str(e)}"
                    )
                ],
                isError=True
            )
        )


async def handle_create_gradient_tweet(
    arguments: Dict[str, Any],
    request_id: str
) -> types.ServerResult:
    """Handle the create-gradient-tweet tool."""
    mcp_logger.info(f"🔧 Executing create-gradient-tweet [{request_id}]")

    tweet_content = arguments.get("tweetContent", "")
    gradient_index = arguments.get("gradientIndex", 0)

    # Validate gradient index
    if not 0 <= gradient_index < len(GRADIENTS):
        gradient_index = 0

    gradient = GRADIENTS[gradient_index]
    mcp_logger.info(f"🌈 Using gradient: {gradient['name']} (index {gradient_index})")

    # Try to get authenticated user profile from database
    profile = None
    try:
        access_token = get_access_token()

        if access_token and access_token.subject:
            # We have an authenticated user
            user_id = access_token.subject
            mcp_logger.info(f"✅ Authenticated user: {user_id}")

            # Look up profile from database (saved during frontend OAuth flow)
            db = get_db()
            try:
                profile = get_profile_by_user_id(db, user_id)

                if profile:
                    mcp_logger.info(f"✅ Profile loaded from database: @{profile.twitter_handle}")
                else:
                    mcp_logger.warning(f"⚠️ Profile not found in database for user: {user_id}")
                    mcp_logger.warning("⚠️ User may need to re-login via frontend to save profile")
            finally:
                db.close()

        if profile:
            # Use real Twitter profile
            twitter_data = {
                "handle": profile.twitter_handle or "twitter_user",
                "name": profile.display_name or "Twitter User",
                "avatar": profile.avatar_url or "https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png"
            }
            mcp_logger.info(f"🐦 Using authenticated profile: @{twitter_data['handle']}")
        else:
            # No profile - use default
            twitter_data = {
                "handle": "twitter_user",
                "name": "Twitter User",
                "avatar": "https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png"
            }
            mcp_logger.warning("⚠️ Using default profile (no profile in database)")

    except Exception as e:
        # If anything goes wrong, fall back to default
        mcp_logger.warning(f"⚠️ Could not get user profile: {str(e)}, using default profile")
        error_logger.exception("Profile lookup error", exc_info=e)
        twitter_data = {
            "handle": "twitter_user",
            "name": "Twitter User",
            "avatar": "https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png"
        }

    # Structured content for the widget
    structured_content = {
        "tweetContent": tweet_content,
        "gradientIndex": gradient_index,
        "gradientName": gradient['name'],
        "profile": twitter_data,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "widgetUrl": f"{MCP_SERVER_URL}/widget/gradient-tweet"
    }

    # Text response
    text_response = f"Created gradient tweet with {gradient['name']} gradient!"

    # Read widget HTML content
    widget_html = ""
    try:
        widget_path = os.path.join(os.path.dirname(__file__), "widgets", "gradient_tweet.html")
        with open(widget_path, 'r', encoding='utf-8') as f:
            widget_html = f.read()
    except Exception as e:
        mcp_logger.warning(f"Could not read widget HTML: {e}")
        widget_html = "<p>Widget HTML not available</p>"

    mcp_logger.info(f"✅ Tool executed successfully [{request_id}]")
    mcp_logger.debug(f"Structured content: {json.dumps(structured_content, indent=2)}")
    mcp_logger.info("=" * 80)

    # Return content that will display the HTML widget inline
    # This approach should work for MCP inline HTML rendering
    content_items = [
        types.TextContent(
            type="text",
            text=text_response
        )
    ]
    
    # Try to include the HTML widget for inline display
    # The MCP system should render HTML content inline when properly formatted
    if widget_html and widget_html != "<p>Widget HTML not available</p>":
        try:
            # Attempt to add HTML content that the MCP client can render inline
            # Based on MCP specifications, this should work for widget rendering
            content_items.append(
                types.TextContent(
                    type="text",
                    text=widget_html
                )
            )
        except Exception as e:
            mcp_logger.warning(f"Failed to add HTML content: {e}")

    # For inline HTML widget display, we need to return the content in a specific way
    # The MCP system should render HTML widgets inline when properly formatted
    
    # Create the response with HTML content for inline rendering
    # The key is to include the HTML in a way that triggers inline widget rendering
    return types.ServerResult(
        types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=text_response
                )
            ] + ([
                types.TextContent(
                    type="text",
                    text=widget_html
                )
            ] if widget_html and widget_html != "<p>Widget HTML not available</p>" else []),
            structuredContent={
                **structured_content,
                # Include widget HTML in structured content for MCP widget handling
                "widget_html": widget_html if widget_html and widget_html != "<p>Widget HTML not available</p>" else None
            },
            _meta={
                "openai/widgetAccessible": True,
                "openai/resultCanProduceWidget": True,
                # Add metadata to indicate this should render as an inline widget
                "widget_type": "html",
                "inline_render": True
            }
        )
    )


# OAuth Protected Resource Metadata endpoint is now handled automatically by FastMCP
# when auth=AuthSettings(...) is configured above.
# FastMCP exposes /.well-known/oauth-protected-resource automatically.


# Register tool handler (following official example pattern)
mcp_server._mcp_server.request_handlers[types.CallToolRequest] = _call_tool

# Create Starlette app from FastMCP
from starlette.routing import Route, Mount
from starlette.responses import HTMLResponse, FileResponse
from starlette.staticfiles import StaticFiles
import os

app = mcp_server.streamable_http_app()

# OAuth Protected Resource Metadata route is automatically added by FastMCP
# when auth=AuthSettings(...) is configured

# Serve built React app
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend", "dist")

# Mount static assets
app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

# API endpoint to save user profile after frontend OAuth
@app.route("/api/save-profile", methods=["POST"])
async def save_profile(request):
    """Save user profile after successful OAuth authentication."""
    import json
    from starlette.responses import JSONResponse

    request_id = uuid.uuid4().hex[:8]
    mcp_logger.info("=" * 80)
    mcp_logger.info(f"📥 Profile save request [{request_id}]")

    try:
        # Parse request body
        body = await request.body()
        data = json.loads(body)
        session_token = data.get("session_token")

        if not session_token:
            mcp_logger.error(f"❌ No session_token provided [{request_id}]")
            return JSONResponse(
                {"success": False, "message": "session_token required"},
                status_code=400
            )

        mcp_logger.info(f"🔐 Verifying session token [{request_id}]")

        # Call Stytch to get full user data including Twitter profile
        user_data = await verify_stytch_session_token(session_token)
        mcp_logger.info(f"✅ Token verified [{request_id}]")

        # Extract Twitter profile
        mcp_logger.info(f"🐦 Extracting Twitter profile [{request_id}]")
        twitter_profile = extract_twitter_profile(user_data)

        if not twitter_profile:
            mcp_logger.warning(f"⚠️ No Twitter profile found in response [{request_id}]")
            return JSONResponse(
                {"success": False, "message": "No Twitter profile found"},
                status_code=400
            )

        # Save to database
        db = get_db()
        try:
            profile = get_or_create_profile(db, twitter_profile)

            if profile:
                mcp_logger.info(f"✅ Profile save endpoint succeeded [@{profile.twitter_handle}] [{request_id}]")
                return JSONResponse({
                    "success": True,
                    "message": "Profile saved successfully",
                    "profile": {
                        "twitter_handle": profile.twitter_handle,
                        "display_name": profile.display_name
                    }
                })
            else:
                mcp_logger.error(f"❌ Failed to save profile to database [{request_id}]")
                return JSONResponse(
                    {"success": False, "message": "Failed to save profile"},
                    status_code=500
                )
        finally:
            db.close()
            mcp_logger.info("=" * 80)

    except Exception as e:
        mcp_logger.error(f"❌ Profile save endpoint failed: {str(e)} [{request_id}]")
        error_logger.exception("Profile save error", exc_info=e)
        mcp_logger.info("=" * 80)
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )


# API endpoint to get all 25 gradients for the widget
@app.route("/api/gradients", methods=["GET"])
async def get_all_gradients_api(request):
    """Get all 25 gradients for the widget."""
    from starlette.responses import JSONResponse
    
    try:
        return JSONResponse({
            "success": True,
            "gradients": GRADIENTS,
            "count": len(GRADIENTS)
        })
    except Exception as e:
        mcp_logger.error(f"❌ Failed to get gradients: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )


# API endpoint to handle image uploads for sharing
@app.route("/api/upload-image", methods=["POST"])
async def upload_image(request):
    """Handle image uploads for sharing functionality."""
    from starlette.responses import JSONResponse
    
    try:
        # For now, return a mock URL since we don't have actual image hosting
        # In a real implementation, you'd upload to a service like Cloudinary, AWS S3, etc.
        return JSONResponse({
            "success": True,
            "url": "https://example.com/uploaded-image.png",
            "message": "Image upload not implemented yet"
        })
    except Exception as e:
        mcp_logger.error(f"❌ Failed to upload image: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )


# Serve widget HTML
@app.route("/widget/gradient-tweet")
async def serve_gradient_widget(request):
    """Serve the gradient tweet widget HTML."""
    try:
        widget_path = os.path.join(os.path.dirname(__file__), "widgets", "gradient_tweet.html")
        return FileResponse(widget_path)
    except Exception as e:
        mcp_logger.error(f"❌ Failed to serve widget: {str(e)}")
        return HTMLResponse("<p>Widget not available</p>", status_code=404)


# Serve index.html at /login
@app.route("/login")
async def login_page(request):
    """Serve the OAuth login page (built React app with Stytch IdentityProvider)."""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False
)


# Startup logging (called when server starts)
def log_startup():
    """Server startup logging."""
    startup_logger.info("=" * 80)
    startup_logger.info("🚀 Beautiful Gradient MCP Server Starting")
    startup_logger.info("=" * 80)
    startup_logger.info(f"Stytch Project ID: {STYTCH_PROJECT_ID[:20] if STYTCH_PROJECT_ID else 'NOT SET'}...")
    startup_logger.info(f"Stytch Authorization Server: {STYTCH_AUTHORIZATION_SERVER}")
    startup_logger.info(f"OAuth Metadata Endpoint: /.well-known/oauth-protected-resource")
    startup_logger.info("=" * 80)


if __name__ == "__main__":
    import uvicorn
    
    # HTTPS Configuration
    SSL_CERT_PATH = os.getenv("SSL_CERT_PATH", "")
    SSL_KEY_PATH = os.getenv("SSL_KEY_PATH", "")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
    USE_HTTPS = os.getenv("USE_HTTPS", "false").lower() == "true"
    
    log_startup()
    
    # Determine if we should use HTTPS based on environment or file presence
    use_ssl = USE_HTTPS or (SSL_CERT_PATH and SSL_KEY_PATH and os.path.exists(SSL_CERT_PATH) and os.path.exists(SSL_KEY_PATH))
    
    if use_ssl and SSL_CERT_PATH and SSL_KEY_PATH:
        startup_logger.info(f"🔒 Starting with HTTPS using certificates: {SSL_CERT_PATH}")
        uvicorn.run(
            "main:app", 
            host="0.0.0.0", 
            port=SERVER_PORT, 
            reload=True,
            ssl_keyfile=SSL_KEY_PATH,
            ssl_certfile=SSL_CERT_PATH
        )
    else:
        startup_logger.info(f"🌐 Starting with HTTP on port {SERVER_PORT}")
        startup_logger.info("💡 For HTTPS, set USE_HTTPS=true and provide SSL_CERT_PATH and SSL_KEY_PATH")
        uvicorn.run("main:app", host="0.0.0.0", port=SERVER_PORT, reload=True)