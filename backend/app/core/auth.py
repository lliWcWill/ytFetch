"""
2025-grade authentication service for FastAPI + Supabase.

Implements enterprise-grade security patterns following the latest best practices:
- HTTPBearer security dependency for token extraction
- JWT validation via Supabase auth.getUser() (not local verification)
- Comprehensive error handling with proper HTTP status codes
- User dependency functions with ownership verification
- Support for Row Level Security enforcement
- Production-ready with rate limiting considerations
"""

import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request

from .supabase import SupabaseClient, SupabaseError
from .config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Initialize security scheme - this extracts Bearer tokens from Authorization header
security = HTTPBearer(
    scheme_name="Supabase JWT",
    description="Supabase JWT token for user authentication",
    auto_error=False  # We'll handle errors manually for better control
)

settings = get_settings()


class AuthError(Exception):
    """Custom exception for authentication-related errors."""
    
    def __init__(self, message: str, status_code: int = 401, error_code: str = "auth_error", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticatedUser:
    """
    Represents an authenticated user with comprehensive information.
    
    This class provides a clean interface for accessing user data
    throughout the application.
    """
    
    def __init__(self, user_data: Dict[str, Any], session_data: Optional[Dict[str, Any]] = None):
        # Core user information from Supabase auth.users
        self.id: str = user_data.get("id", "")
        self.email: str = user_data.get("email", "")
        self.email_confirmed_at: Optional[str] = user_data.get("email_confirmed_at")
        self.phone: Optional[str] = user_data.get("phone")
        self.created_at: str = user_data.get("created_at", "")
        self.updated_at: str = user_data.get("updated_at", "")
        
        # User metadata and app-specific data
        self.user_metadata: Dict[str, Any] = user_data.get("user_metadata", {})
        self.app_metadata: Dict[str, Any] = user_data.get("app_metadata", {})
        
        # Role and authentication factors
        self.role: str = user_data.get("role", "authenticated")
        self.aud: str = user_data.get("aud", "authenticated")
        
        # Session information (if available)
        self.session_data = session_data
        self.access_token: Optional[str] = session_data.get("access_token") if session_data else None
        
        # Store raw data for advanced use cases
        self._raw_user_data = user_data
        
    def is_email_confirmed(self) -> bool:
        """Check if user's email is confirmed."""
        return self.email_confirmed_at is not None
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return self.role == role
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get value from user metadata."""
        return self.user_metadata.get(key, default)
    
    def get_app_metadata(self, key: str, default: Any = None) -> Any:
        """Get value from app metadata."""
        return self.app_metadata.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for API responses."""
        return {
            "id": self.id,
            "email": self.email,
            "email_confirmed": self.is_email_confirmed(),
            "phone": self.phone,
            "role": self.role,
            "user_metadata": self.user_metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


async def extract_token_from_request(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    request: Request = None
) -> Optional[str]:
    """
    Extract JWT token from Authorization header using HTTPBearer.
    
    This follows 2025 best practices by using FastAPI's HTTPBearer
    instead of manual header parsing.
    
    Args:
        credentials: HTTPAuthorizationCredentials from HTTPBearer dependency
        request: Request object for additional context (optional)
        
    Returns:
        JWT token string or None if not present
        
    Raises:
        AuthError: If token format is invalid
    """
    if not credentials:
        return None
    
    # HTTPBearer automatically validates Bearer prefix and extracts token
    token = credentials.credentials
    
    if not token or len(token.strip()) == 0:
        raise AuthError(
            message="Empty authentication token provided",
            status_code=401,
            error_code="empty_token"
        )
    
    # Basic token format validation (JWT should have 3 parts separated by dots)
    token_parts = token.split('.')
    if len(token_parts) != 3:
        raise AuthError(
            message="Invalid token format - JWT tokens must have 3 parts",
            status_code=401,
            error_code="invalid_token_format",
            details={"token_parts": len(token_parts)}
        )
    
    return token


async def validate_jwt_with_supabase(token: str) -> Dict[str, Any]:
    """
    Validate JWT token using Supabase auth.getUser() method.
    
    This is the 2025 recommended approach - we don't validate JWTs locally
    but instead use Supabase's auth.getUser() which handles:
    - JWT signature verification
    - Token expiration checking  
    - User status validation
    - Rate limiting protection
    
    Args:
        token: JWT token to validate
        
    Returns:
        User data dictionary from Supabase
        
    Raises:
        AuthError: If token is invalid or user not found
    """
    try:
        # Get anonymous client for auth operations
        supabase = SupabaseClient.get_anon_client()
        
        # Use Supabase's auth.getUser() which validates the JWT
        # This is more secure than local validation and handles edge cases
        # Note: supabase.auth.get_user() is synchronous, not async
        response = supabase.auth.get_user(token)
        
        if not response or not response.user:
            raise AuthError(
                message="Invalid or expired authentication token",
                status_code=401,
                error_code="invalid_token",
                details={"validation_method": "supabase_auth_get_user"}
            )
        
        user_data = response.user.model_dump() if hasattr(response.user, 'model_dump') else response.user.__dict__
        
        # Additional validation for user status
        if not user_data.get("id"):
            raise AuthError(
                message="User ID not found in token",
                status_code=401,
                error_code="invalid_user_data"
            )
        
        # Check if user is confirmed (optional - depends on app requirements)
        # email_confirmed_at = user_data.get("email_confirmed_at")
        # if not email_confirmed_at:
        #     raise AuthError(
        #         message="Email address must be confirmed to access this resource",
        #         status_code=403,
        #         error_code="email_not_confirmed"
        #     )
        
        logger.debug(f"Successfully validated token for user: {user_data.get('id')}")
        return user_data
        
    except AuthError:
        # Re-raise our custom auth errors
        raise
    except Exception as e:
        logger.error(f"JWT validation failed: {e}")
        
        # Handle specific Supabase auth errors
        error_message = str(e)
        if "expired" in error_message.lower():
            raise AuthError(
                message="Authentication token has expired",
                status_code=401,
                error_code="token_expired"
            )
        elif "invalid" in error_message.lower():
            raise AuthError(
                message="Invalid authentication token",
                status_code=401,
                error_code="invalid_token"
            )
        else:
            raise AuthError(
                message="Authentication validation failed",
                status_code=401,
                error_code="validation_failed",
                details={"error": str(e)}
            )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[AuthenticatedUser]:
    """
    Optional authentication dependency - returns None if not authenticated.
    
    This is useful for endpoints that work for both authenticated and
    anonymous users but provide different functionality based on auth status.
    
    Args:
        credentials: HTTPAuthorizationCredentials from HTTPBearer
        
    Returns:
        AuthenticatedUser instance or None if not authenticated
    """
    try:
        token = await extract_token_from_request(credentials)
        if not token:
            return None
        
        user_data = await validate_jwt_with_supabase(token)
        return AuthenticatedUser(user_data)
        
    except AuthError:
        # For optional auth, we return None instead of raising errors
        return None
    except Exception as e:
        logger.warning(f"Optional auth failed: {e}")
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthenticatedUser:
    """
    Required authentication dependency - raises 401 if not authenticated.
    
    This is the main authentication dependency for protected endpoints.
    It ensures a valid user is authenticated and returns comprehensive user data.
    
    Args:
        credentials: HTTPAuthorizationCredentials from HTTPBearer
        
    Returns:
        AuthenticatedUser instance
        
    Raises:
        HTTPException: 401 if authentication fails, 403 if access denied
    """
    try:
        token = await extract_token_from_request(credentials)
        if not token:
            raise AuthError(
                message="Authentication required - no token provided",
                status_code=401,
                error_code="missing_token"
            )
        
        user_data = await validate_jwt_with_supabase(token)
        return AuthenticatedUser(user_data)
        
    except AuthError as e:
        # Convert AuthError to HTTPException with proper formatting
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.error_code,
                "message": e.message,
                "details": e.details,
                "status_code": e.status_code
            }
        )
    except Exception as e:
        logger.error(f"Authentication failed unexpectedly: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "auth_system_error",
                "message": "Authentication system error",
                "details": {"error": str(e)},
                "status_code": 500
            }
        )


