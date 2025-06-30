"""
Guest access service for ytFetch.
Handles guest usage tracking and limits without requiring authentication.
"""

import logging
import secrets
from typing import Dict, Any, Optional, Literal
from datetime import datetime
import hashlib

from ..core.supabase import SupabaseClient, SupabaseError
from ..core.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Guest usage types
GuestUsageType = Literal["unofficial_transcriptions", "groq_transcriptions", "bulk_videos"]

# Guest limits (matching database defaults)
GUEST_LIMITS = {
    "unofficial_transcriptions": 10,
    "groq_transcriptions": 10,
    "bulk_videos": 65,  # One-time demo - increased from 50
    "daily_requests": 100
}


class GuestService:
    """
    Service for managing guest access and usage tracking.
    
    Guests are identified by session ID stored in cookies/localStorage.
    Usage is tracked per session with limits enforced.
    """
    
    def __init__(self):
        """Initialize the guest service."""
        self.settings = get_settings()
        self._supabase = None
    
    @property
    def supabase(self):
        """Lazy load Supabase client."""
        if self._supabase is None:
            self._supabase = SupabaseClient.get_service_client()
        return self._supabase
    
    def generate_session_id(self) -> str:
        """
        Generate a secure session ID for a guest user.
        
        Returns:
            Secure random session ID
        """
        # Generate 32 bytes of random data and convert to hex
        return secrets.token_hex(32)
    
    def hash_ip_address(self, ip_address: str) -> str:
        """
        Hash IP address for privacy-preserving storage.
        
        Args:
            ip_address: Raw IP address
            
        Returns:
            Hashed IP address
        """
        # Use SHA-256 with a salt for privacy
        salt = self.settings.app_secret_key or "ytfetch-guest-salt"
        return hashlib.sha256(f"{ip_address}{salt}".encode()).hexdigest()[:16]
    
    async def check_guest_limit(
        self,
        session_id: str,
        usage_type: GuestUsageType,
        requested_count: int = 1
    ) -> Dict[str, Any]:
        """
        Check if a guest can perform an action based on usage limits.
        
        Args:
            session_id: Guest session ID
            usage_type: Type of usage to check
            requested_count: Number of items requested
            
        Returns:
            Dictionary with limit check results
        """
        try:
            # Call the database function to check limits
            response = self.supabase.rpc(
                'check_guest_usage_limit',
                {
                    'p_session_id': session_id,
                    'p_limit_type': usage_type,
                    'p_requested_count': requested_count
                }
            ).execute()
            
            if not response.data or not response.data[0]:
                # No data returned, assume not allowed
                return {
                    "allowed": False,
                    "current_usage": 0,
                    "limit": GUEST_LIMITS.get(usage_type, 0),
                    "remaining": 0,
                    "message": "Unable to check guest limits"
                }
            
            result = response.data[0]
            return {
                "allowed": result.get("allowed", False),
                "current_usage": result.get("current_usage", 0),
                "limit": result.get("limit_value", GUEST_LIMITS.get(usage_type, 0)),
                "remaining": result.get("remaining", 0),
                "message": result.get("message", ""),
                "usage_type": usage_type
            }
            
        except Exception as e:
            logger.error(f"Failed to check guest limit for session {session_id}: {e}")
            # Return conservative defaults on error
            return {
                "allowed": False,
                "current_usage": 0,
                "limit": GUEST_LIMITS.get(usage_type, 0),
                "remaining": 0,
                "message": f"Error checking limits: {str(e)}",
                "usage_type": usage_type
            }
    
    async def increment_guest_usage(
        self,
        session_id: str,
        usage_type: GuestUsageType,
        ip_address: Optional[str] = None,
        increment: int = 1
    ) -> Dict[str, Any]:
        """
        Increment guest usage counter.
        
        Args:
            session_id: Guest session ID
            usage_type: Type of usage to increment
            ip_address: Optional IP address for tracking
            increment: Amount to increment
            
        Returns:
            Dictionary with increment results
        """
        try:
            # Hash IP address if provided
            hashed_ip = None
            if ip_address:
                hashed_ip = self.hash_ip_address(ip_address)
            
            # Call the database function to increment usage
            response = self.supabase.rpc(
                'increment_guest_usage',
                {
                    'p_session_id': session_id,
                    'p_ip_address': hashed_ip,
                    'p_usage_type': usage_type,
                    'p_increment': increment
                }
            ).execute()
            
            if not response.data or not response.data[0]:
                raise SupabaseError("Failed to increment guest usage")
            
            result = response.data[0]
            logger.info(f"Incremented {usage_type} by {increment} for guest session {session_id}")
            
            return {
                "success": result.get("success", False),
                "new_usage": result.get("new_usage", 0),
                "message": result.get("message", ""),
                "usage_type": usage_type
            }
            
        except Exception as e:
            logger.error(f"Failed to increment guest usage for session {session_id}: {e}")
            return {
                "success": False,
                "new_usage": 0,
                "message": f"Error incrementing usage: {str(e)}",
                "usage_type": usage_type
            }
    
    async def get_guest_usage_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive usage summary for a guest.
        
        Args:
            session_id: Guest session ID
            
        Returns:
            Dictionary with usage summary
        """
        try:
            # Call the database function to get usage summary
            response = self.supabase.rpc(
                'get_guest_usage_summary',
                {
                    'p_session_id': session_id
                }
            ).execute()
            
            if not response.data or not response.data[0]:
                # No existing usage, return defaults
                return {
                    "session_id": session_id,
                    "is_new_guest": True,
                    "usage": {
                        "unofficial": {
                            "used": 0,
                            "limit": GUEST_LIMITS["unofficial_transcriptions"],
                            "remaining": GUEST_LIMITS["unofficial_transcriptions"]
                        },
                        "groq": {
                            "used": 0,
                            "limit": GUEST_LIMITS["groq_transcriptions"],
                            "remaining": GUEST_LIMITS["groq_transcriptions"]
                        },
                        "bulk": {
                            "used": 0,
                            "limit": GUEST_LIMITS["bulk_videos"],
                            "remaining": GUEST_LIMITS["bulk_videos"]
                        }
                    },
                    "first_use_at": None,
                    "last_use_at": None
                }
            
            result = response.data[0]
            return {
                "session_id": session_id,
                "is_new_guest": False,
                "usage": {
                    "unofficial": {
                        "used": result.get("unofficial_used", 0),
                        "limit": result.get("unofficial_limit", GUEST_LIMITS["unofficial_transcriptions"]),
                        "remaining": result.get("unofficial_remaining", 0)
                    },
                    "groq": {
                        "used": result.get("groq_used", 0),
                        "limit": result.get("groq_limit", GUEST_LIMITS["groq_transcriptions"]),
                        "remaining": result.get("groq_remaining", 0)
                    },
                    "bulk": {
                        "used": result.get("bulk_used", 0),
                        "limit": result.get("bulk_limit", GUEST_LIMITS["bulk_videos"]),
                        "remaining": result.get("bulk_remaining", 0)
                    }
                },
                "first_use_at": result.get("first_use_at"),
                "last_use_at": result.get("last_use_at")
            }
            
        except Exception as e:
            logger.error(f"Failed to get guest usage summary for session {session_id}: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
                "usage": {
                    "unofficial": {"used": 0, "limit": 0, "remaining": 0},
                    "groq": {"used": 0, "limit": 0, "remaining": 0},
                    "bulk": {"used": 0, "limit": 0, "remaining": 0}
                }
            }
    
    async def check_and_increment_if_allowed(
        self,
        session_id: str,
        usage_type: GuestUsageType,
        ip_address: Optional[str] = None,
        requested_count: int = 1
    ) -> Dict[str, Any]:
        """
        Atomically check limit and increment if allowed.
        
        This combines check and increment to avoid race conditions.
        
        Args:
            session_id: Guest session ID
            usage_type: Type of usage
            ip_address: Optional IP address
            requested_count: Number requested
            
        Returns:
            Dictionary with results including 'allowed' and 'reason'
        """
        # First check if allowed
        limit_check = await self.check_guest_limit(session_id, usage_type, requested_count)
        
        if not limit_check["allowed"]:
            return {
                "allowed": False,
                "reason": limit_check["message"],
                "usage": limit_check,
                "requires_auth": True,
                "upgrade_message": f"You've reached the guest limit of {limit_check['limit']} {usage_type.replace('_', ' ')}. Sign up for a free account to continue!"
            }
        
        # If allowed, increment the usage
        increment_result = await self.increment_guest_usage(
            session_id, 
            usage_type, 
            ip_address, 
            requested_count
        )
        
        if not increment_result["success"]:
            return {
                "allowed": False,
                "reason": increment_result["message"],
                "usage": limit_check,
                "requires_auth": False
            }
        
        return {
            "allowed": True,
            "reason": "Usage recorded successfully",
            "usage": {
                "current_usage": increment_result["new_usage"],
                "limit": limit_check["limit"],
                "remaining": limit_check["limit"] - increment_result["new_usage"]
            },
            "requires_auth": False
        }
    
    def get_usage_type_for_method(self, transcription_method: str) -> GuestUsageType:
        """
        Map transcription method to guest usage type.
        
        Args:
            transcription_method: The transcription method (e.g., "unofficial", "groq")
            
        Returns:
            Corresponding guest usage type
        """
        method_mapping = {
            "unofficial": "unofficial_transcriptions",
            "groq": "groq_transcriptions",
            "openai": "groq_transcriptions",  # Count OpenAI as Groq for guest limits
            "bulk": "bulk_videos"
        }
        
        return method_mapping.get(transcription_method.lower(), "groq_transcriptions")


# Global instance
guest_service = GuestService()