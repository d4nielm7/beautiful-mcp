"""Stytch OAuth token verification with comprehensive logging."""

import base64
import json
import os
from typing import Optional, Dict, Any

import httpx
import jwt
from jwt import PyJWKClient
from logger import oauth_logger, error_logger

# Stytch configuration
STYTCH_PROJECT_ID = os.getenv("STYTCH_PROJECT_ID", "")
STYTCH_SECRET = os.getenv("STYTCH_SECRET", "")  # For server-side auth
STYTCH_PUBLIC_TOKEN = os.getenv("STYTCH_PUBLIC_TOKEN", "")
STYTCH_AUTHORIZATION_SERVER = os.getenv(
    "STYTCH_AUTHORIZATION_SERVER",
    "https://decorous-scale-5822.customers.stytch.dev"
)

# OAuth endpoints
STYTCH_AUTHENTICATE_URL = "https://test.stytch.com/v1/oauth/authenticate"
STYTCH_SESSION_AUTH_URL = "https://test.stytch.com/v1/sessions/authenticate"
STYTCH_JWKS_URL = f"https://test.stytch.com/v1/sessions/jwks/{STYTCH_PROJECT_ID}"


async def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT access token from Stytch Connected Apps OAuth flow.

    This is used when ChatGPT sends a JWT access token in the Authorization header.

    Args:
        token: JWT access token from OAuth flow

    Returns:
        dict: Decoded JWT claims with user data

    Raises:
        Exception: If JWT verification fails
    """
    oauth_logger.info("=" * 80)
    oauth_logger.info("🔐 Starting JWT token verification")
    oauth_logger.info(f"Token (first 20 chars): {token[:20]}...")
    oauth_logger.info(f"Token length: {len(token)}")

    if not STYTCH_PROJECT_ID:
        oauth_logger.error("❌ STYTCH_PROJECT_ID not configured")
        raise ValueError("Stytch Project ID not configured")

    try:
        oauth_logger.debug(f"JWKS URL: {STYTCH_JWKS_URL}")
        oauth_logger.debug(f"Expected issuer: {STYTCH_AUTHORIZATION_SERVER}")
        oauth_logger.debug(f"Expected audience: {STYTCH_PROJECT_ID}")

        # Create JWKS client to fetch signing keys
        jwks_client = PyJWKClient(STYTCH_JWKS_URL)

        # Get signing key from token header
        oauth_logger.debug("Fetching signing key from JWKS endpoint")
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Verify and decode JWT
        oauth_logger.debug("Verifying JWT signature and claims")
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=STYTCH_AUTHORIZATION_SERVER,
            audience=STYTCH_PROJECT_ID,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )

        oauth_logger.info("✅ JWT verified successfully")
        oauth_logger.debug(f"JWT claims: {json.dumps(decoded, indent=2)}")

        # Extract user info from JWT claims
        subject = decoded.get('sub', 'UNKNOWN')
        oauth_logger.info(f"✅ Token valid for subject: {subject}")

        # Log all claims for debugging
        oauth_logger.debug(f"JWT claims keys: {list(decoded.keys())}")

        return decoded

    except jwt.ExpiredSignatureError:
        oauth_logger.error("❌ JWT token has expired")
        raise Exception("JWT token has expired")
    except jwt.InvalidIssuerError as e:
        oauth_logger.error(f"❌ Invalid JWT issuer: {str(e)}")
        raise Exception(f"Invalid JWT issuer: {str(e)}")
    except jwt.InvalidAudienceError as e:
        oauth_logger.error(f"❌ Invalid JWT audience: {str(e)}")
        raise Exception(f"Invalid JWT audience: {str(e)}")
    except jwt.InvalidSignatureError:
        oauth_logger.error("❌ Invalid JWT signature")
        raise Exception("Invalid JWT signature")
    except Exception as e:
        oauth_logger.error(f"❌ JWT verification failed: {str(e)}")
        error_logger.exception("JWT verification error", exc_info=e)
        raise Exception(f"JWT verification failed: {str(e)}")
    finally:
        oauth_logger.info("=" * 80)


async def verify_stytch_token(token: str) -> Dict[str, Any]:
    """
    Verify OAuth token with Stytch and extract user profile.

    Args:
        token: OAuth token from ChatGPT/MCP client

    Returns:
        dict: User data including Twitter profile

    Raises:
        Exception: If token verification fails
    """
    oauth_logger.info("=" * 80)
    oauth_logger.info("🔐 Starting OAuth token verification")
    oauth_logger.info(f"Token (first 20 chars): {token[:20]}...")
    oauth_logger.info(f"Token length: {len(token)}")

    if not STYTCH_PROJECT_ID:
        oauth_logger.error("❌ STYTCH_PROJECT_ID not configured")
        raise ValueError("Stytch Project ID not configured")

    try:
        oauth_logger.debug("Calling Stytch /oauth/authenticate endpoint")
        oauth_logger.debug(f"Stytch Project ID: {STYTCH_PROJECT_ID[:20]}...")
        oauth_logger.debug(f"Authenticate URL: {STYTCH_AUTHENTICATE_URL}")

        # Create Basic Auth header (project_id:secret)
        # For public clients, we might use public token instead
        if STYTCH_SECRET:
            credentials = f"{STYTCH_PROJECT_ID}:{STYTCH_SECRET}"
            b64_credentials = base64.b64encode(credentials.encode()).decode()
            auth_header = f"Basic {b64_credentials}"
        elif STYTCH_PUBLIC_TOKEN:
            # Use public token for verification
            auth_header = f"Bearer {STYTCH_PUBLIC_TOKEN}"
        else:
            oauth_logger.error("❌ No Stytch credentials configured (need SECRET or PUBLIC_TOKEN)")
            raise ValueError("Stytch credentials not configured")

        oauth_logger.debug(f"Using auth method: {'Basic (secret)' if STYTCH_SECRET else 'Bearer (public token)'}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                STYTCH_AUTHENTICATE_URL,
                json={"token": token},
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json"
                }
            )

        oauth_logger.info(f"📡 Stytch response status: {response.status_code}")
        oauth_logger.debug(f"Stytch response headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            oauth_logger.debug(f"Full Stytch response: {json.dumps(data, indent=2)}")

            # Extract user info
            user = data.get('user', {})
            user_id = user.get('user_id', 'UNKNOWN')
            oauth_logger.info(f"✅ Token valid for user: {user_id}")

            # Extract Twitter profile from provider_values
            provider_values = data.get('provider_values', {})
            oauth_logger.debug(f"Provider values keys: {list(provider_values.keys())}")

            # Twitter data structure might vary - log what we get
            if 'twitter' in provider_values:
                twitter_profile = provider_values['twitter']
                oauth_logger.info(f"🐦 Twitter data found")
                oauth_logger.info(f"🐦 Twitter handle: @{twitter_profile.get('screen_name', 'UNKNOWN')}")
                oauth_logger.info(f"🐦 Twitter name: {twitter_profile.get('name', 'UNKNOWN')}")
                oauth_logger.info(f"🐦 Twitter ID: {twitter_profile.get('id', 'UNKNOWN')}")
                avatar_url = twitter_profile.get('profile_image_url', '')
                if avatar_url:
                    oauth_logger.info(f"🐦 Twitter avatar: {avatar_url[:60]}...")
                else:
                    oauth_logger.warning("⚠️ No Twitter avatar URL found")
            else:
                oauth_logger.warning(f"⚠️ No Twitter data in provider_values. Available: {list(provider_values.keys())}")

            return data

        else:
            oauth_logger.error(f"❌ Stytch authentication failed: {response.status_code}")
            oauth_logger.error(f"Response body: {response.text}")
            error_logger.error(f"Stytch auth failed: {response.status_code} - {response.text}")
            raise Exception(f"Stytch authentication failed: {response.status_code}")

    except httpx.RequestError as e:
        oauth_logger.error(f"❌ Network error calling Stytch: {str(e)}")
        error_logger.exception("Stytch network error", exc_info=e)
        raise Exception(f"Network error contacting Stytch: {str(e)}")

    except Exception as e:
        oauth_logger.error(f"❌ Unexpected error in token verification: {str(e)}")
        error_logger.exception("Token verification error", exc_info=e)
        raise

    finally:
        oauth_logger.info("=" * 80)


async def verify_stytch_session_token(session_token: str) -> Dict[str, Any]:
    """
    Verify session token from Stytch OAuth flow and get user data.

    This is used when the frontend completes OAuth and gets a session token.

    Args:
        session_token: Session token from Stytch OAuth flow

    Returns:
        dict: User data including provider_values with Twitter profile

    Raises:
        Exception: If session authentication fails
    """
    oauth_logger.info("=" * 80)
    oauth_logger.info("🔐 Starting session token verification")
    oauth_logger.info(f"Token (first 20 chars): {session_token[:20]}...")
    oauth_logger.info(f"Token length: {len(session_token)}")

    if not STYTCH_PROJECT_ID or not STYTCH_SECRET:
        oauth_logger.error("❌ STYTCH_PROJECT_ID or STYTCH_SECRET not configured")
        raise ValueError("Stytch credentials not configured")

    try:
        oauth_logger.debug(f"Session auth URL: {STYTCH_SESSION_AUTH_URL}")
        oauth_logger.debug("Using Basic authentication with project credentials")

        # Create Basic Auth header (project_id:secret)
        credentials = f"{STYTCH_PROJECT_ID}:{STYTCH_SECRET}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()
        auth_header = f"Basic {b64_credentials}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                STYTCH_SESSION_AUTH_URL,
                json={"session_token": session_token},
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json"
                }
            )

        oauth_logger.info(f"📡 Stytch response status: {response.status_code}")
        oauth_logger.debug(f"Stytch response headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            oauth_logger.debug(f"Full Stytch response: {json.dumps(data, indent=2)}")

            # Extract user info
            user = data.get('user', {})
            user_id = user.get('user_id', 'UNKNOWN')
            oauth_logger.info(f"✅ Session valid for user: {user_id}")

            # Extract provider values (Twitter profile)
            provider_values = user.get('provider_values', {})
            oauth_logger.debug(f"Provider values keys: {list(provider_values.keys())}")

            # Twitter data structure
            if 'twitter' in provider_values:
                twitter_profile = provider_values['twitter']
                oauth_logger.info(f"🐦 Twitter data found")
                oauth_logger.info(f"🐦 Twitter handle: @{twitter_profile.get('screen_name', 'UNKNOWN')}")
                oauth_logger.info(f"🐦 Twitter name: {twitter_profile.get('name', 'UNKNOWN')}")
                oauth_logger.info(f"🐦 Twitter ID: {twitter_profile.get('id', 'UNKNOWN')}")
                avatar_url = twitter_profile.get('profile_image_url', '')
                if avatar_url:
                    oauth_logger.info(f"🐦 Twitter avatar: {avatar_url[:60]}...")
            else:
                oauth_logger.warning(f"⚠️ No Twitter data in provider_values. Available: {list(provider_values.keys())}")

            return data

        else:
            oauth_logger.error(f"❌ Stytch session authentication failed: {response.status_code}")
            oauth_logger.error(f"Response body: {response.text}")
            error_logger.error(f"Stytch session auth failed: {response.status_code} - {response.text}")
            raise Exception(f"Stytch session authentication failed: {response.status_code}")

    except httpx.RequestError as e:
        oauth_logger.error(f"❌ Network error calling Stytch: {str(e)}")
        error_logger.exception("Stytch network error", exc_info=e)
        raise Exception(f"Network error contacting Stytch: {str(e)}")

    except Exception as e:
        oauth_logger.error(f"❌ Unexpected error in session token verification: {str(e)}")
        error_logger.exception("Session token verification error", exc_info=e)
        raise

    finally:
        oauth_logger.info("=" * 80)


def extract_twitter_profile(stytch_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Extract Twitter profile data from Stytch response.

    Handles two response formats:
    1. /v1/oauth/authenticate - has provider_values.twitter with full profile
    2. /v1/sessions/authenticate - has user.providers[] with limited profile

    Args:
        stytch_data: Response from Stytch authenticate endpoint

    Returns:
        dict: Twitter profile with keys: stytch_user_id, twitter_id, twitter_handle, display_name, avatar_url
        None: If no Twitter data found
    """
    try:
        user = stytch_data.get('user', {})
        stytch_user_id = user.get('user_id')

        # Try format 1: provider_values.twitter (from /v1/oauth/authenticate)
        provider_values = stytch_data.get('provider_values', {})
        twitter = provider_values.get('twitter', {})

        if twitter:
            oauth_logger.info("🐦 Found Twitter data in provider_values (OAuth authenticate response)")
            profile = {
                'stytch_user_id': stytch_user_id,
                'twitter_id': twitter.get('id'),
                'twitter_handle': twitter.get('screen_name'),
                'display_name': twitter.get('name'),
                'avatar_url': twitter.get('profile_image_url', '').replace('_normal', '_400x400'),  # Get higher res
            }
            oauth_logger.debug(f"Extracted Twitter profile: {profile}")
            return profile

        # Try format 2: user.providers[] (from /v1/sessions/authenticate)
        providers = user.get('providers', [])
        twitter_provider = next((p for p in providers if p.get('provider_type') == 'Twitter'), None)

        if twitter_provider:
            oauth_logger.info("🐦 Found Twitter data in user.providers (session authenticate response)")

            # Get display name from user.name
            name = user.get('name', {})
            display_name = name.get('first_name', '') or 'Unknown'

            # Extract Twitter handle from provider_subject (Twitter user ID)
            # Note: We only have the Twitter user ID, not the @handle
            # We'll use the display name as the handle for now
            twitter_id = twitter_provider.get('provider_subject')

            profile = {
                'stytch_user_id': stytch_user_id,
                'twitter_id': twitter_id,
                'twitter_handle': display_name,  # Using display name since we don't have @handle
                'display_name': display_name,
                'avatar_url': twitter_provider.get('profile_picture_url', '').replace('_normal', '_400x400'),
            }
            oauth_logger.debug(f"Extracted Twitter profile: {profile}")
            return profile

        oauth_logger.warning("No Twitter data in Stytch response (checked both formats)")
        return None

    except Exception as e:
        oauth_logger.error(f"Error extracting Twitter profile: {str(e)}")
        error_logger.exception("Twitter profile extraction error", exc_info=e)
        return None


__all__ = ['verify_stytch_token', 'verify_jwt_token', 'verify_stytch_session_token', 'extract_twitter_profile']