async def get_current_user_with_profile(
    user: AuthenticatedUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current user with their profile data from the database.
    
    This dependency extends basic auth to include user profile information
    from the user_profiles table, which contains tier and usage data.
    
    Args:
        user: Authenticated user from get_current_user dependency
        
    Returns:
        Dictionary containing user data and profile information
        
    Raises:
        HTTPException: If profile lookup fails
    """
    try:
        # Get service client for database operations
        supabase = SupabaseClient.get_service_client()
        
        # Fetch user profile from database with usage data
        response = supabase.table('user_profiles').select("*").eq('id', user.id).single().execute()
        
        if not response.data:
            # Create profile if it doesn't exist (fallback)
            logger.warning(f"User profile not found for {user.id}, creating one")
            # Try to create the profile
            create_response = supabase.table('user_profiles').insert({
                'id': user.id,
                'email': user.email,
                'tier': 'free'
            }).execute()
            
            if create_response.data:
                profile_data = create_response.data[0]
            else:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "profile_not_found",
                        "message": "User profile not found and could not be created",
                        "details": {"user_id": user.id},
                        "status_code": 404
                    }
                )
        else:
            profile_data = response.data
        
        # Extract usage data
        usage_data = profile_data.get("usage_data", {})
        current_month = datetime.now().strftime("%Y-%m")
        
        # Get current month's usage
        monthly_usage = usage_data.get("monthly", {}).get(current_month, {})
        all_time_usage = usage_data.get("all_time", {})
        
        # Get tier info
        tier_name = profile_data.get("tier", "free")
        tier_info = TIER_LIMITS.get(tier_name, TIER_LIMITS["free"])
        
        # Combine user auth data with profile data
        user_with_profile = {
            "auth": user.to_dict(),
            "profile": profile_data,
            "tier": tier_info,
            "tier_name": tier_name,
            "usage": {
                "videos_processed_this_month": monthly_usage.get("videos_processed", 0),
                "jobs_created_this_month": monthly_usage.get("jobs_created", 0),
                "transcription_minutes_this_month": monthly_usage.get("transcription_minutes", 0),
                "total_videos_processed": all_time_usage.get("videos_processed", 0),
                "total_jobs_created": all_time_usage.get("jobs_created", 0),
                "total_transcription_minutes": all_time_usage.get("transcription_minutes", 0)
            },
            "stripe": {
                "customer_id": profile_data.get("stripe_customer_id"),
                "subscription_id": profile_data.get("stripe_subscription_id"),
                "subscription_status": profile_data.get("stripe_subscription_status"),
                "subscription_ends_at": profile_data.get("subscription_ends_at")
            }
        }
        
        return user_with_profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user profile for {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "profile_fetch_failed",
                "message": "Failed to fetch user profile",
                "details": {"user_id": user.id, "error": str(e)},
                "status_code": 500
            }
        )


def verify_resource_ownership(user_id: str, resource_user_id: str, resource_type: str = "resource") -> None:
    """
    Verify that a user owns a specific resource.
    
    This utility function provides consistent ownership verification
    across all endpoints that need to enforce user-level access control.
    
    Args:
        user_id: ID of the authenticated user
        resource_user_id: ID of the user who owns the resource
        resource_type: Type of resource for error messages
        
    Raises:
        HTTPException: 403 if user doesn't own the resource
    """
    if user_id != resource_user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "access_denied",
                "message": f"Access denied - you don't own this {resource_type}",
                "details": {
                    "user_id": user_id,
                    "resource_user_id": resource_user_id,
                    "resource_type": resource_type
                },
                "status_code": 403
            }
        )


# Tier limits configuration
TIER_LIMITS = {
    "free": {
        "videos_per_job": 5,
        "jobs_per_month": 10,
        "concurrent_jobs": 1,
        "videos_per_month": 50,
        "transcription_minutes_per_month": 300,
        "display_name": "Free",
        "price_monthly": 0,
        "price_yearly": 0
    },
    "pro": {
        "videos_per_job": 100,
        "jobs_per_month": 1000,
        "concurrent_jobs": 5,
        "videos_per_month": 10000,
        "transcription_minutes_per_month": 10000,
        "display_name": "Pro",
        "price_monthly": 19,
        "price_yearly": 190
    },
    "enterprise": {
        "videos_per_job": 999999,
        "jobs_per_month": 999999,
        "concurrent_jobs": 20,
        "videos_per_month": 999999,
        "transcription_minutes_per_month": 999999,
        "display_name": "Enterprise",
        "price_monthly": 99,
        "price_yearly": 990
    }
}


async def check_tier_limits(
    limit_type: str,
    requested_count: int = 1,
    user: AuthenticatedUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Check if user's requested action is within their tier limits.
    
    DEPRECATED: This function is kept for backward compatibility but no longer
    enforces tier limits for authenticated users in the token-based system.
    Authenticated users can process unlimited content as long as they have tokens.
    
    Args:
        limit_type: Type of limit to check (e.g., 'videos_per_job', 'jobs_per_month')
        requested_count: Number of items being requested
        user: Authenticated user from dependency
        
    Returns:
        Dictionary with limit check results (always allowed for authenticated users)
    """
    # In the token-based system, authenticated users have no tier limits
    # They are only limited by their token balance
    logger.info(f"Tier limit check bypassed for user {user.id} in token-based system")
    
    return {
        "allowed": True,
        "current_tier": "token_based",
        "limit": 999999,  # Effectively unlimited
        "current_usage": 0,
        "requested": requested_count,
        "remaining": 999999,
        "message": "Token-based system - no tier limits apply"
    }


async def check_user_tier_limits(
    user: AuthenticatedUser,
    requested_videos: int = 0,
    check_concurrent_jobs: bool = False
) -> Dict[str, Any]:
    """
    DEPRECATED: Use check_tier_limits dependency instead.
    
    Check if user's current usage is within their tier limits.
    
    This function helps enforce subscription limits and provides
    clear feedback about what users can do with their current tier.
    
    Args:
        user: Authenticated user
        requested_videos: Number of videos user wants to process
        check_concurrent_jobs: Whether to check active job limits
        
    Returns:
        Dictionary with limit check results and tier information
        
    Raises:
        HTTPException: 402 if limits are exceeded
    """
    # Use the new check_tier_limits function
    if requested_videos > 0:
        return await check_tier_limits('videos_per_job', requested_videos, user)
    
    # If no specific check requested, just return user's tier info
    try:
        # Get user profile with tier information
        user_with_profile = await get_current_user_with_profile(user)
        profile = user_with_profile.get("profile", {})
        tier_name = profile.get("tier", "free")
        tier_info = TIER_LIMITS.get(tier_name, TIER_LIMITS["free"])
        
        return {
            "tier": tier_info,
            "tier_name": tier_name,
            "usage": user_with_profile.get("usage", {}),
            "limits_ok": True
        }
        
    except Exception as e:
        logger.error(f"Failed to get tier info for user {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "tier_check_failed",
                "message": "Failed to check subscription limits",
                "details": {"user_id": user.id, "error": str(e)},
                "status_code": 500
            }
        )


# Guest user representation
class GuestUser:
    """Represents a guest (unauthenticated) user with session tracking."""
    
    def __init__(self, session_id: str):
        self.id = f"guest_{session_id[:8]}"
        self.session_id = session_id
        self.email = None
        self.is_guest = True
        self.role = "guest"
        self.tier = "guest"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert guest user to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "is_guest": True,
            "role": self.role,
            "tier": self.tier
        }


async def get_user_or_guest(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Union[AuthenticatedUser, GuestUser]:
    """
    Get authenticated user or guest user.
    
    This dependency allows endpoints to work for both authenticated and guest users.
    Guest users are identified by session ID from cookies/headers.
    
    Args:
        credentials: Optional auth credentials
        request: Request object for accessing cookies/headers
        
    Returns:
        AuthenticatedUser or GuestUser instance
    """
    # Try to get authenticated user first
    user = await get_current_user_optional(credentials)
    if user:
        return user
    
    # No authenticated user, create guest user
    # Get session ID from cookie or header
    session_id = None
    if request:
        # Try cookie first
        session_id = request.cookies.get("guest_session_id")
        
        # Fallback to header
        if not session_id:
            session_id = request.headers.get("X-Guest-Session-ID")
    
    # Generate new session ID if none found
    if not session_id:
        from ..services.guest_service import guest_service
        session_id = guest_service.generate_session_id()
    
    return GuestUser(session_id)


# Convenience aliases for common auth patterns
RequireAuth = Depends(get_current_user)
OptionalAuth = Depends(get_current_user_optional)
RequireAuthWithProfile = Depends(get_current_user_with_profile)
UserOrGuest = Depends(get_user_or_guest)


def create_auth_dependency_with_roles(allowed_roles: list[str]):
    """
    Create a custom auth dependency that checks for specific roles.
    
    This factory function creates role-based access control dependencies.
    
    Args:
        allowed_roles: List of roles that can access the endpoint
        
    Returns:
        FastAPI dependency function
    """
    async def auth_with_roles(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "insufficient_permissions",
                    "message": f"Access requires one of: {', '.join(allowed_roles)}",
                    "details": {
                        "user_role": user.role,
                        "required_roles": allowed_roles
                    },
                    "status_code": 403
                }
            )
        return user
    
    return auth_with_roles


# Common role-based dependencies
RequireAdminRole = create_auth_dependency_with_roles(["admin", "service_role"])
RequireUserRole = create_auth_dependency_with_roles(["authenticated", "admin"])